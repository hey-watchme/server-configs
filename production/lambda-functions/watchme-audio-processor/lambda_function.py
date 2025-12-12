import json
import boto3
import os
import requests
import hashlib
from urllib.parse import unquote_plus

# Environment variables - FIFO Queue URLs
ASR_QUEUE_URL = os.environ.get('ASR_QUEUE_URL', 'https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-asr-queue-v2.fifo')
SED_QUEUE_URL = os.environ.get('SED_QUEUE_URL', 'https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-sed-queue-v2.fifo')
SER_QUEUE_URL = os.environ.get('SER_QUEUE_URL', 'https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-ser-queue-v2.fifo')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

def get_deduplication_id(device_id, recorded_at, api_type):
    """
    Generate FIFO Queue Deduplication ID
    Same combination of device_id + recorded_at + api_type always produces the same ID

    Args:
        device_id: Device ID
        recorded_at: Recording timestamp (ISO8601)
        api_type: API type (asr/sed/ser)

    Returns:
        Deduplication ID (max 80 chars)
    """
    unique_string = f"{device_id}-{recorded_at}-{api_type}"
    return hashlib.sha256(unique_string.encode()).hexdigest()[:80]


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
    Receive S3 event and send to 3 SQS queues for parallel processing
    Processing time: 1-2 seconds

    Flow:
    1. S3 event triggers this Lambda
    2. Query audio_files table to get recorded_at
    3. Send message to 3 SQS queues (ASR, SED, SER) in parallel
    """

    print(f"Received S3 event: {json.dumps(event)}")

    # SQS client
    sqs = boto3.client('sqs', region_name='ap-southeast-2')

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

        message_body = json.dumps(message)

        # Send to all 3 FIFO SQS queues in parallel
        message_ids = []

        # Send to ASR FIFO queue
        message_group_id_asr = f"{device_id}-asr"
        deduplication_id_asr = get_deduplication_id(device_id, recorded_at, "asr")
        response_asr = sqs.send_message(
            QueueUrl=ASR_QUEUE_URL,
            MessageBody=message_body,
            MessageGroupId=message_group_id_asr,
            MessageDeduplicationId=deduplication_id_asr
        )
        message_ids.append(('ASR', response_asr['MessageId']))
        print(f"Message sent to ASR FIFO queue: {response_asr['MessageId']}, GroupId={message_group_id_asr}")

        # Send to SED FIFO queue
        message_group_id_sed = f"{device_id}-sed"
        deduplication_id_sed = get_deduplication_id(device_id, recorded_at, "sed")
        response_sed = sqs.send_message(
            QueueUrl=SED_QUEUE_URL,
            MessageBody=message_body,
            MessageGroupId=message_group_id_sed,
            MessageDeduplicationId=deduplication_id_sed
        )
        message_ids.append(('SED', response_sed['MessageId']))
        print(f"Message sent to SED FIFO queue: {response_sed['MessageId']}, GroupId={message_group_id_sed}")

        # Send to SER FIFO queue
        message_group_id_ser = f"{device_id}-ser"
        deduplication_id_ser = get_deduplication_id(device_id, recorded_at, "ser")
        response_ser = sqs.send_message(
            QueueUrl=SER_QUEUE_URL,
            MessageBody=message_body,
            MessageGroupId=message_group_id_ser,
            MessageDeduplicationId=deduplication_id_ser
        )
        message_ids.append(('SER', response_ser['MessageId']))
        print(f"Message sent to SER FIFO queue: {response_ser['MessageId']}, GroupId={message_group_id_ser}")

        print(f"Successfully sent to all 3 queues for Device: {device_id}, Recorded at: {recorded_at}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully queued for parallel processing',
                'messageIds': dict(message_ids),
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