# Serverless Sync Connector to BigCommerce using Google Cloud

This tutorial outlines the process of syncing products from a third-party API to a BigCommerce store using Google Cloud Functions and the Pub/Sub messaging system. Our approach leverages Pub/Sub to efficiently handle large volumes of product data by queuing and processing one record at a time, thus preventing function timeouts.

For more information and the source code, visit our repository: [bigcommerce-gcf-importer](https://github.com/CatalogIQ/bigcommerce-gcf-importer).

## Requirements

- Google Cloud Console Developer Account with Billing Enabled
- Enabled Google Cloud services: Cloud Functions, Pub/Sub, and Cloud Run
- Basic knowledge of Python
- BigCommerce Store Account with API Key access

## Architecture Overview

The process is triggered by a Pub/Sub message containing an "offset" value, which then invokes the Cloud Function to sync a single product template at a time to BigCommerce. Upon completion, the function publishes a new message with an incremented offset to continue the process. If a duplicate product template is detected, it will be skipped.

This setup is flexible and can be adapted to connect with other APIs like Shopify, Salesforce, Odoo, or Microsoft Dynamics.

### Alternative Usage

You can modify this function to process specific records by `template_id`, making it possible to trigger imports directly from a Google Sheet containing product IDs and details via an HTTP function.

## Getting Started

### Setting up Pub/Sub

1. Navigate to Pub/Sub in the Google Cloud Console.
2. Create a new topic.
3. Enter the desired topic name.
4. Add a schema with the property `offset` as a String.
5. Save your topic configuration.
6. Click "+Trigger Cloud Function" to connect your function.

### Configuring Cloud Function

1. Set the function name and runtime to Python 3.12.
2. Configure the number of messages to process at a time to `1`.
3. Visit the [project repository](https://github.com/CatalogIQ/bigcommerce-gcf-importer).
4. In the Cloud Function Inline Editor, copy the contents of `Requirements.txt` and `Main.py` from the repository.5. 
6. Set the `entry_point` to `process_product`.
7. Set the following environment variables:
    - `CATALOGIQ_API_KEY`: Your CatalogIQ API key.
    - `BIGCOMMERCE_API_KEY`: Your BigCommerce API key.
    - `BIGCOMMERCE_STORE_HASH`: Your BigCommerce store hash.
    - `SENDGRID_API_KEY`: Your SendGrid API key for sending email notifications.
8. Deploy the function.

### Testing

1. Navigate to Pub/Sub -> Topics -> Messages.
2. Publish a message with the message body `{ "offset": "0" }` to initiate syncing from the beginning of the list.
3. Go to Cloud Function, select your function, and check the Logs for debugging information.
4. Verify the addition of new products in your BigCommerce store.

## Support and Contributions

Contributions to this project are welcome! Feel free to fork the repository, make improvements, and submit pull requests.

## TODO
1. Verify message are not received more than once and make sure duplicates are not processed.


