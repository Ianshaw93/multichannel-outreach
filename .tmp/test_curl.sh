#!/bin/bash
# Test HeyReach API with one personalized lead

curl -X POST https://api.heyreach.io/api/v1/lists/291127/leads \
  -H "X-API-KEY: D2IMEWXJKSZGDKBWRPBGK42V5Y" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d @.tmp/heyreach_test_payload.json

echo ""
echo "Payload file: .tmp/heyreach_test_payload.json"
