import json
import boto3
import requests
from urllib.parse import unquote_plus
import os
from datetime import datetime

# 環境変数
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.hey-watch.me')
IPHONE_PREFIX = os.environ.get('IPHONE_PREFIX', 'iphone_')
ENABLE_ALL_DEVICES = os.environ.get('ENABLE_ALL_DEVICES', 'false').lower() == 'true'
TEST_DEVICES = os.environ.get('TEST_DEVICES', '').split(',')

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
    
    # 全デバイス処理モード（テスト用）
    if ENABLE_ALL_DEVICES:
        print(f"All devices enabled, processing {device_id}")
        return True
    
    # iPhoneデバイスのみ処理
    if device_id.startswith(IPHONE_PREFIX):
        print(f"iPhone device detected: {device_id}")
        return True
    
    # 環境変数で指定されたテストデバイス
    if device_id in TEST_DEVICES:
        print(f"Test device detected: {device_id}")
        return True
    
    return False


def trigger_processing_pipeline(file_path, device_id, date, time_slot):
    """各APIを順次呼び出し"""
    
    results = {}
    
    # 1. Azure Speech API (音声書き起こし)
    # vibe-transcriber-v2 エンドポイントを使用
    try:
        print(f"Calling Azure Speech API for transcription...")
        transcribe_response = requests.post(
            f"{API_BASE_URL}/vibe-transcriber-v2/fetch-and-transcribe",
            json={
                "file_paths": [file_path]
            },
            timeout=60  # Azureは時間かかる場合があるため長めに
        )
        results['transcription'] = {
            'status_code': transcribe_response.status_code,
            'success': transcribe_response.status_code == 200
        }
        
        # 文字起こし結果を取得（後続の処理で使用する場合）
        if transcribe_response.status_code == 200:
            try:
                transcription_text = transcribe_response.json().get('text', '')
                results['transcription']['has_text'] = bool(transcription_text)
            except:
                pass
                
    except requests.Timeout:
        print("Transcription API timeout")
        results['transcription'] = {'error': 'Timeout', 'success': False}
    except Exception as e:
        print(f"Transcription API error: {str(e)}")
        results['transcription'] = {'error': str(e), 'success': False}
    
    # 2. 並列処理（AST + SUPERB）
    # 音響分析と感情分析を同時実行
    
    # AST API (音響イベント検出)
    try:
        print(f"Calling AST API for audio event detection...")
        ast_response = requests.post(
            f"{API_BASE_URL}/behavior-features/fetch-and-process-paths",
            json={
                "file_paths": [file_path]
            },
            timeout=45
        )
        results['ast_behavior'] = {
            'status_code': ast_response.status_code,
            'success': ast_response.status_code == 200
        }
    except requests.Timeout:
        print("AST API timeout")
        results['ast_behavior'] = {'error': 'Timeout', 'success': False}
    except Exception as e:
        print(f"AST API error: {str(e)}")
        results['ast_behavior'] = {'error': str(e), 'success': False}
    
    # SUPERB API (感情認識)
    try:
        print(f"Calling SUPERB API for emotion recognition...")
        superb_response = requests.post(
            f"{API_BASE_URL}/emotion-features/process/emotion-features",
            json={
                "file_paths": [file_path]
            },
            timeout=45
        )
        results['superb_emotion'] = {
            'status_code': superb_response.status_code,
            'success': superb_response.status_code == 200
        }
    except requests.Timeout:
        print("SUPERB API timeout")
        results['superb_emotion'] = {'error': 'Timeout', 'success': False}
    except Exception as e:
        print(f"SUPERB API error: {str(e)}")
        results['superb_emotion'] = {'error': str(e), 'success': False}
    
    # 3. Vibe Aggregator/Scorer (必要に応じて)
    # 文字起こしが成功した場合のみ実行
    # if results.get('transcription', {}).get('success'):
    #     try:
    #         print(f"Calling Vibe Scorer API...")
    #         vibe_response = requests.post(
    #             f"{API_BASE_URL}/vibe-scorer/",
    #             json={
    #                 "file_path": file_path,
    #                 "device_id": device_id,
    #                 "date": date,
    #                 "time_slot": time_slot
    #             },
    #             timeout=30
    #         )
    #         results['vibe_scorer'] = {
    #             'status_code': vibe_response.status_code,
    #             'success': vibe_response.status_code == 200
    #         }
    #     except Exception as e:
    #         print(f"Vibe Scorer API error: {str(e)}")
    #         results['vibe_scorer'] = {'error': str(e), 'success': False}
    
    return results