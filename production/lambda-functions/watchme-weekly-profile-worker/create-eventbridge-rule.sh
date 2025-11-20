#!/bin/bash

# Create EventBridge Rule for Weekly Profile Worker

FUNCTION_NAME="watchme-weekly-profile-worker"
RULE_NAME="watchme-weekly-profile-daily-trigger"
REGION="ap-southeast-2"
ACCOUNT_ID="754724220380"

# Cron expression: Every day at 15:00 UTC (00:00 JST = 15:00 UTC previous day)
# Note: JST is UTC+9, so 00:00 JST = 15:00 UTC
SCHEDULE_EXPRESSION="cron(0 15 * * ? *)"

echo "=== Creating EventBridge Rule for Weekly Profile Worker ==="
echo "Rule name: $RULE_NAME"
echo "Schedule: $SCHEDULE_EXPRESSION"
echo "Schedule (human): Every day at 15:00 UTC (00:00 JST)"
echo ""

# Create EventBridge rule
echo "Creating EventBridge rule..."
aws events put-rule \
    --name $RULE_NAME \
    --description "Trigger weekly profile worker daily at 00:00 JST (15:00 UTC)" \
    --schedule-expression "$SCHEDULE_EXPRESSION" \
    --state ENABLED \
    --region $REGION

# Add Lambda permission to be invoked by EventBridge
echo "Adding Lambda permission..."
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id $RULE_NAME \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:$REGION:$ACCOUNT_ID:rule/$RULE_NAME" \
    --region $REGION

# Add Lambda as target
echo "Adding Lambda function as target..."
aws events put-targets \
    --rule $RULE_NAME \
    --targets "Id=1,Arn=arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$FUNCTION_NAME" \
    --region $REGION

echo ""
echo "=== EventBridge Rule Created Successfully ==="
echo ""
echo "Rule ARN: arn:aws:events:$REGION:$ACCOUNT_ID:rule/$RULE_NAME"
echo "Target Lambda: $FUNCTION_NAME"
echo "Schedule: Daily at 00:00 JST (15:00 UTC)"
echo ""
echo "To verify:"
echo "  aws events list-rules --region $REGION | grep $RULE_NAME"
echo "  aws events list-targets-by-rule --rule $RULE_NAME --region $REGION"
echo ""
echo "To test manually:"
echo "  aws lambda invoke --function-name $FUNCTION_NAME out.json --region $REGION"
