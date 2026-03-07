#!/bin/bash

set -euo pipefail

REGION="${REGION:-ap-southeast-2}"
TOPIC_NAME="${TOPIC_NAME:-watchme-alerts}"
ALERT_EMAIL="${ALERT_EMAIL:-}"
TOPIC_ARN="${TOPIC_ARN:-}"

DLQ_QUEUES=(
    "watchme-asr-dlq-v2.fifo"
    "watchme-sed-dlq-v2.fifo"
    "watchme-ser-dlq-v2.fifo"
    "watchme-spot-analysis-dlq.fifo"
    "watchme-dashboard-summary-dlq"
    "watchme-dashboard-analysis-dlq"
)

SOURCE_QUEUES=(
    "watchme-asr-queue-v2.fifo"
    "watchme-sed-queue-v2.fifo"
    "watchme-ser-queue-v2.fifo"
    "watchme-spot-analysis-queue.fifo"
    "watchme-dashboard-summary-queue"
    "watchme-dashboard-analysis-queue"
)

LAMBDA_FUNCTIONS=(
    "watchme-audio-processor"
    "watchme-asr-worker"
    "watchme-sed-worker"
    "watchme-ser-worker"
    "watchme-aggregator-checker"
    "watchme-spot-analysis-worker"
    "watchme-dashboard-summary-worker"
    "watchme-dashboard-analysis-worker"
)

echo "Creating or updating watchme alarms in ${REGION}..."

if [ -z "${TOPIC_ARN}" ]; then
    if TOPIC_ARN=$(aws sns create-topic \
        --name "${TOPIC_NAME}" \
        --region "${REGION}" \
        --query 'TopicArn' \
        --output text 2>/dev/null); then
        if [ -n "${ALERT_EMAIL}" ]; then
            echo "Subscribing ${ALERT_EMAIL} to ${TOPIC_ARN}..."
            aws sns subscribe \
                --topic-arn "${TOPIC_ARN}" \
                --protocol email \
                --notification-endpoint "${ALERT_EMAIL}" \
                --region "${REGION}" >/dev/null
        fi
    else
        TOPIC_ARN=""
        echo "SNS topic could not be created with current IAM permissions. Creating alarms without actions."
    fi
fi

put_alarm() {
    if [ -n "${TOPIC_ARN}" ]; then
        aws cloudwatch put-metric-alarm "$@" --alarm-actions "${TOPIC_ARN}" --region "${REGION}"
    else
        aws cloudwatch put-metric-alarm "$@" --region "${REGION}"
    fi
}

for queue in "${DLQ_QUEUES[@]}"; do
    echo "Configuring DLQ alarm for ${queue}..."
    put_alarm \
        --alarm-name "${queue}-visible" \
        --alarm-description "DLQ ${queue} has visible messages" \
        --metric-name ApproximateNumberOfMessagesVisible \
        --namespace AWS/SQS \
        --statistic Maximum \
        --period 300 \
        --evaluation-periods 1 \
        --threshold 0 \
        --comparison-operator GreaterThanThreshold \
        --dimensions "Name=QueueName,Value=${queue}"
done

for queue in "${SOURCE_QUEUES[@]}"; do
    echo "Configuring queue age alarm for ${queue}..."
    put_alarm \
        --alarm-name "${queue}-oldest-message-age" \
        --alarm-description "Queue ${queue} has messages older than 5 minutes" \
        --metric-name ApproximateAgeOfOldestMessage \
        --namespace AWS/SQS \
        --statistic Maximum \
        --period 300 \
        --evaluation-periods 1 \
        --threshold 300 \
        --comparison-operator GreaterThanThreshold \
        --dimensions "Name=QueueName,Value=${queue}"
done

for function_name in "${LAMBDA_FUNCTIONS[@]}"; do
    echo "Configuring Lambda error alarm for ${function_name}..."
    put_alarm \
        --alarm-name "${function_name}-errors" \
        --alarm-description "Lambda ${function_name} returned errors" \
        --metric-name Errors \
        --namespace AWS/Lambda \
        --statistic Sum \
        --period 300 \
        --evaluation-periods 1 \
        --threshold 0 \
        --comparison-operator GreaterThanThreshold \
        --dimensions "Name=FunctionName,Value=${function_name}"
done

echo
echo "Alarm configuration complete."
if [ -n "${TOPIC_ARN}" ]; then
    echo "SNS topic: ${TOPIC_ARN}"
fi
if [ -n "${ALERT_EMAIL}" ] && [ -n "${TOPIC_ARN}" ]; then
    echo "Subscription created. Check your inbox and confirm the SNS email."
elif [ -n "${TOPIC_ARN}" ]; then
    echo "No ALERT_EMAIL was provided, so the topic has no email subscription yet."
else
    echo "No SNS action was attached. Re-run with TOPIC_ARN or stronger SNS permissions when a notification channel is ready."
fi
