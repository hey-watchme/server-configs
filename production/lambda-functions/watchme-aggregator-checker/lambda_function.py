import json
import os
from datetime import datetime, timedelta, timezone

import boto3
import requests

# Environment variables
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.hey-watch.me")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
DASHBOARD_SUMMARY_QUEUE_URL = os.environ.get(
    "DASHBOARD_SUMMARY_QUEUE_URL",
    "https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-dashboard-summary-queue",
)
RECONCILIATION_LOOKBACK_MINUTES = int(
    os.environ.get("RECONCILIATION_LOOKBACK_MINUTES", "1440")
)
RECONCILIATION_BATCH_SIZE = int(os.environ.get("RECONCILIATION_BATCH_SIZE", "200"))

FEATURE_STATUS_FIELDS = ("vibe_status", "behavior_status", "emotion_status")

# SQS client
sqs = boto3.client("sqs", region_name="ap-southeast-2")


def lambda_handler(event, context):
    """
    Trigger spot aggregation when all three feature extractors are complete.

    Supported invocations:
    - SQS notifications from watchme-feature-completed-queue
    - EventBridge scheduled reconciliation
    - Manual invoke with {"device_id": "...", "recorded_at": "..."}
    """
    if is_sqs_event(event):
        return handle_sqs_notifications(event)

    if is_scheduled_event(event):
        return reconcile_recent_recordings("eventbridge")

    if isinstance(event, dict) and event.get("action") == "reconcile_recent":
        return reconcile_recent_recordings(event.get("source", "manual-reconcile"))

    if isinstance(event, dict) and event.get("device_id") and event.get("recorded_at"):
        result = attempt_pipeline(
            event["device_id"],
            event["recorded_at"],
            event.get("source", "manual"),
        )
        return {"statusCode": 200, "body": json.dumps(result)}

    print(f"Unsupported event payload: {json.dumps(event)}")
    return {"statusCode": 400, "body": json.dumps({"error": "Unsupported event"})}


def is_sqs_event(event):
    return (
        isinstance(event, dict)
        and isinstance(event.get("Records"), list)
        and event["Records"]
        and event["Records"][0].get("eventSource") == "aws:sqs"
    )


def is_scheduled_event(event):
    return (
        isinstance(event, dict)
        and event.get("source") == "aws.events"
        and event.get("detail-type") == "Scheduled Event"
    )


def handle_sqs_notifications(event):
    print(f"Processing {len(event['Records'])} feature completion notifications")

    results = []

    for record in event["Records"]:
        try:
            message = json.loads(record["body"])

            device_id = message["device_id"]
            recorded_at = message["recorded_at"]
            feature_type = message.get("feature_type", "unknown")
            status = message.get("status")

            print(
                f"Feature completion: {feature_type} for {device_id} at {recorded_at} - "
                f"Status: {status}"
            )

            if status and status != "completed":
                print(f"Feature {feature_type} failed, skipping aggregation check")
                results.append(
                    {
                        "device_id": device_id,
                        "recorded_at": recorded_at,
                        "status": "feature_failed",
                        "feature_type": feature_type,
                    }
                )
                continue

            results.append(
                attempt_pipeline(
                    device_id,
                    recorded_at,
                    f"sqs:{feature_type}",
                )
            )

        except Exception as exc:
            print(f"Error processing completion notification: {str(exc)}")
            results.append({"status": "notification_error", "error": str(exc)})

    return {"statusCode": 200, "body": json.dumps({"results": results})}


def reconcile_recent_recordings(trigger_source):
    candidates = get_recent_completed_candidates()
    print(
        f"Reconciliation trigger={trigger_source} found {len(candidates)} "
        "completed candidates"
    )

    results = []
    for candidate in candidates:
        results.append(
            attempt_pipeline(
                candidate["device_id"],
                candidate["recorded_at"],
                trigger_source,
            )
        )

    return {"statusCode": 200, "body": json.dumps({"results": results})}


def attempt_pipeline(device_id, recorded_at, trigger_source):
    recording_key = f"{device_id}/{recorded_at}"
    statuses = get_feature_statuses(device_id, recorded_at)

    if not statuses:
        print(f"[{trigger_source}] No feature status found for {recording_key}")
        return {
            "device_id": device_id,
            "recorded_at": recorded_at,
            "status": "missing_feature_status",
        }

    print(
        f"[{trigger_source}] Feature statuses for {recording_key}: "
        f"vibe={statuses.get('vibe_status')}, "
        f"behavior={statuses.get('behavior_status')}, "
        f"emotion={statuses.get('emotion_status')}"
    )

    if not all(statuses.get(field) == "completed" for field in FEATURE_STATUS_FIELDS):
        print(f"[{trigger_source}] Not all features complete yet for {recording_key}")
        return {
            "device_id": device_id,
            "recorded_at": recorded_at,
            "status": "waiting_for_features",
            "feature_statuses": statuses,
        }

    pipeline_state = get_pipeline_state(device_id, recorded_at)
    if pipeline_state["profiler_completed"]:
        print(f"[{trigger_source}] Spot analysis already completed for {recording_key}")
        return {
            "device_id": device_id,
            "recorded_at": recorded_at,
            "status": "already_completed",
        }

    if pipeline_state["profiler_in_progress"]:
        print(f"[{trigger_source}] Profiler already in progress for {recording_key}")
        return {
            "device_id": device_id,
            "recorded_at": recorded_at,
            "status": "profiler_in_progress",
        }

    aggregator_ready = pipeline_state["aggregator_exists"]
    if not aggregator_ready:
        agg_response = requests.post(
            f"{API_BASE_URL}/aggregator/spot",
            json={"device_id": device_id, "recorded_at": recorded_at},
            timeout=180,
        )

        if agg_response.status_code != 200:
            print(
                f"[{trigger_source}] Aggregator failed for {recording_key}: "
                f"{agg_response.status_code} {agg_response.text}"
            )
            update_aggregator_status(device_id, recorded_at, "failed")
            return {
                "device_id": device_id,
                "recorded_at": recorded_at,
                "status": "aggregator_failed",
                "http_status": agg_response.status_code,
            }

        print(f"[{trigger_source}] Aggregator completed successfully for {recording_key}")
        update_aggregator_status(device_id, recorded_at, "completed")
    else:
        print(
            f"[{trigger_source}] Reusing existing spot_aggregators row for {recording_key}"
        )

    prof_response = requests.post(
        f"{API_BASE_URL}/profiler/spot-profiler",
        json={"device_id": device_id, "recorded_at": recorded_at},
        timeout=180,
    )

    if prof_response.status_code != 200:
        print(
            f"[{trigger_source}] Profiler failed for {recording_key}: "
            f"{prof_response.status_code} {prof_response.text}"
        )
        update_profiler_status(device_id, recorded_at, "failed")
        return {
            "device_id": device_id,
            "recorded_at": recorded_at,
            "status": "profiler_failed",
            "http_status": prof_response.status_code,
        }

    print(f"[{trigger_source}] Profiler completed successfully for {recording_key}")
    update_profiler_status(device_id, recorded_at, "completed")

    local_date = statuses.get("local_date")
    if local_date:
        try:
            trigger_dashboard_summary(device_id, recorded_at, local_date)
        except Exception as exc:
            print(
                f"[{trigger_source}] Dashboard summary trigger failed for "
                f"{recording_key}: {str(exc)}"
            )
    else:
        print(
            f"[{trigger_source}] local_date is missing for {recording_key}; "
            "skipping dashboard summary trigger"
        )

    return {
        "device_id": device_id,
        "recorded_at": recorded_at,
        "status": "completed",
        "trigger_source": trigger_source,
    }


def get_feature_statuses(device_id, recorded_at):
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/spot_features",
        params={
            "device_id": f"eq.{device_id}",
            "recorded_at": f"eq.{recorded_at}",
            "select": "vibe_status,behavior_status,emotion_status,local_date",
        },
        headers=supabase_headers(),
        timeout=10,
    )

    if response.status_code != 200:
        print(
            f"Error fetching feature statuses for {device_id}/{recorded_at}: "
            f"{response.status_code} {response.text}"
        )
        return {}

    data = response.json()
    return data[0] if data else {}


def get_pipeline_state(device_id, recorded_at):
    aggregator_row = fetch_single_row(
        "spot_aggregators",
        device_id,
        recorded_at,
        "aggregator_status,created_at",
    )
    profiler_row = fetch_single_row(
        "spot_results",
        device_id,
        recorded_at,
        "profiler_status,created_at,summary,vibe_score",
    )

    profiler_completed = bool(
        profiler_row
        and (
            profiler_row.get("profiler_status") == "completed"
            or profiler_row.get("summary")
            or profiler_row.get("vibe_score") is not None
        )
    )
    profiler_in_progress = bool(
        profiler_row and profiler_row.get("profiler_status") in {"queued", "processing"}
    )

    return {
        "aggregator_exists": bool(aggregator_row),
        "aggregator_status": (aggregator_row or {}).get("aggregator_status"),
        "profiler_exists": bool(profiler_row),
        "profiler_status": (profiler_row or {}).get("profiler_status"),
        "profiler_completed": profiler_completed,
        "profiler_in_progress": profiler_in_progress,
    }


def fetch_single_row(table_name, device_id, recorded_at, select_clause):
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table_name}",
        params={
            "device_id": f"eq.{device_id}",
            "recorded_at": f"eq.{recorded_at}",
            "select": select_clause,
        },
        headers=supabase_headers(),
        timeout=10,
    )

    if response.status_code != 200:
        print(
            f"Error fetching {table_name} for {device_id}/{recorded_at}: "
            f"{response.status_code} {response.text}"
        )
        return None

    data = response.json()
    return data[0] if data else None


def get_recent_completed_candidates():
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=RECONCILIATION_LOOKBACK_MINUTES
    )
    cutoff_iso = cutoff.isoformat()

    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/spot_features",
        params={
            "created_at": f"gte.{cutoff_iso}",
            "vibe_status": "eq.completed",
            "behavior_status": "eq.completed",
            "emotion_status": "eq.completed",
            "select": "device_id,recorded_at,local_date,created_at",
            "order": "recorded_at.asc",
            "limit": str(RECONCILIATION_BATCH_SIZE),
        },
        headers=supabase_headers(),
        timeout=20,
    )

    if response.status_code != 200:
        print(
            f"Error fetching reconciliation candidates: "
            f"{response.status_code} {response.text}"
        )
        return []

    return response.json()


def update_aggregator_status(device_id, recorded_at, status):
    patch_single_status("spot_aggregators", "aggregator_status", device_id, recorded_at, status)


def update_profiler_status(device_id, recorded_at, status):
    patch_single_status("spot_results", "profiler_status", device_id, recorded_at, status)


def patch_single_status(table_name, status_field, device_id, recorded_at, status):
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table_name}",
        params={"device_id": f"eq.{device_id}", "recorded_at": f"eq.{recorded_at}"},
        json={status_field: status},
        headers={
            **supabase_headers(),
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        timeout=10,
    )

    if response.status_code not in {200, 204}:
        print(
            f"Failed to update {table_name}.{status_field} for {device_id}/{recorded_at}: "
            f"{response.status_code} {response.text}"
        )
        return

    try:
        updated_rows = response.json()
    except ValueError:
        updated_rows = []

    if updated_rows:
        print(
            f"Updated {table_name}.{status_field} to '{status}' for "
            f"{device_id}/{recorded_at}"
        )
    else:
        print(
            f"No rows updated for {table_name}.{status_field} on "
            f"{device_id}/{recorded_at}"
        )


def trigger_dashboard_summary(device_id, recorded_at, local_date):
    response = sqs.send_message(
        QueueUrl=DASHBOARD_SUMMARY_QUEUE_URL,
        MessageBody=json.dumps(
            {
                "device_id": device_id,
                "recorded_at": recorded_at,
                "local_date": local_date,
            }
        ),
    )
    print(
        f"Dashboard summary triggered for {device_id}/{recorded_at}: "
        f"MessageId={response['MessageId']}"
    )


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
