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

    pipeline_state = get_pipeline_state(device_id, recorded_at)
    if pipeline_state["profiler_completed"]:
        print(f"[{trigger_source}] Spot result already exists for {recording_key}")
        trigger_dashboard_summary(device_id, recorded_at, local_date or statuses.get("local_date"))
        return

    if not pipeline_state["aggregator_exists"]:
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

        update_aggregator_status(device_id, recorded_at, "completed")
        print(f"[{trigger_source}] Aggregator completed for {recording_key}")
    else:
        print(f"[{trigger_source}] Reusing existing aggregator row for {recording_key}")

    prof_response = requests.post(
        f"{API_BASE_URL}/profiler/spot-profiler",
        json={"device_id": device_id, "recorded_at": recorded_at},
        timeout=180,
    )

    if prof_response.status_code != 200:
        update_profiler_status(device_id, recorded_at, "failed")
        raise RuntimeError(
            f"Profiler failed for {recording_key}: "
            f"{prof_response.status_code} {prof_response.text}"
        )

    update_profiler_status(device_id, recorded_at, "completed")
    print(f"[{trigger_source}] Profiler completed for {recording_key}")
    trigger_dashboard_summary(device_id, recorded_at, local_date or statuses.get("local_date"))


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

    return {
        "aggregator_exists": bool(aggregator_row),
        "profiler_completed": profiler_completed,
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
        raise RuntimeError(
            f"Failed to fetch {table_name} for {device_id}/{recorded_at}: "
            f"{response.status_code} {response.text}"
        )

    data = response.json()
    return data[0] if data else None


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
        raise RuntimeError(
            f"Failed to update {table_name}.{status_field} for {device_id}/{recorded_at}: "
            f"{response.status_code} {response.text}"
        )

    try:
        updated_rows = response.json()
    except ValueError:
        updated_rows = []

    if not updated_rows:
        print(
            f"No rows updated for {table_name}.{status_field} on "
            f"{device_id}/{recorded_at}"
        )


def trigger_dashboard_summary(device_id, recorded_at, local_date):
    if not local_date:
        raise RuntimeError(f"local_date is required for dashboard summary: {device_id}/{recorded_at}")

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
