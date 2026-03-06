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
PROFILER_IN_PROGRESS_STATUSES = {"queued", "processing"}

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

    local_date = statuses.get("local_date")
    claim_result = claim_profiler_queue_slot(
        device_id,
        recorded_at,
        local_date,
        pipeline_state,
    )

    if claim_result["status"] != "claimed":
        print(f"[{trigger_source}] Queue claim skipped for {recording_key}: {claim_result}")
        return {
            "device_id": device_id,
            "recorded_at": recorded_at,
            **claim_result,
        }

    try:
        response = sqs.send_message(
            QueueUrl=SPOT_ANALYSIS_QUEUE_URL,
            MessageBody=json.dumps(
                {
                    "device_id": device_id,
                    "recorded_at": recorded_at,
                    "local_date": local_date,
                    "trigger_source": trigger_source,
                }
            ),
            MessageGroupId=f"{device_id}-spot-analysis",
            MessageDeduplicationId=get_deduplication_id(device_id, recorded_at),
        )
    except Exception:
        revert_profiler_queue_claim(device_id, recorded_at)
        raise

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


def claim_profiler_queue_slot(device_id, recorded_at, local_date, pipeline_state):
    profiler_row = pipeline_state["profiler_row"]
    profiler_status = pipeline_state["profiler_status"]

    if pipeline_state["profiler_completed"]:
        return {"status": "already_completed"}

    if profiler_status in PROFILER_IN_PROGRESS_STATUSES:
        return {"status": "already_in_progress", "profiler_status": profiler_status}

    if profiler_row:
        updated_rows = patch_rows(
            "spot_results",
            {
                "device_id": f"eq.{device_id}",
                "recorded_at": f"eq.{recorded_at}",
                "or": (
                    "(profiler_status.is.null,"
                    "profiler_status.eq.pending,"
                    "profiler_status.eq.failed)"
                ),
            },
            {"profiler_status": "queued"},
        )

        if updated_rows:
            return {"status": "claimed", "profiler_status": "queued"}

        refreshed_state = get_pipeline_state(device_id, recorded_at)
        if refreshed_state["profiler_completed"]:
            return {"status": "already_completed"}

        refreshed_status = refreshed_state["profiler_status"]
        if refreshed_status in PROFILER_IN_PROGRESS_STATUSES:
            return {
                "status": "already_in_progress",
                "profiler_status": refreshed_status,
            }

        return {
            "status": "claim_failed",
            "profiler_status": refreshed_status,
        }

    create_profiler_placeholder(device_id, recorded_at, local_date, "queued")
    return {"status": "claimed", "profiler_status": "queued"}


def revert_profiler_queue_claim(device_id, recorded_at):
    patch_rows(
        "spot_results",
        {
            "device_id": f"eq.{device_id}",
            "recorded_at": f"eq.{recorded_at}",
            "profiler_status": "eq.queued",
        },
        {"profiler_status": "failed"},
    )


def create_profiler_placeholder(device_id, recorded_at, local_date, profiler_status):
    payload = {
        "device_id": device_id,
        "recorded_at": recorded_at,
        "profile_result": {"pipeline_state": profiler_status},
        "profiler_status": profiler_status,
    }

    if local_date:
        payload["local_date"] = local_date

    upsert_row("spot_results", payload, "device_id,recorded_at")


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
    aggregator_row = fetch_single_row(
        "spot_aggregators",
        device_id,
        recorded_at,
        "aggregator_status,prompt,created_at",
    )
    profiler_row = fetch_single_row(
        "spot_results",
        device_id,
        recorded_at,
        "profiler_status,created_at,summary,vibe_score,profile_result,daily_aggregator_status",
    )

    profiler_status = (profiler_row or {}).get("profiler_status")
    profiler_completed = is_profiler_completed(profiler_row)

    return {
        "aggregator_row": aggregator_row,
        "profiler_row": profiler_row,
        "aggregator_status": (aggregator_row or {}).get("aggregator_status"),
        "profiler_status": profiler_status,
        "profiler_completed": profiler_completed,
    }


def is_profiler_completed(profiler_row):
    if not profiler_row:
        return False

    if profiler_row.get("profiler_status") == "completed":
        return True

    if profiler_row.get("summary") or profiler_row.get("vibe_score") is not None:
        return True

    profile_result = profiler_row.get("profile_result")
    return bool(
        profile_result
        and profile_result
        not in ({"pipeline_state": "queued"}, {"pipeline_state": "processing"})
    )


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


def upsert_row(table_name, payload, on_conflict):
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table_name}",
        params={"on_conflict": on_conflict},
        json=payload,
        headers={
            **supabase_headers(),
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        },
        timeout=10,
    )

    if response.status_code not in {200, 201}:
        raise RuntimeError(
            f"Failed to upsert into {table_name}: "
            f"{response.status_code} {response.text}"
        )

    return response.json()


def patch_rows(table_name, filters, payload):
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table_name}",
        params={**filters, "select": "*"},
        json=payload,
        headers={
            **supabase_headers(),
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        timeout=10,
    )

    if response.status_code not in {200, 204}:
        raise RuntimeError(
            f"Failed to update {table_name}: {response.status_code} {response.text}"
        )

    try:
        return response.json()
    except ValueError:
        return []


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
