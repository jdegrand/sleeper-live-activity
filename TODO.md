# Sleeper Live Activity - TODO List

## Security Issues

### Critical Security Vulnerabilities
- [x] **API Authentication**: Add authentication to prevent unauthorized Live Activity starts
  - [x] ~~Option A: API Key authentication for all endpoints~~ **IMPLEMENTED**
  - [ ] Option B: Device token validation (require push token to prove ownership)
  - [ ] Option C: User-based authorization system
  - [ ] Option D: Signed requests with device-specific keys
- [ ] **Rate Limiting**: Implement rate limiting to prevent endpoint spam
- [ ] **Device ID Protection**: Prevent device ID enumeration attacks
- [ ] **Cross-user Access Control**: Ensure users can only control their own devices

## UI/UX Improvements

### Live Activity & Widget
- [ ] **Custom App Icon**: Create cat-shaped icon similar to Telegram/Sleeper style
- [ ] **Live Activity End Message**: Fix message that doesn't disappear after 1 minute
- [ ] **Banner Positioning**: Move banner to bottom right, centered with "last updated" timestamp
- [ ] **Scrolling Team Names**: Implement scrolling for long team names that don't fit
- [ ] **Clear End Live Activity**: Figure out if this ends a live activity or not

### App Behavior
- [ ] **Prevent Duplicate Entries**: Stop app from creating new device entries on each restart
  - [ ] Check if device already exists before creating new entry
  - [ ] Edit existing entry instead of creating duplicate
- [ ] **Device Management**: Clean up stale/duplicate device entries
  - [ ] Remove stale entries from devices list automatically
  - [ ] Add manual remove endpoint for device cleanup
  - [ ] Add device list cleanup UI in app

## Backend Improvements

### Live Activity Management
- [x] **Smart Game Start Notifications**: Only notify users who have players in games that are starting
- [x] **Optimized User Filtering**: Batch API calls by league to reduce load for multiple users
- [x] **Dynamic Game End Scheduler**: Only run ending checks when games are live (status: "in")
- [x] **Startup Live Game Detection**: Check for live games on API restart and initialize ending scheduler
- [ ] **Live Activity Persistence**: Restore live activities after API restart (currently lost on restart)
- [ ] **Game Status Monitoring**: Add more granular game status tracking (pre, in, post, suspended)

### Device Management
- [ ] **Stale Device Cleanup**: Automatically remove inactive devices after X days
- [ ] **Device Remove Endpoint**: Add `DELETE /device/{device_id}` endpoint
- [ ] **Device Ownership Tracking**: Link devices to specific users for better management
- [ ] **Device Health Check**: Ping devices periodically and mark inactive ones

### API Enhancements
- [x] **Authentication Middleware**: ~~Implement secure authentication system~~ **IMPLEMENTED**
- [ ] **Request Validation**: Add proper input validation and sanitization
- [ ] **Error Handling**: Improve error responses and logging
- [x] **API Documentation**: ~~Update API docs with security requirements~~ **IMPLEMENTED**

## Testing & Deployment

### Security Testing
- [ ] **Penetration Testing**: Test all security vulnerabilities listed above
- [ ] **Authentication Testing**: Verify auth system works correctly
- [ ] **Rate Limiting Testing**: Ensure rate limits prevent abuse

### Production Readiness
- [ ] **APNS Production**: Resolve production vs development APNS token issues
- [ ] **SSL/TLS**: Ensure all communication uses proper encryption
- [ ] **Monitoring**: Add security monitoring and alerting

### API Restart Behavior
- [x] **Live Game Detection**: API checks for live games on startup and starts ending scheduler if needed
- [x] **Game Data Refresh**: Fetches latest game data immediately on startup
- [ ] **Live Activity Recovery**: Active live activities are lost on restart (in-memory only)
- [ ] **User Session Persistence**: User configs persist but live activity states don't

### API Security Configuration
- [x] **Global API Key Protection**: All endpoints require `X-API-Key` header
- [x] **Development Mode**: API runs unprotected if `API_KEY` environment variable not set
- [x] **Health Check Exception**: `/health` and `/nfl-state` endpoints accessible without auth
- [x] **CORS Support**: `X-API-Key` header allowed in CORS configuration
- [x] **iOS App Integration**: App reads API key from `Config.plist` (not committed to git)
- [x] **Secure Storage**: `Config.plist` added to `.gitignore` for security

#### Server Setup:
```bash
# Set environment variable
export API_KEY="your-secret-api-key-here"

# Make authenticated requests
curl -H "X-API-Key: your-secret-api-key-here" \
     -X POST http://localhost:8000/register \
     -H "Content-Type: application/json" \
     -d '{"user_id": "123", "league_id": "456", ...}'
```

#### iOS App Setup:
```bash
# 1. Copy the example config file
cp SleeperLiveActivityApp/SleeperLiveActivityApp/Config.plist.example \
   SleeperLiveActivityApp/SleeperLiveActivityApp/Config.plist

# 2. Edit Config.plist and set your API key
# <key>API_KEY</key>
# <string>your-secret-api-key-here</string>

# 3. Build and run the app - it will automatically send the API key
```

## Priority Order

### P0 - Critical (Security)
1. ~~API Authentication implementation~~ **COMPLETED**
2. Device ownership validation
3. Rate limiting

### P1 - High (User Experience)
1. Prevent duplicate device entries
2. Live Activity end message fix
3. Custom cat-shaped icon

### P2 - Medium (Polish)
1. Banner positioning improvements
2. Scrolling team names
3. Device cleanup endpoints

### P3 - Low (Nice to have)
1. Advanced security features
2. Comprehensive monitoring
3. Performance optimizations

---

**Note**: Security issues should be addressed before any production deployment or public release.