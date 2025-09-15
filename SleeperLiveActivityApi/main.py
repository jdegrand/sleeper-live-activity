from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import threading
import time
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime, timedelta
import json
import os
import asyncio
import base64
from apscheduler.schedulers.background import BackgroundScheduler
from aioapns import APNs, NotificationRequest, PushType
from aioapns.common import NotificationResult
import aiohttp
from PIL import Image
import io
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Enable CORS for all routes with specific settings
cors = CORS(app, resources={
    r"/*": {
        "origins": ["*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Global state management
class AppState:
    def __init__(self):
        self.active_live_activities: Dict[str, Dict] = {}
        self.player_cache: Dict[str, Dict] = {}
        self.nfl_state_cache: Dict = {}
        self.user_configs: Dict[str, Dict] = {}
        self.push_tokens: Dict[str, str] = {}
        self.avatar_cache: Dict[str, str] = {}  # URL -> base64 data
        self.last_scores: Dict[str, Dict] = {}  # device_id -> last score data

app_state = AppState()
scheduler = BackgroundScheduler()

# Data models as simple classes
class UserConfig:
    def __init__(self, user_id: str, league_id: str, push_token: str, device_id: str):
        self.user_id = user_id
        self.league_id = league_id
        self.push_token = push_token
        self.device_id = device_id
    
    def to_dict(self):
        return {
            'user_id': self.user_id,
            'league_id': self.league_id,
            'push_token': self.push_token,
            'device_id': self.device_id
        }

class LiveActivityData:
    def __init__(self, total_points: float, active_players: int, team_name: str, 
                 opponent_points: float, time_remaining: str, game_status: str):
        self.total_points = total_points
        self.active_players = active_players
        self.team_name = team_name
        self.opponent_points = opponent_points
        self.time_remaining = time_remaining
        self.game_status = game_status
    
    def to_dict(self):
        return {
            'total_points': self.total_points,
            'active_players': self.active_players,
            'team_name': self.team_name,
            'opponent_points': self.opponent_points,
            'time_remaining': self.time_remaining,
            'game_status': self.game_status
        }

class SleeperAPIClient:
    BASE_URL = "https://api.sleeper.app/v1"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 30
    
    def get_user_info(self, username: str) -> Dict:
        """Fetch user info by username"""
        try:
            response = self.session.get(f"{self.BASE_URL}/user/{username}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching user info: {e}")
            raise Exception(f"Failed to fetch user info: {str(e)}")
    
    def get_user_leagues(self, user_id: str, season: str = "2025") -> List[Dict]:
        """Get all leagues for a user"""
        try:
            response = self.session.get(f"{self.BASE_URL}/user/{user_id}/leagues/nfl/{season}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching user leagues: {e}")
            raise Exception(f"Failed to fetch leagues: {str(e)}")
    
    def get_league_rosters(self, league_id: str) -> List[Dict]:
        """Get rosters for a league"""
        try:
            response = self.session.get(f"{self.BASE_URL}/league/{league_id}/rosters")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching league rosters: {e}")
            raise Exception(f"Failed to fetch rosters: {str(e)}")
    
    def get_matchups(self, league_id: str, week: int) -> List[Dict]:
        """Get matchups for a specific week"""
        try:
            response = self.session.get(f"{self.BASE_URL}/league/{league_id}/matchups/{week}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching matchups: {e}")
            raise Exception(f"Failed to fetch matchups: {str(e)}")
    
    def get_nfl_players(self) -> Dict:
        """Get all NFL players"""
        try:
            response = self.session.get(f"{self.BASE_URL}/players/nfl")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching NFL players: {e}")
            raise Exception(f"Failed to fetch players: {str(e)}")
    
    def get_nfl_state(self) -> Dict:
        """Get current NFL state"""
        try:
            response = self.session.get(f"{self.BASE_URL}/state/nfl")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching NFL state: {e}")
            raise Exception(f"Failed to fetch NFL state: {str(e)}")

sleeper_client = SleeperAPIClient()

async def download_and_cache_avatar(url: str) -> Optional[str]:
    """Download avatar image and convert to base64"""
    if url in app_state.avatar_cache:
        return app_state.avatar_cache[url]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    image_data = await response.read()

                    # Resize image to small size for Live Activity
                    img = Image.open(io.BytesIO(image_data))
                    img = img.resize((60, 60), Image.Resampling.LANCZOS)

                    # Convert to base64
                    buffer = io.BytesIO()
                    img.save(buffer, format='PNG')
                    base64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')

                    # Cache the result
                    app_state.avatar_cache[url] = base64_data
                    logger.info(f"Downloaded and cached avatar: {url}")
                    return base64_data
    except Exception as e:
        logger.error(f"Failed to download avatar {url}: {e}")
        return None

class LiveActivityManager:
    def __init__(self):
        self.apns_client = None
        self.initialize_apns()

    def initialize_apns(self):
        """Initialize APNS client with credentials"""
        # You'll need to add your APNS credentials here
        # For development: use sandbox environment
        # For production: use production environment

        # Load APNS configuration from environment variables
        apns_key_path = os.getenv('APNS_KEY_PATH')
        apns_key_id = os.getenv('APNS_KEY_ID')
        apns_team_id = os.getenv('APNS_TEAM_ID')
        apns_topic = os.getenv('APNS_TOPIC')
        use_sandbox = os.getenv('APNS_USE_SANDBOX', 'true').lower() == 'true'

        if apns_key_path and apns_key_id and apns_team_id and apns_topic and os.path.exists(apns_key_path):
            try:
                logger.info(f"Initializing APNS with key_id={apns_key_id}, team_id={apns_team_id}, topic={apns_topic}, sandbox={use_sandbox}")

                # Read the key file content
                with open(apns_key_path, 'r') as key_file:
                    key_content = key_file.read()

                # Initialize APNS client with all required parameters
                self.apns_client = APNs(
                    key=key_content,
                    key_id=apns_key_id,
                    team_id=apns_team_id,
                    topic=apns_topic,
                    use_sandbox=use_sandbox
                )
                logger.info(f"APNS client initialized successfully (sandbox: {use_sandbox})")
            except Exception as e:
                logger.error(f"APNS client initialization failed: {e}")
                logger.warning("Push notifications will not work. API will continue in testing mode.")
        else:
            missing_vars = []
            if not apns_key_path:
                missing_vars.append("APNS_KEY_PATH")
            if not apns_key_id:
                missing_vars.append("APNS_KEY_ID")
            if not apns_team_id:
                missing_vars.append("APNS_TEAM_ID")
            if not apns_topic:
                missing_vars.append("APNS_TOPIC")

            if missing_vars:
                logger.warning(f"Missing APNS environment variables: {', '.join(missing_vars)}")
            elif not os.path.exists(apns_key_path):
                logger.warning(f"APNS key file not found at {apns_key_path}")

            logger.warning("APNS client not initialized. Push notifications will not work.")

    async def send_live_activity_update(self, push_token: str, activity_data: Dict):
        """Send Live Activity update via APNS"""
        if not self.apns_client:
            logger.warning("APNS client not initialized, skipping push notification")
            return

        try:
            # Create Live Activity push payload
            payload = {
                "aps": {
                    "timestamp": int(datetime.now().timestamp()),
                    "event": "update",
                    "content-state": activity_data
                }
            }

            request = NotificationRequest(
                device_token=push_token,
                message=payload,
                push_type=PushType.LIVE_ACTIVITY
            )

            result = await self.apns_client.send_notification(request)

            if result.is_successful:
                logger.info(f"Successfully sent Live Activity update to {push_token}")
            else:
                logger.error(f"Failed to send Live Activity update: {result.description}")

        except Exception as e:
            logger.error(f"Error sending Live Activity update: {e}")

    def start_live_activity(self, device_id: str, user_config: Dict):
        """Start a Live Activity for a user"""
        logger.info(f"Starting Live Activity for device {device_id}")
        app_state.active_live_activities[device_id] = {
            "user_config": user_config,
            "started_at": datetime.now(),
            "last_update": datetime.now()
        }

    def end_live_activity(self, device_id: str):
        """End a Live Activity"""
        logger.info(f"Ending Live Activity for device {device_id}")
        if device_id in app_state.active_live_activities:
            del app_state.active_live_activities[device_id]
            if device_id in app_state.last_scores:
                del app_state.last_scores[device_id]

live_activity_manager = LiveActivityManager()

# API Endpoints
@app.route('/register', methods=['POST'])
def register_user():
    """Register a user with their Sleeper credentials and push token"""
    try:
        data = request.get_json()
        config = UserConfig(
            user_id=data['user_id'],
            league_id=data['league_id'],
            push_token=data['push_token'],
            device_id=data['device_id']
        )
        
        # Validate user exists
        user_info = sleeper_client.get_user_info(config.user_id)
        
        # Store user configuration
        app_state.user_configs[config.device_id] = config.to_dict()
        app_state.push_tokens[config.device_id] = config.push_token
        
        logger.info(f"Registered user {config.user_id} with device {config.device_id}")
        return jsonify({"status": "success", "message": "User registered successfully"})
    
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/user/<username>', methods=['GET'])
def get_user_info(username):
    """Get user information by username"""
    try:
        return jsonify(sleeper_client.get_user_info(username))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/user/<user_id>/leagues/<season>', methods=['GET'])
def get_user_leagues(user_id, season="2025"):
    """Get all leagues for a user"""
    try:
        return jsonify(sleeper_client.get_user_leagues(user_id, season))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/user/<user_id>', methods=['GET'])
def get_user_by_id(user_id):
    """Get user information by user ID"""
    try:
        response = requests.get(f"https://api.sleeper.app/v1/user/{user_id}")
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/league/<league_id>', methods=['GET'])
def get_league_info(league_id):
    """Get league information"""
    try:
        response = requests.get(f"https://api.sleeper.app/v1/league/{league_id}")
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/league/<league_id>/rosters', methods=['GET'])
def get_league_rosters(league_id):
    """Get rosters for a league"""
    try:
        return jsonify(sleeper_client.get_league_rosters(league_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/league/<league_id>/matchups/<int:week>', methods=['GET'])
def get_matchups(league_id, week):
    """Get matchups for a specific week"""
    try:
        return jsonify(sleeper_client.get_matchups(league_id, week))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/players/nfl', methods=['GET'])
def get_nfl_players():
    """Get all NFL players (cached)"""
    try:
        if not app_state.player_cache:
            app_state.player_cache = sleeper_client.get_nfl_players()
        return jsonify(app_state.player_cache)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/state/nfl', methods=['GET'])
def get_nfl_state():
    """Get current NFL state"""
    try:
        app_state.nfl_state_cache = sleeper_client.get_nfl_state()
        return jsonify(app_state.nfl_state_cache)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/live-activity/start/<device_id>', methods=['POST'])
def start_live_activity(device_id):
    """Start Live Activity for a device"""
    if device_id not in app_state.user_configs:
        return jsonify({"error": "Device not registered"}), 404
    
    user_config = app_state.user_configs[device_id]
    live_activity_manager.start_live_activity(device_id, user_config)
    return jsonify({"status": "success", "message": "Live Activity started"})

@app.route('/live-activity/end/<device_id>', methods=['POST'])
def end_live_activity(device_id):
    """End Live Activity for a device"""
    live_activity_manager.end_live_activity(device_id)
    return jsonify({"status": "success", "message": "Live Activity ended"})

@app.route('/live-activity/status/<device_id>', methods=['GET'])
def get_live_activity_status(device_id):
    """Get Live Activity status for a device"""
    if device_id in app_state.active_live_activities:
        activity = app_state.active_live_activities[device_id]
        return jsonify({
            "active": True,
            "started_at": activity["started_at"].isoformat(),
            "last_update": activity["last_update"].isoformat()
        })
    return jsonify({"active": False})

def check_and_update_live_activities():
    """Background task to check for scoring updates and push to Live Activities"""
    logger.info("Checking for Live Activity updates...")

    async def process_live_activities():
        for device_id, activity in app_state.active_live_activities.items():
            try:
                user_config = activity["user_config"]

                # Get current NFL state
                nfl_state = sleeper_client.get_nfl_state()
                current_week = nfl_state.get("week", 1)

                # Get user's matchup data
                matchups = sleeper_client.get_matchups(user_config["league_id"], current_week)

                # Get rosters to find user's team
                rosters = sleeper_client.get_league_rosters(user_config["league_id"])
                user_roster = None
                opponent_roster = None

                for roster in rosters:
                    if roster.get("owner_id") == user_config["user_id"]:
                        user_roster = roster
                        break

                if not user_roster:
                    continue

                # Find user's matchup
                user_matchup = None
                for matchup in matchups:
                    if matchup.get("roster_id") == user_roster.get("roster_id"):
                        user_matchup = matchup
                        break

                if not user_matchup:
                    continue

                # Find opponent's roster and matchup
                opponent_points = 0.0
                opponent_name = "Opponent"
                user_avatar_url = ""
                opponent_avatar_url = ""

                matchup_id = user_matchup.get("matchup_id")
                for matchup in matchups:
                    if (matchup.get("matchup_id") == matchup_id and
                        matchup.get("roster_id") != user_roster.get("roster_id")):
                        opponent_points = matchup.get("points", 0.0)

                        # Find opponent roster
                        for roster in rosters:
                            if roster.get("roster_id") == matchup.get("roster_id"):
                                opponent_roster = roster
                                break
                        break

                # Get user info for both players
                if user_roster and opponent_roster:
                    try:
                        user_info_response = requests.get(f"https://api.sleeper.app/v1/user/{user_config['user_id']}")
                        if user_info_response.status_code == 200:
                            user_info = user_info_response.json()
                            if user_info.get("avatar"):
                                user_avatar_url = f"https://sleepercdn.com/avatars/thumbs/{user_info['avatar']}"

                        opponent_owner_id = opponent_roster.get("owner_id")
                        if opponent_owner_id:
                            opponent_info_response = requests.get(f"https://api.sleeper.app/v1/user/{opponent_owner_id}")
                            if opponent_info_response.status_code == 200:
                                opponent_info = opponent_info_response.json()
                                opponent_name = opponent_info.get("display_name") or opponent_info.get("username", "Opponent")
                                if opponent_info.get("avatar"):
                                    opponent_avatar_url = f"https://sleepercdn.com/avatars/thumbs/{opponent_info['avatar']}"
                    except Exception as e:
                        logger.error(f"Error fetching user info: {e}")

                # Calculate current data
                total_points = user_matchup.get("points", 0.0)
                user_name = f"Team {user_roster.get('roster_id', 'Unknown')}"

                # Check if data has changed since last update
                current_data = {
                    "total_points": total_points,
                    "opponent_points": opponent_points,
                    "user_avatar_url": user_avatar_url,
                    "opponent_avatar_url": opponent_avatar_url
                }

                last_data = app_state.last_scores.get(device_id, {})
                has_changed = (
                    last_data.get("total_points") != total_points or
                    last_data.get("opponent_points") != opponent_points or
                    last_data.get("user_avatar_url") != user_avatar_url or
                    last_data.get("opponent_avatar_url") != opponent_avatar_url
                )

                if not has_changed:
                    logger.info(f"No changes for device {device_id}, skipping update")
                    continue

                # Download and cache avatars
                user_avatar_data = None
                opponent_avatar_data = None

                if user_avatar_url:
                    user_avatar_data = await download_and_cache_avatar(user_avatar_url)
                if opponent_avatar_url:
                    opponent_avatar_data = await download_and_cache_avatar(opponent_avatar_url)

                # Create activity data with avatars
                activity_data = {
                    "totalPoints": total_points,
                    "activePlayersCount": len(user_roster.get("starters", [])),
                    "teamName": user_name,
                    "opponentPoints": opponent_points,
                    "opponentTeamName": opponent_name,
                    "userAvatarURL": user_avatar_url,
                    "opponentAvatarURL": opponent_avatar_url,
                    "userAvatarData": user_avatar_data,  # Base64 image data
                    "opponentAvatarData": opponent_avatar_data,  # Base64 image data
                    "gameStatus": "Live",
                    "lastUpdate": datetime.now().isoformat()
                }

                # Send push notification
                push_token = app_state.push_tokens.get(device_id)
                if push_token:
                    await live_activity_manager.send_live_activity_update(push_token, activity_data)
                    activity["last_update"] = datetime.now()
                    app_state.last_scores[device_id] = current_data
                    logger.info(f"Sent Live Activity update for device {device_id}")

            except Exception as e:
                logger.error(f"Error updating Live Activity for device {device_id}: {e}")

    # Run the async function
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_live_activities())
        loop.close()
    except Exception as e:
        logger.error(f"Error in background task: {e}")

def startup_tasks():
    """Initialize background tasks"""
    # Schedule Live Activity updates every 2 minutes
    scheduler.add_job(
        func=check_and_update_live_activities,
        trigger="interval",
        minutes=2,
        id="live_activity_updates"
    )
    scheduler.start()
    logger.info("Sleeper Live Activity API started")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == "__main__":
    startup_tasks()
    try:
        # Run on all network interfaces with debug mode off for production
        app.run(host="0.0.0.0", port=8000, debug=False, threaded=True)
    finally:
        scheduler.shutdown()
        logger.info("Sleeper Live Activity API stopped")
