#!/bin/bash

# Load environment variables from the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -a
source "$SCRIPT_DIR/.env"
set +a

# Test Live Activity End Notification
echo "🛑 Testing Live Activity End Notification..."
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

# Create end payload file
cat > /tmp/end_payload.json << EOF
{
  "aps": {
    "timestamp": $(date +%s),
    "event": "end",
    "dismissal-date": "$(date -v+30M +%s)",
    "content-state": {
      "totalPoints": 115.7,
      "activePlayersCount": 0,
      "teamName": "Durungus",
      "opponentPoints": 102.3,
      "opponentTeamName": "Dorungus",
      "leagueName": "Football League",
      "userAvatarURL": "",
      "opponentAvatarURL": "",
      "gameStatus": "Final",
      "lastUpdate": 1726358465,
      "message": "Game completed!"
    }
  }
}
EOF
    # "dismissal-date": "$(date -v+30M +%s)",

echo "📤 Sending end notification..."
cat /tmp/end_payload.json

curl -v \
    -H "apns-topic: $APNS_TOPIC" \
    -H "apns-push-type: liveactivity" \
    -H "apns-priority: 10" \
    -H "authorization: bearer $jwt" \
    -d @/tmp/end_payload.json \
    --http2 \
    "https://api.sandbox.push.apple.com/3/device/$ACTIVITY_PUSH_TOKEN"

echo ""
echo "✅ End notification test completed!"

# Clean up
rm -f /tmp/end_payload.json