import json
import requests
import os

DEFAULT_API_BASE_URL = "https://api.hey-watch.me"
API_ENDPOINT_URL = os.environ.get(
    "API_ENDPOINT_URL",
    f"{os.environ.get('API_BASE_URL', DEFAULT_API_BASE_URL).rstrip('/')}/emotion-analysis/feature-extractor/async-process",
)
API_HOST_HEADER = os.environ.get("API_HOST_HEADER", "")
VERIFY_TLS = os.environ.get("VERIFY_TLS", "true").lower() not in {"0", "false", "no"}
REQUEST_CONNECT_TIMEOUT = float(os.environ.get("REQUEST_CONNECT_TIMEOUT", "3"))
REQUEST_READ_TIMEOUT = float(os.environ.get("REQUEST_READ_TIMEOUT", "10"))

def lambda_handler(event, context):
    """
    Process SQS messages and trigger SER API async processing
    """
    print(f"Processing {len(event['Records'])} messages from SER queue")

    for record in event['Records']:
        try:
            # Parse SQS message
            message = json.loads(record['body'])

            file_path = message['file_path']
            device_id = message['device_id']
            recorded_at = message['recorded_at']

            print(f"Processing SER for device {device_id} at {recorded_at}")
            print(f"File path: {file_path}")
            print(f"Endpoint URL: {API_ENDPOINT_URL}")
            if API_HOST_HEADER:
                print(f"Host header: {API_HOST_HEADER}")

            # Call SER API async endpoint (returns 202 immediately)
            response = requests.post(
                API_ENDPOINT_URL,
                json={
                    "file_path": file_path,
                    "device_id": device_id,
                    "recorded_at": recorded_at
                },
                headers={"Host": API_HOST_HEADER} if API_HOST_HEADER else None,
                verify=VERIFY_TLS,
                timeout=(REQUEST_CONNECT_TIMEOUT, REQUEST_READ_TIMEOUT),
            )

            if response.status_code == 202:
                print(f"SER processing started successfully for {device_id}")
            else:
                error_msg = f"Failed to start SER processing: {response.status_code}"
                print(f"Error: {error_msg}")
                print(f"Response: {response.text}")
                raise Exception(error_msg)

        except Exception as e:
            print(f"Error processing message: {str(e)}")
            # Re-raise to trigger SQS retry
            raise

    return {
        'statusCode': 200,
        'body': json.dumps('SER processing initiated')
    }
