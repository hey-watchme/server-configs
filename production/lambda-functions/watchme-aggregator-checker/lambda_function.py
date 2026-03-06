import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

import boto3
import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.hey-watch.me")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SPOT_ANALYSIS_QUEUE_URL = os.environ.get(
    "SPOT_ANALYSIS_QUEUE_URL",
    "https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-spot-analysis-queue.fifo",
)
RECONCILIATION_LOOKBACK_MINUTES = int(
    os.environ.get("RECONCILIATION_LOOKBACK_MINUTES", "1440")
)
RECONCILIATION_BATCH_SIZE = int(os.environ.get("RECONCILIATION_BATCH_SIZE", "200"))

FEATURE_STATUS_FIELDS = ("vibe_status", "behavior_status", "emotion_status")

sqs = boto3.client("sqs", region_name="ap-southeast-2")


def lambda_handler(event, context):
    if is_sqs_event(event):
        return handle_sqs_notifications(event)

    if is_scheduled_event(event):
        return reconcile_recent_recordings("eventbridge")

    if isinstance(event, dict) and event.get("action") == "reconcile_recent":
        return reconcile_recent_recordings(event.get("source", "manual-reconcile"))

    if isinstance(event, dict) and event.get("device_id") and event.get("recorded_at"):
        result = attempt_enqueue(
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
            print(f"Feature {feature_type} failed, skipping enqueue")
            results.append(
                {
                    "device_id": device_id,
                    "recorded_at": recorded_at,
                    "status": "feature_failed",
                    "feature_type": feature_type,
                }
            )
            continue

        results.append(attempt_enqueue(device_id, recorded_at, f"sqs:{feature_type}"))

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
            attempt_enqueue(
                candidate["device_id"],
                candidate["recorded_at"],
                trigger_source,
            )
        )

    return {"statusCode": 200, "body": json.dumps({"results": results})}


def attempt_enqueue(device_id, recorded_at, trigger_source):
    recording_key = f"{device_id}/{recorded_at}"
    statuses = get_feature_statuses(device_id, recorded_at)

    if not statuses:
        print(f"[{trigger_source}] No feature status found for {recording_key}")
        return {
            "device_id": device_id,
            "recorded_at": recorded_at,
            "status": "missing_feature_status",
        }

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

    response = sqs.send_message(
        QueueUrl=SPOT_ANALYSIS_QUEUE_URL,
        MessageBody=json.dumps(
            {
                "device_id": device_id,
                "recorded_at": recorded_at,
                "local_date": statuses.get("local_date"),
                "trigger_source": trigger_source,
            }
        ),
        MessageGroupId=f"{device_id}-spot-analysis",
        MessageDeduplicationId=get_deduplication_id(device_id, recorded_at),
    )

    print(
        f"[{trigger_source}] Enqueued spot analysis for {recording_key}: "
        f"MessageId={response['MessageId']}"
    )

    return {
        "device_id": device_id,
        "recorded_at": recorded_at,
        "status": "queued",
        "trigger_source": trigger_source,
        "message_id": response["MessageId"],
    }


def get_deduplication_id(device_id, recorded_at):
    return hashlib.sha256(f"{device_id}-{recorded_at}-spot-analysis".encode()).hexdigest()[:80]


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

    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/spot_features",
        params={
            "created_at": f"gte.{cutoff.isoformat()}",
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


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
