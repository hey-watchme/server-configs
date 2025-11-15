import json
import boto3
import requests
import os
import time
from datetime import datetime

# Environment variables
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.hey-watch.me')
DASHBOARD_SUMMARY_QUEUE_URL = os.environ.get('DASHBOARD_SUMMARY_QUEUE_URL', 'https://sqs.ap-southeast-2.amazonaws.com/975050024946/watchme-dashboard-summary-queue')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

# SQS client
sqs = boto3.client('sqs', region_name='ap-southeast-2')


def get_transcription_status(file_path: str) -> str:
    """
    Get processing status from DB

    Args:
        file_path: S3 file path

    Returns:
        transcriptions_status ('pending', 'skipped', 'completed', etc)
    """
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/audio_files",
            params={
                "file_path": f"eq.{file_path}",
                "select": "transcriptions_status"
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
                status = data[0].get('transcriptions_status', 'pending')
                print(f"Status from DB: {status} (file: {file_path})")
                return status

        print(f"Warning: Could not fetch status from DB, defaulting to 'pending'")
        return 'pending'

    except Exception as e:
        print(f"Warning: Error getting transcription status: {e}")
        return 'pending'  # Default to pending on error


def lambda_handler(event, context):
    """
    Process SQS messages and execute audio processing pipeline
    Automatically retried by SQS on failure
    """

    print(f"Processing SQS messages: {len(event['Records'])} messages")

    # Process SQS messages
    for record in event['Records']:
        try:
            # Parse message body
            message = json.loads(record['body'])

            file_path = message['file_path']
            device_id = message['device_id']
            recorded_at = message['recorded_at']  # Now using recorded_at instead of date/time_slot

            print(f"Processing audio: {device_id} at {recorded_at}")
            print(f"File path: {file_path}")

            # Execute processing pipeline (including SKIP handling)
            results = trigger_processing_pipeline(
                file_path, device_id, recorded_at
            )

            # Log results
            print(f"Processing results: {json.dumps(results)}")

            # Log based on processing results
            if results.get('status') == 'skipped':
                print(f"Processing skipped (night hours): {device_id} at {recorded_at}")
            elif results.get('status') == 'failed':
                print(f"Processing failed: {device_id} at {recorded_at}")
            else:
                print(f"Processing completed: {device_id} at {recorded_at}")

            # Always trigger cumulative analysis (even for SKIP or failure)
            # This resolves the 06:00 issue
            print(f"Triggering dashboard summary (always executed)")
            trigger_dashboard_summary(device_id, recorded_at)

            # Successfully processed messages are automatically deleted from SQS

        except Exception as e:
            print(f"Error processing message: {str(e)}")
            # Re-raise exception to enable SQS retry
            raise

    return {
        'statusCode': 200,
        'body': json.dumps('Processing completed')
    }


def trigger_processing_pipeline(file_path, device_id, recorded_at):
    """Call each API sequentially (unified processing including SKIP)"""

    results = {}

    # Check status (whether to SKIP or not)
    status = get_transcription_status(file_path)

    # If SKIP status, create failure record and skip processing
    if status == 'skipped':
        print(f"Processing skipped for night hours: {file_path}")

        # Create failure record (treat SKIP as a type of failure)
        try:
            # Note: This endpoint might need to be updated to use recorded_at
            response = requests.post(
                f"{API_BASE_URL}/vibe-analysis/aggregator/create-failed-record",
                params={
                    "device_id": device_id,
                    "recorded_at": recorded_at,
                    "failure_reason": "night_skip",
                    "error_message": "Skipped during quiet hours (23:00-05:59)"
                },
                timeout=30
            )

            if response.status_code == 200:
                print(f"Skip record created successfully")
            else:
                print(f"Warning: Failed to create skip record: {response.status_code}")

        except Exception as e:
            print(f"Warning: Error creating skip record: {str(e)}")

        # Return SKIP status (cumulative analysis will be triggered by caller)
        return {
            'status': 'skipped',
            'message': 'Night hours skip (23:00-05:59)',
            'device_id': device_id,
            'recorded_at': recorded_at
        }

    # Normal processing (not SKIP)

    # 1. ASR API (Speech-to-text) - Vibe Transcriber
    asr_success = False
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries and not asr_success:
        try:
            if retry_count > 0:
                # Exponential backoff
                wait_time = min(30, 5 * (2 ** (retry_count - 1)))
                print(f"Retry {retry_count}/{max_retries} after {wait_time} seconds...")
                time.sleep(wait_time)

            print(f"Calling ASR API (attempt {retry_count + 1}/{max_retries})...")
            transcribe_response = requests.post(
                f"{API_BASE_URL}/vibe-analysis/transcriber/fetch-and-transcribe",
                json={
                    "file_paths": [file_path]
                },
                timeout=900
            )

            # Retry on 429/503
            if transcribe_response.status_code in [429, 503]:
                print(f"Received {transcribe_response.status_code}, will retry...")
                retry_count += 1
                continue

            # Parse response for HTTP 200
            if transcribe_response.status_code == 200:
                try:
                    response_data = transcribe_response.json()
                    print(f"ASR API response: {response_data}")

                    # Check if file was processed successfully
                    processed_files = response_data.get('processed_files', [])
                    error_files = response_data.get('error_files', [])

                    if file_path in processed_files:
                        # Success
                        asr_success = True
                        results['asr'] = {
                            'status_code': 200,
                            'success': True,
                            'response': response_data
                        }
                        print(f"ASR API: File successfully processed")

                    elif file_path in error_files:
                        # Failure
                        asr_success = False
                        results['asr'] = {
                            'status_code': 200,
                            'success': False,
                            'error_type': 'processing_failed',
                            'response': response_data
                        }
                        print(f"Warning: ASR API: File processing failed")

                    else:
                        # Check errors count if file not in either list
                        errors_count = response_data.get('summary', {}).get('errors', 0)
                        asr_success = (errors_count == 0)

                        results['asr'] = {
                            'status_code': 200,
                            'success': asr_success,
                            'response': response_data
                        }
                        print(f"{'✓' if asr_success else 'Warning:'} ASR API: Errors: {errors_count}")

                    break  # Exit loop after parsing response

                except Exception as e:
                    print(f"Error parsing ASR response: {str(e)}")
                    asr_success = False
                    results['asr'] = {
                        'status_code': 200,
                        'success': False,
                        'error': f'Response parsing error: {str(e)}'
                    }
                    break
            else:
                # HTTP error
                print(f"ASR API failed with status: {transcribe_response.status_code}")
                asr_success = False
                results['asr'] = {
                    'status_code': transcribe_response.status_code,
                    'success': False,
                    'error': f'HTTP {transcribe_response.status_code}'
                }
                break

        except requests.Timeout:
            print("ASR API timeout")
            retry_count += 1
            if retry_count >= max_retries:
                results['asr'] = {'error': 'Timeout after retries', 'success': False}

        except Exception as e:
            print(f"ASR API error: {str(e)}")
            retry_count += 1
            if retry_count >= max_retries:
                results['asr'] = {'error': str(e), 'success': False}

    # 2. SED API (Sound Event Detection) - Behavior Features
    sed_success = False
    try:
        print(f"Calling SED API for sound event detection...")
        sed_response = requests.post(
            f"{API_BASE_URL}/behavior-analysis/features/fetch-and-process-paths",
            json={
                "file_paths": [file_path]
            },
            timeout=900
        )
        sed_success = sed_response.status_code == 200
        results['sed'] = {
            'status_code': sed_response.status_code,
            'success': sed_success
        }

        if sed_success:
            print(f"SED API successful")
        else:
            print(f"SED API failed: {sed_response.status_code}")

    except requests.Timeout:
        print("SED API timeout")
        results['sed'] = {'error': 'Timeout', 'success': False}
    except Exception as e:
        print(f"SED API error: {str(e)}")
        results['sed'] = {'error': str(e), 'success': False}

    # 3. SER API (Speech Emotion Recognition) - Emotion Features
    ser_success = False
    try:
        print(f"Calling SER API for emotion recognition...")
        ser_response = requests.post(
            f"{API_BASE_URL}/emotion-analysis/feature-extractor/process/emotion-features",
            json={
                "file_paths": [file_path]
            },
            timeout=900
        )
        ser_success = ser_response.status_code == 200
        results['ser'] = {
            'status_code': ser_response.status_code,
            'success': ser_success
        }

        if ser_success:
            print(f"SER API successful")
        else:
            print(f"SER API failed: {ser_response.status_code}")

    except requests.Timeout:
        print("SER API timeout")
        results['ser'] = {'error': 'Timeout', 'success': False}
    except Exception as e:
        print(f"SER API error: {str(e)}")
        results['ser'] = {'error': str(e), 'success': False}

    # 4. Aggregator API (if all 3 APIs succeeded)
    if asr_success and sed_success and ser_success:
        print(f"All feature extraction APIs successful. Starting Aggregator...")
        try:
            aggregator_response = requests.post(
                f"{API_BASE_URL}/aggregator/spot",
                json={
                    "device_id": device_id,
                    "recorded_at": recorded_at
                },
                timeout=180
            )

            if aggregator_response.status_code == 200:
                print(f"Aggregator API successful")
                results['aggregator'] = {
                    'status_code': 200,
                    'success': True
                }

                # 5. Profiler API (LLM Analysis)
                print(f"Starting Profiler (LLM analysis)...")
                try:
                    profiler_response = requests.post(
                        f"{API_BASE_URL}/profiler/spot-profiler",
                        json={
                            "device_id": device_id,
                            "recorded_at": recorded_at
                        },
                        timeout=180
                    )

                    if profiler_response.status_code == 200:
                        print(f"Profiler API successful")
                        profiler_data = profiler_response.json()
                        results['profiler'] = {
                            'status_code': 200,
                            'success': True,
                            'vibe_score': profiler_data.get('vibe_score'),
                            'summary': profiler_data.get('summary')
                        }
                        print(f"LLM Analysis complete. Vibe Score: {profiler_data.get('vibe_score')}")

                    else:
                        print(f"Profiler API failed: {profiler_response.status_code}")
                        results['profiler'] = {
                            'status_code': profiler_response.status_code,
                            'success': False
                        }

                except Exception as e:
                    print(f"Profiler API error: {str(e)}")
                    results['profiler'] = {'error': str(e), 'success': False}

            else:
                print(f"Aggregator API failed: {aggregator_response.status_code}")
                results['aggregator'] = {
                    'status_code': aggregator_response.status_code,
                    'success': False
                }

        except Exception as e:
            print(f"Aggregator API error: {str(e)}")
            results['aggregator'] = {'error': str(e), 'success': False}
    else:
        print(f"Skipping Aggregator/Profiler - Prerequisites not met")
        results['aggregator'] = {
            'skipped': True,
            'reason': f'Prerequisites not met: ASR={asr_success}, SED={sed_success}, SER={ser_success}'
        }
        results['profiler'] = {
            'skipped': True,
            'reason': 'Aggregator was skipped'
        }

    return results


def trigger_dashboard_summary(device_id, recorded_at):
    """
    Trigger cumulative analysis by sending message to SQS queue
    """
    try:
        print(f"Triggering dashboard summary for {device_id} at {recorded_at}")

        # Fetch local_date from audio_files table
        local_date = None
        try:
            response = requests.get(
                f"{SUPABASE_URL}/rest/v1/audio_files",
                params={
                    "device_id": f"eq.{device_id}",
                    "recorded_at": f"eq.{recorded_at}",
                    "select": "local_date"
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
                    local_date = data[0].get('local_date')
                    print(f"Fetched local_date from audio_files: {local_date}")

        except Exception as e:
            print(f"Warning: Could not fetch local_date from audio_files: {e}")

        # Fallback: calculate from recorded_at (UTC) if fetch failed
        if not local_date:
            print(f"Warning: Using UTC date as fallback")
            try:
                dt = datetime.fromisoformat(recorded_at.replace('Z', '+00:00'))
                local_date = dt.strftime('%Y-%m-%d')
            except:
                local_date = datetime.utcnow().strftime('%Y-%m-%d')
            print(f"Fallback local_date: {local_date}")

        # Create message for cumulative analysis
        message = {
            'device_id': device_id,
            'recorded_at': recorded_at,
            'local_date': local_date,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'watchme-audio-worker',
            'trigger_reason': 'spot_processing_completed'
        }

        # Send message to SQS
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
        # Continue main processing even if error occurs
        return False