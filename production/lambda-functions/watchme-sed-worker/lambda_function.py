import json
import boto3
import requests
import os

# Environment variables
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.hey-watch.me')

def lambda_handler(event, context):
    """
    Process SQS messages and trigger SED API async processing
    """
    print(f"Processing {len(event['Records'])} messages from SED queue")

    for record in event['Records']:
        try:
            # Parse SQS message
            message = json.loads(record['body'])

            file_path = message['file_path']
            device_id = message['device_id']
            recorded_at = message['recorded_at']

            print(f"Processing SED for device {device_id} at {recorded_at}")
            print(f"File path: {file_path}")

            # Call SED API async endpoint (returns 202 immediately)
            response = requests.post(
                f"{API_BASE_URL}/behavior-analysis/features/async-process",
                json={
                    "file_path": file_path,
                    "device_id": device_id,
                    "recorded_at": recorded_at
                },
                timeout=30  # 30 seconds is enough for 202 response
            )

            if response.status_code == 202:
                print(f"SED processing started successfully for {device_id}")
            else:
                error_msg = f"Failed to start SED processing: {response.status_code}"
                print(f"Error: {error_msg}")
                print(f"Response: {response.text}")
                raise Exception(error_msg)

        except Exception as e:
            print(f"Error processing message: {str(e)}")
            # Re-raise to trigger SQS retry
            raise

    return {
        'statusCode': 200,
        'body': json.dumps('SED processing initiated')
    }