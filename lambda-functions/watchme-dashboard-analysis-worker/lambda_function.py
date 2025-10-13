import json
import boto3
import requests
import os
from datetime import datetime

# 環境変数
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.hey-watch.me')
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://qvtlwotzuzbavrzqhyvt.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
SNS_PLATFORM_APP_ARN = 'arn:aws:sns:ap-southeast-2:754724220380:app/APNS/watchme-ios-app'

# SNSクライアント
sns_client = boto3.client('sns', region_name='ap-southeast-2')

def lambda_handler(event, context):
    """
    Dashboard Analysis Worker Lambda
    SQSメッセージを処理してChatGPT分析APIを呼び出し、
    結果をデータベースに保存
    """
    
    print(f"Processing Dashboard Analysis: {len(event['Records'])} messages")
    
    for record in event['Records']:
        try:
            # メッセージ本文を解析
            message = json.loads(record['body'])
            
            device_id = message['device_id']
            date = message['date']
            time_slot = message.get('time_slot', '')
            prompt = message.get('prompt', '')
            
            if not prompt:
                raise ValueError("No prompt provided in message")
            
            print(f"Processing dashboard analysis for: {device_id}/{date}")
            print(f"Triggered by timeblock: {time_slot}")
            print(f"Prompt length: {len(prompt)} characters")
            
            # Dashboard Analysis APIを呼び出し（ChatGPT分析）
            analysis_result = call_dashboard_analysis_api(
                device_id, date, prompt
            )
            
            if analysis_result['success']:
                print(f"Dashboard analysis completed successfully")
                print(f"Analysis result saved to database")

                # 成功ログ
                log_success_metrics(device_id, date, time_slot, analysis_result)

                # プッシュ通知を送信
                send_push_notification(device_id, date)
                
            else:
                print(f"Dashboard analysis API failed: {analysis_result.get('error', 'Unknown error')}")
                # エラーの場合、SQSのリトライ機能により自動的に再試行される
                raise Exception(f"Dashboard analysis failed: {analysis_result.get('error')}")
            
        except Exception as e:
            print(f"Error processing message: {str(e)}")
            # 例外を再発生させてSQSのリトライを有効にする
            raise
    
    return {
        'statusCode': 200,
        'body': json.dumps('Dashboard analysis processing completed')
    }


def call_dashboard_analysis_api(device_id, date, prompt):
    """
    Dashboard Analysis API（ChatGPT分析）を呼び出し
    """
    try:
        print(f"Calling Dashboard Analysis API...")
        print(f"URL: {API_BASE_URL}/vibe-scorer/analyze-dashboard-summary")
        
        # APIを呼び出し
        response = requests.post(
            f"{API_BASE_URL}/vibe-scorer/analyze-dashboard-summary",
            json={
                "device_id": device_id,
                "date": date
            },
            timeout=180
        )
        
        if response.status_code == 200:
            try:
                response_data = response.json()

                # 分析結果の確認（APIは'status'フィールドを返す）
                if response_data.get('status') == 'success' or response_data.get('success'):
                    print(f"Dashboard Analysis API successful")
                    
                    # 分析結果の概要をログ出力
                    analysis_data = response_data.get('analysis_result', {})
                    if analysis_data:
                        print(f"Analysis contains: {list(analysis_data.keys())}")
                        
                        # 主要な分析結果をログ出力
                        if 'overall_summary' in analysis_data:
                            summary = analysis_data['overall_summary']
                            print(f"Overall summary length: {len(str(summary))} characters")
                        
                        if 'hourly_summaries' in analysis_data:
                            hourly_count = len(analysis_data['hourly_summaries'])
                            print(f"Hourly summaries: {hourly_count} entries")
                        
                        if 'emotion_trends' in analysis_data:
                            print("Emotion trends data included")
                        
                        if 'behavioral_patterns' in analysis_data:
                            print("Behavioral patterns data included")
                    
                    return {
                        'success': True,
                        'analysis_result': analysis_data,
                        'status_code': response.status_code
                    }
                else:
                    error_msg = response_data.get('error', 'Analysis indicated failure')
                    print(f"API returned success=false: {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg,
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
            print(f"Dashboard Analysis API failed with status: {response.status_code}")
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
        print("Dashboard Analysis API timeout")
        return {
            'success': False,
            'error': 'API timeout after 180 seconds'
        }
        
    except Exception as e:
        print(f"Dashboard Analysis API error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def log_success_metrics(device_id, date, time_slot, analysis_result):
    """
    成功時のメトリクスをログ出力（CloudWatch監視用）
    """
    try:
        metrics = {
            'event': 'dashboard_analysis_completed',
            'device_id': device_id,
            'date': date,
            'triggered_by_timeblock': time_slot,
            'timestamp': datetime.utcnow().isoformat(),
            'status_code': analysis_result.get('status_code', 200)
        }
        
        # 分析結果のサイズ情報を追加
        if 'analysis_result' in analysis_result:
            analysis_data = analysis_result['analysis_result']
            metrics['has_overall_summary'] = 'overall_summary' in analysis_data
            metrics['has_hourly_summaries'] = 'hourly_summaries' in analysis_data
            metrics['has_emotion_trends'] = 'emotion_trends' in analysis_data
            metrics['has_behavioral_patterns'] = 'behavioral_patterns' in analysis_data
            
            # データサイズの概要
            if 'hourly_summaries' in analysis_data:
                metrics['hourly_summaries_count'] = len(analysis_data['hourly_summaries'])
        
        # CloudWatch用のJSON形式でログ出力
        print(f"METRICS: {json.dumps(metrics)}")

    except Exception as e:
        print(f"Error logging metrics: {str(e)}")


def send_push_notification(device_id, date):
    """
    iOSアプリにサイレントプッシュ通知を送信
    """
    try:
        print(f"[PUSH] Starting push notification for device: {device_id}, date: {date}")

        # 1. Supabaseからデバイストークンを取得
        apns_token = get_device_apns_token(device_id)

        if not apns_token:
            print(f"[PUSH] No APNs token found for device: {device_id}")
            return False

        print(f"[PUSH] APNs token found: {apns_token[:20]}...")

        # 2. SNS Platform Endpointを作成または取得
        endpoint_arn = create_or_update_endpoint(device_id, apns_token)

        if not endpoint_arn:
            print(f"[PUSH] Failed to create/update SNS endpoint")
            return False

        print(f"[PUSH] SNS Endpoint ARN: {endpoint_arn}")

        # 3. サイレント通知ペイロードを作成
        message = {
            'APNS_SANDBOX': json.dumps({
                'aps': {
                    'content-available': 1  # サイレント通知
                },
                'device_id': device_id,
                'date': date,
                'action': 'refresh_dashboard'
            }),
            'APNS': json.dumps({
                'aps': {
                    'content-available': 1  # サイレント通知
                },
                'device_id': device_id,
                'date': date,
                'action': 'refresh_dashboard'
            })
        }

        # 4. プッシュ通知を送信
        response = sns_client.publish(
            TargetArn=endpoint_arn,
            Message=json.dumps(message),
            MessageStructure='json'
        )

        print(f"[PUSH] ✅ Push notification sent successfully: {response['MessageId']}")
        return True

    except Exception as e:
        print(f"[PUSH] ❌ Failed to send push notification: {str(e)}")
        return False


def get_device_apns_token(device_id):
    """
    SupabaseからデバイスのAPNsトークンを取得
    """
    try:
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}'
        }

        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/devices",
            params={'device_id': f'eq.{device_id}', 'select': 'apns_token'},
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0 and data[0].get('apns_token'):
                return data[0]['apns_token']

        print(f"[PUSH] Device not found or no APNs token: {device_id}")
        return None

    except Exception as e:
        print(f"[PUSH] Error fetching APNs token: {str(e)}")
        return None


def create_or_update_endpoint(device_id, apns_token):
    """
    SNS Platform Endpointを作成または更新
    """
    try:
        # カスタムユーザーデータ（デバイスIDを保存）
        custom_user_data = json.dumps({'device_id': device_id})

        # Endpointを作成
        response = sns_client.create_platform_endpoint(
            PlatformApplicationArn=SNS_PLATFORM_APP_ARN,
            Token=apns_token,
            CustomUserData=custom_user_data
        )

        endpoint_arn = response['EndpointArn']
        print(f"[PUSH] SNS Endpoint created: {endpoint_arn}")
        return endpoint_arn

    except sns_client.exceptions.InvalidParameterException as e:
        # Endpointが既に存在する場合
        error_message = str(e)
        if 'Endpoint already exists' in error_message:
            # エラーメッセージからARNを抽出
            import re
            match = re.search(r'arn:aws:sns[^\s]+', error_message)
            if match:
                endpoint_arn = match.group(0)
                print(f"[PUSH] SNS Endpoint already exists: {endpoint_arn}")

                # トークンを更新
                try:
                    sns_client.set_endpoint_attributes(
                        EndpointArn=endpoint_arn,
                        Attributes={
                            'Token': apns_token,
                            'Enabled': 'true',
                            'CustomUserData': custom_user_data
                        }
                    )
                    print(f"[PUSH] SNS Endpoint updated")
                except Exception as update_error:
                    print(f"[PUSH] Failed to update endpoint: {update_error}")

                return endpoint_arn

        print(f"[PUSH] InvalidParameterException: {e}")
        return None

    except Exception as e:
        print(f"[PUSH] Error creating/updating endpoint: {str(e)}")
        return None