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

##### Prerequisites
- AWS account with Lightsail access
- Apple Developer account with APNS keys
- SSH client
- Domain name (optional, for SSL)

##### Step 1: Create Lightsail Instance
1. Go to AWS Lightsail console
2. Click "Create instance"
3. Select "Linux/Unix" platform
4. Choose "Ubuntu 22.04 LTS"
5. Select instance plan ($5/month minimum recommended)
6. Create SSH key pair or use existing
7. Name your instance (e.g., "sleeper-api")
8. Click "Create instance"

##### Step 2: Configure Networking & Security
```bash
# In Lightsail console, go to "Networking" tab
# Add these firewall rules:
# - SSH (22) - Restrict to your IP only
# - HTTP (80) - Any IP (0.0.0.0/0)
# - HTTPS (443) - Any IP (0.0.0.0/0)
# - Custom TCP (8000) - Any IP (0.0.0.0/0) [TEMPORARY: Remove after Step 11]

# Note your instance's public IP address
```

##### Step 3: Initial Server Security Hardening
```bash
# Connect via SSH
ssh -i your-key.pem ubuntu@YOUR_PUBLIC_IP

# Update system immediately
sudo apt update && sudo apt upgrade -y

# Install security tools
sudo apt install fail2ban ufw -y

# Configure UFW firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 8000/tcp  # TEMPORARY: For direct testing only, remove in Step 11
sudo ufw --force enable

# Note: Port 8000 is temporary for testing the app directly
# Once nginx is configured as reverse proxy, we'll remove this rule
# The app will only accept connections from localhost (127.0.0.1)

# Configure fail2ban
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

##### Step 4: Install Dependencies
```bash
# Install required packages
sudo apt install python3 python3-pip python3-venv nginx git unattended-upgrades -y

# Configure automatic security updates
v```

##### Step 5: Create Non-Root User (Security Best Practice)
```bash
# Create application user
sudo adduser sleeper --disabled-password --gecos ""
sudo usermod -aG sudo sleeper

# Configure passwordless sudo for sleeper user
sudo echo "sleeper ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/sleeper
sudo chmod 440 /etc/sudoers.d/sleeper

# Copy SSH keys so you can SSH directly as sleeper user
sudo mkdir -p /home/sleeper/.ssh
sudo cp ~/.ssh/authorized_keys /home/sleeper/.ssh/
sudo chown -R sleeper:sleeper /home/sleeper/.ssh
sudo chmod 700 /home/sleeper/.ssh
sudo chmod 600 /home/sleeper/.ssh/authorized_keys

# Now you can SSH directly as sleeper user:
# ssh -i your-key.pem sleeper@YOUR_PUBLIC_IP

# Disable root SSH access for security
sudo vim /etc/ssh/sshd_config
# Find and change: PermitRootLogin no
# Find and change: PasswordAuthentication no
# Save and restart SSH
sudo systemctl restart ssh

# Switch to application user
sudo su - sleeper
```

##### Step 6: Deploy Application
```bash
# Clone repository as sleeper user
git clone https://github.com/jdegrand/sleeper-live-activity.git
cd sleeper-live-activity/SleeperLiveActivityApi

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

##### Step 7: Secure Configuration
```bash
# Create secure environment file
vim .env

# Add configuration with secure permissions:
```
```env
ENVIRONMENT=production
HOST=127.0.0.1  # Only bind to localhost (nginx proxy)
PORT=8000
LOG_LEVEL=INFO

# APNS Configuration
APNS_KEY_ID=your_key_id
APNS_TEAM_ID=your_team_id
APNS_BUNDLE_ID=com.yourcompany.sleeperliveactivity
APNS_KEY_PATH=/home/sleeper/sleeper-live-activity/SleeperLiveActivityApi/AuthKey_KEYID.p8
APNS_USE_SANDBOX=false
```

```bash
# Secure environment file
chmod 600 .env

# Upload APNS key directly to API folder (use scp)
# scp -i your-key.pem AuthKey_KEYID.p8 sleeper@YOUR_PUBLIC_IP:/home/sleeper/sleeper-live-activity/SleeperLiveActivityApi/
# Or if already uploaded to /tmp:
# sudo mv /tmp/AuthKey_KEYID.p8 /home/sleeper/sleeper-live-activity/SleeperLiveActivityApi/
# sudo chown sleeper:sleeper /home/sleeper/sleeper-live-activity/SleeperLiveActivityApi/AuthKey_KEYID.p8
chmod 600 AuthKey_KEYID.p8
```

##### Step 8: Create SystemD Service
```bash
# Create service file (as ubuntu user with sudo)
exit  # Return to ubuntu user
sudo vim /etc/systemd/system/sleeper-api.service
```

```ini
[Unit]
Description=Sleeper Live Activity API
After=network.target

[Service]
Type=simple
User=sleeper
Group=sleeper
WorkingDirectory=/home/sleeper/sleeper-live-activity/SleeperLiveActivityApi
Environment=PATH=/home/sleeper/sleeper-live-activity/SleeperLiveActivityApi/venv/bin
ExecStart=/home/sleeper/sleeper-live-activity/SleeperLiveActivityApi/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Production security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths=/home/sleeper/sleeper-live-activity/SleeperLiveActivityApi
PrivateDevices=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictRealtime=true
RestrictSUIDSGID=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictNamespaces=true
SystemCallArchitectures=native

[Install]
WantedBy=multi-user.target
```

##### Step 9: Configure Nginx with Security Headers
```bash
# First, configure nginx security settings
sudo vim /etc/nginx/nginx.conf
# Find the http block and add these lines (without the # symbols):
```

Add these lines in the http block:
```
server_tokens off;
client_max_body_size 1M;
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
```

```bash

# Now create the site config
sudo vim /etc/nginx/sites-available/sleeper-api
```

```nginx
server {
    listen 80;
    server_name YOUR_PUBLIC_IP;  # Replace with domain if you have one

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    add_header Content-Security-Policy "default-src 'self'";

    # Rate limiting
    limit_req zone=api burst=20 nodelay;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Security
        proxy_hide_header X-Powered-By;
        proxy_set_header X-Forwarded-Host $host;

        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Block common attack paths
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

```bash
# Enable site and test configuration
sudo ln -s /etc/nginx/sites-available/sleeper-api /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
```

##### Step 10: SSL/TLS Setup (Recommended)
```bash
# Install Certbot for Let's Encrypt
sudo apt install certbot python3-certbot-nginx -y

# If you have a domain name:
sudo certbot --nginx -d yourdomain.com
# Certbot will automatically update your nginx config for SSL

# Or create self-signed certificate for IP access:
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/sleeper-selfsigned.key \
    -out /etc/ssl/certs/sleeper-selfsigned.crt

# For self-signed certificate, update nginx config:
sudo vim /etc/nginx/sites-available/sleeper-api
# Replace the server block with:
```

```nginx
server {
    listen 80;
    server_name YOUR_PUBLIC_IP;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name YOUR_PUBLIC_IP;

    ssl_certificate /etc/ssl/certs/sleeper-selfsigned.crt;
    ssl_certificate_key /etc/ssl/private/sleeper-selfsigned.key;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";
    add_header Content-Security-Policy "default-src 'self'";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Rate limiting
    limit_req zone=api burst=20 nodelay;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Security
        proxy_hide_header X-Powered-By;
        proxy_set_header X-Forwarded-Host $host;

        # Timeouts
        proxy_connect_timeout 30s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    # Block common attack paths
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
```

```bash
# Test and reload nginx
sudo nginx -t
sudo systemctl reload nginx
```

##### Step 11: Start and Enable Services
```bash
# Start services
sudo systemctl enable sleeper-api nginx
sudo systemctl start sleeper-api nginx

# Check status
sudo systemctl status sleeper-api
sudo systemctl status nginx

# Remove temporary firewall rule (port 8000 no longer needed)
# App now only accepts connections from nginx on localhost
sudo ufw delete allow 8000/tcp
sudo ufw status  # Verify port 8000 is removed
```

##### Step 12: Security Monitoring Setup
```bash
# Install log monitoring
sudo apt install logwatch -y
# When prompted for mail server configuration:
# - Select: "Local only"
# - System mail name: use the default hostname (e.g., ip-172-26-10-93.us-west-2.compute.internal)

# Configure log rotation
sudo vim /etc/logrotate.d/sleeper-api
```

```
/var/log/sleeper-api.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    copytruncate
}
```

##### Step 13: Final Security Verification
```bash
# Test firewall status
sudo ufw status verbose

# Test fail2ban status
sudo fail2ban-client status

# Check for listening ports
sudo apt install -y net-tools
sudo netstat -tlnp

# Test API endpoint (expect 301 redirect if SSL is configured)
curl -I http://YOUR_PUBLIC_IP/
# If you get 301 redirect, test HTTPS:
curl -I -k https://YOUR_PUBLIC_IP/

# Check logs
sudo journalctl -u sleeper-api -f
```

##### Step 14: Backup and Monitoring
```bash
# Create backup script
vim /home/sleeper/backup.sh
```

```bash
#!/bin/bash
# Backup script for Sleeper API
tar -czf "/home/sleeper/backup-$(date +%Y%m%d).tar.gz" \
    /home/sleeper/sleeper-live-activity \
    /home/sleeper/.env \
    /home/sleeper/apns
```

```bash
chmod +x /home/sleeper/backup.sh

# Add to crontab for weekly backups
(crontab -l 2>/dev/null; echo "0 2 * * 0 /home/sleeper/backup.sh") | crontab -
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

## Security Hardening Checklist

### Server Security
- [ ] UFW firewall enabled with minimal open ports
- [ ] Fail2ban configured for intrusion prevention
- [ ] Automatic security updates enabled
- [ ] Non-root user created for application
- [ ] SSH access restricted to specific IPs
- [ ] Strong SSH key authentication (disable password auth)
- [ ] Regular security updates scheduled

### Application Security
- [ ] Environment variables properly secured (600 permissions)
- [ ] APNS keys stored in secure directory (700/600 permissions)
- [ ] Application runs as non-privileged user
- [ ] SystemD service hardened with security options
- [ ] Rate limiting configured in nginx
- [ ] Security headers implemented
- [ ] Log rotation configured
- [ ] Regular backups scheduled

### Network Security
- [ ] SSL/TLS certificate configured
- [ ] Security headers (HSTS, CSP, etc.) enabled
- [ ] Rate limiting per IP address
- [ ] Nginx security configurations applied
- [ ] Unnecessary services disabled
- [ ] Port scanning protection (fail2ban)

### Monitoring & Maintenance
- [ ] Log monitoring configured
- [ ] Failed login attempt monitoring
- [ ] Disk space monitoring
- [ ] Service health monitoring
- [ ] Regular security audit schedule
- [ ] Incident response plan documented

### Post-Deployment Security Verification
```bash
# Run these commands to verify security setup:

# 1. Check firewall status
sudo ufw status verbose

# 2. Verify fail2ban is protecting SSH
sudo fail2ban-client status sshd

# 3. Check for unnecessary open ports
sudo netstat -tlnp

# 4. Verify SSL configuration (if domain configured)
curl -I https://yourdomain.com

# 5. Test rate limiting
for i in {1..25}; do curl -s -o /dev/null -w "%{http_code}\n" http://YOUR_IP/; done

# 6. Check service permissions
ps aux | grep sleeper-api

# 7. Verify file permissions
ls -la /home/sleeper/.env
ls -la /home/sleeper/apns/

# 8. Check for security updates
sudo apt list --upgradable
```

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

## Switching Between Development and Production Modes

### Switch to Development Mode (Sandbox APNS)
```bash
# 1. SSH to your server
ssh -i your-key.pem ubuntu@YOUR_PUBLIC_IP

# 2. Switch to sleeper user and edit environment
sudo su - sleeper
cd sleeper-live-activity/SleeperLiveActivityApi/
vim .env

# 3. Change APNS setting:
# APNS_USE_SANDBOX=true

# 4. Restart the service
exit  # Back to ubuntu user
sudo systemctl restart sleeper-api
sudo systemctl status sleeper-api

# 5. Verify the change in logs
sudo journalctl -u sleeper-api --since "1 minute ago"
```

### Switch to Production Mode (Production APNS)
```bash
# 1. SSH to your server
ssh -i your-key.pem ubuntu@YOUR_PUBLIC_IP

# 2. Switch to sleeper user and edit environment
sudo su - sleeper
cd sleeper-live-activity/SleeperLiveActivityApi/
vim .env

# 3. Change APNS setting:
# APNS_USE_SANDBOX=false

# 4. Restart the service
exit  # Back to ubuntu user
sudo systemctl restart sleeper-api
sudo systemctl status sleeper-api

# 5. Verify the change in logs
sudo journalctl -u sleeper-api --since "1 minute ago"
```

### iOS App Configuration
Make sure your iOS app matches the server mode:

#### For Development Testing:
```swift
// In your iOS app, use Debug configuration
#if DEBUG
let apnsEnvironment = "development"  // Matches APNS_USE_SANDBOX=true
#else
let apnsEnvironment = "production"
#endif
```

#### Build Configuration in Xcode:
- **Development**: Product → Scheme → Edit Scheme → Run → Debug
- **Production**: Product → Scheme → Edit Scheme → Run → Release

#### For Production:
```swift
// Build in Release mode for production APNS
// Matches APNS_USE_SANDBOX=false on server
```

### Quick Mode Check
```bash
# Check current APNS mode
ssh -i your-key.pem ubuntu@YOUR_PUBLIC_IP
sudo su - sleeper
cd sleeper-live-activity/SleeperLiveActivityApi/
grep APNS_USE_SANDBOX .env

# Check service status
exit
sudo systemctl status sleeper-api
```

### Important Notes:
- **Development mode**: Use when testing with Xcode builds to physical device
- **Production mode**: Use when deploying to TestFlight or App Store
- **Always restart the service** after changing APNS mode
- **iOS app build configuration** must match server APNS mode for push notifications to work
