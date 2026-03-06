#!/bin/bash

# Configure an EventBridge fallback trigger for watchme-aggregator-checker.
# This catches recordings where all three features completed in DB but the last
# completion notification never reached the checker.

set -e

REGION="ap-southeast-2"
ACCOUNT_ID="754724220380"
RULE_NAME="watchme-aggregator-reconciliation-every-5-minutes"
TARGET_ID="watchme-aggregator-checker"
FUNCTION_NAME="watchme-aggregator-checker"

echo "⏰ Configuring EventBridge reconciliation schedule..."

aws events put-rule \
  --name "${RULE_NAME}" \
  --schedule-expression "rate(5 minutes)" \
  --state ENABLED \
  --description "Fallback reconciliation for completed spot features without spot results" \
  --region "${REGION}" >/dev/null

aws lambda add-permission \
  --function-name "${FUNCTION_NAME}" \
  --statement-id "${RULE_NAME}" \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn "arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/${RULE_NAME}" \
  --region "${REGION}" 2>/dev/null || echo "Lambda permission already exists"

aws events put-targets \
  --rule "${RULE_NAME}" \
  --targets "Id"="${TARGET_ID}","Arn"="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}" \
  --region "${REGION}" >/dev/null

echo "✅ EventBridge schedule is configured"
echo "Rule name: ${RULE_NAME}"
