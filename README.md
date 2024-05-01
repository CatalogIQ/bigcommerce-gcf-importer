# Google Cloud Function for Product Synchronization

This repository contains a Google Cloud Function written in Python for synchronizing product data from CatalogIQ to BigCommerce.

## Functionality

The function fetches product data from the CatalogIQ API and maps it to the format required by the BigCommerce API. It then posts the mapped product data to BigCommerce. The function runs in a loop, fetching and posting products one by one, until all products have been processed.

The function also cleans and converts certain attribute values to floats, and sends an email notification upon completion of the synchronization process.

## Setup

1. Clone this repository to your local machine.
2. Install the required Python packages by running `pip install -r requirements.txt`.
3. Set the following environment variables:
    - `CATALOGIQ_API_KEY`: Your CatalogIQ API key.
    - `BIGCOMMERCE_API_KEY`: Your BigCommerce API key.
    - `BIGCOMMERCE_STORE_HASH`: Your BigCommerce store hash.
    - `SENDGRID_API_KEY`: Your SendGrid API key for sending email notifications.

## Deployment

To deploy this function to Google Cloud Functions, you can use the `gcloud` command-line tool:

```bash
gcloud functions deploy sync_products --runtime python312 --trigger-http --allow-unauthenticated
