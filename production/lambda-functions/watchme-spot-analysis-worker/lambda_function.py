import json
import os

import boto3
import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.hey-watch.me")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
DASHBOARD_SUMMARY_QUEUE_URL = os.environ.get(
    "DASHBOARD_SUMMARY_QUEUE_URL",
    "https://sqs.ap-southeast-2.amazonaws.com/754724220380/watchme-dashboard-summary-queue",
)

FEATURE_STATUS_FIELDS = ("vibe_status", "behavior_status", "emotion_status")

sqs = boto3.client("sqs", region_name="ap-southeast-2")


def lambda_handler(event, context):
    print(f"Processing {len(event['Records'])} spot analysis messages")

    for record in event["Records"]:
        message = json.loads(record["body"])
        process_spot_analysis(message)

    return {"statusCode": 200, "body": json.dumps("Spot analysis completed")}


def process_spot_analysis(message):
    device_id = message["device_id"]
    recorded_at = message["recorded_at"]
    local_date = message.get("local_date")
    trigger_source = message.get("trigger_source", "spot-analysis-queue")
    recording_key = f"{device_id}/{recorded_at}"

    statuses = get_feature_statuses(device_id, recorded_at)
    if not statuses:
        raise RuntimeError(f"No feature status found for {recording_key}")

    if not all(statuses.get(field) == "completed" for field in FEATURE_STATUS_FIELDS):
        raise RuntimeError(
            f"Features are not complete for {recording_key}: "
            f"{json.dumps(statuses, ensure_ascii=False)}"
        )

    effective_local_date = local_date or statuses.get("local_date")
    pipeline_state = get_pipeline_state(device_id, recorded_at)

    if pipeline_state["profiler_completed"]:
        print(f"[{trigger_source}] Spot result already exists for {recording_key}")
        trigger_dashboard_summary_once(
            device_id,
            recorded_at,
            effective_local_date,
            trigger_source,
        )
        return

    ensure_aggregator_completed(
        device_id,
        recorded_at,
        effective_local_date,
        trigger_source,
        pipeline_state,
    )

    ensure_profiler_completed(
        device_id,
        recorded_at,
        effective_local_date,
        trigger_source,
    )

    trigger_dashboard_summary_once(
        device_id,
        recorded_at,
        effective_local_date,
        trigger_source,
    )


def ensure_aggregator_completed(
    device_id,
    recorded_at,
    local_date,
    trigger_source,
    pipeline_state=None,
):
    recording_key = f"{device_id}/{recorded_at}"
    state = pipeline_state or get_pipeline_state(device_id, recorded_at)

    if state["aggregator_completed"]:
        print(f"[{trigger_source}] Aggregator already completed for {recording_key}")
        return

    if not claim_aggregator_processing(device_id, recorded_at, local_date):
        print(f"[{trigger_source}] Aggregator claim skipped for {recording_key}")
        return

    try:
        agg_response = requests.post(
            f"{API_BASE_URL}/aggregator/spot",
            json={"device_id": device_id, "recorded_at": recorded_at},
            timeout=180,
        )

        if agg_response.status_code != 200:
            raise RuntimeError(
                f"Aggregator failed for {recording_key}: "
                f"{agg_response.status_code} {agg_response.text}"
            )
    except Exception:
        patch_rows(
            "spot_aggregators",
            {
                "device_id": f"eq.{device_id}",
                "recorded_at": f"eq.{recorded_at}",
            },
            {"aggregator_status": "failed"},
        )
        raise

    patch_rows(
        "spot_aggregators",
        {
            "device_id": f"eq.{device_id}",
            "recorded_at": f"eq.{recorded_at}",
        },
        {"aggregator_status": "completed"},
    )
    print(f"[{trigger_source}] Aggregator completed for {recording_key}")


def claim_aggregator_processing(device_id, recorded_at, local_date):
    aggregator_row = fetch_single_row(
        "spot_aggregators",
        device_id,
        recorded_at,
        "aggregator_status,prompt",
    )

    if aggregator_row:
        updated_rows = patch_rows(
            "spot_aggregators",
            {
                "device_id": f"eq.{device_id}",
                "recorded_at": f"eq.{recorded_at}",
                "or": (
                    "(aggregator_status.is.null,"
                    "aggregator_status.eq.pending,"
                    "aggregator_status.eq.failed,"
                    "aggregator_status.eq.queued,"
                    "aggregator_status.eq.processing)"
                ),
            },
            {"aggregator_status": "processing"},
        )
        return bool(updated_rows) or not is_aggregator_completed(
            fetch_single_row(
                "spot_aggregators",
                device_id,
                recorded_at,
                "aggregator_status,prompt",
            )
        )

    payload = {
        "device_id": device_id,
        "recorded_at": recorded_at,
        "prompt": "",
        "context_data": {"pipeline_state": "processing"},
        "aggregator_status": "processing",
    }

    if local_date:
        payload["local_date"] = local_date

    upsert_row("spot_aggregators", payload, "device_id,recorded_at")
    return True


def ensure_profiler_completed(device_id, recorded_at, local_date, trigger_source):
    recording_key = f"{device_id}/{recorded_at}"
    state = get_pipeline_state(device_id, recorded_at)

    if state["profiler_completed"]:
        print(f"[{trigger_source}] Profiler already completed for {recording_key}")
        return

    if not claim_profiler_processing(device_id, recorded_at, local_date):
        print(f"[{trigger_source}] Profiler claim skipped for {recording_key}")
        return

    try:
        prof_response = requests.post(
            f"{API_BASE_URL}/profiler/spot-profiler",
            json={"device_id": device_id, "recorded_at": recorded_at},
            timeout=180,
        )

        if prof_response.status_code != 200:
            raise RuntimeError(
                f"Profiler failed for {recording_key}: "
                f"{prof_response.status_code} {prof_response.text}"
            )
    except Exception:
        patch_rows(
            "spot_results",
            {
                "device_id": f"eq.{device_id}",
                "recorded_at": f"eq.{recorded_at}",
            },
            {"profiler_status": "failed"},
        )
        raise

    patch_rows(
        "spot_results",
        {
            "device_id": f"eq.{device_id}",
            "recorded_at": f"eq.{recorded_at}",
        },
        {"profiler_status": "completed"},
    )
    print(f"[{trigger_source}] Profiler completed for {recording_key}")


def claim_profiler_processing(device_id, recorded_at, local_date):
    profiler_row = fetch_single_row(
        "spot_results",
        device_id,
        recorded_at,
        "profiler_status,profile_result,summary,vibe_score",
    )

    if profiler_row:
        updated_rows = patch_rows(
            "spot_results",
            {
                "device_id": f"eq.{device_id}",
                "recorded_at": f"eq.{recorded_at}",
                "or": (
                    "(profiler_status.is.null,"
                    "profiler_status.eq.pending,"
                    "profiler_status.eq.failed,"
                    "profiler_status.eq.queued,"
                    "profiler_status.eq.processing)"
                ),
            },
            {"profiler_status": "processing"},
        )
        return bool(updated_rows) or not is_profiler_completed(
            fetch_single_row(
                "spot_results",
                device_id,
                recorded_at,
                "profiler_status,profile_result,summary,vibe_score",
            )
        )

    payload = {
        "device_id": device_id,
        "recorded_at": recorded_at,
        "profile_result": {"pipeline_state": "processing"},
        "profiler_status": "processing",
    }

    if local_date:
        payload["local_date"] = local_date

    upsert_row("spot_results", payload, "device_id,recorded_at")
    return True


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
        raise RuntimeError(
            f"Failed to fetch feature statuses for {device_id}/{recorded_at}: "
            f"{response.status_code} {response.text}"
        )

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

    return {
        "aggregator_row": aggregator_row,
        "profiler_row": profiler_row,
        "aggregator_completed": is_aggregator_completed(aggregator_row),
        "profiler_completed": is_profiler_completed(profiler_row),
        "daily_aggregator_status": (profiler_row or {}).get("daily_aggregator_status"),
    }


def is_aggregator_completed(aggregator_row):
    if not aggregator_row:
        return False

    return (
        aggregator_row.get("aggregator_status") == "completed"
        and bool(aggregator_row.get("prompt"))
    )


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
        raise RuntimeError(
            f"Failed to fetch {table_name} for {device_id}/{recorded_at}: "
            f"{response.status_code} {response.text}"
        )

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


def trigger_dashboard_summary_once(device_id, recorded_at, local_date, trigger_source):
    if not local_date:
        raise RuntimeError(
            f"local_date is required for dashboard summary: {device_id}/{recorded_at}"
        )

    current_row = fetch_single_row(
        "spot_results",
        device_id,
        recorded_at,
        "daily_aggregator_status",
    )
    current_status = (current_row or {}).get("daily_aggregator_status")

    if current_status == "queued":
        print(
            f"[{trigger_source}] Daily trigger already claimed for "
            f"{device_id}/{recorded_at}: {current_status}"
        )
        return

    updated_rows = patch_rows(
        "spot_results",
        {
            "device_id": f"eq.{device_id}",
            "recorded_at": f"eq.{recorded_at}",
            "or": (
                "(daily_aggregator_status.is.null,"
                "daily_aggregator_status.eq.pending,"
                "daily_aggregator_status.eq.failed)"
            ),
        },
        {"daily_aggregator_status": "queued"},
    )

    if not updated_rows:
        refreshed_row = fetch_single_row(
            "spot_results",
            device_id,
            recorded_at,
            "daily_aggregator_status",
        )
        refreshed_status = (refreshed_row or {}).get("daily_aggregator_status")

        if current_status in {None, "pending", "failed"} and refreshed_status == "queued":
            print(
                f"[{trigger_source}] Daily trigger claimed via status transition for "
                f"{device_id}/{recorded_at}"
            )
        else:
            print(
                f"[{trigger_source}] Daily trigger already claimed for "
                f"{device_id}/{recorded_at}: {refreshed_status}"
            )
            return

    try:
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
    except Exception:
        patch_rows(
            "spot_results",
            {
                "device_id": f"eq.{device_id}",
                "recorded_at": f"eq.{recorded_at}",
                "daily_aggregator_status": "eq.queued",
            },
            {"daily_aggregator_status": "failed"},
        )
        raise

    print(
        f"[{trigger_source}] Dashboard summary triggered for {device_id}/{recorded_at}: "
        f"MessageId={response['MessageId']}"
    )


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
