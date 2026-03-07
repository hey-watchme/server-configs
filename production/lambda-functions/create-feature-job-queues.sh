#!/bin/bash

# Create FIFO queues for API-side feature job workers.
# These queues are consumed by EC2 API containers (ASR/SED/SER queue workers).

set -e

REGION="ap-southeast-2"
ACCOUNT_ID="754724220380"

create_fifo_with_dlq() {
  local name="$1"
  local dlq_name="$2"

  local dlq_arn="arn:aws:sqs:${REGION}:${ACCOUNT_ID}:${dlq_name}"

  echo "Creating ${dlq_name}..."
  aws sqs create-queue \
    --queue-name "${dlq_name}" \
    --region "${REGION}" \
    --attributes '{
      "FifoQueue": "true",
      "ContentBasedDeduplication": "false",
      "MessageRetentionPeriod": "1209600"
    }' >/dev/null || echo "DLQ already exists"

  echo "Creating ${name}..."
  aws sqs create-queue \
    --queue-name "${name}" \
    --region "${REGION}" \
    --attributes "{
      \"FifoQueue\": \"true\",
      \"ContentBasedDeduplication\": \"false\",
      \"MessageRetentionPeriod\": \"1209600\",
      \"VisibilityTimeout\": \"600\",
      \"ReceiveMessageWaitTimeSeconds\": \"20\",
      \"RedrivePolicy\": \"{\\\"deadLetterTargetArn\\\":\\\"${dlq_arn}\\\",\\\"maxReceiveCount\\\":3}\"
    }" >/dev/null || echo "Queue already exists"

  echo "Queue URL:"
  aws sqs get-queue-url --queue-name "${name}" --region "${REGION}" --query 'QueueUrl' --output text
  aws sqs get-queue-url --queue-name "${dlq_name}" --region "${REGION}" --query 'QueueUrl' --output text
  echo ""
}

echo "🚀 Creating feature job queues (ASR/SED/SER)..."

create_fifo_with_dlq "watchme-asr-job-queue-v1.fifo" "watchme-asr-job-dlq-v1.fifo"
create_fifo_with_dlq "watchme-sed-job-queue-v1.fifo" "watchme-sed-job-dlq-v1.fifo"
create_fifo_with_dlq "watchme-ser-job-queue-v1.fifo" "watchme-ser-job-dlq-v1.fifo"

echo "✅ Feature job queue creation completed"
