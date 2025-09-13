# Sleeper Live Activity Backend API

This is the backend server for the Sleeper Fantasy Football Live Activity iOS app. It handles Sleeper API integration, Live Activity push notifications, and real-time scoring updates.

## Features

- **Sleeper API Integration**: Fetches user data, leagues, rosters, matchups, and NFL state
- **Live Activity Management**: Handles starting/stopping Live Activities and push notifications
- **Real-time Updates**: Monitors scoring changes every 2 minutes during active games
- **Caching**: Efficiently caches player data and NFL state to minimize API calls
- **Push Notifications**: Sends Live Activity updates via APNS

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python main.py
```

The server will start on `http://localhost:8000`

## API Endpoints

### User Management
- `POST /register` - Register a user with Sleeper credentials and push token
- `GET /user/{username}` - Get user information by username
- `GET /user/{user_id}/leagues/{season}` - Get all leagues for a user

### League Data
- `GET /league/{league_id}/rosters` - Get rosters for a league
- `GET /league/{league_id}/matchups/{week}` - Get matchups for a specific week

### NFL Data
- `GET /players/nfl` - Get all NFL players (cached)
- `GET /state/nfl` - Get current NFL state

### Live Activity
- `POST /live-activity/start/{device_id}` - Start Live Activity for a device
- `POST /live-activity/end/{device_id}` - End Live Activity for a device
- `GET /live-activity/status/{device_id}` - Get Live Activity status

## Configuration

To enable APNS push notifications, you'll need to:
1. Add your APNS certificate/key
2. Configure the `LiveActivityManager` with proper APNS credentials
3. Set up your iOS app's bundle ID and team ID

## Architecture

The server uses:
- **FastAPI** for the REST API
- **httpx** for async HTTP requests to Sleeper API
- **APScheduler** for background tasks
- **aioapns** for Apple Push Notifications (when configured)

## Live Activity Flow

1. iOS app registers user with backend
2. Backend monitors Sleeper API for active games
3. When user's players are active, Live Activity updates are pushed
4. Updates continue until 30 minutes after last active player finishes
