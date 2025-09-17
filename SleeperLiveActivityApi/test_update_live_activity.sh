#!/bin/bash

# Documentation
# https://developer.apple.com/documentation/ActivityKit/starting-and-updating-live-activities-with-activitykit-push-notifications

# Load environment variables from the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -a
source "$SCRIPT_DIR/.env"
set +a

# Test Live Activity Update Notification
echo "🛑 Testing Live Activity Update Notification..."
echo "Token: ${ACTIVITY_PUSH_TOKEN:0:20}..."
echo "JWT: ${jwt:0:50}..."

# Generate JWT
header='{"alg":"ES256","kid":"'$APNS_KEY_ID'"}'
header_b64=$(echo -n "$header" | base64 | tr -d '=' | tr '/+' '_-' | tr -d '\n')

iat=$(date +%s)
payload='{"iss":"'$APNS_TEAM_ID'","iat":'$iat'}'
payload_b64=$(echo -n "$payload" | base64 | tr -d '=' | tr '/+' '_-' | tr -d '\n')

unsigned_token="$header_b64.$payload_b64"
signature=$(echo -n "$unsigned_token" | openssl dgst -sha256 -sign "$APNS_KEY_PATH" | base64 | tr -d '=' | tr '/+' '_-' | tr -d '\n')
jwt="$unsigned_token.$signature"

echo "🛑 Testing Live Activity Update Notification..."
echo "Token: ${ACTIVITY_PUSH_TOKEN:0:20}..."
echo "JWT: ${jwt:0:50}..."

# Create Update payload file
cat > /tmp/update_payload.json << EOF
{
  "aps": {
    "timestamp": $(date +%s),
    "event": "update",
    "content-state": {
      "totalPoints": 92.8,
      "activePlayersCount": 8,
      "teamName": "Durungus",
      "opponentPoints": 87.5,
      "opponentTeamName": "Dorungus",
      "leagueName": "Rungy",
      "userID": "test_user_id",
      "opponentUserID": "test_opponent_id",
      "gameStatus": "Live",
      "lastUpdate": 1726358465,
      "message": "Score updated!",
      "userProjectedScore": 98.3,
      "opponentProjectedScore": 91.7
    }
  }
}
EOF

echo "📤 Sending Update notification..."
cat /tmp/update_payload.json

curl -v \
    -H "apns-topic: $APNS_TOPIC" \
    -H "apns-push-type: liveactivity" \
    -H "apns-priority: 10" \
    -H "authorization: bearer $jwt" \
    -d @/tmp/update_payload.json \
    --http2 \
    "https://api.sandbox.push.apple.com/3/device/$ACTIVITY_PUSH_TOKEN"

echo ""
echo "✅ Update notification test completed!"

# Clean up
rm -f /tmp/update_payload.json