import json
import boto3
import requests
import os
import time
from datetime import datetime

# 環境変数
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.hey-watch.me')
DASHBOARD_SUMMARY_QUEUE_URL = os.environ.get('DASHBOARD_SUMMARY_QUEUE_URL', 'https://sqs.ap-southeast-2.amazonaws.com/975050024946/watchme-dashboard-summary-queue')

# SQSクライアント
sqs = boto3.client('sqs', region_name='ap-southeast-2')

def lambda_handler(event, context):
    """
    SQSメッセージを処理して音声処理パイプラインを実行
    SQSのリトライ機能により、失敗時は自動的に再試行される
    """
    
    print(f"Processing SQS messages: {len(event['Records'])} messages")
    
    # SQSメッセージを処理
    for record in event['Records']:
        try:
            # メッセージ本文を解析
            message = json.loads(record['body'])
            
            file_path = message['file_path']
            device_id = message['device_id']
            date = message['date']
            time_slot = message['time_slot']
            
            print(f"Processing audio: {device_id}/{date}/{time_slot}")
            print(f"File path: {file_path}")
            
            # 処理パイプラインを実行
            results = trigger_processing_pipeline(
                file_path, device_id, date, time_slot
            )
            
            # 結果をログに出力
            print(f"Processing results: {json.dumps(results)}")
            
            # Vibe Scorerが成功した場合、累積分析キューにメッセージを送信
            if results.get('vibe_scorer', {}).get('success'):
                trigger_dashboard_summary(device_id, date, time_slot)
            
            # 成功したメッセージは自動的にSQSから削除される
            
        except Exception as e:
            print(f"Error processing message: {str(e)}")
            # 例外を再発生させてSQSのリトライを有効にする
            raise
    
    return {
        'statusCode': 200,
        'body': json.dumps('Processing completed')
    }


def trigger_processing_pipeline(file_path, device_id, date, time_slot):
    """各APIを順次呼び出し（現在のロジックをそのまま移植）"""
    
    results = {}
    
    # 1. Azure Speech API (音声書き起こし)
    azure_success = False
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries and not azure_success:
        try:
            if retry_count > 0:
                # 指数バックオフ
                wait_time = min(30, 5 * (2 ** (retry_count - 1)))
                print(f"Retry {retry_count}/{max_retries} after {wait_time} seconds...")
                time.sleep(wait_time)
            
            print(f"Calling Azure Speech API (attempt {retry_count + 1}/{max_retries})...")
            transcribe_response = requests.post(
                f"{API_BASE_URL}/vibe-analysis/transcriber/fetch-and-transcribe",
                json={
                    "file_paths": [file_path]
                },
                timeout=900
            )
            
            # 429/503の場合はリトライ
            if transcribe_response.status_code in [429, 503]:
                print(f"Received {transcribe_response.status_code}, will retry...")
                retry_count += 1
                continue

            # HTTP 200の場合、レスポンス本文を解析してファイル単位で判定
            if transcribe_response.status_code == 200:
                try:
                    response_data = transcribe_response.json()
                    print(f"Azure Speech API response: {response_data}")

                    # 【重要】該当ファイルが成功したか失敗したかを判定
                    processed_files = response_data.get('processed_files', [])
                    error_files = response_data.get('error_files', [])

                    # ファイル単位で成功/失敗を判定
                    if file_path in processed_files:
                        # ✅ 成功
                        azure_success = True
                        results['transcription'] = {
                            'status_code': 200,
                            'success': True,
                            'response': response_data,
                            'retry_count': retry_count
                        }
                        print(f"✅ Azure Speech API: File successfully processed")

                    elif file_path in error_files:
                        # ❌ 失敗（クォーター超過など）
                        azure_success = False
                        results['transcription'] = {
                            'status_code': 200,
                            'success': False,
                            'error_type': 'processing_failed',
                            'response': response_data,
                            'retry_count': retry_count,
                            'message': 'File was in error_files list'
                        }
                        print(f"⚠️ Azure Speech API: File processing failed")

                    else:
                        # ファイルがどちらのリストにもない場合はsummary.errorsで判定
                        errors_count = response_data.get('summary', {}).get('errors', 0)
                        azure_success = (errors_count == 0)

                        results['transcription'] = {
                            'status_code': 200,
                            'success': azure_success,
                            'response': response_data,
                            'retry_count': retry_count,
                            'message': f'Errors: {errors_count}' if not azure_success else 'Success'
                        }
                        print(f"{'✅' if azure_success else '⚠️'} Azure Speech API: {results['transcription']['message']}")

                    break  # レスポンス解析完了、ループを抜ける

                except Exception as e:
                    print(f"Error parsing Azure response: {str(e)}")
                    azure_success = False
                    results['transcription'] = {
                        'status_code': 200,
                        'success': False,
                        'error': f'Response parsing error: {str(e)}'
                    }
                    break
            else:
                # HTTP 200以外のエラー
                print(f"Azure API failed with status: {transcribe_response.status_code}")
                azure_success = False
                results['transcription'] = {
                    'status_code': transcribe_response.status_code,
                    'success': False,
                    'error': f'HTTP {transcribe_response.status_code}'
                }
                break
                
        except requests.Timeout:
            print("Transcription API timeout")
            retry_count += 1
            if retry_count >= max_retries:
                results['transcription'] = {'error': 'Timeout after retries', 'success': False}
                
        except Exception as e:
            print(f"Transcription API error: {str(e)}")
            retry_count += 1
            if retry_count >= max_retries:
                results['transcription'] = {'error': str(e), 'success': False}
    
    # 2. AST API (音響イベント検出)
    ast_success = False
    try:
        print(f"Calling AST API for audio event detection...")
        ast_response = requests.post(
            f"{API_BASE_URL}/behavior-analysis/features/fetch-and-process-paths",
            json={
                "file_paths": [file_path]
            },
            timeout=900
        )
        ast_success = ast_response.status_code == 200
        results['ast_behavior'] = {
            'status_code': ast_response.status_code,
            'success': ast_success
        }
        
        # AST処理が成功したら、SED Aggregatorを自動起動
        if ast_response.status_code == 200:
            print(f"AST API successful. Starting SED Aggregator...")
            try:
                sed_aggregator_response = requests.post(
                    f"{API_BASE_URL}/behavior-aggregator/analysis/sed",
                    json={
                        "device_id": device_id,
                        "date": date
                    },
                    timeout=900
                )
                
                if sed_aggregator_response.status_code == 200:
                    response_data = sed_aggregator_response.json()
                    task_id = response_data.get('task_id')
                    print(f"SED Aggregator started. Task ID: {task_id}")
                    results['sed_aggregator'] = {
                        'status_code': sed_aggregator_response.status_code,
                        'success': True,
                        'task_id': task_id
                    }
                else:
                    print(f"SED Aggregator failed: {sed_aggregator_response.status_code}")
                    results['sed_aggregator'] = {
                        'status_code': sed_aggregator_response.status_code,
                        'success': False
                    }
                    
            except Exception as e:
                print(f"SED Aggregator error: {str(e)}")
                results['sed_aggregator'] = {'error': str(e), 'success': False}
                
    except requests.Timeout:
        print("AST API timeout")
        results['ast_behavior'] = {'error': 'Timeout', 'success': False}
    except Exception as e:
        print(f"AST API error: {str(e)}")
        results['ast_behavior'] = {'error': str(e), 'success': False}
    
    # 3. SUPERB API (感情認識)
    superb_success = False
    try:
        print(f"Calling SUPERB API for emotion recognition...")
        superb_response = requests.post(
            f"{API_BASE_URL}/emotion-analysis/feature-extractor/process/emotion-features",
            json={
                "file_paths": [file_path]
            },
            timeout=900
        )
        superb_success = superb_response.status_code == 200
        results['superb_emotion'] = {
            'status_code': superb_response.status_code,
            'success': superb_success
        }
        
        # SUPERB処理が成功したら、Emotion Aggregatorを自動起動
        if superb_response.status_code == 200:
            print(f"SUPERB API successful. Starting Emotion Aggregator...")
            try:
                emotion_aggregator_response = requests.post(
                    f"{API_BASE_URL}/emotion-analysis/aggregator/analyze/opensmile-aggregator",
                    json={
                        "device_id": device_id,
                        "date": date
                    },
                    timeout=900
                )
                
                if emotion_aggregator_response.status_code == 200:
                    response_data = emotion_aggregator_response.json()
                    task_id = response_data.get('task_id')
                    print(f"Emotion Aggregator started. Task ID: {task_id}")
                    results['emotion_aggregator'] = {
                        'status_code': emotion_aggregator_response.status_code,
                        'success': True,
                        'task_id': task_id
                    }
                else:
                    print(f"Emotion Aggregator failed: {emotion_aggregator_response.status_code}")
                    results['emotion_aggregator'] = {
                        'status_code': emotion_aggregator_response.status_code,
                        'success': False
                    }
                    
            except Exception as e:
                print(f"Emotion Aggregator error: {str(e)}")
                results['emotion_aggregator'] = {'error': str(e), 'success': False}
                
    except requests.Timeout:
        print("SUPERB API timeout")
        results['superb_emotion'] = {'error': 'Timeout', 'success': False}
    except Exception as e:
        print(f"SUPERB API error: {str(e)}")
        results['superb_emotion'] = {'error': str(e), 'success': False}
    
    # 3.5. Azure失敗時の処理: dashboardテーブルに失敗レコードを作成
    if not azure_success:
        print(f"⚠️ Azure API failed. Creating failed record in dashboard table...")
        try:
            failed_record_response = requests.post(
                f"{API_BASE_URL}/vibe-analysis/aggregator/create-failed-record",
                params={
                    "device_id": device_id,
                    "date": date,
                    "time_block": time_slot,
                    "failure_reason": "quota_exceeded",
                    "error_message": "Azure Speech API failed"
                },
                timeout=900
            )

            if failed_record_response.status_code == 200:
                print(f"✅ Failed record created successfully in dashboard table")
                results['failed_record'] = {
                    'status_code': failed_record_response.status_code,
                    'success': True
                }

                # 失敗レコード作成成功時も累積分析をトリガー
                # （dashboard.status='completed'になっているため、次のプロセスに進める）
                trigger_dashboard_summary(device_id, date, time_slot)
            else:
                print(f"❌ Failed to create failed record: {failed_record_response.status_code}")
                results['failed_record'] = {
                    'status_code': failed_record_response.status_code,
                    'success': False
                }
        except Exception as e:
            print(f"❌ Error creating failed record: {str(e)}")
            results['failed_record'] = {'error': str(e), 'success': False}

    # 4. Vibe Aggregator（3つのAPIが全て成功した場合のみ）
    if azure_success and ast_success and superb_success:
        print(f"All APIs successful. Starting Vibe Aggregator...")
        try:
            vibe_aggregator_response = requests.get(
                f"{API_BASE_URL}/vibe-analysis/aggregator/generate-timeblock-prompt",
                params={
                    "device_id": device_id,
                    "date": date,
                    "time_block": time_slot
                },
                timeout=900
            )
            
            if vibe_aggregator_response.status_code == 200:
                print(f"Vibe Aggregator successful")
                
                try:
                    aggregator_data = vibe_aggregator_response.json()
                    prompt = aggregator_data.get('prompt', '')
                    
                    if prompt:
                        print(f"Prompt generated. Length: {len(prompt)} chars")
                        results['vibe_aggregator'] = {
                            'status_code': vibe_aggregator_response.status_code,
                            'success': True,
                            'prompt_length': len(prompt)
                        }
                        
                        # 5. Vibe Scorer (ChatGPT分析)
                        print(f"Starting Vibe Scorer...")
                        try:
                            vibe_scorer_response = requests.post(
                                f"{API_BASE_URL}/vibe-analysis/scorer/analyze-timeblock",
                                json={
                                    "prompt": prompt,
                                    "device_id": device_id,
                                    "date": date,
                                    "time_block": time_slot
                                },
                                timeout=900
                            )
                            
                            if vibe_scorer_response.status_code == 200:
                                scorer_data = vibe_scorer_response.json()
                                print(f"Vibe Scorer successful")
                                results['vibe_scorer'] = {
                                    'status_code': vibe_scorer_response.status_code,
                                    'success': True,
                                    'vibe_score': scorer_data.get('analysis_result', {}).get('vibe_score')
                                }
                            else:
                                print(f"Vibe Scorer failed: {vibe_scorer_response.status_code}")
                                results['vibe_scorer'] = {
                                    'status_code': vibe_scorer_response.status_code,
                                    'success': False
                                }
                                
                        except Exception as e:
                            print(f"Vibe Scorer error: {str(e)}")
                            results['vibe_scorer'] = {'error': str(e), 'success': False}
                    else:
                        print("Empty prompt from Vibe Aggregator")
                        results['vibe_aggregator'] = {
                            'status_code': vibe_aggregator_response.status_code,
                            'success': False,
                            'error': 'Empty prompt'
                        }
                        
                except Exception as e:
                    print(f"Error parsing Vibe Aggregator response: {str(e)}")
                    results['vibe_aggregator'] = {
                        'status_code': vibe_aggregator_response.status_code,
                        'success': False,
                        'parse_error': str(e)
                    }
                
            else:
                print(f"Vibe Aggregator failed: {vibe_aggregator_response.status_code}")
                results['vibe_aggregator'] = {
                    'status_code': vibe_aggregator_response.status_code,
                    'success': False
                }
                
        except Exception as e:
            print(f"Vibe Aggregator error: {str(e)}")
            results['vibe_aggregator'] = {'error': str(e), 'success': False}
    else:
        print(f"Skipping Vibe Aggregator - Prerequisites not met")
        results['vibe_aggregator'] = {
            'skipped': True,
            'reason': f'Prerequisites not met: Azure={azure_success}, AST={ast_success}, SUPERB={superb_success}'
        }
    
    return results


def trigger_dashboard_summary(device_id, date, time_slot):
    """
    累積分析処理をトリガーするためにSQSキューにメッセージを送信
    """
    try:
        print(f"Triggering dashboard summary for {device_id}/{date}")
        
        # 累積分析用のメッセージを作成
        message = {
            'device_id': device_id,
            'date': date,
            'time_slot': time_slot,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'watchme-audio-worker',
            'trigger_reason': 'timeblock_completed'
        }
        
        # SQSにメッセージを送信
        response = sqs.send_message(
            QueueUrl=DASHBOARD_SUMMARY_QUEUE_URL,
            MessageBody=json.dumps(message)
        )
        
        print(f"Dashboard summary triggered successfully")
        print(f"SQS MessageId: {response['MessageId']}")
        print(f"Queue URL: {DASHBOARD_SUMMARY_QUEUE_URL}")
        
        return True
        
    except Exception as e:
        print(f"Error triggering dashboard summary: {str(e)}")
        # エラーが発生してもメイン処理は継続
        return False