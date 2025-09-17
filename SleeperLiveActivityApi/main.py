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
        # Player scoring system
        self.user_previous_pts_ppr: Dict[str, float] = {}  # device_id -> previous total pts_ppr
        self.user_starter_player_ids: Dict[str, List[str]] = {}  # device_id -> list of starter player IDs
        self.last_projection_totals: Dict[str, float] = {}  # device_id -> last total projections

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
# GraphQL client for player stats and projections
# -----------------------
class PlayerStatsClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.timeout = 30
        # You need to replace this with the actual GraphQL endpoint from your API provider
        # This is a placeholder - the real endpoint is not publicly documented
        self.graphql_url = "https://sleeper.com/graphql"
        logger.warning(f"GraphQL endpoint configured: {self.graphql_url}")

    def get_player_scores_and_projections(self, player_ids: List[str], season: str = "2025", week: int = 3) -> Dict:
        """Fetch player stats and projections for given player IDs using the GraphQL API from read.txt"""
        if not player_ids:
            return {"data": {"nfl__regular__2025__3__stat": [], "nfl__regular__2025__3__proj": []}}

        # Build the GraphQL query based on the structure in read.txt
        query = f"""
        query get_player_score_and_projections_batch {{
          nfl__regular__{season}__{week}__stat: stats_for_players_in_week(
            sport: "nfl"
            season: "{season}"
            category: "stat"
            season_type: "regular"
            week: {week}
            player_ids: {json.dumps(player_ids)}
          ) {{
            game_id
            opponent
            player_id
            stats
            team
            week
            season
          }}

          nfl__regular__{season}__{week}__proj: stats_for_players_in_week(
            sport: "nfl"
            season: "{season}"
            category: "proj"
            season_type: "regular"
            week: {week}
            player_ids: {json.dumps(player_ids)}
          ) {{
            game_id
            opponent
            player_id
            stats
            team
            week
            season
          }}
        }}
        """

        try:
            logger.info(f"Sending GraphQL request for {len(player_ids)} players to {self.graphql_url}")
            response = self.session.post(
                self.graphql_url,
                json={"query": query},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"GraphQL response status: {response.status_code}")
            if "data" in result:
                stats_count = len(result["data"].get(f"nfl__regular__{season}__{week}__stat", []))
                proj_count = len(result["data"].get(f"nfl__regular__{season}__{week}__proj", []))
                logger.info(f"Received {stats_count} player stats and {proj_count} projections")
            return result
        except Exception as e:
            logger.error(f"Error fetching player stats from GraphQL: {e}")
            logger.error(f"GraphQL URL: {self.graphql_url}")
            logger.error(f"Query sample: {query[:200]}...")
            # Return empty data structure to avoid crashes
            return {"data": {"nfl__regular__2025__3__stat": [], "nfl__regular__2025__3__proj": []}}

player_stats_client = PlayerStatsClient()

# -----------------------
# Player scoring helper functions
# -----------------------
def get_user_starter_player_ids(device_id: str) -> List[str]:
    """Get the list of starter player IDs for a user's live activity"""
    if device_id not in app_state.user_configs:
        return []

    user_config = app_state.user_configs[device_id]
    league_id = user_config["league_id"]
    user_id = user_config["user_id"]

    try:
        # Get current week
        nfl_state = sleeper_client.get_nfl_state()
        current_week = nfl_state.get("week", 1) if isinstance(nfl_state, dict) else 1

        # Get league rosters
        rosters = sleeper_client.get_league_rosters(league_id)

        # Find user's roster
        user_roster = None
        for roster in rosters:
            if roster.get("owner_id") == user_id:
                user_roster = roster
                break

        if user_roster and "starters" in user_roster:
            starter_ids = user_roster["starters"]
            # Cache the starter IDs for this device
            app_state.user_starter_player_ids[device_id] = starter_ids
            logger.info(f"Found {len(starter_ids)} starters for device {device_id}")
            return starter_ids
        else:
            logger.warning(f"No roster or starters found for device {device_id}")
            return []

    except Exception as e:
        logger.error(f"Error getting starter player IDs for device {device_id}: {e}")
        return []

def calculate_total_pts_ppr(player_stats_data: List[Dict]) -> float:
    """Calculate total pts_ppr from player stats data"""
    total_pts_ppr = 0.0
    logger.debug(f"Calculating pts_ppr for {len(player_stats_data)} players")

    for i, player_data in enumerate(player_stats_data):
        player_id = player_data.get("player_id", "unknown")
        stats = player_data.get("stats", {})
        if isinstance(stats, dict):
            pts_ppr = stats.get("pts_ppr", 0.0)
            if isinstance(pts_ppr, (int, float)):
                total_pts_ppr += float(pts_ppr)
                logger.debug(f"Player {player_id}: {pts_ppr} pts_ppr")
            else:
                logger.debug(f"Player {player_id}: No valid pts_ppr data")
        else:
            logger.debug(f"Player {player_id}: No stats data")

    total_pts_ppr = round(total_pts_ppr, 2)
    logger.info(f"Total pts_ppr calculated: {total_pts_ppr}")
    return total_pts_ppr

def calculate_total_projections(player_proj_data: List[Dict]) -> float:
    """Calculate total projected pts_ppr from player projection data"""
    total_projections = 0.0
    logger.debug(f"Calculating projections for {len(player_proj_data)} players")

    for player_data in player_proj_data:
        player_id = player_data.get("player_id", "unknown")
        stats = player_data.get("stats", {})
        if isinstance(stats, dict):
            pts_ppr = stats.get("pts_ppr", 0.0)
            if isinstance(pts_ppr, (int, float)):
                total_projections += float(pts_ppr)
                # Get player name from cached NFL players data
                player_name = app_state.nfl_players.get(player_id, {}).get("full_name", f"Player {player_id}")
                logger.info(f"{player_name} ({player_id}): {pts_ppr} projected pts_ppr")
            else:
                logger.debug(f"Player {player_id}: No valid projected pts_ppr data")
        else:
            logger.debug(f"Player {player_id}: No projection stats data")

    total_projections = round(total_projections, 2)
    logger.info(f"Total projections calculated: {total_projections}")
    return total_projections

async def update_user_player_scores(device_id: str):
    """Update player scores and projections for a specific user/device"""
    try:
        # Get starter player IDs
        starter_ids = get_user_starter_player_ids(device_id)
        if not starter_ids:
            logger.warning(f"No starter IDs found for device {device_id}")
            return

        # Get current week from NFL state
        nfl_state_data = await asyncio.to_thread(sleeper_client.get_nfl_state)
        current_week = nfl_state_data.get("week", 1) if isinstance(nfl_state_data, dict) else 1

        # Fetch player stats and projections
        logger.info(f"Fetching stats for {len(starter_ids)} players for device {device_id}")
        stats_data = await asyncio.to_thread(
            player_stats_client.get_player_scores_and_projections,
            starter_ids,
            "2025",
            current_week
        )

        if "data" in stats_data:
            # Extract player stats and projections
            player_stats = stats_data["data"].get(f"nfl__regular__2025__{current_week}__stat", [])
            player_projections = stats_data["data"].get(f"nfl__regular__2025__{current_week}__proj", [])

            # Calculate totals
            current_pts_ppr = calculate_total_pts_ppr(player_stats)
            current_projections = calculate_total_projections(player_projections)

            logger.info(f"Device {device_id}: Current pts_ppr={current_pts_ppr}, Projections={current_projections}")

            # Get previous scores
            previous_pts_ppr = app_state.user_previous_pts_ppr.get(device_id, 0.0)
            previous_projections = app_state.last_projection_totals.get(device_id, 0.0)

            # Check if scores or projections have changed
            pts_ppr_changed = abs(current_pts_ppr - previous_pts_ppr) > 0.01  # Small tolerance for floating point
            projections_changed = abs(current_projections - previous_projections) > 0.01

            if pts_ppr_changed or projections_changed:
                logger.info(f"Device {device_id}: pts_ppr changed from {previous_pts_ppr} to {current_pts_ppr}, projections from {previous_projections} to {current_projections}")

                # Update stored values
                app_state.user_previous_pts_ppr[device_id] = current_pts_ppr
                app_state.last_projection_totals[device_id] = current_projections

                # Update live activity with new scoring data
                if device_id in app_state.active_live_activities:
                    activity = app_state.active_live_activities[device_id]
                    user_config = activity["user_config"]

                    # Get live activity token
                    live_activity_token = app_state.live_activity_tokens.get(device_id)
                    if live_activity_token:
                        # Get comprehensive activity data and add player scoring info
                        activity_data = await live_activity_manager.get_comprehensive_activity_data(user_config)

                        # Add player scoring information to the activity data
                        activity_data["playerPtsPpr"] = current_pts_ppr
                        activity_data["projectedTotal"] = current_projections

                        # Create appropriate message based on what changed
                        if pts_ppr_changed and current_pts_ppr > 0:
                            activity_data["message"] = f"Player scores updated: {current_pts_ppr:.1f} pts"
                        elif projections_changed:
                            activity_data["message"] = f"Projections updated: {current_projections:.1f} pts projected"
                        else:
                            activity_data["message"] = f"Fantasy data updated"

                        # Send update
                        await live_activity_manager.send_live_activity_update(live_activity_token, activity_data)

                        # Update last update timestamp
                        activity["last_update"] = datetime.now()

                        logger.info(f"Updated live activity for device {device_id} with new player scores")
                    else:
                        logger.warning(f"No live activity token for device {device_id}")
            else:
                logger.debug(f"Device {device_id}: No significant change in pts_ppr ({current_pts_ppr})")

        else:
            logger.error(f"Invalid stats data structure for device {device_id}")

    except Exception as e:
        logger.exception(f"Error updating player scores for device {device_id}: {e}")

async def update_all_live_activity_player_scores():
    """Update player scores for all active live activities"""
    logger.info(f"Updating player scores for {len(app_state.active_live_activities)} active live activities")

    # Process all active live activities
    update_tasks = []
    for device_id in list(app_state.active_live_activities.keys()):
        task = update_user_player_scores(device_id)
        update_tasks.append(task)

    # Run all updates concurrently for efficiency
    if update_tasks:
        await asyncio.gather(*update_tasks, return_exceptions=True)

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

    # Schedule player score updates every minute
    def schedule_player_score_updates():
        try:
            submit_to_apns_loop(update_all_live_activity_player_scores())
        except Exception:
            logger.exception("Failed to run scheduled player score updates")

    scheduler.add_job(func=schedule_player_score_updates, trigger="interval", minutes=1, id="player_score_updates", next_run_time=datetime.now())

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

@app.route("/player-scores/<device_id>", methods=["GET"])
def get_player_scores(device_id):
    """Get player scoring data for a specific device"""
    if device_id not in app_state.user_configs:
        return jsonify({"error": "Device not found"}), 404

    starter_ids = app_state.user_starter_player_ids.get(device_id, [])
    current_pts_ppr = app_state.user_previous_pts_ppr.get(device_id, 0.0)
    current_projections = app_state.last_projection_totals.get(device_id, 0.0)

    return jsonify({
        "device_id": device_id,
        "starter_player_ids": starter_ids,
        "current_pts_ppr": current_pts_ppr,
        "current_projections": current_projections,
        "total_starters": len(starter_ids)
    })

@app.route("/player-scores", methods=["GET"])
def get_all_player_scores():
    """Get player scoring data for all devices"""
    scores_data = []
    for device_id in app_state.user_configs.keys():
        starter_ids = app_state.user_starter_player_ids.get(device_id, [])
        current_pts_ppr = app_state.user_previous_pts_ppr.get(device_id, 0.0)
        current_projections = app_state.last_projection_totals.get(device_id, 0.0)

        scores_data.append({
            "device_id": device_id,
            "starter_player_ids": starter_ids,
            "current_pts_ppr": current_pts_ppr,
            "current_projections": current_projections,
            "total_starters": len(starter_ids),
            "has_live_activity": device_id in app_state.active_live_activities
        })

    return jsonify({
        "player_scores": scores_data,
        "total_devices": len(scores_data)
    })

@app.route("/player-scores/refresh/<device_id>", methods=["POST"])
def refresh_player_scores(device_id):
    """Manually refresh player scores for a specific device"""
    if device_id not in app_state.user_configs:
        return jsonify({"error": "Device not found"}), 404

    try:
        # Submit the update task to the APNS loop
        submit_to_apns_loop(update_user_player_scores(device_id))
        return jsonify({
            "status": "success",
            "message": f"Player scores refresh initiated for device {device_id}"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/player-scores/refresh", methods=["POST"])
def refresh_all_player_scores():
    """Manually refresh player scores for all devices"""
    try:
        # Submit the update task to the APNS loop
        submit_to_apns_loop(update_all_live_activity_player_scores())
        return jsonify({
            "status": "success",
            "message": "Player scores refresh initiated for all active live activities"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/debug/graphql-test", methods=["POST"])
def test_graphql():
    """Test GraphQL endpoint with sample player IDs"""
    try:
        data = request.get_json() or {}
        player_ids = data.get("player_ids", ["4892", "8150", "8228"])  # Sample IDs from read.txt
        season = data.get("season", "2025")
        week = data.get("week", 3)

        # Test the GraphQL call
        result = player_stats_client.get_player_scores_and_projections(player_ids, season, week)

        return jsonify({
            "status": "success",
            "graphql_url": player_stats_client.graphql_url,
            "player_ids": player_ids,
            "season": season,
            "week": week,
            "result": result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/debug/config", methods=["GET"])
def debug_config():
    """Get debug configuration info"""
    return jsonify({
        "graphql_url": player_stats_client.graphql_url,
        "active_live_activities": len(app_state.active_live_activities),
        "user_configs": len(app_state.user_configs),
        "cached_starter_ids": {k: len(v) for k, v in app_state.user_starter_player_ids.items()},
        "cached_pts_ppr": app_state.user_previous_pts_ppr,
        "projection_totals": app_state.last_projection_totals
    })

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