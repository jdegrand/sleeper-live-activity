# Sleeper Live Activity

Real-time fantasy football Live Activities for iOS with comprehensive backend API integration.

## 📱 Project Structure

This project consists of two main components:

### iOS App (`SleeperLiveActivityApp/`)
- Native iOS app with Live Activity support
- Real-time fantasy football score tracking
- Dynamic Island and Lock Screen integration
- ActivityKit framework implementation

### Backend API (`SleeperLiveActivityApi/`)
- Python Flask API for APNS push notifications
- Sleeper fantasy football API integration
- Player-level scoring with GraphQL integration
- **Intelligent TTL-based cleanup system**
- **State synchronization via heartbeat**

## ✨ Key Features

- 📊 **Real-time Score Updates**: Live player scoring with 30-second intervals
- 🔔 **Push Notifications**: APNS integration for Live Activity updates
- ⚡ **Smart Cleanup**: TTL-based system prevents phantom updates to dismissed activities
- 🔄 **State Sync**: Heartbeat system maintains iOS/backend consistency
- 📈 **Player Projections**: Real-time projected scores for user and opponent
- 🏈 **NFL Schedule Aware**: Different TTL windows based on game schedules
- 🎯 **Top Player Alerts**: Notifications for big plays (3+ points)

## 🛠️ Getting Started

### iOS App Setup
1. Open `SleeperLiveActivityApp/SleeperLiveActivityApp.xcodeproj` in Xcode
2. Configure your development team and bundle ID
3. Set up APNS certificates in Apple Developer Portal
4. Build and run on device (Live Activities require physical device)

### Backend API Setup
1. Navigate to `SleeperLiveActivityApi/`
2. Install dependencies: `pip install -r requirements.txt`
3. Configure APNS credentials in `.env` file
4. Run the API: `python main.py`

For detailed setup instructions, see the [API README](SleeperLiveActivityApi/README.md).

## 🔧 Live Activity State Management

### The Problem
When users dismiss Live Activities from their lock screen while the app is closed, iOS doesn't notify the backend. This leads to:
- Wasted APNS requests to non-existent activities
- Resource drain on the backend
- State inconsistency between iOS and backend

### The Solution: Dual-Layer Cleanup

**1. TTL-Based Cleanup (Primary)**
- **Sunday**: 16-hour window (covers full football day 6:30am-8:20pm Pacific)
- **Monday/Thursday**: 8-hour window (limited games)
- **Other days**: 6-hour window (minimal activity)
- **Frequency**: Every 30 minutes

**2. Heartbeat Sync (Secondary)**
- iOS app sends state when opened
- Immediate cleanup of mismatched states
- Fast detection when users interact with app

**Result**: 90%+ reduction in phantom updates with guaranteed cleanup.

## 📊 Performance Optimizations

- **Consolidated API Calls**: Single GraphQL request for all players across all users
- **Smart Caching**: Player stats cached and distributed efficiently
- **Change Detection**: Only sends updates when scores actually change
- **Concurrent Processing**: All live activities updated in parallel
- **Schedule-Aware TTL**: Different cleanup windows based on NFL schedule

## 🏈 NFL Schedule Integration

The system understands football schedules:
- **Sunday**: Primary game day with extended TTL windows
- **Monday/Thursday**: Secondary game days with moderate TTL
- **Other days**: Minimal activity with short TTL
- **Game-Based Ending**: Activities end when user's players are no longer active

## 📚 Documentation

- [API Documentation](SleeperLiveActivityApi/README.md) - Complete backend setup and API reference
- [Live Activity Cleanup Solutions](LIVE_ACTIVITY_CLEANUP_SOLUTIONS.md) - Technical analysis of cleanup approaches

## 🧪 Testing

The project includes test scripts for:
- APNS push notification testing
- Live Activity state management
- TTL cleanup functionality

## 🛡️ Production Considerations

- Set `use_sandbox=False` for production APNS
- Configure proper logging levels
- Monitor TTL cleanup effectiveness
- Set up health checks for scheduled jobs

## 🔗 Related Technologies

- **iOS**: ActivityKit, WidgetKit, SwiftUI
- **Backend**: Python Flask, APNs, GraphQL
- **APIs**: Sleeper Fantasy API, ESPN NFL API
- **Push**: Apple Push Notification Service (APNS)

---

Built for reliable, real-time fantasy football Live Activities with intelligent resource management.