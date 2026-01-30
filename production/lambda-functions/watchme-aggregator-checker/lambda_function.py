import json
import boto3
import requests
import os
from datetime import datetime

# Environment variables
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.hey-watch.me')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
DASHBOARD_SUMMARY_QUEUE_URL = os.environ.get(
    'DASHBOARD_SUMMARY_QUEUE_URL',
    'https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-dashboard-summary-queue'
)

# SQS client
sqs = boto3.client('sqs', region_name='ap-southeast-2')

def lambda_handler(event, context):
    """
    Process feature completion notifications and trigger Aggregator when all features are ready
    """
    print(f"Processing {len(event['Records'])} feature completion notifications")

    for record in event['Records']:
        try:
            # Parse SQS message
            message = json.loads(record['body'])

            device_id = message['device_id']
            recorded_at = message['recorded_at']
            feature_type = message.get('feature_type')
            status = message.get('status')

            print(f"Feature completion: {feature_type} for {device_id} at {recorded_at} - Status: {status}")

            # Only proceed if this feature completed successfully
            if status != 'completed':
                print(f"Feature {feature_type} failed, skipping aggregation check")
                continue

            # Check if all three features are complete
            statuses = get_feature_statuses(device_id, recorded_at)

            print(f"Feature statuses: vibe={statuses.get('vibe_status')}, "
                  f"behavior={statuses.get('behavior_status')}, "
                  f"emotion={statuses.get('emotion_status')}")

            # Check if all features are complete
            if (statuses.get('vibe_status') == 'completed' and
                statuses.get('behavior_status') == 'completed' and
                statuses.get('emotion_status') == 'completed'):

                print(f"All features complete! Starting Aggregator...")

                # Call Aggregator API
                try:
                    agg_response = requests.post(
                        f"{API_BASE_URL}/aggregator/spot",
                        json={
                            "device_id": device_id,
                            "recorded_at": recorded_at
                        },
                        timeout=180  # 3 minutes timeout
                    )

                    if agg_response.status_code == 200:
                        print(f"Aggregator completed successfully")

                        # ✅ UPDATE spot_aggregators.aggregator_status to 'completed'
                        update_aggregator_status(device_id, recorded_at, "completed")

                        # Call Profiler API
                        try:
                            prof_response = requests.post(
                                f"{API_BASE_URL}/profiler/spot-profiler",
                                json={
                                    "device_id": device_id,
                                    "recorded_at": recorded_at
                                },
                                timeout=180  # 3 minutes timeout
                            )

                            if prof_response.status_code == 200:
                                print(f"Profiler completed successfully")
                                prof_data = prof_response.json()
                                print(f"Vibe Score: {prof_data.get('vibe_score')}")

                                # ✅ UPDATE spot_results.profiler_status to 'completed'
                                update_profiler_status(device_id, recorded_at, "completed")

                                # Trigger dashboard summary with local_date
                                trigger_dashboard_summary(device_id, recorded_at, statuses.get('local_date'))

                            else:
                                print(f"Profiler failed: {prof_response.status_code}")
                                # ❌ UPDATE spot_results.profiler_status to 'failed'
                                update_profiler_status(device_id, recorded_at, "failed")

                        except Exception as e:
                            print(f"Profiler API error: {str(e)}")
                            # ❌ UPDATE spot_results.profiler_status to 'failed'
                            update_profiler_status(device_id, recorded_at, "failed")

                    else:
                        print(f"Aggregator failed: {agg_response.status_code}")
                        # ❌ UPDATE aggregator_status to 'failed'
                        update_aggregator_status(device_id, recorded_at, "failed")

                except Exception as e:
                    print(f"Aggregator API error: {str(e)}")
                    # ❌ UPDATE aggregator_status to 'failed'
                    update_aggregator_status(device_id, recorded_at, "failed")

            else:
                print(f"Not all features complete yet, waiting for: "
                      f"vibe={'❌' if statuses.get('vibe_status') != 'completed' else '✅'} "
                      f"behavior={'❌' if statuses.get('behavior_status') != 'completed' else '✅'} "
                      f"emotion={'❌' if statuses.get('emotion_status') != 'completed' else '✅'}")

        except Exception as e:
            print(f"Error processing completion notification: {str(e)}")
            # Don't re-raise - we don't want to retry completion notifications

    return {
        'statusCode': 200,
        'body': json.dumps('Feature completion processing complete')
    }


def get_feature_statuses(device_id: str, recorded_at: str) -> dict:
    """
    Get the current status of all features from spot_features table
    """
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/spot_features",
            params={
                "device_id": f"eq.{device_id}",
                "recorded_at": f"eq.{recorded_at}",
                "select": "vibe_status,behavior_status,emotion_status,local_date"
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
                return data[0]

        print(f"No feature status found for {device_id}/{recorded_at}")
        return {}

    except Exception as e:
        print(f"Error fetching feature statuses: {str(e)}")
        return {}


def update_aggregator_status(device_id: str, recorded_at: str, status: str):
    """
    Update aggregator_status in spot_aggregators table
    """
    try:
        response = requests.patch(
            f"{SUPABASE_URL}/rest/v1/spot_aggregators",
            params={
                "device_id": f"eq.{device_id}",
                "recorded_at": f"eq.{recorded_at}"
            },
            json={
                "aggregator_status": status
            },
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            timeout=10
        )

        if response.status_code in [200, 204]:
            print(f"✅ spot_aggregators.aggregator_status updated to '{status}' for {device_id}/{recorded_at}")
        else:
            print(f"❌ Failed to update spot_aggregators.aggregator_status: {response.status_code}")

    except Exception as e:
        print(f"Error updating spot_aggregators.aggregator_status: {str(e)}")


def update_profiler_status(device_id: str, recorded_at: str, status: str):
    """
    Update profiler_status in spot_results table
    """
    try:
        response = requests.patch(
            f"{SUPABASE_URL}/rest/v1/spot_results",
            params={
                "device_id": f"eq.{device_id}",
                "recorded_at": f"eq.{recorded_at}"
            },
            json={
                "profiler_status": status
            },
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            timeout=10
        )

        if response.status_code in [200, 204]:
            print(f"✅ spot_results.profiler_status updated to '{status}' for {device_id}/{recorded_at}")
        else:
            print(f"❌ Failed to update spot_results.profiler_status: {response.status_code}")

    except Exception as e:
        print(f"Error updating spot_results.profiler_status: {str(e)}")


def trigger_dashboard_summary(device_id: str, recorded_at: str, local_date: str):
    """
    Send message to dashboard summary queue with local_date
    """
    try:
        if not local_date:
            print(f"ERROR: local_date is None, cannot trigger dashboard summary")
            raise ValueError("local_date is required for dashboard summary")

        message_body = json.dumps({
            "device_id": device_id,
            "recorded_at": recorded_at,
            "local_date": local_date
        })

        response = sqs.send_message(
            QueueUrl=DASHBOARD_SUMMARY_QUEUE_URL,
            MessageBody=message_body
        )

        print(f"Dashboard summary triggered: MessageId={response['MessageId']}, local_date={local_date}")

    except Exception as e:
        print(f"Error triggering dashboard summary: {str(e)}")
        raise
