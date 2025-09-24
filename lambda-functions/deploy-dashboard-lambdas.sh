#!/bin/bash

# Dashboard累積分析Lambda関数のデプロイスクリプト

set -e

REGION="ap-southeast-2"
ACCOUNT_ID="975050024946"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/lambda-execution-role"

echo "========================================="
echo "Deploying Dashboard Lambda Functions"
echo "========================================="

# 1. SQSキューの作成
echo ""
echo "Step 1: Creating SQS Queues"
echo "-----------------------------------------"
bash create-sqs-queues.sh

# 2. watchme-dashboard-summary-worker のビルドとデプロイ
echo ""
echo "Step 2: Building and Deploying watchme-dashboard-summary-worker"
echo "-----------------------------------------"
cd watchme-dashboard-summary-worker
chmod +x build.sh
./build.sh

echo "Creating/Updating Lambda function..."
aws lambda create-function \
    --function-name watchme-dashboard-summary-worker \
    --runtime python3.9 \
    --role $ROLE_ARN \
    --handler lambda_function.lambda_handler \
    --timeout 900 \
    --memory-size 512 \
    --region $REGION \
    --zip-file fileb://function.zip \
    --environment "Variables={
        API_BASE_URL=https://api.hey-watch.me,
        ANALYSIS_QUEUE_URL=https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-dashboard-analysis-queue
    }" || \
aws lambda update-function-code \
    --function-name watchme-dashboard-summary-worker \
    --region $REGION \
    --zip-file fileb://function.zip

# 環境変数を更新
aws lambda update-function-configuration \
    --function-name watchme-dashboard-summary-worker \
    --region $REGION \
    --timeout 900 \
    --memory-size 512 \
    --environment "Variables={
        API_BASE_URL=https://api.hey-watch.me,
        ANALYSIS_QUEUE_URL=https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-dashboard-analysis-queue
    }"

# SQSトリガーを設定
echo "Setting up SQS trigger for watchme-dashboard-summary-worker..."
aws lambda create-event-source-mapping \
    --function-name watchme-dashboard-summary-worker \
    --event-source-arn arn:aws:sqs:${REGION}:${ACCOUNT_ID}:watchme-dashboard-summary-queue \
    --batch-size 1 \
    --region $REGION || echo "Event source mapping may already exist"

cd ..

# 3. watchme-dashboard-analysis-worker のビルドとデプロイ
echo ""
echo "Step 3: Building and Deploying watchme-dashboard-analysis-worker"
echo "-----------------------------------------"
cd watchme-dashboard-analysis-worker
chmod +x build.sh
./build.sh

echo "Creating/Updating Lambda function..."
aws lambda create-function \
    --function-name watchme-dashboard-analysis-worker \
    --runtime python3.9 \
    --role $ROLE_ARN \
    --handler lambda_function.lambda_handler \
    --timeout 900 \
    --memory-size 512 \
    --region $REGION \
    --zip-file fileb://function.zip \
    --environment "Variables={
        API_BASE_URL=https://api.hey-watch.me
    }" || \
aws lambda update-function-code \
    --function-name watchme-dashboard-analysis-worker \
    --region $REGION \
    --zip-file fileb://function.zip

# 環境変数を更新
aws lambda update-function-configuration \
    --function-name watchme-dashboard-analysis-worker \
    --region $REGION \
    --timeout 900 \
    --memory-size 512 \
    --environment "Variables={
        API_BASE_URL=https://api.hey-watch.me
    }"

# SQSトリガーを設定
echo "Setting up SQS trigger for watchme-dashboard-analysis-worker..."
aws lambda create-event-source-mapping \
    --function-name watchme-dashboard-analysis-worker \
    --event-source-arn arn:aws:sqs:${REGION}:${ACCOUNT_ID}:watchme-dashboard-analysis-queue \
    --batch-size 1 \
    --region $REGION || echo "Event source mapping may already exist"

cd ..

# 4. watchme-audio-worker の更新（既存関数の更新）
echo ""
echo "Step 4: Updating watchme-audio-worker"
echo "-----------------------------------------"
cd watchme-audio-worker
chmod +x build.sh
./build.sh

echo "Updating Lambda function code..."
aws lambda update-function-code \
    --function-name watchme-audio-worker \
    --region $REGION \
    --zip-file fileb://function.zip

# 環境変数を更新（DASHBOARD_SUMMARY_QUEUE_URLを追加）
echo "Updating environment variables..."
aws lambda update-function-configuration \
    --function-name watchme-audio-worker \
    --region $REGION \
    --environment "Variables={
        API_BASE_URL=https://api.hey-watch.me,
        DASHBOARD_SUMMARY_QUEUE_URL=https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-dashboard-summary-queue
    }"

cd ..

echo ""
echo "========================================="
echo "Deployment Complete!"
echo "========================================="
echo ""
echo "Lambda Functions:"
echo "  - watchme-dashboard-summary-worker"
echo "  - watchme-dashboard-analysis-worker"
echo "  - watchme-audio-worker (updated)"
echo ""
echo "SQS Queues:"
echo "  - watchme-dashboard-summary-queue"
echo "  - watchme-dashboard-analysis-queue"
echo "  - watchme-dashboard-summary-dlq"
echo "  - watchme-dashboard-analysis-dlq"
echo ""
echo "Next Steps:"
echo "1. Monitor Lambda logs in CloudWatch"
echo "2. Check SQS queue metrics"
echo "3. Test the complete pipeline"