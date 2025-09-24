import json
import boto3
import requests
import os
from datetime import datetime

# 環境変数
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.hey-watch.me')
ANALYSIS_QUEUE_URL = os.environ.get('ANALYSIS_QUEUE_URL', 'https://sqs.ap-southeast-2.amazonaws.com/975050024946/watchme-dashboard-analysis-queue')

# SQSクライアント
sqs = boto3.client('sqs', region_name='ap-southeast-2')

def lambda_handler(event, context):
    """
    Dashboard Summary Worker Lambda
    SQSメッセージを処理してプロンプト生成APIを呼び出し、
    結果を次のキューに送信
    """
    
    print(f"Processing Dashboard Summary: {len(event['Records'])} messages")
    
    for record in event['Records']:
        try:
            # メッセージ本文を解析
            message = json.loads(record['body'])
            
            device_id = message['device_id']
            date = message['date']
            time_slot = message.get('time_slot', '')  # タイムブロック処理完了時のタイムスロット
            
            print(f"Processing dashboard summary for: {device_id}/{date}")
            print(f"Triggered by timeblock: {time_slot}")
            
            # 1. Dashboard Summary APIを呼び出し（プロンプト生成）
            summary_result = call_dashboard_summary_api(device_id, date)
            
            if summary_result['success']:
                # 2. 成功したら次のキュー（Analysis Queue）にメッセージを送信
                analysis_message = {
                    'device_id': device_id,
                    'date': date,
                    'time_slot': time_slot,
                    'prompt': summary_result['prompt'],
                    'timestamp': datetime.utcnow().isoformat(),
                    'source': 'dashboard-summary-worker'
                }
                
                # SQSに送信
                sqs_response = sqs.send_message(
                    QueueUrl=ANALYSIS_QUEUE_URL,
                    MessageBody=json.dumps(analysis_message)
                )
                
                print(f"Sent to analysis queue: MessageId={sqs_response['MessageId']}")
                print(f"Prompt length: {len(summary_result['prompt'])} characters")
                
            else:
                print(f"Dashboard summary API failed: {summary_result.get('error', 'Unknown error')}")
                # エラーの場合、SQSのリトライ機能により自動的に再試行される
                raise Exception(f"Dashboard summary failed: {summary_result.get('error')}")
            
        except Exception as e:
            print(f"Error processing message: {str(e)}")
            # 例外を再発生させてSQSのリトライを有効にする
            raise
    
    return {
        'statusCode': 200,
        'body': json.dumps('Dashboard summary processing completed')
    }


def call_dashboard_summary_api(device_id, date):
    """
    Dashboard Summary API（プロンプト生成）を呼び出し
    """
    try:
        print(f"Calling Dashboard Summary API...")
        print(f"URL: {API_BASE_URL}/vibe-aggregator/generate-dashboard-summary")
        print(f"Parameters: device_id={device_id}, date={date}")
        
        # APIを呼び出し（GET with params)
        response = requests.get(
            f"{API_BASE_URL}/vibe-aggregator/generate-dashboard-summary",
            params={
                "device_id": device_id,
                "date": date
            },
            timeout=180
        )
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                prompt = response_data.get('prompt', '')
                
                if prompt:
                    print(f"Dashboard Summary API successful")
                    print(f"Generated prompt length: {len(prompt)} characters")
                    
                    return {
                        'success': True,
                        'prompt': prompt,
                        'status_code': response.status_code
                    }
                else:
                    print("Empty prompt received from API")
                    return {
                        'success': False,
                        'error': 'Empty prompt received',
                        'status_code': response.status_code
                    }
                    
            except Exception as e:
                print(f"Error parsing API response: {str(e)}")
                return {
                    'success': False,
                    'error': f'Response parsing error: {str(e)}',
                    'status_code': response.status_code
                }
        else:
            print(f"Dashboard Summary API failed with status: {response.status_code}")
            try:
                error_detail = response.text
                print(f"Error response: {error_detail}")
            except:
                error_detail = 'No error detail available'
                
            return {
                'success': False,
                'error': f'API returned status {response.status_code}: {error_detail}',
                'status_code': response.status_code
            }
            
    except requests.Timeout:
        print("Dashboard Summary API timeout")
        return {
            'success': False,
            'error': 'API timeout after 180 seconds'
        }
        
    except Exception as e:
        print(f"Dashboard Summary API error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }