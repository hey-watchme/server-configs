#!/bin/bash

# Deploy new Lambda functions for event-driven architecture
# Run this script to create/update Lambda functions

set -e

REGION="ap-southeast-2"
ACCOUNT_ID="754724220380"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/watchme-lambda-s3-processor"
PUBLIC_API_BASE_URL="${API_BASE_URL:-https://api.hey-watch.me}"
WORKER_CONNECT_TIMEOUT="${WORKER_CONNECT_TIMEOUT:-3}"
WORKER_READ_TIMEOUT="${WORKER_READ_TIMEOUT:-10}"
WORKER_API_HOST_HEADER="${WORKER_API_HOST_HEADER:-api.hey-watch.me}"
WORKER_VERIFY_TLS="${WORKER_VERIFY_TLS:-false}"
ASR_WORKER_API_ENDPOINT_URL="${ASR_WORKER_API_ENDPOINT_URL:-https://3.24.16.82/vibe-analysis/transcriber/async-process}"
SED_WORKER_API_ENDPOINT_URL="${SED_WORKER_API_ENDPOINT_URL:-https://3.24.16.82/behavior-analysis/features/async-process}"
SER_WORKER_API_ENDPOINT_URL="${SER_WORKER_API_ENDPOINT_URL:-https://3.24.16.82/emotion-analysis/feature-extractor/async-process}"

# Environment variables for Lambda functions
SUPABASE_URL="${SUPABASE_URL}"
SUPABASE_KEY="${SUPABASE_KEY}"

echo "🚀 Deploying Lambda functions for event-driven architecture..."

join_by_comma() {
    local IFS=","
    echo "$*"
}

build_environment_string() {
    local function_name=$1
    local env_vars=(
        "SUPABASE_URL='${SUPABASE_URL}'"
        "SUPABASE_KEY='${SUPABASE_KEY}'"
        "ASR_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-asr-queue-v2.fifo'"
        "SED_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-sed-queue-v2.fifo'"
        "SER_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-ser-queue-v2.fifo'"
        "FEATURE_COMPLETED_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-feature-completed-queue'"
        "SPOT_ANALYSIS_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-spot-analysis-queue.fifo'"
        "DASHBOARD_SUMMARY_QUEUE_URL='https://sqs.ap-southeast-2.amazonaws.com/${ACCOUNT_ID}/watchme-dashboard-summary-queue'"
        "RECONCILIATION_LOOKBACK_MINUTES='1440'"
        "RECONCILIATION_BATCH_SIZE='200'"
    )

    case "${function_name}" in
        watchme-asr-worker)
            env_vars+=(
                "API_ENDPOINT_URL='${ASR_WORKER_API_ENDPOINT_URL}'"
                "API_HOST_HEADER='${WORKER_API_HOST_HEADER}'"
                "VERIFY_TLS='${WORKER_VERIFY_TLS}'"
                "REQUEST_CONNECT_TIMEOUT='${WORKER_CONNECT_TIMEOUT}'"
                "REQUEST_READ_TIMEOUT='${WORKER_READ_TIMEOUT}'"
            )
            ;;
        watchme-sed-worker)
            env_vars+=(
                "API_ENDPOINT_URL='${SED_WORKER_API_ENDPOINT_URL}'"
                "API_HOST_HEADER='${WORKER_API_HOST_HEADER}'"
                "VERIFY_TLS='${WORKER_VERIFY_TLS}'"
                "REQUEST_CONNECT_TIMEOUT='${WORKER_CONNECT_TIMEOUT}'"
                "REQUEST_READ_TIMEOUT='${WORKER_READ_TIMEOUT}'"
            )
            ;;
        watchme-ser-worker)
            env_vars+=(
                "API_ENDPOINT_URL='${SER_WORKER_API_ENDPOINT_URL}'"
                "API_HOST_HEADER='${WORKER_API_HOST_HEADER}'"
                "VERIFY_TLS='${WORKER_VERIFY_TLS}'"
                "REQUEST_CONNECT_TIMEOUT='${WORKER_CONNECT_TIMEOUT}'"
                "REQUEST_READ_TIMEOUT='${WORKER_READ_TIMEOUT}'"
            )
            ;;
        watchme-aggregator-checker|watchme-spot-analysis-worker)
            env_vars+=("API_BASE_URL='${PUBLIC_API_BASE_URL}'")
            ;;
    esac

    echo "Variables={$(join_by_comma "${env_vars[@]}")}"
}

# Function to create/update Lambda function
deploy_lambda() {
    local FUNCTION_NAME=$1
    local HANDLER=$2
    local TIMEOUT=$3
    local MEMORY=$4
    local ENVIRONMENT

    ENVIRONMENT=$(build_environment_string "${FUNCTION_NAME}")

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
            --environment "${ENVIRONMENT}" \
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
            --environment "${ENVIRONMENT}" \
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
echo "Feature worker endpoints:"
echo "  ASR: ${ASR_WORKER_API_ENDPOINT_URL}"
echo "  SED: ${SED_WORKER_API_ENDPOINT_URL}"
echo "  SER: ${SER_WORKER_API_ENDPOINT_URL}"
echo ""
echo "Next steps:"
echo "1. Create the spot analysis FIFO queue"
echo "2. Configure SQS triggers for each Lambda function"
echo "3. Configure the EventBridge reconciliation schedule"
echo "4. Disable the old audio-worker function"
echo "5. Deploy EC2 API changes"
echo "6. Test the new event-driven pipeline"
