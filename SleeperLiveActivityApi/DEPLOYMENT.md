# Sleeper Live Activity - Deployment Guide

This guide provides step-by-step instructions for deploying and running the complete Sleeper Live Activity system.

## Prerequisites

### System Requirements
- **Backend**: Python 3.8+ (avoid 3.13 due to dependency conflicts)
- **iOS App**: Xcode 14+, iOS 16.1+, Physical iPhone (Live Activities require device testing)
- **Apple Developer Account**: Required for Live Activities and push notifications

### Hardware Requirements
- **iPhone**: iPhone 14 Pro/Pro Max or later for full Dynamic Island support
- **Development Mac**: macOS 13+ with Xcode 14+

## Backend Deployment

### 1. Environment Setup
```bash
# Clone or navigate to the backend directory
cd SleeperLiveActivityApi

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration
Create a `.env` file for production settings:
```bash
# .env file
ENVIRONMENT=production
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# APNS Configuration (required for production)
APNS_KEY_ID=your_key_id
APNS_TEAM_ID=your_team_id
APNS_BUNDLE_ID=com.yourcompany.sleeperliveactivity
APNS_KEY_PATH=path/to/AuthKey_KEYID.p8
APNS_USE_SANDBOX=false
```

### 3. Start the Server
```bash
# Development
python3 main.py

# Production with custom settings
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4. Verify Backend
Test the API endpoints:
```bash
# Health check
curl http://localhost:8000/docs

# Test Sleeper API integration
curl http://localhost:8000/state/nfl
```

## iOS App Deployment

### 1. Xcode Configuration

#### Bundle Identifier
1. Open `SleeperLiveActivityApp.xcodeproj`
2. Select project → Target → General
3. Set unique Bundle Identifier: `com.yourcompany.sleeperliveactivity`

#### Signing & Capabilities
1. Select your Apple Developer Team
2. Add capabilities:
   - **Push Notifications**
   - **Background Modes**: Background fetch, Remote notifications
   - **Live Activities** (if available in capabilities list)

#### Info.plist Verification
Ensure these keys are present in Info.plist:
```xml
<key>NSSupportsLiveActivities</key>
<true/>
<key>NSSupportsLiveActivitiesFrequentUpdates</key>
<true/>
<key>UIBackgroundModes</key>
<array>
    <string>background-fetch</string>
    <string>remote-notification</string>
</array>
```

### 2. APNS Certificate Setup

#### Generate APNS Key
1. Go to [Apple Developer Portal](https://developer.apple.com)
2. Certificates, Identifiers & Profiles → Keys
3. Create new key with "Apple Push Notifications service (APNs)"
4. Download the `.p8` file
5. Note the Key ID and Team ID

#### Configure Backend
Update your backend with APNS credentials:
```python
# In main.py, update LiveActivityManager
class LiveActivityManager:
    def __init__(self):
        self.apns_client = APNsClient(
            key_path="path/to/AuthKey_KEYID.p8",
            key_id="YOUR_KEY_ID",
            team_id="YOUR_TEAM_ID",
            use_sandbox=False  # True for development
        )
```

### 3. Build and Deploy

#### Development Testing
```bash
# Build for device (Live Activities require physical device)
1. Connect iPhone via USB
2. Select device in Xcode
3. Build and Run (⌘R)
```

#### App Store Deployment
```bash
# Archive for distribution
1. Product → Archive
2. Distribute App → App Store Connect
3. Upload to TestFlight or App Store
```

## Configuration Guide

### 1. Finding Sleeper Credentials

#### User ID
```bash
# Method 1: Profile URL
# Go to sleeper.app/user/YOUR_USER_ID
# The number after /user/ is your User ID

# Method 2: API lookup by username
curl "https://api.sleeper.app/v1/user/your_username"
```

#### League ID
```bash
# Method 1: League URL
# Go to sleeper.app/leagues/LEAGUE_ID
# The number in the URL is your League ID

# Method 2: Get from user leagues
curl "https://api.sleeper.app/v1/user/USER_ID/leagues/nfl/2024"
```

### 2. App Configuration
1. Open the iOS app
2. Tap "Configure Settings"
3. Enter your Sleeper User ID and League ID
4. Save configuration
5. Grant permissions when prompted

## Testing the Complete Flow

### 1. Backend Testing
```bash
# Test user registration
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "YOUR_USER_ID",
    "league_id": "YOUR_LEAGUE_ID", 
    "push_token": "test_token",
    "device_id": "test_device"
  }'

# Test Live Activity start
curl -X POST http://localhost:8000/live-activity/start-by-id/test_device
```

### 2. iOS App Testing
1. Configure app with valid Sleeper credentials
2. Tap "Start Live Activity"
3. Verify Live Activity appears on Lock Screen
4. Test Dynamic Island (iPhone 14 Pro+ only)

### 3. End-to-End Testing
1. Start Live Activity from iOS app
2. Verify backend receives registration
3. Check backend logs for scoring updates
4. Confirm Live Activity updates on device

## Production Deployment

### 1. Backend Hosting Options

#### Option A: Cloud Hosting (Recommended)
```bash
# Deploy to services like:
# - AWS EC2 Lightsail (Recommended - simple & cost-effective)
# - Heroku
# - Railway
# - DigitalOcean App Platform
# - AWS Elastic Beanstalk

# Example Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "main.py"]
```

#### AWS EC2 Lightsail Deployment (Detailed)
```bash
# 1. Create Lightsail instance (Ubuntu 22.04 LTS, $5/month minimum)
# 2. Connect via SSH and install dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv nginx -y

# 3. Clone your repository
git clone https://github.com/yourusername/sleeper-live-activity.git
cd sleeper-live-activity/SleeperLiveActivityApi

# 4. Set up Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Configure environment variables
cp .env.example .env
# Edit .env with your APNS credentials

# 6. Create systemd service for auto-restart
sudo nano /etc/systemd/system/sleeper-api.service

# 7. Configure nginx reverse proxy
sudo nano /etc/nginx/sites-available/sleeper-api

# 8. Enable and start services
sudo systemctl enable sleeper-api nginx
sudo systemctl start sleeper-api nginx
```

#### Option B: VPS Deployment
```bash
# Install dependencies on Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip nginx

# Setup reverse proxy with Nginx
# Configure SSL with Let's Encrypt
# Use systemd for process management
```

### 2. iOS App Store Submission
1. Complete App Store Connect setup
2. Upload via Xcode Archive
3. Submit for review with Live Activity description
4. Include privacy policy for data usage

## Monitoring and Maintenance

### 1. Backend Monitoring
```bash
# Log monitoring
tail -f /var/log/sleeper-api.log

# API health checks
curl http://your-domain.com/health

# Monitor Sleeper API rate limits
# Stay under 1000 calls/minute
```

### 2. iOS App Analytics
- Monitor Live Activity engagement
- Track push notification delivery rates
- Monitor app crashes and performance

## Troubleshooting

### Common Issues

#### Backend Issues
```bash
# Port already in use
lsof -ti:8000 | xargs kill -9

# Dependencies not installing
pip install --upgrade pip setuptools wheel

# APNS authentication errors
# Verify key file path and permissions
# Check Key ID and Team ID match
```

#### iOS Issues
```bash
# Live Activities not appearing
# 1. Check device settings: Settings > Face ID & Passcode > Live Activities
# 2. Verify iOS 16.1+ and supported device
# 3. Check Xcode console for errors

# Push notifications not working
# 1. Verify APNS certificate configuration
# 2. Check app permissions in Settings
# 3. Test with development APNS first
```

### Debug Mode
Enable debug logging in both backend and iOS app:

#### Backend Debug
```python
# In main.py
logging.basicConfig(level=logging.DEBUG)
```

#### iOS Debug
```swift
// Add to SleeperViewModel
#if DEBUG
print("Debug: \(message)")
#endif
```

## Security Considerations

### 1. API Security
- Use HTTPS in production
- Implement rate limiting
- Validate all input data
- Store APNS keys securely

### 2. iOS Security
- Never hardcode API keys
- Use Keychain for sensitive data
- Validate server certificates
- Implement certificate pinning for production

## Support and Updates

### Maintenance Schedule
- **Daily**: Monitor API health and error rates
- **Weekly**: Check Sleeper API changes and NFL schedule
- **Seasonally**: Update for new NFL season data

### Scheduled Tasks Information
- **8:00 AM Daily**: NFL games data refresh (ESPN API)
- **8:05 AM Daily**: NFL players data refresh (Sleeper API)
- **Every 30 seconds**: Live Activity updates (when active)
- **Every 5 minutes**: Game start detection

**Important**: If your server starts after 8:00 AM, the system will:
- ✅ **Immediately fetch games data on startup** (regardless of time)
- ✅ **Load player data from cache** (players.json file)
- ✅ **Continue normal operation** without waiting for next 8 AM
- ⚠️ **Miss scheduled 8 AM refresh** but compensate with startup fetch

**EC2 Lightsail Compatibility**: ✅ **Fully supported**
- All dependencies (Python 3.8+, Flask, APScheduler) work perfectly
- Background scheduler runs continuously
- SystemD service ensures auto-restart on server reboot
- Nginx handles SSL termination and reverse proxy

### Version Updates
- Backend: Use semantic versioning
- iOS: Follow App Store guidelines
- Coordinate updates for API compatibility

This deployment guide ensures a smooth setup and operation of the Sleeper Live Activity system in production environments.
