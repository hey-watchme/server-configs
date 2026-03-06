#!/bin/bash

# Create the FIFO queue used after all three feature extractors complete.

set -e

REGION="ap-southeast-2"
ACCOUNT_ID="754724220380"
QUEUE_NAME="watchme-spot-analysis-queue.fifo"
DLQ_NAME="watchme-spot-analysis-dlq.fifo"
DLQ_ARN="arn:aws:sqs:${REGION}:${ACCOUNT_ID}:${DLQ_NAME}"

echo "Creating ${DLQ_NAME}..."
aws sqs create-queue \
  --queue-name "${DLQ_NAME}" \
  --region "${REGION}" \
  --attributes '{
    "FifoQueue": "true",
    "ContentBasedDeduplication": "false",
    "MessageRetentionPeriod": "1209600"
  }' >/dev/null || echo "DLQ already exists"

echo "Creating ${QUEUE_NAME}..."
aws sqs create-queue \
  --queue-name "${QUEUE_NAME}" \
  --region "${REGION}" \
  --attributes "{
    \"FifoQueue\": \"true\",
    \"ContentBasedDeduplication\": \"false\",
    \"MessageRetentionPeriod\": \"1209600\",
    \"VisibilityTimeout\": \"330\",
    \"ReceiveMessageWaitTimeSeconds\": \"20\",
    \"RedrivePolicy\": \"{\\\"deadLetterTargetArn\\\":\\\"${DLQ_ARN}\\\",\\\"maxReceiveCount\\\":3}\"
  }" >/dev/null || echo "Queue already exists"

echo "Queue URLs:"
aws sqs get-queue-url --queue-name "${QUEUE_NAME}" --region "${REGION}" --query 'QueueUrl' --output text
aws sqs get-queue-url --queue-name "${DLQ_NAME}" --region "${REGION}" --query 'QueueUrl' --output text
