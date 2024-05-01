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
topic_path = publisher.topic_path('bitnami-ttqjdimqca', 'demo-bigcommerce-function')

def publish_offset(offset):
    """Publish the updated offset to the Pub/Sub topic."""
    message_json = json.dumps({'offset': str(offset)})  # Ensure offset is a string if your schema requires it
    message_bytes = message_json.encode('utf-8')
    publisher.publish(topic_path, message_bytes)

@functions_framework.cloud_event
def process_product(cloud_event):
    """Function to be triggered by Pub/Sub to process product synchronization."""
    data = base64.b64decode(cloud_event.data['message']['data']).decode('utf-8')
    data = json.loads(data)
    offset = int(data['offset'])
    sync_products(offset)

def sync_products(offset):
    limit = 1

    # Retrieve API keys and endpoints
    catalogiq_api_key = os.getenv('CATALOGIQ_API_KEY', 'default_catalogiq_key')
    bigcommerce_api_key = os.getenv('BIGCOMMERCE_API_KEY', 'default_bigcommerce_key')
    bigcommerce_store_hash = os.getenv('BIGCOMMERCE_STORE_HASH', 'default_store_hash')
    catalogiq_endpoint = "https://catalogiq.app/api/v1/products"
    bigcommerce_endpoint = f"https://api.bigcommerce.com/stores/{bigcommerce_store_hash}/v3/catalog/products"

    headers_catalogiq = {'Catalogiq-Api-Key': catalogiq_api_key}
    headers_bigcommerce = {'X-Auth-Token': bigcommerce_api_key, 'Content-Type': 'application/json'}

    response_catalogiq = requests.get(f"{catalogiq_endpoint}?limit={limit}&offset={offset}", headers=headers_catalogiq)
    if response_catalogiq.status_code != 200:
        print(f"Error fetching product from CatalogIQ: {response_catalogiq.status_code} - {response_catalogiq.text}")
        return  # Consider adding error handling here

    product_data = response_catalogiq.json()
    products = product_data['results']

    if not products:
        send_completion_email()
        return "Sync Complete!"

    for product in products:
        bc_product = map_catalogiq_to_bigcommerce(product)
        response_bigcommerce = requests.post(bigcommerce_endpoint, json=bc_product, headers=headers_bigcommerce)
        if response_bigcommerce.status_code not in [200, 201]:
            print(f"Error posting product to BigCommerce: {response_bigcommerce.status_code} - {response_bigcommerce.text}")            

    publish_offset(offset + 1)  # Update the offset for the next invocation
    return


def map_catalogiq_to_bigcommerce(product):
    attributes = {attr['name']: attr['value'] for attr in product['attributes']}
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

    images = [{
        "image_url": image['url'],
        "is_thumbnail": False  # Set the first image as the thumbnail
    } for idx, image in enumerate(product['images'])]

    #Add the main_image as the first image
    if product.get('main_image'):
        images.insert(0, {
            "image_url": product['main_image'] + '/1000x1000',
            "is_thumbnail": True
        })
    
    custom_fields = [{"name": k, "value": v} for k, v in attributes.items() if v and len(v) < 255]

    return {
        "name": product['name'] + ' by ' + attributes.get('Vendor Name', ''),
        "type": "physical",
        "sku": product['model'] + '-' + product['vendor_id'],
        "description": "<p>{}</p>".format(product.get('description_sale', 'No description available.')),
        "weight": clean_and_convert_to_float(attributes.get('Weight', 0)),
        "width": clean_and_convert_to_float(attributes.get('Width', 0)),
        "depth": clean_and_convert_to_float(attributes.get('Length', 0)),
        "height": clean_and_convert_to_float(attributes.get('Height', 0)),
        "price": 0,
        "variants": variants,
        "images": images,
        "custom_fields": custom_fields
    }



def clean_and_convert_to_float(input_value):
    if isinstance(input_value, int):
        return float(input_value)
    elif isinstance(input_value, str):
        cleaned_string = re.sub(r'[^0-9.]', '', input_value)
        return float(cleaned_string) if cleaned_string else 0.0
    else:
        return 0.00

def send_completion_email():
    sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
    message = Mail(
        from_email='your-email@example.com',
        to_emails='notify@catalogiq.app',
        subject='Brand Completed',
        html_content='The synchronization process for your products has been completed successfully.'
    )
    try:
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)
        print(f"Email sent! Status code: {response.status_code}")
    except Exception as e:
        print(f"An error occurred: {e}")
