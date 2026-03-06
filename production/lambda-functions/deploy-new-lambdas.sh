#!/bin/bash

# Deploy new Lambda functions for event-driven architecture
# Run this script to create/update Lambda functions

set -e

REGION="ap-southeast-2"
ACCOUNT_ID="754724220380"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/watchme-lambda-s3-processor"

# Environment variables for Lambda functions
SUPABASE_URL="${SUPABASE_URL}"
SUPABASE_KEY="${SUPABASE_KEY}"

echo "🚀 Deploying Lambda functions for event-driven architecture..."

# Function to create/update Lambda function
deploy_lambda() {
    local FUNCTION_NAME=$1
    local HANDLER=$2
    local TIMEOUT=$3
    local MEMORY=$4

    echo ""
    echo "📦 Deploying ${FUNCTION_NAME}..."

    cd /Users/kaya.matsumoto/projects/watchme/server-configs/production/lambda-functions/${FUNCTION_NAME}

    # Create deployment package
    rm -rf package function.zip

    # Install dependencies if requirements.txt exists
    if [ -f requirements.txt ]; then
        pip3 install --target ./package -r requirements.txt --platform manylinux2014_x86_64 --only-binary=:all:
        cd package
        zip -r ../function.zip . -q
        cd ..
    fi

    # Add Lambda function code
    zip -g function.zip lambda_function.py

    # Check if function exists
    if aws lambda get-function --function-name ${FUNCTION_NAME} --region ${REGION} 2>/dev/null; then
        echo "Updating existing function..."
        aws lambda update-function-code \
            --function-name ${FUNCTION_NAME} \
            --zip-file fileb://function.zip \
            --region ${REGION}

        # Wait for update to complete
        aws lambda wait function-updated --function-name ${FUNCTION_NAME} --region ${REGION}

        # Update configuration
        aws lambda update-function-configuration \
            --function-name ${FUNCTION_NAME} \
            --timeout ${TIMEOUT} \
            --memory-size ${MEMORY} \
            --environment Variables="{API_BASE_URL='https://api.hey-watch.me',SUPABASE_URL='${SUPABASE_URL}',SUPABASE_KEY='${SUPABASE_KEY}',ASR_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-asr-queue-v2.fifo',SED_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-sed-queue-v2.fifo',SER_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-ser-queue-v2.fifo',FEATURE_COMPLETED_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-feature-completed-queue',SPOT_ANALYSIS_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-spot-analysis-queue.fifo',DASHBOARD_SUMMARY_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-dashboard-summary-queue',RECONCILIATION_LOOKBACK_MINUTES='1440',RECONCILIATION_BATCH_SIZE='200'}" \
            --region ${REGION}
    else
        echo "Creating new function..."
        aws lambda create-function \
            --function-name ${FUNCTION_NAME} \
            --runtime python3.11 \
            --role ${ROLE_ARN} \
            --handler ${HANDLER} \
            --zip-file fileb://function.zip \
            --timeout ${TIMEOUT} \
            --memory-size ${MEMORY} \
            --environment Variables="{API_BASE_URL='https://api.hey-watch.me',SUPABASE_URL='${SUPABASE_URL}',SUPABASE_KEY='${SUPABASE_KEY}',ASR_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-asr-queue-v2.fifo',SED_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-sed-queue-v2.fifo',SER_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-ser-queue-v2.fifo',FEATURE_COMPLETED_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-feature-completed-queue',SPOT_ANALYSIS_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-spot-analysis-queue.fifo',DASHBOARD_SUMMARY_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-dashboard-summary-queue',RECONCILIATION_LOOKBACK_MINUTES='1440',RECONCILIATION_BATCH_SIZE='200'}" \
            --region ${REGION}
    fi

    # Clean up
    rm -rf package function.zip

    echo "✅ ${FUNCTION_NAME} deployed successfully!"
}

# Deploy each Lambda function
# Function name, Handler, Timeout (seconds), Memory (MB)

echo "1️⃣ Deploying ASR Worker..."
deploy_lambda "watchme-asr-worker" "lambda_function.lambda_handler" 60 256

echo ""
echo "2️⃣ Deploying SED Worker..."
deploy_lambda "watchme-sed-worker" "lambda_function.lambda_handler" 60 256

echo ""
echo "3️⃣ Deploying SER Worker..."
deploy_lambda "watchme-ser-worker" "lambda_function.lambda_handler" 60 256

echo ""
echo "4️⃣ Deploying Aggregator Checker..."
deploy_lambda "watchme-aggregator-checker" "lambda_function.lambda_handler" 300 512

echo ""
echo "5️⃣ Deploying Spot Analysis Worker..."
deploy_lambda "watchme-spot-analysis-worker" "lambda_function.lambda_handler" 300 512

echo ""
echo "6️⃣ Updating audio-processor..."
deploy_lambda "watchme-audio-processor" "lambda_function.lambda_handler" 30 256

echo ""
echo "🎉 All Lambda functions deployed successfully!"
echo ""
echo "Next steps:"
echo "1. Create the spot analysis FIFO queue"
echo "2. Configure SQS triggers for each Lambda function"
echo "3. Configure the EventBridge reconciliation schedule"
echo "4. Disable the old audio-worker function"
echo "5. Deploy EC2 API changes"
echo "6. Test the new event-driven pipeline"
