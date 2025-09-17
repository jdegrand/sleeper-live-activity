# Sleeper Live Activity API

This API provides real-time push notifications for Sleeper fantasy football Live Activities with comprehensive player scoring tracking.

## Features

- ✅ APNS push notifications for Live Activity updates
- ✅ Real-time score monitoring from Sleeper API
- ✅ **Player-level scoring tracking with pts_ppr data**
- ✅ **GraphQL API integration for player stats and projections**
- ✅ **User and opponent projected score tracking**
- ✅ **Optimized single GraphQL call for all active players**
- ✅ **30-second update intervals for real-time responsiveness**
- ✅ **Efficient batch processing for starter players**
- ✅ Remote avatar URL support
- ✅ Optional message field for notifications
- ✅ Automatic game detection and live activity management
- ✅ NFL games and players data caching

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
2. **API** monitors Sleeper data and player scores every 30 seconds with optimized batch processing
3. **API** detects score changes (team totals, player pts_ppr, and projected scores)
4. **API** sends APNS push notification with:
   - Updated team scores
   - Player-level pts_ppr totals
   - **User projected score total**
   - **Opponent projected score total**
   - Team names and avatars
   - Game status
   - Optional custom messages
5. **Live Activity** receives push and updates UI immediately

### Optimized Player Scoring System

1. **Global Player Collection**: API collects all unique player IDs from all active live activities
2. **Single GraphQL Request**: One consolidated GraphQL call fetches stats for ALL players across ALL users
3. **Smart Caching**: Player stats cached and distributed to individual users from single source
4. **Score Calculation**: Calculates both user and opponent projected totals from cached data
5. **Change Detection**: Only updates when pts_ppr scores or projections actually change
6. **Live Updates**: All active live activities updated concurrently every 30 seconds

**Performance Benefits:**
- **90% API reduction**: 10 users = 1 GraphQL call instead of 10
- **Faster updates**: 30-second intervals (was 60 seconds)
- **Better scalability**: 100 users still = 1 API call
- **Opponent tracking**: Automatically calculates opponent projected scores

### Key Benefits

- **Real-time updates**: 30-second player score and projection monitoring
- **Battery efficient**: App doesn't need to run background tasks
- **Player-level precision**: Individual player pts_ppr tracking and projections
- **Optimized efficiency**: Single GraphQL request for ALL players across ALL users
- **Opponent awareness**: Automatic opponent projected score tracking
- **Smart change detection**: Only sends updates when scores actually change
- **Remote avatar support**: Uses Sleeper's avatar URLs directly
- **Reliable**: Backend monitors continuously even when app is closed
- **Flexible messaging**: Optional message field for custom notifications

## API Endpoints

### Device Management
- `POST /register` - Register device for Live Activity updates
- `POST /register-live-activity-token` - Register Live Activity token for push updates
- `GET /devices` - List all registered devices and their status
- `GET /devices/{device_id}` - Get detailed information about a specific device

### Live Activity Control
- `POST /live-activity/start/{device_id}` - Start monitoring for a device (original endpoint)
- `POST /live-activity/end/{device_id}` - Stop monitoring for a device (original endpoint)
- `POST /live-activity/start-by-id/{device_id}` - Start Live Activity by device ID (new)
- `POST /live-activity/stop-by-id/{device_id}` - Stop Live Activity by device ID (new)
- `GET /live-activity/status/{device_id}` - Check if monitoring is active

### **Player Scoring (New)**
- `GET /player-scores` - Get player scoring data for all devices
- `GET /player-scores/{device_id}` - Get player scoring data for a specific device
- `POST /player-scores/refresh` - Manually refresh player scores for all devices
- `POST /player-scores/refresh/{device_id}` - Manually refresh player scores for a specific device

### NFL Data Management
- `GET /games` - Get today's NFL games data from ESPN
- `POST /games/refresh` - Manually refresh NFL games data
- `POST /players/refresh` - Manually refresh NFL players data from Sleeper

### Sleeper API Proxies
- `GET /state/nfl` - Get current NFL state
- `GET /user/{username}` - Get user info by username
- `GET /user/{user_id}` - Get user info by ID
- `GET /league/{league_id}` - Get league information
- `GET /league/{league_id}/rosters` - Get league rosters
- `GET /league/{league_id}/matchups/{week}` - Get matchups for specific week
- `GET /players/nfl` - Get all NFL players (cached)

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
    "device_id": "unique_device_identifier",
    "push_to_start_token": "push_to_start_token_optional"
  }'

# Register Live Activity token (called by app when Live Activity starts)
curl -X POST http://localhost:8000/register-live-activity-token \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "your_device_id",
    "live_activity_token": "live_activity_push_token",
    "activity_id": "activity_identifier_optional"
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

### **Player Scoring Management (New)**
```bash
# Get all player scores
curl -X GET http://localhost:8000/player-scores

# Get player scores for specific device
curl -X GET http://localhost:8000/player-scores/your_device_id

# Manually refresh player scores for all devices
curl -X POST http://localhost:8000/player-scores/refresh

# Manually refresh player scores for specific device
curl -X POST http://localhost:8000/player-scores/refresh/your_device_id
```

### NFL Data Management
```bash
# Get current NFL games
curl -X GET http://localhost:8000/games

# Refresh NFL games data
curl -X POST http://localhost:8000/games/refresh

# Refresh NFL players data
curl -X POST http://localhost:8000/players/refresh
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
      "has_remote_notification_token": true,
      "has_push_to_start_token": true,
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

**Player Scores Response:**
```json
{
  "device_id": "abc123",
  "starter_player_ids": ["4892", "8150", "8228", "4039", "1479", "12506", "3198", "8148", "8259"],
  "current_pts_ppr": 87.6,
  "current_projections": 92.3,
  "total_starters": 9,
  "cache_age_seconds": 15,
  "data_source": "optimized_cache"
}
```

**All Player Scores Response:**
```json
{
  "player_scores": [
    {
      "device_id": "abc123",
      "starter_player_ids": ["4892", "8150", "8228"],
      "current_pts_ppr": 87.6,
      "current_projections": 92.3,
      "total_starters": 9,
      "has_live_activity": true,
      "data_source": "optimized_cache"
    },
    {
      "device_id": "def456",
      "starter_player_ids": ["4039", "1479", "12506"],
      "current_pts_ppr": 64.2,
      "current_projections": 78.1,
      "total_starters": 9,
      "has_live_activity": false,
      "data_source": "optimized_cache"
    }
  ],
  "total_devices": 2,
  "cache_age_seconds": 15,
  "cache_populated": true
}
```

**NFL Games Response:**
```json
{
  "games": [
    {
      "date": "2025-09-16T21:00:00Z",
      "name": "Pittsburgh Steelers at New England Patriots",
      "competitors": [
        {"abbreviation": "PIT"},
        {"abbreviation": "NE"}
      ]
    }
  ],
  "last_fetched": "2025-09-16T08:00:00.123456",
  "total_games": 1
}
```

## Configuration Notes

### APNS Environment
- **Development**: Set `use_sandbox=True` in `main.py` (line ~482)
- **Production**: Set `use_sandbox=False` in `main.py` (line ~482)

### Update Frequency
- **Live Activity Updates**: Every minute (line ~1574)
- **Optimized Player Score Updates**: Every 30 seconds (line ~1581)
- **Game Start Checker**: Every 5 minutes (line ~1572)
- **NFL Games Refresh**: Daily at 8:00 AM (line ~1567)
- **NFL Players Refresh**: Daily at 8:05 AM (line ~1570)

### Player Scoring Configuration
- **GraphQL Endpoint**: Update `self.graphql_url` in `PlayerStatsClient` (line ~192)
- **Season/Week**: Automatically detected from NFL state or defaults to 2025/week 3
- **Change Threshold**: 0.01 pts_ppr minimum change to trigger updates
- **Optimized Processing**: Single GraphQL call for all active players across all users
- **Cache Management**: Automatic cache population and refresh on app load
- **Concurrent Updates**: All live activities updated in parallel from shared cache

### Avatar Support
- Uses remote Sleeper avatar URLs directly
- No local caching required
- Lightweight approach for Live Activity performance

### Performance Optimizations
- **Consolidated GraphQL Requests**: Single request for ALL players across ALL users (90% API reduction)
- **Smart Caching**: Player stats cached and distributed to individual users
- **Change Detection**: Only sends updates when scores or projections change
- **Concurrent Updates**: All live activities updated in parallel from shared cache
- **Data Caching**: NFL players and games cached daily
- **Starter ID Caching**: User roster starters cached to reduce API calls
- **On-Demand Cache Population**: Fresh data fetched automatically on app load

## Live Activity Content State Fields

The Live Activity ContentState now includes projected score fields for enhanced user experience:

```swift
public struct ContentState: Codable, Hashable {
    public var totalPoints: Double           // Current user points
    public var activePlayersCount: Int       // Active players count
    public var teamName: String              // User team name
    public var opponentPoints: Double        // Current opponent points
    public var opponentTeamName: String      // Opponent team name
    public var leagueName: String            // League name
    public var userID: String                // User ID
    public var opponentUserID: String        // Opponent user ID
    public var gameStatus: String            // Game status
    public var lastUpdate: Date              // Last update timestamp
    public var message: String?              // Optional message
    public var userProjectedScore: Double    // ✨ NEW: User projected total
    public var opponentProjectedScore: Double // ✨ NEW: Opponent projected total
}
```

**New Fields:**
- `userProjectedScore`: The user's total projected points for all starter players
- `opponentProjectedScore`: The opponent's total projected points for all starter players

These fields are automatically calculated by the backend and sent via push notifications to update Live Activities in real-time.

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

### Player Scoring Issues
- **No Player Scores**: Check `/player-scores/{device_id}` endpoint for starter data
- **GraphQL Errors**: Verify GraphQL endpoint URL is correct (line 176 in main.py)
- **No Score Updates**: Check logs for GraphQL API errors or network issues
- **Wrong Players**: Verify user is in correct league and has starters set
- **Debug Commands**:
  ```bash
  # Check if user has starters
  curl http://localhost:8000/player-scores/your_device_id

  # Force refresh scores
  curl -X POST http://localhost:8000/player-scores/refresh/your_device_id

  # Check NFL state
  curl http://localhost:8000/state/nfl
  ```

### Performance Issues
- **High API Usage**: Increase update intervals in scheduler configuration
- **Slow Updates**: Check GraphQL endpoint response times
- **Memory Usage**: Monitor concurrent processing of multiple users

### Avatar Issues
- Check Sleeper API responses for valid avatar URLs
- Verify avatar URLs are accessible from Sleeper CDN
- Avatar display depends on device's internet connection

### Data Issues
- **Stale Player Data**: Use `POST /players/refresh` to update NFL players
- **Missing Games**: Use `POST /games/refresh` to update today's games
- **Wrong Week**: Check NFL state API for current week detection