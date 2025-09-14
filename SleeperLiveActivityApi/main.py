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
from apscheduler.schedulers.background import BackgroundScheduler

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

class LiveActivityManager:
    def __init__(self):
        self.apns_client = None  # Will be initialized with proper APNS credentials
    
    def send_live_activity_update(self, push_token: str, activity_data: LiveActivityData):
        """Send Live Activity update via APNS"""
        # This would normally use aioapns or similar library
        # For now, we'll log the update
        logger.info(f"Sending Live Activity update to {push_token}: {activity_data.to_dict()}")
        
        # TODO: Implement actual APNS push notification
        # payload = {
        #     "aps": {
        #         "timestamp": int(datetime.now().timestamp()),
        #         "event": "update",
        #         "content-state": activity_data.to_dict()
        #     }
        # }
    
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
            
            # Calculate Live Activity data
            total_points = user_matchup.get("points", 0.0)
            
            # Find opponent's points
            opponent_points = 0.0
            matchup_id = user_matchup.get("matchup_id")
            for matchup in matchups:
                if (matchup.get("matchup_id") == matchup_id and 
                    matchup.get("roster_id") != user_roster.get("roster_id")):
                    opponent_points = matchup.get("points", 0.0)
                    break
            
            # Create activity data
            activity_data = LiveActivityData(
                total_points=total_points,
                active_players=len(user_roster.get("starters", [])),
                team_name=f"Team {user_roster.get('roster_id', 'Unknown')}",
                opponent_points=opponent_points,
                time_remaining="Live",
                game_status="In Progress"
            )
            
            # Send update
            push_token = app_state.push_tokens.get(device_id)
            if push_token:
                live_activity_manager.send_live_activity_update(push_token, activity_data)
                activity["last_update"] = datetime.now()
        
        except Exception as e:
            logger.error(f"Error updating Live Activity for device {device_id}: {e}")

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
