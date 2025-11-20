import json
import requests
import os
from datetime import datetime, timedelta

# Environment variables
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.hey-watch.me')
# Device IDs to process (comma-separated)
DEVICE_IDS = os.environ.get('DEVICE_IDS', '9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93').split(',')

def lambda_handler(event, context):
    """
    Weekly Profile Worker Lambda
    Triggered daily at 00:00 (JST) by EventBridge
    Processes the week containing yesterday's date (Monday-Sunday)
    """

    print(f"Starting Weekly Profile Worker at {datetime.utcnow().isoformat()}")

    # Calculate week_start_date (Monday of the week containing yesterday)
    yesterday = datetime.utcnow().date() - timedelta(days=1)
    week_start_date = yesterday - timedelta(days=yesterday.weekday())

    print(f"Yesterday: {yesterday.isoformat()}")
    print(f"Week start date (Monday): {week_start_date.isoformat()}")
    print(f"Processing {len(DEVICE_IDS)} device(s)")

    results = []

    for device_id in DEVICE_IDS:
        device_id = device_id.strip()
        print(f"\n--- Processing device: {device_id} ---")

        try:
            # Step 1: Call Weekly Aggregator API
            aggregator_result = call_weekly_aggregator_api(device_id, week_start_date)

            if not aggregator_result['success']:
                print(f"Aggregator API failed for {device_id}: {aggregator_result.get('error')}")
                results.append({
                    'device_id': device_id,
                    'success': False,
                    'error': aggregator_result.get('error'),
                    'step': 'aggregator'
                })
                continue

            # Step 2: Call Weekly Profiler API
            profiler_result = call_weekly_profiler_api(device_id, week_start_date)

            if not profiler_result['success']:
                print(f"Profiler API failed for {device_id}: {profiler_result.get('error')}")
                results.append({
                    'device_id': device_id,
                    'success': False,
                    'error': profiler_result.get('error'),
                    'step': 'profiler'
                })
                continue

            # Success
            print(f"Weekly profile completed successfully for {device_id}")
            results.append({
                'device_id': device_id,
                'success': True,
                'week_start_date': week_start_date.isoformat(),
                'aggregator_spot_count': aggregator_result.get('spot_count', 0),
                'profiler_memorable_events': profiler_result.get('memorable_events_count', 0)
            })

        except Exception as e:
            print(f"Error processing device {device_id}: {str(e)}")
            results.append({
                'device_id': device_id,
                'success': False,
                'error': str(e),
                'step': 'exception'
            })

    # Summary
    success_count = sum(1 for r in results if r['success'])
    failure_count = len(results) - success_count

    print(f"\n=== Weekly Profile Worker Summary ===")
    print(f"Total devices: {len(results)}")
    print(f"Success: {success_count}")
    print(f"Failure: {failure_count}")
    print(f"Week start date: {week_start_date.isoformat()}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Weekly profile processing completed',
            'week_start_date': week_start_date.isoformat(),
            'total_devices': len(results),
            'success_count': success_count,
            'failure_count': failure_count,
            'results': results
        })
    }


def call_weekly_aggregator_api(device_id, week_start_date):
    """
    Call Weekly Aggregator API to generate weekly prompt

    Args:
        device_id: Device ID
        week_start_date: Week start date (Monday, date object)

    Returns:
        dict: {'success': bool, 'spot_count': int, 'error': str}
    """
    try:
        url = f"{API_BASE_URL}/aggregator/weekly"
        payload = {
            "device_id": device_id,
            "week_start_date": week_start_date.isoformat()
        }

        print(f"Calling Weekly Aggregator API: {url}")
        print(f"Payload: {json.dumps(payload)}")

        response = requests.post(
            url,
            json=payload,
            timeout=180
        )

        if response.status_code == 200:
            response_data = response.json()
            spot_count = response_data.get('spot_count', 0)

            print(f"Weekly Aggregator API successful")
            print(f"Spot count: {spot_count}")

            return {
                'success': True,
                'spot_count': spot_count,
                'status_code': response.status_code
            }
        else:
            error_detail = response.text
            print(f"Weekly Aggregator API failed with status: {response.status_code}")
            print(f"Error response: {error_detail}")

            return {
                'success': False,
                'error': f'API returned status {response.status_code}: {error_detail}',
                'status_code': response.status_code
            }

    except requests.Timeout:
        print("Weekly Aggregator API timeout")
        return {
            'success': False,
            'error': 'API timeout after 180 seconds'
        }

    except Exception as e:
        print(f"Weekly Aggregator API error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def call_weekly_profiler_api(device_id, week_start_date):
    """
    Call Weekly Profiler API to analyze weekly data

    Args:
        device_id: Device ID
        week_start_date: Week start date (Monday, date object)

    Returns:
        dict: {'success': bool, 'memorable_events_count': int, 'error': str}
    """
    try:
        url = f"{API_BASE_URL}/profiler/weekly-profiler"
        payload = {
            "device_id": device_id,
            "week_start_date": week_start_date.isoformat()
        }

        print(f"Calling Weekly Profiler API: {url}")
        print(f"Payload: {json.dumps(payload)}")

        response = requests.post(
            url,
            json=payload,
            timeout=180
        )

        if response.status_code == 200:
            response_data = response.json()
            analysis_result = response_data.get('analysis_result', {})
            memorable_events = analysis_result.get('memorable_events', [])

            print(f"Weekly Profiler API successful")
            print(f"Memorable events count: {len(memorable_events)}")

            return {
                'success': True,
                'memorable_events_count': len(memorable_events),
                'status_code': response.status_code
            }
        else:
            error_detail = response.text
            print(f"Weekly Profiler API failed with status: {response.status_code}")
            print(f"Error response: {error_detail}")

            return {
                'success': False,
                'error': f'API returned status {response.status_code}: {error_detail}',
                'status_code': response.status_code
            }

    except requests.Timeout:
        print("Weekly Profiler API timeout")
        return {
            'success': False,
            'error': 'API timeout after 180 seconds'
        }

    except Exception as e:
        print(f"Weekly Profiler API error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
