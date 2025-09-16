# Sleeper Live Activity API

This API provides real-time push notifications for Sleeper fantasy football Live Activities.

## Features

- ✅ APNS push notifications for Live Activity updates
- ✅ Real-time score monitoring from Sleeper API
- ✅ Efficient updates (only sends when data changes)
- ✅ Remote avatar URL support
- ✅ Optional message field for notifications

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure APNS

1. Go to [Apple Developer Portal](https://developer.apple.com)
2. Navigate to **Certificates, Identifiers & Profiles**
3. Go to **Keys** section
4. Create a new key with **Apple Push Notifications service (APNs)** enabled
5. Download the `.p8` file and note the Key ID
6. Get your Team ID from the top right of the developer portal

### 3. Environment Configuration

Copy `.env.example` to `.env` and fill in your APNS credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```bash
APNS_KEY_PATH=/path/to/your/AuthKey_XXXXXXXXXX.p8
APNS_KEY_ID=1234567890
APNS_TEAM_ID=ABCDEFGHIJ
```

### 4. Run the API

```bash
python main.py
```

The API will run on `http://localhost:8000`

## How It Works

### Push Notification Flow

1. **iOS App** starts Live Activity and registers with API
2. **API** monitors Sleeper data every 2 minutes
3. **API** detects score changes
4. **API** sends APNS push notification with:
   - Updated scores
   - Team names
   - Avatar URLs (for Sleeper profile images)
   - Game status
   - Optional custom message
5. **Live Activity** receives push and updates UI immediately

### Key Benefits

- **Real-time updates**: No 30-second polling delays
- **Battery efficient**: App doesn't need to run background tasks
- **Remote avatar support**: Uses Sleeper's avatar URLs directly
- **Reliable**: Backend monitors continuously even when app is closed
- **Flexible messaging**: Optional message field for custom notifications

## API Endpoints

### Device Management
- `POST /register` - Register device for Live Activity updates
- `GET /devices` - List all registered devices and their status
- `GET /devices/{device_id}` - Get detailed information about a specific device

### Live Activity Control
- `POST /live-activity/start/{device_id}` - Start monitoring for a device (original endpoint)
- `POST /live-activity/end/{device_id}` - Stop monitoring for a device (original endpoint)
- `POST /live-activity/start-by-id/{device_id}` - Start Live Activity by device ID (new)
- `POST /live-activity/stop-by-id/{device_id}` - Stop Live Activity by device ID (new)
- `GET /live-activity/status/{device_id}` - Check if monitoring is active

### Sleeper API Proxies
- `GET /state/nfl` - Get current NFL state
- `GET /user/{username}` - Get user info by username
- `GET /user/{user_id}` - Get user info by ID
- `GET /league/{league_id}` - Get league information
- `GET /league/{league_id}/rosters` - Get league rosters
- `GET /league/{league_id}/matchups/{week}` - Get matchups for specific week
- `GET /players/nfl` - Get all NFL players

### System
- `GET /health` - Health check

## Usage Examples

### Device Management
```bash
# List all registered devices
curl -X GET http://localhost:8000/devices

# Get specific device details
curl -X GET http://localhost:8000/devices/your_device_id

# Register a new device
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your_sleeper_user_id",
    "league_id": "your_league_id",
    "push_token": "device_push_token",
    "device_id": "unique_device_identifier"
  }'
```

### Live Activity Management
```bash
# Start Live Activity for a specific device
curl -X POST http://localhost:8000/live-activity/start-by-id/your_device_id

# Stop Live Activity for a specific device
curl -X POST http://localhost:8000/live-activity/stop-by-id/your_device_id

# Check Live Activity status
curl -X GET http://localhost:8000/live-activity/status/your_device_id
```

### Response Examples

**List Devices Response:**
```json
{
  "devices": [
    {
      "device_id": "abc123",
      "user_id": "user_456",
      "league_id": "league_789",
      "has_push_token": true,
      "live_activity_active": true,
      "live_activity_started_at": "2025-09-14T21:53:56.798805",
      "live_activity_last_update": "2025-09-14T21:53:56.798809"
    }
  ],
  "total_registered": 1,
  "total_active_live_activities": 1
}
```

**Start Live Activity Response:**
```json
{
  "status": "success",
  "message": "Live Activity started for device abc123",
  "device_id": "abc123",
  "user_id": "user_456",
  "league_id": "league_789"
}
```

## Configuration Notes

### APNS Environment
- **Development**: Set `use_sandbox=True` in `main.py`
- **Production**: Set `use_sandbox=False` in `main.py`

### Update Frequency
- Current: Every 2 minutes (configurable in `startup_tasks()`)
- Recommended: 1-2 minutes during games, 5+ minutes off-season

### Avatar Support
- Uses remote Sleeper avatar URLs directly
- No local caching required
- Lightweight approach for Live Activity performance

## Troubleshooting

### APNS Issues
- Verify `.p8` file path is correct
- Check Key ID and Team ID are accurate
- Ensure app bundle ID matches your provisioning profile
- Check Xcode logs for APNS registration errors

### No Push Notifications
- Verify device is registered (`/live-activity/status/{device_id}`)
- Check API logs for APNS errors
- Ensure Live Activity is active on device
- Verify network connectivity to Apple's APNS servers

### Avatar Issues
- Check Sleeper API responses for valid avatar URLs
- Verify avatar URLs are accessible from Sleeper CDN
- Avatar display depends on device's internet connection