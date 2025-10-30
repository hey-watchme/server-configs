import json
import boto3
import os
from urllib.parse import unquote_plus

# 環境変数
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')

def lambda_handler(event, context):
    """
    S3イベントを受信してSQSキューに送信する軽量Lambda
    処理時間: 1-2秒
    """
    
    print(f"Received S3 event: {json.dumps(event)}")
    
    # SQSクライアント
    sqs = boto3.client('sqs')
    
    try:
        # S3イベントから情報を抽出
        s3_record = event['Records'][0]['s3']
        bucket_name = s3_record['bucket']['name']
        object_key = unquote_plus(s3_record['object']['key'])
        
        print(f"Processing S3 object: {bucket_name}/{object_key}")
        
        # パスから情報を抽出
        # 形式: files/{device_id}/{date}/{time_slot}/audio.wav
        parts = object_key.split('/')
        if len(parts) < 4:
            print(f"Invalid path format: {object_key}")
            return {'statusCode': 400, 'body': 'Invalid path format'}
        
        device_id = parts[1]
        date = parts[2]
        time_slot = parts[3]
        
        # SQSメッセージを準備
        message = {
            'file_path': object_key,
            'device_id': device_id,
            'date': date,
            'time_slot': time_slot,
            'bucket_name': bucket_name,
            'timestamp': context.aws_request_id
        }
        
        # SQSに送信
        response = sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(message),
            MessageAttributes={
                'device_id': {
                    'StringValue': device_id,
                    'DataType': 'String'
                },
                'date': {
                    'StringValue': date,
                    'DataType': 'String'
                },
                'time_slot': {
                    'StringValue': time_slot,
                    'DataType': 'String'
                }
            }
        )
        
        print(f"Message sent to SQS: {response['MessageId']}")
        print(f"Device: {device_id}, Date: {date}, TimeSlot: {time_slot}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully queued for processing',
                'messageId': response['MessageId'],
                'device_id': device_id,
                'date': date,
                'time_slot': time_slot
            })
        }
        
    except Exception as e:
        print(f"Error processing S3 event: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }