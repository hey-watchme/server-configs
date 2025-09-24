#!/bin/bash

# 累積分析用のSQSキューを作成するスクリプト

REGION="ap-southeast-2"

echo "Creating SQS queues for dashboard cumulative analysis..."

# 1. Dashboard Summary Queue (プロンプト生成用)
echo "Creating watchme-dashboard-summary-queue..."
aws sqs create-queue \
    --queue-name watchme-dashboard-summary-queue \
    --region $REGION \
    --attributes '{
        "MessageRetentionPeriod": "1209600",
        "VisibilityTimeout": "900",
        "MaximumMessageSize": "262144",
        "DelaySeconds": "0",
        "ReceiveMessageWaitTimeSeconds": "20",
        "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:ap-southeast-2:975050024946:watchme-dashboard-summary-dlq\",\"maxReceiveCount\":3}"
    }' || echo "Queue already exists or error occurred"

# 2. Dashboard Summary DLQ (デッドレターキュー)
echo "Creating watchme-dashboard-summary-dlq..."
aws sqs create-queue \
    --queue-name watchme-dashboard-summary-dlq \
    --region $REGION \
    --attributes '{
        "MessageRetentionPeriod": "1209600"
    }' || echo "DLQ already exists or error occurred"

# 3. Dashboard Analysis Queue (ChatGPT分析用)
echo "Creating watchme-dashboard-analysis-queue..."
aws sqs create-queue \
    --queue-name watchme-dashboard-analysis-queue \
    --region $REGION \
    --attributes '{
        "MessageRetentionPeriod": "1209600",
        "VisibilityTimeout": "900",
        "MaximumMessageSize": "262144",
        "DelaySeconds": "0",
        "ReceiveMessageWaitTimeSeconds": "20",
        "RedrivePolicy": "{\"deadLetterTargetArn\":\"arn:aws:sqs:ap-southeast-2:975050024946:watchme-dashboard-analysis-dlq\",\"maxReceiveCount\":3}"
    }' || echo "Queue already exists or error occurred"

# 4. Dashboard Analysis DLQ (デッドレターキュー)
echo "Creating watchme-dashboard-analysis-dlq..."
aws sqs create-queue \
    --queue-name watchme-dashboard-analysis-dlq \
    --region $REGION \
    --attributes '{
        "MessageRetentionPeriod": "1209600"
    }' || echo "DLQ already exists or error occurred"

echo "Queue creation completed. Getting queue URLs..."

# キューのURLを取得して表示
echo ""
echo "Queue URLs:"
aws sqs get-queue-url --queue-name watchme-dashboard-summary-queue --region $REGION --query 'QueueUrl' --output text
aws sqs get-queue-url --queue-name watchme-dashboard-summary-dlq --region $REGION --query 'QueueUrl' --output text
aws sqs get-queue-url --queue-name watchme-dashboard-analysis-queue --region $REGION --query 'QueueUrl' --output text
aws sqs get-queue-url --queue-name watchme-dashboard-analysis-dlq --region $REGION --query 'QueueUrl' --output text

echo ""
echo "SQS queues have been created successfully!"