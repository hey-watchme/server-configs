import json
import boto3
import os
import requests
from urllib.parse import unquote_plus

# Environment variables
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

def get_recorded_at_from_audio_files(file_path):
    """
    Get recorded_at from audio_files table using file_path

    Args:
        file_path: S3 file path (e.g., files/{device_id}/{date}/{time_slot}/audio.wav)

    Returns:
        recorded_at: UTC timestamp string or None if not found
    """
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/audio_files",
            params={
                "file_path": f"eq.{file_path}",
                "select": "recorded_at,device_id"
            },
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            },
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                recorded_at = data[0].get('recorded_at')
                device_id = data[0].get('device_id')
                print(f"Found recorded_at: {recorded_at} for device: {device_id}")
                return recorded_at, device_id

        print(f"Warning: Could not find recorded_at for file_path: {file_path}")
        return None, None

    except Exception as e:
        print(f"Error getting recorded_at: {e}")
        return None, None


def lambda_handler(event, context):
    """
    Receive S3 event and send to SQS queue with recorded_at
    Processing time: 1-2 seconds

    Flow:
    1. S3 event triggers this Lambda
    2. Query audio_files table to get recorded_at
    3. Send message to SQS with device_id and recorded_at
    """

    print(f"Received S3 event: {json.dumps(event)}")

    # SQS client
    sqs = boto3.client('sqs')

    try:
        # Extract information from S3 event
        s3_record = event['Records'][0]['s3']
        bucket_name = s3_record['bucket']['name']
        object_key = unquote_plus(s3_record['object']['key'])

        print(f"Processing S3 object: {bucket_name}/{object_key}")

        # Get recorded_at from audio_files table
        recorded_at, device_id = get_recorded_at_from_audio_files(object_key)

        if not recorded_at or not device_id:
            # Fallback: extract device_id from path if not found in DB
            # Format: files/{device_id}/{date}/{time_slot}/audio.wav
            parts = object_key.split('/')
            if len(parts) >= 4:
                device_id = parts[1]
                print(f"Using device_id from path: {device_id}")
            else:
                print(f"Error: Cannot determine device_id and recorded_at for {object_key}")
                return {'statusCode': 400, 'body': 'Cannot determine device_id and recorded_at'}

        # Prepare SQS message with recorded_at
        message = {
            'file_path': object_key,
            'device_id': device_id,
            'recorded_at': recorded_at,  # This is the key field for new pipeline
            'bucket_name': bucket_name,
            'timestamp': context.aws_request_id
        }

        # Send to SQS
        response = sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message),
            MessageAttributes={
                'device_id': {
                    'StringValue': device_id,
                    'DataType': 'String'
                }
            }
        )

        print(f"Message sent to SQS: {response['MessageId']}")
        print(f"Device: {device_id}, Recorded at: {recorded_at}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully queued for processing',
                'messageId': response['MessageId'],
                'device_id': device_id,
                'recorded_at': recorded_at
            })
        }

    except Exception as e:
        print(f"Error processing S3 event: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }