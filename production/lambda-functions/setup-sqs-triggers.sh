#!/bin/bash

# Setup SQS triggers for Lambda functions
set -e

REGION="ap-southeast-2"
ACCOUNT_ID="754724220380"

echo "🔗 Setting up SQS triggers for Lambda functions..."

# 1. ASR Worker - triggered by ASR queue
echo "Setting up watchme-asr-worker trigger..."
aws lambda create-event-source-mapping \
  --function-name watchme-asr-worker \
  --event-source-arn arn:aws:sqs:${REGION}:${ACCOUNT_ID}:watchme-asr-queue-v2.fifo \
  --batch-size 1 \
  --maximum-batching-window-in-seconds 0 \
  --region ${REGION} 2>/dev/null || echo "Trigger already exists"

# 2. SED Worker - triggered by SED queue
echo "Setting up watchme-sed-worker trigger..."
aws lambda create-event-source-mapping \
  --function-name watchme-sed-worker \
  --event-source-arn arn:aws:sqs:${REGION}:${ACCOUNT_ID}:watchme-sed-queue-v2.fifo \
  --batch-size 1 \
  --maximum-batching-window-in-seconds 0 \
  --region ${REGION} 2>/dev/null || echo "Trigger already exists"

# 3. SER Worker - triggered by SER queue
echo "Setting up watchme-ser-worker trigger..."
aws lambda create-event-source-mapping \
  --function-name watchme-ser-worker \
  --event-source-arn arn:aws:sqs:${REGION}:${ACCOUNT_ID}:watchme-ser-queue-v2.fifo \
  --batch-size 1 \
  --maximum-batching-window-in-seconds 0 \
  --region ${REGION} 2>/dev/null || echo "Trigger already exists"

# 4. Aggregator Checker - triggered by feature-completed queue
echo "Setting up watchme-aggregator-checker trigger..."
aws lambda create-event-source-mapping \
  --function-name watchme-aggregator-checker \
  --event-source-arn arn:aws:sqs:${REGION}:${ACCOUNT_ID}:watchme-feature-completed-queue \
  --batch-size 1 \
  --maximum-batching-window-in-seconds 0 \
  --region ${REGION} 2>/dev/null || echo "Trigger already exists"

# 5. Spot Analysis Worker - triggered by spot analysis FIFO queue
echo "Setting up watchme-spot-analysis-worker trigger..."
aws lambda create-event-source-mapping \
  --function-name watchme-spot-analysis-worker \
  --event-source-arn arn:aws:sqs:${REGION}:${ACCOUNT_ID}:watchme-spot-analysis-queue.fifo \
  --batch-size 1 \
  --maximum-batching-window-in-seconds 0 \
  --region ${REGION} 2>/dev/null || echo "Trigger already exists"

echo ""
echo "✅ All SQS triggers configured!"
echo ""
echo "Listing all event source mappings..."
aws lambda list-event-source-mappings --region ${REGION} --query "EventSourceMappings[?contains(FunctionArn, 'watchme')].[FunctionArn, EventSourceArn, State]" --output table
