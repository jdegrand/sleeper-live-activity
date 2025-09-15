# Sleeper Live Activity API

This API provides real-time push notifications for Sleeper fantasy football Live Activities.

## Features

- ✅ APNS push notifications for Live Activity updates
- ✅ Avatar image downloading and caching
- ✅ Real-time score monitoring from Sleeper API
- ✅ Efficient updates (only sends when data changes)
- ✅ Base64 encoded avatar data in push payloads

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
3. **API** detects score changes and downloads avatars
4. **API** sends APNS push notification with:
   - Updated scores
   - Team names
   - Base64 encoded avatar images
   - Game status
5. **Live Activity** receives push and updates UI immediately

### Key Benefits

- **Real-time updates**: No 30-second polling delays
- **Battery efficient**: App doesn't need to run background tasks
- **Always current avatars**: API downloads and includes avatar data
- **Reliable**: Backend monitors continuously even when app is closed

## API Endpoints

- `POST /register` - Register device for Live Activity updates
- `POST /live-activity/start/{device_id}` - Start monitoring for a device
- `POST /live-activity/end/{device_id}` - Stop monitoring for a device
- `GET /live-activity/status/{device_id}` - Check if monitoring is active
- `GET /health` - Health check

## Configuration Notes

### APNS Environment
- **Development**: Set `use_sandbox=True` in `main.py`
- **Production**: Set `use_sandbox=False` in `main.py`

### Update Frequency
- Current: Every 2 minutes (configurable in `startup_tasks()`)
- Recommended: 1-2 minutes during games, 5+ minutes off-season

### Avatar Caching
- Images resized to 60x60px for optimal Live Activity performance
- Cached in memory to avoid re-downloading
- Included as base64 data in push notifications

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

### Missing Avatars
- Check Sleeper API responses in logs
- Verify avatar URLs are accessible
- Check image download/encoding in API logs