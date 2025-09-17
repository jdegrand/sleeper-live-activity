# main.py
import os
import io
import json
import base64
import logging
import threading
import requests
from PIL import Image
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Async / APNS
import asyncio
import aiohttp
from aioapns import APNs, NotificationRequest, PushType
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# -----------------------
# Global application state
# -----------------------
class AppState:
    def __init__(self):
        self.active_live_activities: Dict[str, Dict] = {}
        self.player_cache: Dict[str, Dict] = {}
        self.nfl_state_cache: Dict = {}
        self.user_configs: Dict[str, Dict] = {}
        self.push_tokens: Dict[str, str] = {}  # device_id -> remote notification token
        self.push_to_start_tokens: Dict[str, str] = {}  # device_id -> push-to-start token
        self.live_activity_tokens: Dict[str, str] = {}  # device_id -> live activity token
        self.avatar_cache: Dict[str, str] = {}  # URL -> base64 data
        self.last_scores: Dict[str, Dict] = {}  # device_id -> last score data
        self.nfl_games: List[Dict] = []  # today's NFL games from ESPN
        self.games_last_fetched: Optional[datetime] = None
        self.nfl_players: Dict = {}  # NFL players data from Sleeper API
        self.players_last_fetched: Optional[datetime] = None

app_state = AppState()
scheduler = BackgroundScheduler()

# APNS thread / loop refs
apns_thread: Optional[threading.Thread] = None
apns_loop: Optional[asyncio.AbstractEventLoop] = None

# -----------------------
# Helper: submit to apns loop
# -----------------------
def start_apns_thread():
    """Start a background thread that runs a dedicated asyncio event loop for APNS operations."""
    global apns_thread, apns_loop

    if apns_thread and apns_thread.is_alive():
        return

    def run_loop_in_thread(loop_ready_event: threading.Event):
        global apns_loop
        apns_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(apns_loop)
        loop_ready_event.set()
        logger.info("APNS event loop starting")
        apns_loop.run_forever()
        logger.info("APNS event loop stopped")

    loop_ready = threading.Event()
    apns_thread = threading.Thread(target=run_loop_in_thread, args=(loop_ready,), daemon=True)
    apns_thread.start()
    # Wait until loop is ready
    loop_ready.wait(timeout=5)
    if not apns_loop:
        raise RuntimeError("Failed to start APNS loop")

def submit_to_apns_loop(coro, timeout: float = 30.0):
    """Submit coroutine `coro` to the apns_loop and return its result (or raise)."""
    global apns_loop
    if apns_loop is None or not apns_thread or not apns_thread.is_alive():
        start_apns_thread()
    future = asyncio.run_coroutine_threadsafe(coro, apns_loop)
    return future.result(timeout=timeout)

# -----------------------
# Sleeper API client (blocking requests.Session)
# -----------------------
class SleeperAPIClient:
    BASE_URL = "https://api.sleeper.app/v1"
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 30

    def get_user_info(self, username: str) -> Dict:
        try:
            response = self.session.get(f"{self.BASE_URL}/user/{username}", timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching user info: {e}")
            raise

    def get_user_leagues(self, user_id: str, season: str = "2025") -> List[Dict]:
        try:
            response = self.session.get(f"{self.BASE_URL}/user/{user_id}/leagues/nfl/{season}", timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching user leagues: {e}")
            raise

    def get_league_rosters(self, league_id: str) -> List[Dict]:
        try:
            response = self.session.get(f"{self.BASE_URL}/league/{league_id}/rosters", timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching league rosters: {e}")
            raise

    def get_matchups(self, league_id: str, week: int) -> List[Dict]:
        try:
            response = self.session.get(f"{self.BASE_URL}/league/{league_id}/matchups/{week}", timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching matchups: {e}")
            raise

    def get_nfl_players(self) -> Dict:
        try:
            response = self.session.get(f"{self.BASE_URL}/players/nfl", timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching NFL players: {e}")
            raise

    def get_nfl_state(self) -> Dict:
        try:
            response = self.session.get(f"{self.BASE_URL}/state/nfl", timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching NFL state: {e}")
            raise

sleeper_client = SleeperAPIClient()

# -----------------------
# ESPN API client for game schedules
# -----------------------
def fetch_nfl_games_from_espn() -> List[Dict]:
    """Fetch today's NFL games from ESPN API, returning only the fields specified in read.txt."""
    try:
        espn_url = "https://site.web.api.espn.com/apis/personalized/v2/scoreboard/header?sport=football&league=nfl&region=us&lang=en&contentorigin=espn"
        response = requests.get(espn_url, timeout=30)
        response.raise_for_status()
        data = response.json()

        games = []
        sports = data.get("sports", [])
        for sport in sports:
            leagues = sport.get("leagues", [])
            for league in leagues:
                events = league.get("events", [])
                for event in events:
                    # Only include the exact fields from read.txt
                    event_data = {
                        "date": event.get("date", ""),
                        "name": event.get("name", ""),
                        "competitors": []
                    }

                    # Only include abbreviation from competitors
                    competitors = event.get("competitors", [])
                    for competitor in competitors:
                        competitor_data = {
                            "abbreviation": competitor.get("abbreviation", "")
                        }
                        event_data["competitors"].append(competitor_data)

                    games.append(event_data)

        logger.info(f"Fetched {len(games)} NFL games from ESPN")
        return games
    except Exception as e:
        logger.error(f"Failed to fetch NFL games from ESPN: {e}")
        return []

def update_nfl_games():
    """Update the stored NFL games data."""
    try:
        games = fetch_nfl_games_from_espn()
        app_state.nfl_games = games
        app_state.games_last_fetched = datetime.now()
        logger.info(f"Updated NFL games data: {len(games)} games stored")
    except Exception as e:
        logger.error(f"Failed to update NFL games: {e}")

def fetch_nfl_players_from_sleeper() -> Dict:
    """Fetch NFL players data from Sleeper API, filtering to only include specified fields."""
    try:
        players_url = "https://api.sleeper.app/v1/players/nfl"
        logger.info("Fetching NFL players data from Sleeper API (this may take a while due to 5MB size)")
        response = requests.get(players_url, timeout=60)  # Longer timeout for large file
        response.raise_for_status()
        raw_players_data = response.json()

        # Filter to only include the fields specified in read.txt
        filtered_players = {}
        for player_id, player_data in raw_players_data.items():
            filtered_players[player_id] = {
                "full_name": player_data.get("full_name"),
                "last_name": player_data.get("last_name"),
                "number": player_data.get("number"),
                "team": player_data.get("team"),
                "position": player_data.get("position"),
                "first_name": player_data.get("first_name")
            }

        logger.info(f"Successfully fetched and filtered NFL players data with {len(filtered_players)} players")
        return filtered_players
    except Exception as e:
        logger.error(f"Failed to fetch NFL players from Sleeper API: {e}")
        return {}

def save_players_to_file(players_data: Dict):
    """Save players data to players.json file."""
    try:
        with open("players.json", "w") as f:
            json.dump(players_data, f, indent=2)
        logger.info("Successfully saved players data to players.json")
    except Exception as e:
        logger.error(f"Failed to save players data to file: {e}")

def load_players_from_file() -> Dict:
    """Load players data from players.json file."""
    try:
        with open("players.json", "r") as f:
            players_data = json.load(f)
        logger.info(f"Successfully loaded players data from file with {len(players_data)} players")
        return players_data
    except FileNotFoundError:
        logger.info("players.json file not found")
        return {}
    except Exception as e:
        logger.error(f"Failed to load players data from file: {e}")
        return {}

def update_nfl_players():
    """Update the stored NFL players data."""
    try:
        players_data = fetch_nfl_players_from_sleeper()
        if players_data:
            app_state.nfl_players = players_data
            app_state.players_last_fetched = datetime.now()

            # Save to file for persistence
            save_players_to_file(players_data)

            logger.info(f"Updated NFL players data: {len(players_data)} players stored")
    except Exception as e:
        logger.error(f"Failed to update NFL players: {e}")

def load_players_on_startup():
    """Load players data on startup - from file if exists, otherwise fetch from API."""
    try:
        # Check if players.json file exists
        if os.path.exists("players.json"):
            logger.info("players.json file found, loading from file")
            players_data = load_players_from_file()
            if players_data:
                app_state.nfl_players = players_data
                # Set a placeholder timestamp since we loaded from file
                app_state.players_last_fetched = datetime.now()
                logger.info("Successfully loaded players data from file on startup")
                return

        # File doesn't exist or failed to load, fetch from API
        logger.info("players.json file not found, fetching from Sleeper API")
        update_nfl_players()

    except Exception as e:
        logger.error(f"Failed to load players on startup: {e}")

def check_and_start_live_activities():
    """Check if any games are starting now and auto-start live activities."""
    try:
        current_time = datetime.now()
        logger.info(f"Checking for games starting at {current_time}")

        # First, find all games starting soon
        games_starting_soon = []
        for game in app_state.nfl_games:
            try:
                # Parse game date
                game_date_str = game.get("date", "")
                if not game_date_str:
                    continue

                game_date = datetime.fromisoformat(game_date_str.replace('Z', '+00:00'))

                # Check if game is starting within the next 5 minutes
                time_diff = (game_date - current_time.replace(tzinfo=game_date.tzinfo)).total_seconds()

                if 0 <= time_diff <= 300:  # Game starting in next 5 minutes
                    games_starting_soon.append(game.get('name', 'Unknown Game'))

            except Exception as e:
                logger.error(f"Error processing game {game}: {e}")

        # If we have games starting soon, start or update live activities with the message
        if games_starting_soon:
            game_names_message = ", ".join(games_starting_soon)
            logger.info(f"Games starting soon: {game_names_message}")

            # Handle all configured users
            for device_id, user_config in app_state.user_configs.items():
                if device_id not in app_state.active_live_activities:
                    # Start new live activity
                    logger.info(f"Auto-starting live activity for device {device_id}")
                    try:
                        start_live_activity_for_device(device_id, game_names_message)
                    except Exception as e:
                        logger.error(f"Failed to auto-start live activity for {device_id}: {e}")
                else:
                    # Update existing live activity with new game message
                    logger.info(f"Updating existing live activity for device {device_id} with new games")
                    try:
                        update_live_activity_with_message(device_id, game_names_message)
                    except Exception as e:
                        logger.error(f"Failed to update live activity for {device_id}: {e}")

    except Exception as e:
        logger.error(f"Error in check_and_start_live_activities: {e}")

def start_live_activity_for_device(device_id: str, game_message: str = ""):
    """Start live activity for a specific device (internal function)."""
    if device_id not in app_state.user_configs:
        logger.warning(f"Device {device_id} not registered, skipping auto-start")
        return

    user_config = app_state.user_configs[device_id]
    push_to_start_token = app_state.push_to_start_tokens.get(device_id)

    if push_to_start_token:
        try:
            # submit start coroutine to apns_loop using push-to-start token
            submit_to_apns_loop(live_activity_manager.send_live_activity_start(push_to_start_token, user_config, game_message))
            logger.info(f"Sent APNS start notification for device {device_id} (auto-start)")
        except Exception:
            logger.exception("Failed to send APNS start notification for auto-start")
    else:
        logger.warning(f"No push-to-start token available for device {device_id}")

    app_state.active_live_activities[device_id] = {
        "user_config": user_config,
        "started_at": datetime.now(),
        "last_update": datetime.now()
    }
    logger.info(f"Auto-started live activity for device {device_id}")

def update_live_activity_with_message(device_id: str, game_message: str):
    """Update existing live activity with new game message."""
    if device_id not in app_state.active_live_activities:
        logger.warning(f"No active live activity found for device {device_id}")
        return

    # Get live activity token for this device
    live_activity_token = app_state.live_activity_tokens.get(device_id)
    if not live_activity_token:
        logger.warning(f"No live activity token available for device {device_id}")
        return

    try:
        # Get user config and current activity data
        activity = app_state.active_live_activities[device_id]
        user_config = activity["user_config"]

        # Submit update coroutine to apns_loop with the new message
        submit_to_apns_loop(live_activity_manager.send_live_activity_update_with_message(
            live_activity_token,
            user_config,
            game_message
        ))

        # Update the last_update timestamp
        activity["last_update"] = datetime.now()

        logger.info(f"Sent live activity update with new games message for device {device_id}")
    except Exception as e:
        logger.error(f"Failed to update live activity message for {device_id}: {e}")

# -----------------------
# Utility: download avatar but offload to thread
# -----------------------
async def download_and_cache_avatar(url: str) -> Optional[str]:
    """Download avatar image and convert to base64. Runs blocking work in thread to avoid blocking the apns loop."""
    if not url:
        return None
    if url in app_state.avatar_cache:
        return app_state.avatar_cache[url]

    try:
        # perform HTTP and image processing in a thread to avoid blocking the event loop
        def blocking_download_and_resize():
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            image_data = resp.content
            img = Image.open(io.BytesIO(image_data)).convert("RGBA")
            img = img.resize((60, 60), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

        b64 = await asyncio.to_thread(blocking_download_and_resize)
        if b64:
            app_state.avatar_cache[url] = b64
            logger.info(f"Downloaded and cached avatar: {url}")
            return b64
    except Exception as e:
        logger.error(f"Failed to download avatar {url}: {e}")
        return None

# -----------------------
# LiveActivityManager (APNS operations live on apns_loop)
# -----------------------
class LiveActivityManager:
    def __init__(self):
        self.apns_client: Optional[APNs] = None
        # We'll initialize APNS asynchronously on the APNS loop
        # (callers should arrange to call async_initialize_apns on the apns_loop)
    async def async_initialize_apns(self):
        """Async initialization of APNS client (should be called on apns_loop)."""
        apns_key_path = os.getenv("APNS_KEY_PATH")
        apns_key_id = os.getenv("APNS_KEY_ID")
        apns_team_id = os.getenv("APNS_TEAM_ID")
        apns_topic = os.getenv("APNS_TOPIC")
        use_sandbox = os.getenv("APNS_USE_SANDBOX", "true").lower() == "true"

        if not (apns_key_path and apns_key_id and apns_team_id and apns_topic):
            missing = [k for k in ("APNS_KEY_PATH", "APNS_KEY_ID", "APNS_TEAM_ID", "APNS_TOPIC") if not os.getenv(k)]
            logger.warning(f"Missing APNS env vars: {missing}")
            self.apns_client = None
            return

        if not os.path.exists(apns_key_path):
            logger.warning(f"APNS key file not found at {apns_key_path}")
            self.apns_client = None
            return

        try:
            logger.info("Initializing APNS client on APNS loop")
            # Read key file in thread (file IO)
            def read_key():
                with open(apns_key_path, "r") as f:
                    return f.read()
            key_content = await asyncio.to_thread(read_key)

            # Initialize the APNs client instance (this is lightweight)
            self.apns_client = APNs(
                key=key_content,
                key_id=apns_key_id,
                team_id=apns_team_id,
                topic=apns_topic,
                use_sandbox=use_sandbox
            )
            logger.info(f"APNS client initialized (sandbox={use_sandbox})")
        except Exception as e:
            logger.exception(f"Failed to initialize APNS client: {e}")
            self.apns_client = None

    async def send_live_activity_update(self, push_token: str, activity_data: Dict):
        """Send Live Activity update via APNS with retry logic. This coroutine must run on the apns_loop."""
        if not self.apns_client:
            logger.warning("APNS client not initialized - skipping send_live_activity_update")
            return

        max_retries = 3
        for attempt in range(max_retries):
            try:
                payload = {
                    "aps": {
                        "timestamp": int(datetime.now().timestamp()),
                        "event": "update",
                        "content-state": activity_data
                    }
                }

                logger.info(f"APNS update attempt {attempt+1} to token {push_token[:16]}...")
                request = NotificationRequest(
                    device_token=push_token,
                    message=payload,
                    push_type=PushType.LIVEACTIVITY,
                    priority=10
                )
                result = await self.apns_client.send_notification(request)

                # `result` is an object with `is_successful` attribute in aioapns
                if getattr(result, "is_successful", False):
                    logger.info("APNS update sent successfully")
                    return
                else:
                    desc = getattr(result, "description", str(result))
                    logger.error(f"APNS update failed: {desc}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.exception(f"Exception sending APNS update: {e}")
                # if connection/loop related, try reinit once
                if attempt < max_retries - 1:
                    logger.info("Reinitializing APNS client and retrying...")
                    await self.async_initialize_apns()
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.error("Max retries reached for send_live_activity_update")

    async def send_live_activity_update_with_message(self, push_token: str, user_config: Dict, game_message: str):
        """Send Live Activity update with custom message via APNS."""
        if not self.apns_client:
            logger.warning("APNS client not initialized - skipping send_live_activity_update_with_message")
            return

        try:
            # Get current activity data
            activity_data = await self.get_comprehensive_activity_data(user_config)

            # Override the message with the new game message
            activity_data["message"] = game_message

            # Send the update
            await self.send_live_activity_update(push_token, activity_data)
            logger.info(f"Sent live activity update with game message: {game_message}")

        except Exception as e:
            logger.exception(f"Error sending live activity update with message: {e}")

    async def get_comprehensive_activity_data(self, user_config: Dict) -> Dict:
        """Gather and return the activity data. Uses blocking HTTP so offloads to threads when needed."""
        try:
            # Offload sleeper calls to thread so apns_loop isn't blocked
            nfl_state = await asyncio.to_thread(sleeper_client.get_nfl_state)
            current_week = nfl_state.get("week", 1) if isinstance(nfl_state, dict) else 1

            matchups = await asyncio.to_thread(sleeper_client.get_matchups, user_config["league_id"], current_week)
            rosters = await asyncio.to_thread(sleeper_client.get_league_rosters, user_config["league_id"])

            # find user roster
            user_roster = None
            opponent_roster = None
            for roster in rosters:
                if roster.get("owner_id") == user_config["user_id"]:
                    user_roster = roster
                    break

            if not user_roster:
                return {
                    "totalPoints": 0.0,
                    "activePlayersCount": 0,
                    "teamName": "Your Team",
                    "opponentPoints": 0.0,
                    "opponentTeamName": "Opponent",
                    "leagueName": "Fantasy Football",
                    "userAvatarURL": "",
                    "opponentAvatarURL": "",
                    "gameStatus": "Live",
                    "lastUpdate": int(datetime.now().timestamp()),
                    "message": ""
                }

            # find matchup for this roster
            user_matchup = None
            for m in matchups:
                if m.get("roster_id") == user_roster.get("roster_id"):
                    user_matchup = m
                    break

            if not user_matchup:
                return {
                    "totalPoints": 0.0,
                    "activePlayersCount": len(user_roster.get("starters", [])),
                    "teamName": f"Team {user_roster.get('roster_id', 'Unknown')}",
                    "opponentPoints": 0.0,
                    "opponentTeamName": "Opponent",
                    "leagueName": "Fantasy Football",
                    "userAvatarURL": "",
                    "opponentAvatarURL": "",
                    "gameStatus": "Live",
                    "lastUpdate": int(datetime.now().timestamp()),
                    "message": ""
                }

            opponent_points = 0.0
            opponent_name = "Opponent"
            user_avatar_url = ""
            opponent_avatar_url = ""

            matchup_id = user_matchup.get("matchup_id")
            for m in matchups:
                if (m.get("matchup_id") == matchup_id and
                        m.get("roster_id") != user_roster.get("roster_id")):
                    opponent_points = m.get("points", 0.0)
                    # find opponent roster
                    for r in rosters:
                        if r.get("roster_id") == m.get("roster_id"):
                            opponent_roster = r
                            break
                    break

            # fetch user and opponent info (blocking HTTP) in threads
            def fetch_user_info(uid):
                try:
                    resp = requests.get(f"https://api.sleeper.app/v1/user/{uid}", timeout=10)
                    resp.raise_for_status()
                    return resp.json()
                except Exception:
                    return {}

            user_info = await asyncio.to_thread(fetch_user_info, user_config["user_id"])
            if user_info.get("avatar"):
                user_avatar_url = f"https://sleepercdn.com/avatars/thumbs/{user_info['avatar']}"

            if opponent_roster:
                opponent_owner_id = opponent_roster.get("owner_id")
                if opponent_owner_id:
                    opponent_info = await asyncio.to_thread(fetch_user_info, opponent_owner_id)
                    opponent_name = opponent_info.get("display_name") or opponent_info.get("username", opponent_name)
                    if opponent_info.get("avatar"):
                        opponent_avatar_url = f"https://sleepercdn.com/avatars/thumbs/{opponent_info['avatar']}"

            total_points = user_matchup.get("points", 0.0)
            user_name = f"Team {user_roster.get('roster_id', 'Unknown')}"

            activity_data = {
                "totalPoints": total_points,
                "activePlayersCount": len(user_roster.get("starters", [])),
                "teamName": user_name,
                "opponentPoints": opponent_points,
                "opponentTeamName": opponent_name,
                "leagueName": "Fantasy Football",
                "userAvatarURL": user_avatar_url,
                "opponentAvatarURL": opponent_avatar_url,
                "gameStatus": "Live",
                "lastUpdate": int(datetime.now().timestamp()),
                "message": ""
            }
            return activity_data
        except Exception as e:
            logger.exception(f"Error in get_comprehensive_activity_data: {e}")
            return {
                "totalPoints": 0.0,
                "activePlayersCount": 0,
                "teamName": "Your Team",
                "opponentPoints": 0.0,
                "opponentTeamName": "Opponent",
                "leagueName": "Fantasy Football",
                "userAvatarURL": "",
                "opponentAvatarURL": "",
                "gameStatus": "Live",
                "lastUpdate": int(datetime.now().timestamp()),
                "message": ""
            }

    async def send_live_activity_start(self, push_token: str, user_config: Dict, game_message: str = ""):
        """Send Live Activity start notification (must run on apns_loop)."""
        if not self.apns_client:
            logger.warning("APNS client not initialized, skipping send_live_activity_start")
            return

        try:
            activity_data = await self.get_comprehensive_activity_data(user_config)

            # Add the game message to the activity data
            if game_message:
                activity_data["message"] = game_message

            payload = {
                "aps": {
                    "timestamp": int(datetime.now().timestamp()),
                    "event": "start",
                    "attributes-type": "SleeperLiveActivityAttributes",
                    "attributes": {
                        "userID": user_config.get("user_id", "test_user_id"),
                        "leagueID": user_config.get("league_id", "test_league_id")
                    },
                    "content-state": activity_data,
                    "alert": {
                        "title": {"loc-key": "%@ is on an adventure!", "loc-args": ["Power Panda"]},
                        "body": {"loc-key": "%@ found a sword!", "loc-args": ["Power Panda"]},
                        "sound": "chime.aiff"
                    }
                }
            }

            logger.info("Sending APNS start notification")
            request = NotificationRequest(
                device_token=push_token,
                message=payload,
                push_type=PushType.LIVEACTIVITY,
                priority=10
            )
            result = await self.apns_client.send_notification(request)
            if getattr(result, "is_successful", False):
                logger.info("APNS start sent successfully")
            else:
                logger.error(f"APNS start failed: {getattr(result, 'description', str(result))}")
        except Exception as e:
            logger.exception(f"Error sending start notification: {e}")

    async def send_live_activity_end(self, push_token: str, user_config: Dict = None):
        """Send Live Activity end notification (run on apns_loop)."""
        if not self.apns_client:
            logger.warning("APNS client not initialized, skipping send_live_activity_end")
            return

        try:
            if user_config:
                final_activity_data = await self.get_comprehensive_activity_data(user_config)
                final_activity_data["activePlayersCount"] = 0
                final_activity_data["gameStatus"] = "Final"
                final_activity_data["message"] = "Game completed!"
            else:
                final_activity_data = {
                    "totalPoints": 115.7,
                    "activePlayersCount": 0,
                    "teamName": "Your Team",
                    "opponentPoints": 102.3,
                    "opponentTeamName": "Opponent",
                    "leagueName": "Fantasy Football",
                    "userAvatarURL": "",
                    "opponentAvatarURL": "",
                    "gameStatus": "Final",
                    "lastUpdate": int(datetime.now().timestamp()),
                    "message": "Game completed!"
                }

            payload = {
                "aps": {
                    "timestamp": int(datetime.now().timestamp()),
                    "event": "end",
                    "dismissal-date": int((datetime.now() + timedelta(minutes=30)).timestamp()),
                    "content-state": final_activity_data
                }
            }

            logger.info("Sending APNS end notification")
            request = NotificationRequest(
                device_token=push_token,
                message=payload,
                push_type=PushType.LIVEACTIVITY
            )
            result = await self.apns_client.send_notification(request)
            if getattr(result, "is_successful", False):
                logger.info("APNS end sent successfully")
            else:
                logger.error(f"APNS end failed: {getattr(result, 'description', str(result))}")
        except Exception as e:
            logger.exception(f"Error sending end notification: {e}")

live_activity_manager = LiveActivityManager()

# -----------------------
# Background updater coroutine (runs on apns_loop)
# -----------------------
async def check_and_update_live_activities():
    logger.info(f"Checking for Live Activity updates... found {len(app_state.active_live_activities)} active activities")

    # Make shallow copy
    active_copy = dict(app_state.active_live_activities)

    for device_id, activity in active_copy.items():
        try:
            user_config = activity["user_config"]

            # get comprehensive data (this offloads blocking calls internally)
            activity_data = await live_activity_manager.get_comprehensive_activity_data(user_config)

            current_data = {
                "total_points": activity_data["totalPoints"],
                "opponent_points": activity_data["opponentPoints"],
                "user_avatar_url": activity_data.get("userAvatarURL", ""),
                "opponent_avatar_url": activity_data.get("opponentAvatarURL", "")
            }

            last_data = app_state.last_scores.get(device_id, {})
            has_changed = (
                last_data.get("total_points") != current_data["total_points"] or
                last_data.get("opponent_points") != current_data["opponent_points"] or
                last_data.get("user_avatar_url") != current_data["user_avatar_url"] or
                last_data.get("opponent_avatar_url") != current_data["opponent_avatar_url"]
            )

            if not has_changed:
                logger.debug(f"No changes for device {device_id}, skipping")
                continue

            # prefer Live Activity token if available (the token used by the app's live activity)
            live_activity_token = app_state.live_activity_tokens.get(device_id)
            if live_activity_token:
                await live_activity_manager.send_live_activity_update(live_activity_token, activity_data)
                activity["last_update"] = datetime.now()
                app_state.last_scores[device_id] = current_data
                logger.info(f"Sent Live Activity update for {device_id}")
            else:
                logger.info(f"No live activity token for {device_id}, skipping APNS update")
        except Exception as e:
            logger.exception(f"Error updating live activity for {device_id}: {e}")

# -----------------------
# Flask endpoints (mostly unchanged, but APNS calls are submitted to apns_loop)
# -----------------------
@app.route("/register", methods=["POST"])
def register_user():
    try:
        data = request.get_json()
        user_id = data["user_id"]
        league_id = data["league_id"]
        push_token = data["push_token"]
        device_id = data["device_id"]

        # validate user exists (blocking) - still ok here
        sleeper_client.get_user_info(user_id)

        # Get optional push-to-start token
        push_to_start_token = data.get("push_to_start_token")

        app_state.user_configs[device_id] = {
            "user_id": user_id,
            "league_id": league_id,
            "device_id": device_id
        }

        # Store both tokens separately
        app_state.push_tokens[device_id] = push_token

        if push_to_start_token:
            app_state.push_to_start_tokens[device_id] = push_to_start_token
            logger.info(f"Registered user {user_id} device {device_id} with both tokens")
            logger.debug(f"REMOTE NOTIFICATION TOKEN {push_token}")
            logger.debug(f"PUSH TO START TOKEN {push_to_start_token}")
        else:
            logger.info(f"Registered user {user_id} device {device_id} with remote notification token only")
            logger.debug(f"REMOTE NOTIFICATION TOKEN {push_token}")
        return jsonify({"status": "success", "message": "User registered successfully"})
    except Exception as e:
        logger.exception("Registration failed")
        return jsonify({"error": str(e)}), 400

@app.route("/register-live-activity-token", methods=["POST"])
def register_live_activity_token():
    try:
        data = request.get_json()
        device_id = data["device_id"]
        live_activity_token = data["live_activity_token"]
        activity_id = data.get("activity_id", "")

        if device_id not in app_state.user_configs:
            return jsonify({"error": "Device not registered. Register device first."}), 400

        app_state.live_activity_tokens[device_id] = live_activity_token
        logger.info(f"Registered Live Activity token for device {device_id}")
        logger.debug(f"LIVE ACTIVITY TOKEN {live_activity_token}")
        if activity_id:
            logger.info(f"Activity ID: {activity_id}")

        # Add to active live activities for backend tracking (app-initiated start)
        user_config = app_state.user_configs[device_id]
        app_state.active_live_activities[device_id] = {
            "user_config": user_config,
            "started_at": datetime.now(),
            "last_update": datetime.now()
        }
        logger.info(f"Added device {device_id} to active live activities (app-initiated)")

        return jsonify({"status": "success", "message": "Live Activity token registered successfully", "device_id": device_id})
    except Exception as e:
        logger.exception("Live Activity token registration failed")
        return jsonify({"error": str(e)}), 400

@app.route("/user/<username>", methods=["GET"])
def get_user_info(username):
    try:
        return jsonify(sleeper_client.get_user_info(username))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/user/<user_id>/leagues/<season>", methods=["GET"])
def get_user_leagues(user_id, season="2025"):
    try:
        return jsonify(sleeper_client.get_user_leagues(user_id, season))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/user/<user_id>", methods=["GET"])
def get_user_by_id(user_id):
    try:
        response = requests.get(f"https://api.sleeper.app/v1/user/{user_id}", timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/league/<league_id>", methods=["GET"])
def get_league_info(league_id):
    try:
        response = requests.get(f"https://api.sleeper.app/v1/league/{league_id}", timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/league/<league_id>/rosters", methods=["GET"])
def get_league_rosters(league_id):
    try:
        return jsonify(sleeper_client.get_league_rosters(league_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/league/<league_id>/matchups/<int:week>", methods=["GET"])
def get_matchups(league_id, week):
    try:
        return jsonify(sleeper_client.get_matchups(league_id, week))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/players/nfl", methods=["GET"])
def get_nfl_players():
    try:
        # Use our cached players data instead of calling the API each time
        return jsonify(app_state.nfl_players)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/state/nfl", methods=["GET"])
def get_nfl_state():
    try:
        app_state.nfl_state_cache = sleeper_client.get_nfl_state()
        return jsonify(app_state.nfl_state_cache)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/live-activity/start/<device_id>", methods=["POST"])
def start_live_activity(device_id):
    if device_id not in app_state.user_configs:
        return jsonify({"error": "Device not registered"}), 404

    user_config = app_state.user_configs[device_id]
    push_to_start_token = app_state.push_to_start_tokens.get(device_id)

    if push_to_start_token:
        try:
            # submit start coroutine to apns_loop using push-to-start token
            submit_to_apns_loop(live_activity_manager.send_live_activity_start(push_to_start_token, user_config))
            logger.info(f"Sent APNS start notification for device {device_id}")
        except Exception:
            logger.exception("Failed to send APNS start notification")
    else:
        logger.warning(f"No push-to-start token available for device {device_id}")

    app_state.active_live_activities[device_id] = {
        "user_config": user_config,
        "started_at": datetime.now(),
        "last_update": datetime.now()
    }
    return jsonify({"status": "success", "message": "Live Activity started"})

@app.route("/live-activity/end/<device_id>", methods=["POST"])
def end_live_activity(device_id):
    live_activity_token = app_state.live_activity_tokens.get(device_id)
    if live_activity_token:
        try:
            user_config = app_state.user_configs.get(device_id)
            submit_to_apns_loop(live_activity_manager.send_live_activity_end(live_activity_token, user_config))
            logger.info(f"Sent APNS end notification for device {device_id}")
        except Exception:
            logger.exception("Failed to send APNS end notification")
    else:
        logger.warning(f"No Live Activity token available for device {device_id}")

    if device_id in app_state.active_live_activities:
        del app_state.active_live_activities[device_id]
    if device_id in app_state.last_scores:
        del app_state.last_scores[device_id]
    if device_id in app_state.live_activity_tokens:
        del app_state.live_activity_tokens[device_id]

    return jsonify({"status": "success", "message": "Live Activity ended"})

@app.route("/live-activity/status/<device_id>", methods=["GET"])
def get_live_activity_status(device_id):
    if device_id in app_state.active_live_activities:
        activity = app_state.active_live_activities[device_id]
        return jsonify({
            "active": True,
            "started_at": activity["started_at"].isoformat(),
            "last_update": activity["last_update"].isoformat()
        })
    return jsonify({"active": False})

@app.route("/devices", methods=["GET"])
def list_devices():
    devices = []
    for device_id, config in app_state.user_configs.items():
        device_info = {
            "device_id": device_id,
            "user_id": config.get("user_id"),
            "league_id": config.get("league_id"),
            "has_remote_notification_token": device_id in app_state.push_tokens,
            "has_push_to_start_token": device_id in app_state.push_to_start_tokens,
            "live_activity_active": device_id in app_state.active_live_activities,
            "remote_notification_token": app_state.push_tokens.get(device_id, ""),
            "push_to_start_token": app_state.push_to_start_tokens.get(device_id, ""),
            "live_activity_token": app_state.live_activity_tokens.get(device_id, "")
        }
        if device_id in app_state.active_live_activities:
            activity = app_state.active_live_activities[device_id]
            device_info.update({
                "live_activity_started_at": activity["started_at"].isoformat(),
                "live_activity_last_update": activity["last_update"].isoformat()
            })
        devices.append(device_info)
    return jsonify({
        "devices": devices,
        "total_registered": len(app_state.user_configs),
        "total_active_live_activities": len(app_state.active_live_activities)
    })

@app.route("/devices/<device_id>", methods=["GET"])
def get_device_details(device_id):
    if device_id not in app_state.user_configs:
        return jsonify({"error": "Device not found"}), 404
    config = app_state.user_configs[device_id]
    device_info = {
        "device_id": device_id,
        "user_id": config.get("user_id"),
        "league_id": config.get("league_id"),
        "has_remote_notification_token": device_id in app_state.push_tokens,
        "has_push_to_start_token": device_id in app_state.push_to_start_tokens,
        "live_activity_active": device_id in app_state.active_live_activities,
        "last_score_data": app_state.last_scores.get(device_id),
        "remote_notification_token": app_state.push_tokens.get(device_id, ""),
        "push_to_start_token": app_state.push_to_start_tokens.get(device_id, ""),
        "live_activity_token": app_state.live_activity_tokens.get(device_id, "")
    }
    if device_id in app_state.active_live_activities:
        activity = app_state.active_live_activities[device_id]
        device_info.update({
            "live_activity_started_at": activity["started_at"].isoformat(),
            "live_activity_last_update": activity["last_update"].isoformat(),
            "live_activity_config": activity["user_config"]
        })
    return jsonify(device_info)

@app.route("/live-activity/start-by-id/<device_id>", methods=["POST"])
def start_live_activity_by_id(device_id):
    if device_id not in app_state.user_configs:
        return jsonify({"error": "Device not registered"}), 404
    if device_id in app_state.active_live_activities:
        return jsonify({
            "status": "already_active",
            "message": f"Live Activity already active for device {device_id}",
            "started_at": app_state.active_live_activities[device_id]["started_at"].isoformat()
        })
    user_config = app_state.user_configs[device_id]
    push_to_start_token = app_state.push_to_start_tokens.get(device_id)
    if push_to_start_token:
        try:
            submit_to_apns_loop(live_activity_manager.send_live_activity_start(push_to_start_token, user_config))
            logger.info(f"Sent APNS start notification for device {device_id}")
        except Exception:
            logger.exception("Failed to send APNS start notification")
    else:
        logger.warning(f"No push-to-start token available for device {device_id}")
    app_state.active_live_activities[device_id] = {
        "user_config": user_config,
        "started_at": datetime.now(),
        "last_update": datetime.now()
    }
    return jsonify({
        "status": "success",
        "message": f"Live Activity started for device {device_id}",
        "device_id": device_id,
        "user_id": user_config.get("user_id"),
        "league_id": user_config.get("league_id")
    })

@app.route("/live-activity/stop-by-id/<device_id>", methods=["POST"])
def stop_live_activity_by_id(device_id):
    if device_id not in app_state.active_live_activities:
        return jsonify({"status": "not_active", "message": f"No active Live Activity for device {device_id}"})
    live_activity_token = app_state.live_activity_tokens.get(device_id)
    if live_activity_token:
        try:
            user_config = app_state.user_configs.get(device_id)
            submit_to_apns_loop(live_activity_manager.send_live_activity_end(live_activity_token, user_config))
            logger.info(f"Sent APNS end notification for device {device_id}")
        except Exception:
            logger.exception("Failed to send APNS end notification")
    else:
        logger.warning(f"No Live Activity token available for device {device_id}")
    # remove activity and clean up tokens
    if device_id in app_state.active_live_activities:
        del app_state.active_live_activities[device_id]
    if device_id in app_state.last_scores:
        del app_state.last_scores[device_id]
    if device_id in app_state.live_activity_tokens:
        del app_state.live_activity_tokens[device_id]
    return jsonify({"status": "success", "message": f"Live Activity stopped for device {device_id}", "device_id": device_id})

# -----------------------
# Startup tasks
# -----------------------
def startup_tasks():
    # Start APNS loop/thread
    start_apns_thread()
    # Initialize APNS client on the APNS loop
    try:
        submit_to_apns_loop(live_activity_manager.async_initialize_apns())
    except Exception:
        logger.exception("Failed to initialize APNS client on startup")

    # Schedule the periodic update job, but submit coroutine to apns loop
    def schedule_job_submit():
        try:
            submit_to_apns_loop(check_and_update_live_activities())
        except Exception:
            logger.exception("Failed to run scheduled check_and_update_live_activities")

    # Use APScheduler to call our submit function every minute
    scheduler.add_job(func=schedule_job_submit, trigger="interval", minutes=1, id="live_activity_updates", next_run_time=datetime.now())

    # Schedule daily NFL games fetch at 8 AM
    scheduler.add_job(func=update_nfl_games, trigger="cron", hour=8, minute=0, id="daily_games_fetch")

    # Schedule daily NFL players fetch at 8 AM
    scheduler.add_job(func=update_nfl_players, trigger="cron", hour=8, minute=5, id="daily_players_fetch")

    # Schedule game start checker every 5 minutes
    scheduler.add_job(func=check_and_start_live_activities, trigger="interval", minutes=5, id="game_start_checker")

    # Load players data on startup (from file if exists, otherwise fetch from API)
    load_players_on_startup()

    # Fetch games immediately on startup
    update_nfl_games()

    scheduler.start()
    logger.info("Startup tasks complete. Scheduler started with game monitoring.")

@app.route("/games", methods=["GET"])
def get_nfl_games():
    return jsonify({
        "games": app_state.nfl_games,
        "last_fetched": app_state.games_last_fetched.isoformat() if app_state.games_last_fetched else None,
        "total_games": len(app_state.nfl_games)
    })

@app.route("/games/refresh", methods=["POST"])
def refresh_nfl_games():
    update_nfl_games()
    return jsonify({
        "status": "success",
        "message": "Games data refreshed",
        "games": app_state.nfl_games,
        "total_games": len(app_state.nfl_games)
    })

@app.route("/players/refresh", methods=["POST"])
def refresh_nfl_players():
    update_nfl_players()
    return jsonify({
        "status": "success",
        "message": "Players data refreshed",
        "total_players": len(app_state.nfl_players),
        "last_fetched": app_state.players_last_fetched.isoformat() if app_state.players_last_fetched else None
    })

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == "__main__":
    startup_tasks()
    try:
        # run Flask normally
        app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=False, threaded=True)
    finally:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass
        logger.info("Sleeper Live Activity API stopped")