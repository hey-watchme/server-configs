import json
import boto3
import requests
from urllib.parse import unquote_plus
import os
from datetime import datetime

# 環境変数
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.hey-watch.me')
# 以下の環境変数は不要になったがコメントアウトで残す（履歴用）
# IPHONE_PREFIX = os.environ.get('IPHONE_PREFIX', 'iphone_')
# ENABLE_ALL_DEVICES = os.environ.get('ENABLE_ALL_DEVICES', 'false').lower() == 'true'
# TEST_DEVICES = os.environ.get('TEST_DEVICES', '').split(',')

def lambda_handler(event, context):
    """
    S3イベントトリガーで音声処理パイプラインを起動
    iPhoneからの録音のみ即座に処理
    """
    
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # S3イベントから情報抽出
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
        
        # 処理対象の判定
        if not should_process(device_id):
            print(f"Skipping processing for device: {device_id}")
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Skipped - not iPhone recording',
                    'device_id': device_id
                })
            }
        
        print(f"Processing iPhone recording: {device_id}/{date}/{time_slot}")
        
        # 処理パイプラインを起動
        results = trigger_processing_pipeline(
            object_key, device_id, date, time_slot
        )
        
        # 結果をログ出力
        print(f"Processing results: {json.dumps(results)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Processing triggered successfully',
                'device_id': device_id,
                'date': date,
                'time_slot': time_slot,
                'results': results,
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
    except Exception as e:
        print(f"Error processing S3 event: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def should_process(device_id):
    """処理対象かどうかを判定"""
    
    # S3に来たすべてのオーディオファイルを一律処理
    print(f"Processing all audio files - device_id: {device_id}")
    return True


def trigger_processing_pipeline(file_path, device_id, date, time_slot):
    """各APIを順次呼び出し"""
    
    results = {}
    
    # 1. Azure Speech API (音声書き起こし)
    # vibe-transcriber-v2 エンドポイントを使用
    azure_success = False
    try:
        print(f"Calling Azure Speech API for transcription...")
        transcribe_response = requests.post(
            f"{API_BASE_URL}/vibe-transcriber-v2/fetch-and-transcribe",
            json={
                "file_paths": [file_path]
            },
            timeout=180  # 3分まで待機（暫定処理）
        )
        azure_success = transcribe_response.status_code == 200
        results['transcription'] = {
            'status_code': transcribe_response.status_code,
            'success': azure_success
        }
        
        # 文字起こし結果を取得（後続の処理で使用する場合）
        if azure_success:
            try:
                response_data = transcribe_response.json()
                print(f"Azure Speech API response: {response_data}")
                transcription_text = response_data.get('text', '')
                results['transcription']['has_text'] = bool(transcription_text)
                results['transcription']['response'] = response_data
            except Exception as e:
                print(f"Error parsing Azure response: {str(e)}")
                print(f"Response text: {transcribe_response.text}")
                results['transcription']['parse_error'] = str(e)
                
    except requests.Timeout:
        print("Transcription API timeout")
        results['transcription'] = {'error': 'Timeout', 'success': False}
    except Exception as e:
        print(f"Transcription API error: {str(e)}")
        results['transcription'] = {'error': str(e), 'success': False}
    
    # 2. 並列処理（AST + SUPERB）
    # 音響分析と感情分析を同時実行
    
    # AST API (音響イベント検出)
    ast_success = False
    try:
        print(f"Calling AST API for audio event detection...")
        ast_response = requests.post(
            f"{API_BASE_URL}/behavior-features/fetch-and-process-paths",
            json={
                "file_paths": [file_path]
            },
            timeout=180  # 3分まで待機（暫定処理）
        )
        ast_success = ast_response.status_code == 200
        results['ast_behavior'] = {
            'status_code': ast_response.status_code,
            'success': ast_success
        }
        
        # AST処理が成功したら、SED Aggregatorを自動起動
        if ast_response.status_code == 200:
            print(f"AST API successful. Starting SED Aggregator for {device_id}/{date}...")
            try:
                sed_aggregator_response = requests.post(
                    f"{API_BASE_URL}/behavior-aggregator/analysis/sed",
                    json={
                        "device_id": device_id,
                        "date": date
                    },
                    timeout=10  # タスク開始の確認のみなので短時間
                )
                
                if sed_aggregator_response.status_code == 200:
                    response_data = sed_aggregator_response.json()
                    task_id = response_data.get('task_id')
                    print(f"SED Aggregator started successfully. Task ID: {task_id}")
                    results['sed_aggregator'] = {
                        'status_code': sed_aggregator_response.status_code,
                        'success': True,
                        'task_id': task_id,
                        'message': response_data.get('message', 'Started')
                    }
                else:
                    print(f"SED Aggregator failed to start: {sed_aggregator_response.status_code}")
                    results['sed_aggregator'] = {
                        'status_code': sed_aggregator_response.status_code,
                        'success': False,
                        'error': f'HTTP {sed_aggregator_response.status_code}'
                    }
                    
            except requests.Timeout:
                print("SED Aggregator timeout")
                results['sed_aggregator'] = {'error': 'Timeout', 'success': False}
            except Exception as e:
                print(f"SED Aggregator error: {str(e)}")
                results['sed_aggregator'] = {'error': str(e), 'success': False}
        else:
            print("AST API failed, skipping SED Aggregator")
            
    except requests.Timeout:
        print("AST API timeout")
        results['ast_behavior'] = {'error': 'Timeout', 'success': False}
    except Exception as e:
        print(f"AST API error: {str(e)}")
        results['ast_behavior'] = {'error': str(e), 'success': False}
    
    # SUPERB API (感情認識)
    superb_success = False
    try:
        print(f"Calling SUPERB API for emotion recognition...")
        superb_response = requests.post(
            f"{API_BASE_URL}/emotion-features/process/emotion-features",
            json={
                "file_paths": [file_path]
            },
            timeout=180  # 3分まで待機（暫定処理）
        )
        superb_success = superb_response.status_code == 200
        results['superb_emotion'] = {
            'status_code': superb_response.status_code,
            'success': superb_success
        }
        
        # SUPERB処理が成功したら、Emotion Aggregatorを自動起動
        if superb_response.status_code == 200:
            print(f"SUPERB API successful. Starting Emotion Aggregator for {device_id}/{date}...")
            try:
                emotion_aggregator_response = requests.post(
                    f"{API_BASE_URL}/emotion-aggregator/analyze/opensmile-aggregator",
                    json={
                        "device_id": device_id,
                        "date": date
                    },
                    timeout=10  # タスク開始の確認のみなので短時間
                )
                
                if emotion_aggregator_response.status_code == 200:
                    response_data = emotion_aggregator_response.json()
                    task_id = response_data.get('task_id')
                    print(f"Emotion Aggregator started successfully. Task ID: {task_id}")
                    results['emotion_aggregator'] = {
                        'status_code': emotion_aggregator_response.status_code,
                        'success': True,
                        'task_id': task_id,
                        'message': response_data.get('message', 'Started')
                    }
                else:
                    print(f"Emotion Aggregator failed to start: {emotion_aggregator_response.status_code}")
                    results['emotion_aggregator'] = {
                        'status_code': emotion_aggregator_response.status_code,
                        'success': False,
                        'error': f'HTTP {emotion_aggregator_response.status_code}'
                    }
                    
            except requests.Timeout:
                print("Emotion Aggregator timeout")
                results['emotion_aggregator'] = {'error': 'Timeout', 'success': False}
            except Exception as e:
                print(f"Emotion Aggregator error: {str(e)}")
                results['emotion_aggregator'] = {'error': str(e), 'success': False}
        else:
            print("SUPERB API failed, skipping Emotion Aggregator")
            
    except requests.Timeout:
        print("SUPERB API timeout")
        results['superb_emotion'] = {'error': 'Timeout', 'success': False}
    except Exception as e:
        print(f"SUPERB API error: {str(e)}")
        results['superb_emotion'] = {'error': str(e), 'success': False}
    
    # 3. Vibe Aggregator (プロンプト生成)
    # 3つの基礎APIがすべて成功した場合のみ実行
    if azure_success and ast_success and superb_success:
        print(f"All 3 APIs successful. Starting Vibe Aggregator for timeblock prompt generation...")
        try:
            # Vibe AggregatorはGETメソッドを使用
            vibe_aggregator_response = requests.get(
                f"{API_BASE_URL}/vibe-aggregator/generate-timeblock-prompt",
                params={
                    "device_id": device_id,
                    "date": date,
                    "time_block": time_slot
                },
                timeout=30  # プロンプト生成は通常短時間
            )
            
            if vibe_aggregator_response.status_code == 200:
                print(f"Vibe Aggregator successful for {device_id}/{date}/{time_slot}")
                results['vibe_aggregator'] = {
                    'status_code': vibe_aggregator_response.status_code,
                    'success': True,
                    'message': 'Timeblock prompt generated and saved to dashboard table'
                }
                
                # Vibe Aggregatorが成功したら、次にVibe Scorerを呼び出すこともできる
                # ただし、今回はプロンプト生成までとする
                
            else:
                print(f"Vibe Aggregator failed: {vibe_aggregator_response.status_code}")
                results['vibe_aggregator'] = {
                    'status_code': vibe_aggregator_response.status_code,
                    'success': False,
                    'error': f'HTTP {vibe_aggregator_response.status_code}'
                }
                
        except requests.Timeout:
            print("Vibe Aggregator timeout")
            results['vibe_aggregator'] = {'error': 'Timeout', 'success': False}
        except Exception as e:
            print(f"Vibe Aggregator error: {str(e)}")
            results['vibe_aggregator'] = {'error': str(e), 'success': False}
    else:
        print(f"Skipping Vibe Aggregator - Prerequisites not met: Azure={azure_success}, AST={ast_success}, SUPERB={superb_success}")
        results['vibe_aggregator'] = {
            'skipped': True,
            'reason': f'Prerequisites not met: Azure={azure_success}, AST={ast_success}, SUPERB={superb_success}'
        }
    
    return results