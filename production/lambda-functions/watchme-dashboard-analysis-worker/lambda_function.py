import json
import boto3
import requests
import os
from datetime import datetime

# 環境変数
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.hey-watch.me')
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://qvtlwotzuzbavrzqhyvt.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
SNS_PLATFORM_APP_ARN = 'arn:aws:sns:ap-southeast-2:754724220380:app/APNS_SANDBOX/watchme-ios-app-sandbox'

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

            else:
                print(f"Dashboard analysis API failed: {analysis_result.get('error', 'Unknown error')}")

            # API成功/失敗に関わらず、プッシュ通知を送信
            # （アプリ側でデータを再取得させる）
            try:
                send_push_notification(device_id, date, time_slot)
            except Exception as push_error:
                print(f"[PUSH] ⚠️ Push notification failed, but continuing: {str(push_error)}")

            # API失敗時はSQSのリトライを有効にする
            if not analysis_result['success']:
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
        print(f"URL: {API_BASE_URL}/vibe-analysis/scorer/analyze-dashboard-summary")

        # APIを呼び出し
        response = requests.post(
            f"{API_BASE_URL}/vibe-analysis/scorer/analyze-dashboard-summary",
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


def send_push_notification(device_id, date, time_slot):
    """
    iOSアプリにプッシュ通知を送信（観測対象名とタイムブロックを含む）
    """
    try:
        print(f"[PUSH] Starting push notification for device: {device_id}, date: {date}, time_slot: {time_slot}")

        # 1. SupabaseからユーザーのAPNsトークンを取得
        apns_token = get_user_apns_token(device_id)

        if not apns_token:
            print(f"[PUSH] No APNs token found for device: {device_id}")
            return False

        print(f"[PUSH] APNs token found: {apns_token[:20]}...")

        # 2. 観測対象名（Subject名）を取得
        subject_name = get_subject_name_for_device(device_id)

        # 3. タイムブロックをフォーマット（例：22-00 → 22:00-22:30）
        if time_slot:
            try:
                # タイムブロック形式: "22-00" → "22:00-22:30"
                hour = int(time_slot.split('-')[0])
                start_time = f"{hour:02d}:00"
                end_time = f"{hour:02d}:30"
                time_range = f"{start_time}-{end_time}"
            except:
                # パースに失敗した場合はタイムブロックなしで表示
                time_range = None
                print(f"[PUSH] Warning: Failed to parse time_slot: {time_slot}")
        else:
            time_range = None

        # 4. メッセージを動的に生成
        if subject_name:
            # 観測対象名がある場合
            if time_range:
                body_text = f"{subject_name}さんの{time_range}のデータが届きました✨"
            else:
                body_text = f"{subject_name}さんの最新データが届きました✨"
            print(f"[PUSH] Message for subject: {subject_name}, time_range: {time_range}")
        else:
            # 観測対象名がない場合：デバイスIDの先頭8文字を使用
            device_id_short = device_id[:8]
            if time_range:
                body_text = f"デバイス {device_id_short} の{time_range}のデータが届きました✨"
            else:
                body_text = f"デバイス {device_id_short} の最新データが届きました✨"
            print(f"[PUSH] Message for device ID (no subject): {device_id_short}, time_range: {time_range}")

        # 4. SNS Platform Endpointを作成または取得
        endpoint_arn = create_or_update_endpoint(device_id, apns_token)

        if not endpoint_arn:
            print(f"[PUSH] Failed to create/update SNS endpoint")
            return False

        print(f"[PUSH] SNS Endpoint ARN: {endpoint_arn}")

        # 5. 通知ペイロードを作成（バナー表示）
        message = {
            'APNS_SANDBOX': json.dumps({
                'aps': {
                    'alert': {
                        'body': body_text
                    },
                    'sound': 'default',
                    'content-available': 1
                },
                'device_id': device_id,
                'date': date,
                'action': 'refresh_dashboard'
            })
        }

        # 4. プッシュ通知を送信
        try:
            response = sns_client.publish(
                TargetArn=endpoint_arn,
                Message=json.dumps(message),
                MessageStructure='json'
            )

            print(f"[PUSH] ✅ Push notification sent successfully: {response['MessageId']}")
            return True

        except sns_client.exceptions.EndpointDisabledException:
            # Endpointが無効化されている場合、再有効化してリトライ
            print(f"[PUSH] Endpoint is disabled. Re-enabling...")

            try:
                sns_client.set_endpoint_attributes(
                    EndpointArn=endpoint_arn,
                    Attributes={'Enabled': 'true'}
                )
                print(f"[PUSH] Endpoint re-enabled successfully")

                # リトライ
                response = sns_client.publish(
                    TargetArn=endpoint_arn,
                    Message=json.dumps(message),
                    MessageStructure='json'
                )

                print(f"[PUSH] ✅ Push notification sent successfully (after re-enable): {response['MessageId']}")
                return True

            except Exception as retry_error:
                print(f"[PUSH] ❌ Failed to re-enable or send after re-enable: {str(retry_error)}")
                return False

    except Exception as e:
        print(f"[PUSH] ❌ Failed to send push notification: {str(e)}")
        return False


def get_user_apns_token(device_id):
    """
    device_idからユーザーIDを取得し、そのユーザーのAPNsトークンを取得
    2段階クエリで確実に取得
    """
    try:
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}'
        }

        # Step 1: device_idからuser_idのリストを取得（roleに関係なく全ユーザー）
        print(f"[PUSH] Step 1: Getting all user_ids for device: {device_id}")
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/user_devices",
            params={
                'device_id': f'eq.{device_id}',
                'select': 'user_id'
            },
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            print(f"[PUSH] Failed to get user_ids for device: {device_id}, status: {response.status_code}")
            print(f"[PUSH] Response: {response.text}")
            return None

        data = response.json()
        if not data or len(data) == 0:
            print(f"[PUSH] No users found for device: {device_id}")
            return None

        user_ids = [item.get('user_id') for item in data if item.get('user_id')]
        if not user_ids:
            print(f"[PUSH] No valid user_ids found")
            return None

        print(f"[PUSH] Found {len(user_ids)} user(s) for device: {user_ids}")

        # Step 2: 各ユーザーのAPNsトークンを取得（最初に見つかったものを返す）
        for user_id in user_ids:
            print(f"[PUSH] Step 2: Getting APNs token for user: {user_id}")
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/users",
                params={
                    'user_id': f'eq.{user_id}',
                    'select': 'apns_token'
                },
                headers=headers,
                timeout=10
            )

            if response.status_code != 200:
                print(f"[PUSH] Failed to get APNs token for user: {user_id}, status: {response.status_code}")
                continue

            user_data = response.json()
            if not user_data or len(user_data) == 0:
                print(f"[PUSH] User not found: {user_id}")
                continue

            apns_token = user_data[0].get('apns_token')
            if apns_token:
                print(f"[PUSH] ✅ APNs token found for user: {user_id}, token: {apns_token[:20]}...")
                return apns_token
            else:
                print(f"[PUSH] No APNs token for user: {user_id}, checking next user...")

        print(f"[PUSH] No APNs token found for any user of device: {device_id}")
        return None

    except Exception as e:
        print(f"[PUSH] Error fetching APNs token: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def get_subject_name_for_device(device_id):
    """
    device_idに紐づく観測対象（Subject）の名前を取得

    Args:
        device_id: 観測対象デバイスのID

    Returns:
        str: 観測対象の名前（例: "山田太郎"）、取得できない場合はNone
    """
    try:
        headers = {
            'apikey': SUPABASE_KEY,
            'Authorization': f'Bearer {SUPABASE_KEY}'
        }

        # Step 1: device_idからsubject_idを取得
        print(f"[PUSH] Getting subject_id for device: {device_id}")
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/devices",
            params={
                'device_id': f'eq.{device_id}',
                'select': 'subject_id'
            },
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            print(f"[PUSH] Failed to get device info: {response.status_code}")
            return None

        device_data = response.json()
        if not device_data or len(device_data) == 0:
            print(f"[PUSH] Device not found: {device_id}")
            return None

        subject_id = device_data[0].get('subject_id')
        if not subject_id:
            print(f"[PUSH] No subject_id for device: {device_id}")
            return None

        print(f"[PUSH] Subject ID found: {subject_id}")

        # Step 2: subject_idから観測対象の名前を取得
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/subjects",
            params={
                'subject_id': f'eq.{subject_id}',
                'select': 'name'
            },
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            print(f"[PUSH] Failed to get subject info: {response.status_code}")
            return None

        subject_data = response.json()
        if not subject_data or len(subject_data) == 0:
            print(f"[PUSH] Subject not found: {subject_id}")
            return None

        subject_name = subject_data[0].get('name')
        if subject_name:
            print(f"[PUSH] ✅ Subject name found: {subject_name}")
            return subject_name
        else:
            print(f"[PUSH] No name for subject: {subject_id}")
            return None

    except Exception as e:
        print(f"[PUSH] Error fetching subject name: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def create_or_update_endpoint(device_id, apns_token):
    """
    SNS Platform Endpointを作成または更新
    既存Endpointとの属性不一致がある場合は削除してから再作成

    注意：device_idは観測対象デバイス（音声録音機器）のIDであり、
    iPhoneのデバイスIDではない。CustomUserDataには使用しない。
    """
    try:
        # CustomUserDataは使用しない（観測対象デバイスが複数あるため、
        # device_idごとに異なる値を設定すると属性エラーが発生する）

        # Endpointを作成
        response = sns_client.create_platform_endpoint(
            PlatformApplicationArn=SNS_PLATFORM_APP_ARN,
            Token=apns_token
        )

        endpoint_arn = response['EndpointArn']
        print(f"[PUSH] SNS Endpoint created: {endpoint_arn}")
        return endpoint_arn

    except sns_client.exceptions.InvalidParameterException as e:
        # Endpointが既に存在する場合
        error_message = str(e)
        if 'already exists' in error_message.lower():
            # エラーメッセージからARNを抽出
            import re
            match = re.search(r'arn:aws:sns[^\s]+', error_message)
            if match:
                endpoint_arn = match.group(0)
                print(f"[PUSH] SNS Endpoint already exists: {endpoint_arn}")

                # 既存Endpointの属性が異なる場合は削除して再作成
                if 'different attributes' in error_message.lower():
                    print(f"[PUSH] Endpoint has different attributes. Deleting and recreating...")

                    try:
                        # 既存Endpointを削除
                        sns_client.delete_endpoint(EndpointArn=endpoint_arn)
                        print(f"[PUSH] Old endpoint deleted successfully")

                        # 新しいEndpointを作成（CustomUserDataなし）
                        response = sns_client.create_platform_endpoint(
                            PlatformApplicationArn=SNS_PLATFORM_APP_ARN,
                            Token=apns_token
                        )

                        new_endpoint_arn = response['EndpointArn']
                        print(f"[PUSH] New SNS Endpoint created: {new_endpoint_arn}")
                        return new_endpoint_arn

                    except Exception as recreate_error:
                        print(f"[PUSH] ❌ Failed to delete/recreate endpoint: {str(recreate_error)}")
                        return None

                else:
                    # 属性が同じ場合は既存Endpointを有効化して使用
                    try:
                        sns_client.set_endpoint_attributes(
                            EndpointArn=endpoint_arn,
                            Attributes={'Enabled': 'true'}
                        )
                        print(f"[PUSH] Existing endpoint re-enabled")
                    except Exception as enable_error:
                        print(f"[PUSH] Failed to re-enable endpoint: {enable_error}")

                    return endpoint_arn

        print(f"[PUSH] InvalidParameterException: {e}")
        return None

    except Exception as e:
        print(f"[PUSH] Error creating/updating endpoint: {str(e)}")
        return None