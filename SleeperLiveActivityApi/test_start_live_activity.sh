#!/bin/bash

# Load environment variables from the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -a
source "$SCRIPT_DIR/.env"
set +a

# Test Live Activity Start Notification
echo "🛑 Testing Live Activity Start Notification..."
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

# Create start payload file
cat > /tmp/start_payload.json << EOF
{
  "aps": {
    "timestamp": $(date +%s),
    "event": "start",
    "attributes-type": "SleeperLiveActivityAttributes",
    "attributes": {
      "userID": "test_user_id",
      "leagueID": "test_league_id"
    },
    "content-state": {
      "totalPoints": 85.5,
      "activePlayersCount": 9,
      "teamName": "Durungus",
      "opponentPoints": 78.2,
      "opponentTeamName": "Dorungus",
      "leagueName": "Rungy",
      "userID": "test_user_id",
      "opponentUserID": "test_opponent_id",
      "gameStatus": "Live",
      "lastUpdate": 1726358465,
      "message": "Game is live!",
      "userProjectedScore": 92.8,
      "opponentProjectedScore": 89.4
    },
    "alert": {
      "title": {
          "loc-key": "%@ is on an adventure!",
          "loc-args": [
              "Power Panda"
          ]
      },
      "body": {
          "loc-key": "%@ found a sword!",
          "loc-args": [
              "Power Panda"
          ]
      },
      "sound": "chime.aiff"
    }
  }
}
EOF

echo "📤 Starting start notification..."
cat /tmp/start_payload.json

curl -v \
    -H "apns-topic: $APNS_TOPIC" \
    -H "apns-push-type: liveactivity" \
    -H "apns-priority: 10" \
    -H "authorization: bearer $jwt" \
    -d @/tmp/start_payload.json \
    --http2 \
    "https://api.sandbox.push.apple.com/3/device/$ACTIVITY_PUSH_TOKEN"

echo ""
echo "✅ Start notification test completed!"

# Clean up
rm -f /tmp/start_payload.json