# Live Activity Update Guide

## Overview
This document outlines when and how Live Activities are started, updated, and ended, including all data fetching frequencies and update conditions.

## Update Frequencies (Configurable)

All update intervals can be modified in `main.py` at the top of the file:

```python
LIVE_ACTIVITY_UPDATE_INTERVAL = 30     # Both player and team score updates (unified)
GAME_START_CHECK_INTERVAL = 300        # NFL game start detection (5 minutes)
NFL_GAMES_REFRESH_HOUR = 8             # Daily NFL games refresh (8 AM)
NFL_PLAYERS_REFRESH_HOUR = 8           # Daily NFL players refresh (8:05 AM)
PLAYER_CACHE_MAX_AGE = 60              # Max age before triggering fresh fetch on app load

# Cache configurations
LEAGUE_USERS_CACHE_SECONDS = 1800      # 30 minutes
LEAGUE_INFO_CACHE_SECONDS = 86400      # 24 hours
LEAGUE_ROSTERS_CACHE_SECONDS = 600     # 10 minutes
```

## Live Activity Lifecycle

### 1. Starting Live Activities

**Manual Start (iOS App):**
- User taps start button in iOS app
- App calls backend `/live-activity/start-by-id/{device_id}`
- Backend sends APNS start notification
- Live Activity appears on Lock Screen/Dynamic Island
- Device added to `active_live_activities`

**Auto Start (Game Detection):**
- **Frequency**: Every 5 minutes (`GAME_START_CHECK_INTERVAL`)
- **Trigger**: NFL games starting within next 5 minutes
- **Action**: Automatically starts Live Activities for all registered devices
- **Method**: `check_and_start_live_activities()`

### 2. Live Activity Updates

When a Live Activity is active, updates are sent on a unified schedule:

#### **Combined Score Updates (Every 30 seconds)**
- **Frequency**: `LIVE_ACTIVITY_UPDATE_INTERVAL` (30 seconds)
- **Method**: `update_all_live_activities()` (combines player and team updates)
- **Data Sources**:
  - Single consolidated GraphQL call for ALL active players (user + opponent)
  - Sleeper matchups API for team totals
- **Update Conditions**:
  - Individual player `pts_ppr` changes by >0.01 points
  - Player projected scores change by >0.01 points
  - User's team total points change
  - Opponent's team total points change
  - User ID changes
  - Opponent user ID changes
  - Top scoring player identified from either team (>0.1 point gain)
- **Efficiency**: 1 GraphQL call serves all users across all matchups (90% API reduction)
- **Smart Messaging**: Shows top performer with emojis (🔥 user, ⚡ opponent)
- **Push Alerts**: APNS notifications for big plays (3+ point gains)

#### **Manual Updates**
- **App Load**: Immediate refresh if cache >60 seconds old
- **Manual Refresh**: Via `/player-scores/refresh` endpoints
- **Device-Specific**: `/player-scores/refresh/{device_id}`
- **All Devices**: `/player-scores/refresh`

### 3. Ending Live Activities

**Manual End:**
- User interaction or app request
- Backend calls `/live-activity/stop-by-id/{device_id}`
- Sends APNS end notification
- Removes from `active_live_activities`
- Cleans up tokens and cached data

**Auto End:**
- Live Activities automatically dismiss after timeout
- Backend cleanup happens when tokens become invalid

## Data Fetching Optimization

### Cached Data (No frequent API calls)

#### **NFL Week**
- **Cache Duration**: 24 hours
- **Update Schedule**: Daily at 8 AM with games refresh
- **Usage**: Used for all GraphQL player stats queries

#### **League Users** (Team Names, Display Names)
- **Cache Duration**: 30 minutes
- **Shared With**: Avatar endpoint cache
- **Usage**: User and opponent display names, custom team names

#### **League Info** (League Names)
- **Cache Duration**: 24 hours
- **Usage**: Real league names instead of "Fantasy Football"

#### **League Rosters** (Starter Lineups)
- **Cache Duration**: 10 minutes
- **Usage**: Determining starter players for scoring

### Fresh Data (Frequent API calls)

#### **Matchups** (Team Scores)
- **Frequency**: Every 60 seconds per active Live Activity
- **Reason**: Team scores change frequently during games
- **Cannot Cache**: Scores update in real-time

#### **Player Stats** (Individual Scoring)
- **Frequency**: Every 30 seconds (single GraphQL call)
- **Reason**: Individual player scores change frequently
- **Scope**: ALL players from ALL active matchups (user + opponent)
- **Optimization**: Consolidated call for all users across all matchups

## API Call Summary

### (Per Live Activity, Every 30 seconds):
- `get_nfl_state()` - Cached (1 call/day) ✅
- `get_matchups()` - Still called ✅
- `get_league_rosters()` - Cached (1 call/10min) ✅
- `get_league_users()` - Cached (1 call/30min) ✅
- `get_league_info()` - Cached (1 call/24hr) ✅
- **GraphQL Player Stats** - 1 call for ALL players across ALL matchups ✅

**3 devices = 3 matchup calls + 1 GraphQL call = 6 calls/minute = 360 calls/hour**
*Note: GraphQL efficiency means this scales to 100+ devices with same API usage*

## Daily Scheduled Tasks

### 8:00 AM Daily
- **Task**: `update_nfl_games()`
- **Data**: Today's NFL games from ESPN
- **Also Updates**: Global NFL week cache

### 8:05 AM Daily
- **Task**: `update_nfl_players()`
- **Data**: All NFL player information from Sleeper
- **Storage**: Cached to `players.json` file

### Every 5 Minutes
- **Task**: `check_and_start_live_activities()`
- **Purpose**: Auto-start Live Activities when games begin
- **Trigger**: Games starting within next 5 minutes

## Update Message Types

### Smart Player Notifications
- `"🔥 Josh Allen +6.2 pts"` (user's player scores big)
- `"⚡ Travis Kelce +8.4 pts"` (opponent's player scores big)
- **APNS Alert**: Triggered for 3+ point gains with sound notification
- **Threshold**: Only shows if point differential >0.1

### Game Events
- `"Game is live!"` (on start)
- `"Game completed!"` (on end)
- `"{team1} vs {team2} starting soon"` (auto-start)

## Performance Characteristics

### Scalability
- **10 users**: 120 GraphQL calls/hour + 600 matchup calls/hour
- **50 users**: 120 GraphQL calls/hour + 3000 matchup calls/hour
- **100 users**: 120 GraphQL calls/hour + 6000 matchup calls/hour
- **Key insight**: GraphQL scales perfectly, matchup calls scale linearly

### Responsiveness
- **Combined updates**: 30-second intervals (both player and team)
- **Smart notifications**: Immediate top scorer identification
- **Push alerts**: Instant APNS alerts for big plays (3+ pts)
- **Fresh data on app load**: <1 second
- **Cache hit response**: <100ms

### Reliability
- **Fallback caching**: Stale data served if API fails
- **Retry logic**: APNS notifications retried up to 3 times
- **Error handling**: Graceful degradation for all API failures

## Monitoring and Debugging

### Key Log Messages
- `"DEBUG: Found X active live activities"`
- `"Collected X unique players (including opponents) from Y active live activities"`
- `"Top performer: {player_name} (+X.X pts) [YOUR/OPP]"`
- `"Using cached league users for {league_id}"`
- `"Fetching fresh league info for {league_id}"`
- `"Updated global NFL week to: {week}"`
- `"Running combined player and team score update for X active activities"`

### Health Check Endpoints
- `/health` - Basic health status
- `/devices` - All registered devices and Live Activity status
- `/player-scores` - Current scoring data for all devices
- `/debug/config` - Debug configuration information

## Configuration Changes

To modify update frequencies:

1. Edit variables at top of `main.py`
2. Restart the backend server
3. Changes take effect immediately
4. Monitor logs to verify new intervals

**Example: Faster combined updates:**
```python
LIVE_ACTIVITY_UPDATE_INTERVAL = 15  # 15 seconds instead of 30
```

**Example: Less frequent combined updates:**
```python
LIVE_ACTIVITY_UPDATE_INTERVAL = 60  # 1 minute instead of 30 seconds
```

**Note**: Since player and team updates are now combined, changing this single value affects both update types.