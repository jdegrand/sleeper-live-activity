# Sleeper Live Activity iOS App

A comprehensive iOS app that provides Live Activity integration for Sleeper Fantasy Football, displaying real-time scoring information on the Lock Screen and Dynamic Island when your starting players are actively playing in NFL games.

## Features

### 🏈 Live Activity Integration
- **Lock Screen Display**: Shows current points, opponent score, and active player count
- **Dynamic Island Support**: Compact and expanded views with real-time updates
- **Automatic Lifecycle**: Starts when players are active, ends 30 minutes after last player finishes

### 📱 User Interface
- **Modern SwiftUI Design**: Clean, intuitive interface with SF Symbols
- **Settings Configuration**: Easy setup for Sleeper User ID and League ID
- **Real-time Status**: Live updates of activity status and scoring data
- **Error Handling**: Comprehensive error messages and validation

### 🔄 Background Monitoring
- **Game State Monitoring**: Automatically detects when your players are in active games
- **Smart Notifications**: Push-driven updates for optimal battery efficiency
- **Data Caching**: Efficient caching of player and league data

## Requirements

- iOS 16.1 or later (for Live Activities)
- iPhone with Dynamic Island support (iPhone 14 Pro/Pro Max or later) for full Dynamic Island experience
- Active Sleeper Fantasy Football account
- Backend API server running (see SleeperLiveActivityApi)

## Setup

### 1. Configure Backend
First, ensure the backend API server is running:
```bash
cd ../SleeperLiveActivityApi
pip install -r requirements.txt
python main.py
```

### 2. iOS App Configuration
1. Open the app
2. Tap "Configure Settings" or the Settings button
3. Enter your Sleeper User ID and League ID
4. Save the configuration

### 3. Finding Your Sleeper IDs

#### User ID
1. Go to your Sleeper profile in the app or web
2. Look at the URL: `https://sleeper.app/user/YOUR_USER_ID`
3. Your User ID is the number/string after `/user/`

#### League ID
1. Open your league in Sleeper
2. Go to League Settings
3. The League ID is displayed at the bottom or visible in the URL

## How It Works

### Live Activity Lifecycle
1. **Pre-Game**: App monitors your starting lineup
2. **Game Start**: Live Activity automatically starts when any starter's game begins
3. **In-Game**: Real-time updates every 1-5 minutes via push notifications
4. **Post-Game**: Activity continues for 30 minutes after last starter finishes
5. **Auto-End**: Activity ends when no starters are active + 30 minute grace period

### Architecture
- **Main App**: User configuration and manual controls
- **GameStateMonitor**: Background monitoring of NFL games and player status
- **SleeperViewModel**: Data management and Live Activity lifecycle
- **SleeperAPIClient**: Communication with backend API
- **Live Activity Widget**: Lock Screen and Dynamic Island UI

## Key Components

### ContentView
Main app interface showing:
- User configuration status
- Live Activity status and controls
- Current scoring data
- Settings access

### SettingsView
Configuration interface for:
- Sleeper User ID input
- League ID input
- Credential validation
- Setup instructions

### Live Activity Widget
Displays on Lock Screen and Dynamic Island:
- **Lock Screen**: Full scoring layout with team comparison
- **Dynamic Island Expanded**: Detailed view with all stats
- **Dynamic Island Compact**: Minimal score display
- **Dynamic Island Minimal**: Simple activity indicator

### GameStateMonitor
Background service that:
- Monitors NFL game states
- Tracks user's active players
- Triggers automatic Live Activity start/stop
- Manages 30-minute timeout logic

## Permissions Required

- **Live Activities**: Required for Lock Screen and Dynamic Island display
- **Push Notifications**: Required for real-time scoring updates
- **Background App Refresh**: Recommended for optimal monitoring

## API Integration

The app communicates with the backend API for:
- User registration and authentication
- Sleeper data fetching (users, leagues, rosters, matchups)
- Live Activity management
- Push notification delivery

## Customization

### Styling
- Colors and fonts can be customized in the SwiftUI views
- SF Symbols used throughout for consistency
- Supports both light and dark mode

### Timing
- Monitoring interval: 5 minutes (configurable in GameStateMonitor)
- Live Activity timeout: 30 minutes (configurable)
- Update frequency: 1-5 minutes via backend

## Troubleshooting

### Live Activity Not Starting
1. Check that Live Activities are enabled in Settings > Face ID & Passcode > Live Activities
2. Verify your Sleeper credentials are correct
3. Ensure backend API is running and accessible
4. Check that you have active players in current games

### No Updates Received
1. Verify push notifications are enabled
2. Check backend API logs for errors
3. Ensure app has background refresh enabled
4. Restart the Live Activity if needed

### Configuration Issues
1. Double-check User ID and League ID format
2. Verify you're using the correct league (current season)
3. Ensure you're the owner of the roster in the league

## Development

### Building
1. Open `SleeperLiveActivityApp.xcodeproj` in Xcode
2. Select your development team
3. Build and run on device (Live Activities require physical device)

### Testing
- Live Activities can only be tested on physical devices
- Use Xcode's Activity Simulator for basic testing
- Backend API includes test endpoints for development

## Privacy & Security

- User credentials are stored locally using UserDefaults
- No sensitive data is transmitted to third parties
- All API communication uses HTTPS
- Push tokens are securely managed by the backend

## Support

For issues or questions:
1. Check the backend API logs
2. Verify Sleeper API status
3. Ensure all permissions are granted
4. Test with a fresh app installation
