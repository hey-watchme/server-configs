#!/bin/bash

set -euo pipefail

REGION="${REGION:-ap-southeast-2}"

if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <source-dlq-name> <destination-queue-name>"
    exit 1
fi

SOURCE_DLQ_NAME="$1"
DESTINATION_QUEUE_NAME="$2"

get_queue_url() {
    local queue_name=$1
    aws sqs get-queue-url \
        --queue-name "${queue_name}" \
        --region "${REGION}" \
        --query 'QueueUrl' \
        --output text
}

get_queue_arn() {
    local queue_url=$1
    aws sqs get-queue-attributes \
        --queue-url "${queue_url}" \
        --attribute-names QueueArn \
        --region "${REGION}" \
        --query 'Attributes.QueueArn' \
        --output text
}

SOURCE_DLQ_URL=$(get_queue_url "${SOURCE_DLQ_NAME}")
DESTINATION_QUEUE_URL=$(get_queue_url "${DESTINATION_QUEUE_NAME}")
SOURCE_DLQ_ARN=$(get_queue_arn "${SOURCE_DLQ_URL}")
DESTINATION_QUEUE_ARN=$(get_queue_arn "${DESTINATION_QUEUE_URL}")

echo "Starting message move task..."
echo "  source: ${SOURCE_DLQ_NAME}"
echo "  destination: ${DESTINATION_QUEUE_NAME}"

TASK_HANDLE=$(aws sqs start-message-move-task \
    --source-arn "${SOURCE_DLQ_ARN}" \
    --destination-arn "${DESTINATION_QUEUE_ARN}" \
    --region "${REGION}" \
    --query 'TaskHandle' \
    --output text)

echo "Task handle: ${TASK_HANDLE}"
echo
echo "Current move task status:"
aws sqs list-message-move-tasks \
    --source-arn "${SOURCE_DLQ_ARN}" \
    --region "${REGION}" \
    --max-results 10
