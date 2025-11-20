#!/bin/bash

# Weekly Profile Worker Lambda Deployment Script

FUNCTION_NAME="watchme-weekly-profile-worker"
REGION="ap-southeast-2"
ROLE_ARN="arn:aws:iam::754724220380:role/service-role/watchme-dashboard-summary-worker-role-aemtm8am"
RUNTIME="python3.12"
HANDLER="lambda_function.lambda_handler"
TIMEOUT=900  # 15 minutes
MEMORY_SIZE=512

# Environment variables
API_BASE_URL="https://api.hey-watch.me"
DEVICE_IDS="9f7d6e27-98c3-4c19-bdfb-f7fda58b9a93"

echo "=== Deploying Weekly Profile Worker Lambda ==="
echo "Function name: $FUNCTION_NAME"
echo "Region: $REGION"

# Create build directory
echo "Creating build directory..."
rm -rf build
mkdir -p build

# Copy lambda function
cp lambda_function.py build/

# Install dependencies
if [ -f requirements.txt ]; then
    echo "Installing dependencies..."
    pip3 install -r requirements.txt -t build/ --upgrade
fi

# Create deployment package
echo "Creating deployment package..."
cd build
zip -r ../deployment.zip . -q
cd ..

echo "Deployment package size:"
du -h deployment.zip

# Check if function exists
echo "Checking if function exists..."
aws lambda get-function --function-name $FUNCTION_NAME --region $REGION > /dev/null 2>&1

if [ $? -eq 0 ]; then
    # Update existing function
    echo "Updating existing function..."
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://deployment.zip \
        --region $REGION

    # Update configuration
    echo "Updating function configuration..."
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --handler $HANDLER \
        --timeout $TIMEOUT \
        --memory-size $MEMORY_SIZE \
        --environment "Variables={API_BASE_URL=$API_BASE_URL,DEVICE_IDS=$DEVICE_IDS}" \
        --region $REGION
else
    # Create new function
    echo "Creating new function..."
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime $RUNTIME \
        --role $ROLE_ARN \
        --handler $HANDLER \
        --zip-file fileb://deployment.zip \
        --timeout $TIMEOUT \
        --memory-size $MEMORY_SIZE \
        --environment "Variables={API_BASE_URL=$API_BASE_URL,DEVICE_IDS=$DEVICE_IDS}" \
        --region $REGION
fi

echo ""
echo "=== Deployment completed ==="
echo ""
echo "Next steps:"
echo "1. Create EventBridge rule: cron(0 15 * * ? *)"
echo "2. Set target to: $FUNCTION_NAME"
echo "3. Test with: aws lambda invoke --function-name $FUNCTION_NAME out.json"
