import functions_framework
import requests
import os
import re
import json
import base64
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from google.cloud import pubsub_v1

publisher = pubsub_v1.PublisherClient()
# Add your project name and topic ID to the topic_path variable.
topic_path = publisher.topic_path('project-name', 'topic-id')

def publish_offset(offset):
    # Publish the updated offset to the Pub/Sub topic.
    message_json = json.dumps({'offset': str(offset)})  # Ensure offset is a string if your schema requires it
    message_bytes = message_json.encode('utf-8')
    publisher.publish(topic_path, message_bytes)

# Our trigger function that will be called by Pub/Sub, we need to set that up in the GCP console when creating the function.
@functions_framework.cloud_event
def process_product(cloud_event):
    """Function to be triggered by Pub/Sub to process product synchronization."""
    data = base64.b64decode(cloud_event.data['message']['data']).decode('utf-8')
    data = json.loads(data)
    offset = int(data['offset'])
    sync_products(offset)

def sync_products(offset):
    limit = 1

    # Retrieve API keys and endpoints from environment variables
    catalogiq_api_key = os.getenv('CATALOGIQ_API_KEY', 'default_catalogiq_key')
    bigcommerce_api_key = os.getenv('BIGCOMMERCE_API_KEY', 'default_bigcommerce_key')
    bigcommerce_store_hash = os.getenv('BIGCOMMERCE_STORE_HASH', 'default_store_hash')
    sendgrid_api_key = os.getenv('SENDGRID_API_KEY')

    catalogiq_endpoint = "https://catalogiq.app/api/v1/products"
    bigcommerce_endpoint = f"https://api.bigcommerce.com/stores/{bigcommerce_store_hash}/v3/catalog/products"

    # Set your authorization headers
    headers_catalogiq = {'Catalogiq-Api-Key': catalogiq_api_key}
    headers_bigcommerce = {'X-Auth-Token': bigcommerce_api_key, 'Content-Type': 'application/json'}

    # Fetch products from CatalogIQ with the offset from Pub/Sub
    response_catalogiq = requests.get(f"{catalogiq_endpoint}?limit={limit}&offset={offset}", headers=headers_catalogiq)
    if response_catalogiq.status_code != 200:
        print(f"Error fetching product from CatalogIQ: {response_catalogiq.status_code} - {response_catalogiq.text}")
        return  # Consider adding error handling here, this will stop the function and not call the next record if there is an error. Monitor the logs for errors.

    product_data = response_catalogiq.json()
    products = product_data['results']

    # If there are no results from the API, we have reached the end of the catalog
    if not products:
        # Placeholder for any callback that you want to handle when the sync is complete
        send_completion_email(sendgrid_api_key)
        return "Sync Complete!"

    # Map the API properties and Post products to BigCommerce
    for product in products:
        bc_product = map_catalogiq_to_bigcommerce(product)
        response_bigcommerce = requests.post(bigcommerce_endpoint, json=bc_product, headers=headers_bigcommerce)
        if response_bigcommerce.status_code not in [200, 201]:
            print(f"Error posting product to BigCommerce: {response_bigcommerce.status_code} - {response_bigcommerce.text}")            

    # Update the offset in Pub/Sub to trigger the next invocation
    publish_offset(offset + 1)  # Update the offset for the next invocation
    return

# Function to map CatalogIQ product to BigCommerce product properties
def map_catalogiq_to_bigcommerce(product):

    # Attributes are added as custom fields and can be used for category filters in BigCommerce
    attributes = {attr['name']: attr['value'] for attr in product['attributes']}

    # Custom fields are limited to 255 characters and require a value to be set 
    # You can add additional attributes to the custom_fields list
    custom_fields = [{"name": k, "value": v} for k, v in attributes.items() if v and len(v) < 255]

    # Variants are the product options in BigCommerce
    # The default_code is the SKU for the variant from the manufacturer    
    # We check that the variant has a SKU before adding it to the product, some pending items and some custom products may not have a SKU
    # If we wanted to filter out variants that contain a custom option we can filter by the is_custom property
    variants = [{
        "sku": variant['default_code'],
        "cost_price": 0,
        "price": 0,
        "sale_price": 0,
        "retail_price": 0,
        "option_values": [
            {
                "option_display_name": attr['name'],
                "label": attr['value']
            } for attr in variant['attributes']
        ]
    } for variant in product['variants'] if variant['default_code']]

    # The images array contains the alternative and lifestyle photos to add as additional images.
    images = [{
        "image_url": image['url'],
        "is_thumbnail": False  # Set the first image as the thumbnail
    } for idx, image in enumerate(product['images'])]

    # Add the main_image as the first image
    if product.get('main_image'):
        images.insert(0, {
            "image_url": product['main_image'] + '/1000x1000',
            "is_thumbnail": True
        })    

    return {
        # Names are unique in BigCommerce so we can append the model, vendor id or other string such as the Vendor Name to make sure the name is unique in the catalog.
        "name": product['name'] + ' by ' + attributes.get('Vendor Name', ''),
        "type": "physical",
        #The SKU number for the product, this should be unique for each product in the catalog. We are using the model and vendor id to create a unique SKU for the parent item. You can modify this to fit your needs.
        "sku": product['model'] + '-' + product['vendor_id'],
        "description": "<p>{}</p>".format(product.get('description_sale', 'No description available.')),
        # Add the brand ID from BigCommerce if you have a brand mapping
        "brand_id": 0,  
        # Check the field types and developer note in the product_attributes endpoint to determine what filtering needs to be done on your properties.abs
        # We are using the clean_and_convert_to_float function to ensure that the values are converted to floats and remove and units. In product we would want to check the units are what we are expecting for BigCommerce.
        "weight": clean_and_convert_to_float(attributes.get('Weight', 0)),
        "width": clean_and_convert_to_float(attributes.get('Width', 0)),
        "depth": clean_and_convert_to_float(attributes.get('Length', 0)),
        "height": clean_and_convert_to_float(attributes.get('Height', 0)),
        "price": 0,
        "variants": variants,
        "images": images,
        "custom_fields": custom_fields
    }


# Add or update the sanitation of the input values from the dimensions above.
def clean_and_convert_to_float(input_value):
    if isinstance(input_value, int):
        return float(input_value)
    elif isinstance(input_value, str):
        cleaned_string = re.sub(r'[^0-9.]', '', input_value)
        return float(cleaned_string) if cleaned_string else 0.0
    else:
        return 0.00


# Callback at the end of the synchronization process to send an email notification
# You can change this to handle whatever you would like to do upon completion.
def send_completion_email(sendgrid_api_key):
    
    message = Mail(
        from_email='info@catalogiq.app',
        to_emails='notify@catalogiq.app',
        subject='Brand Completed',
        html_content='The synchronization process for your products has been completed successfully.'
    )
    try:
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)
        print(f"Email sent! Status code: {response.status_code}")
    except Exception as e:
        print(f"An error sending mail occurred: {e}")
