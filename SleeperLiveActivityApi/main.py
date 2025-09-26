# main.py
import os
import io
import json
import base64
import logging
import threading
import requests
import time
from PIL import Image
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from functools import wraps

# Async / APNS
import asyncio
import aiohttp

# =============================================================================
# CONFIGURABLE UPDATE FREQUENCIES (in seconds)
# =============================================================================
LIVE_ACTIVITY_UPDATE_INTERVAL = 30     # Both player and team score updates
GAME_START_CHECK_INTERVAL = 300        # NFL game start detection (5 minutes)
GAME_END_CHECK_INTERVAL = 180          # NFL game end detection (3 minutes)
NFL_GAMES_REFRESH_HOUR = 8             # Daily NFL games refresh (8 AM)
NFL_PLAYERS_REFRESH_HOUR = 8           # Daily NFL players refresh (8:05 AM)
NFL_PLAYERS_REFRESH_MINUTE = 5

# Cache expiration for on-demand requests
PLAYER_CACHE_MAX_AGE = 60              # Max age before triggering fresh fetch on app load

# Global NFL state cache (updated once daily)
global_nfl_week = 1                    # Default fallback
global_nfl_week_last_update = None

# Cache configurations
LEAGUE_USERS_CACHE_SECONDS = 30 * 60   # 30 minutes (same as avatar cache)
LEAGUE_INFO_CACHE_SECONDS = 24 * 60 * 60  # 24 hours
LEAGUE_ROSTERS_CACHE_SECONDS = 10 * 60  # 10 minutes (rosters change more frequently)
from aioapns import APNs, NotificationRequest, PushType
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables
load_dotenv()

# API Key Configuration
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    logger = logging.getLogger(__name__)
    logger.warning("No API_KEY found in environment variables. API will be unprotected!")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": ["*"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-API-Key"]
    }
})

# API Key Authentication - Global Protection
@app.before_request
def require_api_key():
    """Global API key authentication for all endpoints except health checks."""
    # Skip auth if no API key is configured (development mode)
    if not API_KEY:
        return None

    # Allow health check endpoints without auth
    if request.endpoint in ['health_check', 'get_nfl_state']:
        return None

    # Allow OPTIONS requests (CORS preflight)
    if request.method == 'OPTIONS':
        return None

    # Check for API key in headers
    provided_key = request.headers.get('X-API-Key')
    if not provided_key:
        return jsonify({"error": "API key required. Provide X-API-Key header."}), 401

    # Validate API key
    if provided_key != API_KEY:
        return jsonify({"error": "Invalid API key"}), 401

    return None

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
        self.league_avatar_cache: Dict[str, Tuple[float, Dict[str, str]]] = {}  # league_id -> (timestamp, {user_id: avatar_url})
        self.league_users_cache: Dict[str, Tuple[float, List[Dict]]] = {}  # league_id -> (timestamp, users_list)
        self.league_info_cache: Dict[str, Tuple[float, Dict]] = {}  # league_id -> (timestamp, league_info)
        self.league_rosters_cache: Dict[str, Tuple[float, List[Dict]]] = {}  # league_id -> (timestamp, rosters_list)
        self.last_scores: Dict[str, Dict] = {}  # device_id -> last score data
        self.nfl_games: List[Dict] = []  # today's NFL games from ESPN
        self.games_last_fetched: Optional[datetime] = None
        self.nfl_players: Dict = {}  # NFL players data from Sleeper API
        self.players_last_fetched: Optional[datetime] = None
        # Player scoring system
        self.user_previous_pts_ppr: Dict[str, float] = {}  # device_id -> previous total pts_ppr
        self.user_starter_player_ids: Dict[str, List[str]] = {}  # device_id -> list of starter player IDs
        self.last_projection_totals: Dict[str, float] = {}  # device_id -> last total projections
        self.previous_player_scores: Dict[str, Dict[str, float]] = {}  # device_id -> {player_id: pts_ppr}

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

    def get_league_users(self, league_id: str) -> List[Dict]:
        try:
            response = self.session.get(f"{self.BASE_URL}/league/{league_id}/users", timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching league users: {e}")
            raise

    def get_league_info(self, league_id: str) -> Dict:
        try:
            response = self.session.get(f"{self.BASE_URL}/league/{league_id}", timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching league info: {e}")
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
# Optimized Player Stats Manager
# -----------------------
class OptimizedPlayerStatsManager:
    def __init__(self):
        self.player_stats_cache: Dict[str, Dict] = {}  # player_id -> {pts_ppr, projected_pts, etc}
        self.last_fetch_time: Optional[datetime] = None
        self.current_week: int = 3
        self.current_season: str = "2025"

    def get_all_active_player_ids(self) -> List[str]:
        """Collect unique player IDs from all active live activities AND their opponents"""
        all_player_ids = set()

        logger.info(f"DEBUG: Found {len(app_state.active_live_activities)} active live activities")
        current_week = get_current_nfl_week()

        for device_id in app_state.active_live_activities.keys():
            try:
                # Get user's starter IDs
                starter_ids = app_state.user_starter_player_ids.get(device_id, [])
                if not starter_ids:
                    # Try to fetch starters if not cached
                    logger.info(f"DEBUG: No cached starters for {device_id}, fetching...")
                    starter_ids = get_user_starter_player_ids(device_id)
                logger.info(f"DEBUG: Device {device_id} has {len(starter_ids)} starters")
                all_player_ids.update(starter_ids)

                # Also get opponent's starter IDs
                user_config = app_state.active_live_activities[device_id]["user_config"]
                league_id = user_config["league_id"]
                user_id = user_config["user_id"]

                # Get matchups and rosters to find opponent
                matchups = sleeper_client.get_matchups(league_id, current_week)
                rosters = get_cached_league_rosters(league_id)

                # Find user's roster and matchup
                user_roster = None
                for roster in rosters:
                    if roster.get("owner_id") == user_id:
                        user_roster = roster
                        break

                if user_roster:
                    user_matchup = None
                    for m in matchups:
                        if m.get("roster_id") == user_roster.get("roster_id"):
                            user_matchup = m
                            break

                    if user_matchup:
                        matchup_id = user_matchup.get("matchup_id")
                        # Find opponent roster in same matchup
                        for m in matchups:
                            if (m.get("matchup_id") == matchup_id and
                                m.get("roster_id") != user_roster.get("roster_id")):
                                # Found opponent matchup, now get their roster
                                opponent_roster_id = m.get("roster_id")
                                for roster in rosters:
                                    if roster.get("roster_id") == opponent_roster_id:
                                        opponent_starters = roster.get("starters", [])
                                        if opponent_starters:
                                            all_player_ids.update(opponent_starters)
                                            logger.info(f"DEBUG: Added {len(opponent_starters)} opponent starters for {device_id}")
                                        break
                                break

            except Exception as e:
                logger.error(f"Error collecting player IDs for device {device_id}: {e}")
                # Continue with other devices even if one fails

        logger.info(f"Collected {len(all_player_ids)} unique players (including opponents) from {len(app_state.active_live_activities)} active live activities")
        return list(all_player_ids)

    async def update_all_player_stats(self):
        """Single GraphQL call for ALL active players across ALL live activities"""
        try:
            # Get current NFL week from cache (no API call needed!)
            self.current_week = get_current_nfl_week()

            # Collect all unique player IDs
            all_player_ids = self.get_all_active_player_ids()

            if not all_player_ids:
                logger.info("No active players to fetch stats for")
                return

            logger.info(f"Fetching stats for {len(all_player_ids)} players in single GraphQL request")

            # Single GraphQL call for ALL players
            stats_data = await asyncio.to_thread(
                player_stats_client.get_player_scores_and_projections,
                all_player_ids,
                self.current_season,
                self.current_week
            )

            # Process and cache the results
            if "data" in stats_data:
                player_stats = stats_data["data"].get(f"nfl__regular__{self.current_season}__{self.current_week}__stat", [])
                player_projections = stats_data["data"].get(f"nfl__regular__{self.current_season}__{self.current_week}__proj", [])

                # Build cache: player_id -> stats
                self.player_stats_cache = {}

                # Process actual stats
                for player_data in player_stats:
                    player_id = player_data.get("player_id")
                    if player_id:
                        stats = player_data.get("stats", {})
                        self.player_stats_cache[player_id] = {
                            "pts_ppr": stats.get("pts_ppr", 0.0),
                            "stats": stats
                        }

                # Process projections
                for player_data in player_projections:
                    player_id = player_data.get("player_id")
                    if player_id:
                        stats = player_data.get("stats", {})
                        if player_id in self.player_stats_cache:
                            self.player_stats_cache[player_id]["projected_pts"] = stats.get("pts_ppr", 0.0)
                        else:
                            self.player_stats_cache[player_id] = {
                                "pts_ppr": 0.0,
                                "projected_pts": stats.get("pts_ppr", 0.0),
                                "stats": {}
                            }

                self.last_fetch_time = datetime.now()
                logger.info(f"Successfully cached stats for {len(self.player_stats_cache)} players")

                # Now update all live activities with the cached data
                await self.update_all_live_activities_from_cache()

            else:
                logger.error("Invalid GraphQL response structure")

        except Exception as e:
            logger.exception(f"Error in optimized player stats update: {e}")

    def get_user_totals(self, device_id: str) -> tuple[float, float]:
        """Get user's pts_ppr and projection totals from cached data"""
        starter_ids = app_state.user_starter_player_ids.get(device_id, [])
        if not starter_ids:
            starter_ids = get_user_starter_player_ids(device_id)

        total_pts_ppr = 0.0
        total_projections = 0.0

        for player_id in starter_ids:
            player_data = self.player_stats_cache.get(player_id, {})
            total_pts_ppr += float(player_data.get("pts_ppr", 0.0))
            total_projections += float(player_data.get("projected_pts", 0.0))

        return round(total_pts_ppr, 2), round(total_projections, 2)

    async def update_all_live_activities_from_cache(self):
        """Update all live activities using cached player data"""
        logger.info(f"Updating {len(app_state.active_live_activities)} live activities from cached player data")

        update_tasks = []
        for device_id in list(app_state.active_live_activities.keys()):
            task = self.update_single_live_activity_from_cache(device_id)
            update_tasks.append(task)

        # Run all updates concurrently
        if update_tasks:
            await asyncio.gather(*update_tasks, return_exceptions=True)

    def get_top_scoring_player_from_matchup(self, device_id: str) -> tuple[str, float, bool]:
        """Find the player with the highest point increase since last update from either team in the matchup"""
        previous_scores = app_state.previous_player_scores.get(device_id, {})
        top_player_name = ""
        top_point_diff = 0.0
        is_user_player = True

        try:
            # Get user's starter IDs
            user_starter_ids = app_state.user_starter_player_ids.get(device_id, [])

            # Get opponent's starter IDs
            opponent_starter_ids = []
            if device_id in app_state.active_live_activities:
                user_config = app_state.active_live_activities[device_id]["user_config"]
                league_id = user_config["league_id"]
                user_id = user_config["user_id"]
                current_week = get_current_nfl_week()

                # Get matchups and rosters to find opponent
                matchups = sleeper_client.get_matchups(league_id, current_week)
                rosters = get_cached_league_rosters(league_id)

                # Find user's roster and matchup
                user_roster = None
                for roster in rosters:
                    if roster.get("owner_id") == user_id:
                        user_roster = roster
                        break

                if user_roster:
                    user_matchup = None
                    for m in matchups:
                        if m.get("roster_id") == user_roster.get("roster_id"):
                            user_matchup = m
                            break

                    if user_matchup:
                        matchup_id = user_matchup.get("matchup_id")
                        # Find opponent roster in same matchup
                        for m in matchups:
                            if (m.get("matchup_id") == matchup_id and
                                m.get("roster_id") != user_roster.get("roster_id")):
                                opponent_roster_id = m.get("roster_id")
                                for roster in rosters:
                                    if roster.get("roster_id") == opponent_roster_id:
                                        opponent_starter_ids = roster.get("starters", [])
                                        break
                                break

            # Check all players from both teams
            all_players = [(pid, True) for pid in user_starter_ids] + [(pid, False) for pid in opponent_starter_ids]

            for player_id, is_user in all_players:
                current_data = self.player_stats_cache.get(player_id, {})
                current_score = float(current_data.get("pts_ppr", 0.0))
                previous_score = previous_scores.get(player_id, 0.0)

                point_diff = current_score - previous_score

                if point_diff > top_point_diff:
                    top_point_diff = point_diff
                    # Get player name from NFL players cache
                    player_info = app_state.nfl_players.get(player_id, {})
                    player_name = player_info.get("full_name", player_info.get("last_name", f"Player {player_id}"))
                    top_player_name = player_name
                    is_user_player = is_user

        except Exception as e:
            logger.error(f"Error finding top scoring player for {device_id}: {e}")

        return top_player_name, top_point_diff, is_user_player

    async def update_single_live_activity_from_cache(self, device_id: str):
        """Update a single live activity using cached player data"""
        try:
            # Get totals from cache
            current_pts_ppr, current_projections = self.get_user_totals(device_id)

            # Get previous scores
            previous_pts_ppr = app_state.user_previous_pts_ppr.get(device_id, 0.0)
            previous_projections = app_state.last_projection_totals.get(device_id, 0.0)

            # Check if scores or projections have changed
            pts_ppr_changed = abs(current_pts_ppr - previous_pts_ppr) > 0.01
            projections_changed = abs(current_projections - previous_projections) > 0.01

            logger.info(f"DEBUG: Device {device_id} - current: {current_pts_ppr:.2f}pts/{current_projections:.2f}proj, previous: {previous_pts_ppr:.2f}pts/{previous_projections:.2f}proj, changed: {pts_ppr_changed}/{projections_changed}")

            # Always check for top scoring player from either team
            top_player_name, top_point_diff, is_user_player = self.get_top_scoring_player_from_matchup(device_id)

            # Store current individual player scores for next comparison (both user and opponent)
            current_player_scores = {}

            # Get user starters
            user_starter_ids = app_state.user_starter_player_ids.get(device_id, [])
            for player_id in user_starter_ids:
                player_data = self.player_stats_cache.get(player_id, {})
                current_player_scores[player_id] = float(player_data.get("pts_ppr", 0.0))

            # Get opponent starters and add to tracking
            try:
                if device_id in app_state.active_live_activities:
                    user_config = app_state.active_live_activities[device_id]["user_config"]
                    league_id = user_config["league_id"]
                    user_id = user_config["user_id"]
                    current_week = get_current_nfl_week()

                    matchups = sleeper_client.get_matchups(league_id, current_week)
                    rosters = get_cached_league_rosters(league_id)

                    # Find opponent's starters
                    user_roster = None
                    for roster in rosters:
                        if roster.get("owner_id") == user_id:
                            user_roster = roster
                            break

                    if user_roster:
                        user_matchup = None
                        for m in matchups:
                            if m.get("roster_id") == user_roster.get("roster_id"):
                                user_matchup = m
                                break

                        if user_matchup:
                            matchup_id = user_matchup.get("matchup_id")
                            for m in matchups:
                                if (m.get("matchup_id") == matchup_id and
                                    m.get("roster_id") != user_roster.get("roster_id")):
                                    opponent_roster_id = m.get("roster_id")
                                    for roster in rosters:
                                        if roster.get("roster_id") == opponent_roster_id:
                                            opponent_starters = roster.get("starters", [])
                                            for player_id in opponent_starters:
                                                player_data = self.player_stats_cache.get(player_id, {})
                                                current_player_scores[player_id] = float(player_data.get("pts_ppr", 0.0))
                                            break
                                    break
            except Exception as e:
                logger.error(f"Error tracking opponent scores for {device_id}: {e}")

            app_state.previous_player_scores[device_id] = current_player_scores

            if pts_ppr_changed or projections_changed or (top_player_name and top_point_diff > 0.1):
                logger.info(f"Device {device_id}: pts_ppr changed from {previous_pts_ppr} to {current_pts_ppr}, projections from {previous_projections} to {current_projections}")
                if top_player_name and top_point_diff > 0:
                    team_indicator = "YOUR" if is_user_player else "OPP"
                    logger.info(f"Top performer: {top_player_name} (+{top_point_diff:.1f} pts) [{team_indicator}]")

                # Update stored total values
                app_state.user_previous_pts_ppr[device_id] = current_pts_ppr
                app_state.last_projection_totals[device_id] = current_projections

                # Update live activity with new scoring data
                if device_id in app_state.active_live_activities:
                    activity = app_state.active_live_activities[device_id]
                    user_config = activity["user_config"]

                    # Get live activity token
                    live_activity_token = app_state.live_activity_tokens.get(device_id)
                    if live_activity_token:
                        logger.info(f"DEBUG: Sending update to live activity token for {device_id}")
                        # Get comprehensive activity data and add player scoring info
                        activity_data = await live_activity_manager.get_comprehensive_activity_data(user_config)

                        # Add player scoring information to the activity data
                        activity_data["playerPtsPpr"] = current_pts_ppr
                        activity_data["projectedTotal"] = current_projections

                        # Create message with top scoring player from either team
                        if top_player_name and top_point_diff > 0.1:
                            team_prefix = "🔥 " if is_user_player else "⚡ "
                            activity_data["message"] = f"{team_prefix}{top_player_name} +{top_point_diff:.1f} pts"
                        else:
                            activity_data["message"] = ""

                        # Determine if we need an alert (3+ points)
                        needs_alert = top_point_diff >= 3.0

                        # Send update with potential alert
                        await live_activity_manager.send_live_activity_update(live_activity_token, activity_data, needs_alert)

                        # Update last update timestamp
                        activity["last_update"] = datetime.now()

                        logger.info(f"Updated live activity for device {device_id} with new player scores")
                    else:
                        logger.warning(f"DEBUG: No live activity token for device {device_id}")
                else:
                    logger.warning(f"DEBUG: Device {device_id} not in active_live_activities")
            else:
                logger.debug(f"Device {device_id}: No significant change in pts_ppr ({current_pts_ppr}) or projections ({current_projections})")

        except Exception as e:
            logger.exception(f"Error updating live activity for device {device_id}: {e}")

# Initialize the optimized manager
optimized_player_manager = OptimizedPlayerStatsManager()

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
        # Get league rosters from cache
        rosters = get_cached_league_rosters(league_id)

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
                        "status": event.get("status", ""),
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

def update_nfl_week():
    """Update the global NFL week cache (called once daily)."""
    global global_nfl_week, global_nfl_week_last_update
    try:
        nfl_state = sleeper_client.get_nfl_state()
        if isinstance(nfl_state, dict) and "week" in nfl_state:
            global_nfl_week = nfl_state["week"]
            global_nfl_week_last_update = datetime.now()
            logger.info(f"Updated global NFL week to: {global_nfl_week}")
        else:
            logger.warning("Failed to get valid NFL week from state")
    except Exception as e:
        logger.error(f"Failed to update NFL week: {e}")

def get_current_nfl_week() -> int:
    """Get current NFL week from cache (no API call needed)."""
    global global_nfl_week, global_nfl_week_last_update

    # If never updated or very stale (>1 day), update once
    if (global_nfl_week_last_update is None or
        (datetime.now() - global_nfl_week_last_update).total_seconds() > 86400):
        logger.info("NFL week cache is stale, updating...")
        update_nfl_week()

    return global_nfl_week

def get_cached_league_users(league_id: str) -> List[Dict]:
    """Get league users from cache, fetch if not available or stale."""
    cached_data = app_state.league_users_cache.get(league_id)

    # Check if cache is valid
    if cached_data:
        cache_time, users_data = cached_data
        if time.time() - cache_time < LEAGUE_USERS_CACHE_SECONDS:
            logger.debug(f"Using cached league users for {league_id}")
            return users_data

    # Cache miss or stale, fetch fresh data
    logger.info(f"Fetching fresh league users for {league_id}")
    try:
        users_data = sleeper_client.get_league_users(league_id)
        # Cache the result
        app_state.league_users_cache[league_id] = (time.time(), users_data)
        return users_data
    except Exception as e:
        logger.error(f"Failed to fetch league users for {league_id}: {e}")
        # Return stale cache if available, empty list otherwise
        if cached_data:
            return cached_data[1]
        return []

def get_cached_league_info(league_id: str) -> Dict:
    """Get league info from cache, fetch if not available or stale."""
    cached_data = app_state.league_info_cache.get(league_id)

    # Check if cache is valid
    if cached_data:
        cache_time, league_info = cached_data
        if time.time() - cache_time < LEAGUE_INFO_CACHE_SECONDS:
            logger.debug(f"Using cached league info for {league_id}")
            return league_info

    # Cache miss or stale, fetch fresh data
    logger.info(f"Fetching fresh league info for {league_id}")
    try:
        league_info = sleeper_client.get_league_info(league_id)
        # Cache the result
        app_state.league_info_cache[league_id] = (time.time(), league_info)
        return league_info
    except Exception as e:
        logger.error(f"Failed to fetch league info for {league_id}: {e}")
        # Return stale cache if available, empty dict otherwise
        if cached_data:
            return cached_data[1]
        return {"name": "Fantasy Football"}  # Fallback

def get_cached_league_rosters(league_id: str) -> List[Dict]:
    """Get league rosters from cache, fetch if not available or stale."""
    cached_data = app_state.league_rosters_cache.get(league_id)

    # Check if cache is valid
    if cached_data:
        cache_time, rosters_data = cached_data
        if time.time() - cache_time < LEAGUE_ROSTERS_CACHE_SECONDS:
            logger.debug(f"Using cached league rosters for {league_id}")
            return rosters_data

    # Cache miss or stale, fetch fresh data
    logger.info(f"Fetching fresh league rosters for {league_id}")
    try:
        rosters_data = sleeper_client.get_league_rosters(league_id)
        # Cache the result
        app_state.league_rosters_cache[league_id] = (time.time(), rosters_data)
        return rosters_data
    except Exception as e:
        logger.error(f"Failed to fetch league rosters for {league_id}: {e}")
        # Return stale cache if available, empty list otherwise
        if cached_data:
            return cached_data[1]
        return []

def update_nfl_games():
    """Update the stored NFL games data."""
    try:
        games = fetch_nfl_games_from_espn()
        app_state.nfl_games = games
        app_state.games_last_fetched = datetime.now()
        logger.info(f"Updated NFL games data: {len(games)} games stored")

        # Also update NFL week since we're doing daily tasks
        update_nfl_week()
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

def get_users_with_players_in_games(games_starting_soon: List[Dict]) -> List[str]:
    """Return device_ids of users who have players in starting games (optimized for multiple users)."""
    try:
        # 1. Extract teams playing once
        teams_playing = set()
        for game in games_starting_soon:
            for competitor in game.get("competitors", []):
                team_abbr = competitor.get("abbreviation", "")
                if team_abbr:
                    teams_playing.add(team_abbr)

        logger.info(f"DEBUG: Teams playing in starting games: {teams_playing}")
        if not teams_playing:
            return []

        logger.debug(f"Teams playing in starting games: {teams_playing}")

        # 2. Group users by league to batch roster fetches
        users_by_league = {}
        for device_id, user_config in app_state.user_configs.items():
            league_id = user_config.get("league_id")
            if league_id:
                users_by_league.setdefault(league_id, []).append((device_id, user_config))

        users_to_notify = []

        # 3. Process each league once
        for league_id, league_users in users_by_league.items():
            try:
                rosters = get_cached_league_rosters(league_id)  # One call per league

                # Get matchups for this league once
                week = league_users[0][1].get("week", 1)  # All users in same league should have same week
                matchups = sleeper_client.get_matchups(league_id, week)

                # 4. Check each user in this league
                for device_id, user_config in league_users:
                    user_id = user_config.get("user_id")
                    if not user_id:
                        continue

                    # Find user's roster
                    user_roster = None
                    for roster in rosters:
                        if roster.get("owner_id") == user_id:
                            user_roster = roster
                            break

                    if not user_roster:
                        continue

                    # Find opponent roster from matchups
                    opponent_roster = None
                    for matchup in matchups:
                        if matchup.get("roster_id") == user_roster.get("roster_id"):
                            # Found user's matchup, find opponent
                            for opponent_matchup in matchups:
                                if (opponent_matchup.get("matchup_id") == matchup.get("matchup_id") and
                                    opponent_matchup.get("roster_id") != user_roster.get("roster_id")):
                                    # Found opponent, get their roster
                                    opponent_roster_id = opponent_matchup.get("roster_id")
                                    for roster in rosters:
                                        if roster.get("roster_id") == opponent_roster_id:
                                            opponent_roster = roster
                                            break
                                    break
                            break

                    # Collect all player IDs from both user and opponent
                    all_player_ids = []
                    if user_roster and "starters" in user_roster:
                        all_player_ids.extend(user_roster.get("starters", []))
                    if opponent_roster and "starters" in opponent_roster:
                        all_player_ids.extend(opponent_roster.get("starters", []))

                    # Check if any players play for teams that are playing
                    has_players_in_games = False
                    logger.debug(f"DEBUG: Checking {len(all_player_ids)} players for teams in {teams_playing}")
                    for player_id in all_player_ids:
                        if player_id in app_state.nfl_players:
                            player_team = app_state.nfl_players[player_id].get("team", "")
                            # Handle team abbreviation mismatch: Sleeper uses WAS, ESPN uses WSH
                            normalized_team = "WSH" if player_team == "WAS" else player_team
                            logger.debug(f"DEBUG: Player {player_id} team: {player_team} -> {normalized_team}")
                            if normalized_team in teams_playing:
                                logger.info(f"DEBUG: MATCH FOUND - Player {player_id} ({normalized_team}) in teams_playing {teams_playing}")
                                has_players_in_games = True
                                break

                    if has_players_in_games:
                        users_to_notify.append(device_id)
                        logger.debug(f"User {device_id} has players in starting games")

            except Exception as e:
                logger.error(f"Error processing league {league_id}: {e}")

        logger.info(f"Found {len(users_to_notify)} users with players in starting games out of {len(app_state.user_configs)} total users")
        return users_to_notify

    except Exception as e:
        logger.error(f"Error in get_users_with_players_in_games: {e}")
        return []

def check_and_start_live_activities():
    """Check if any games are starting now and auto-start live activities."""
    try:
        current_time = datetime.now()
        logger.info(f"Checking for games starting at {current_time}")

        # First, find all games starting soon
        games_starting_soon = []
        game_names = []
        has_live_games = False

        for game in app_state.nfl_games:
            try:
                # Check for live games to manage ending scheduler
                if game.get("status", "") == "in":
                    has_live_games = True

                # Parse game date
                game_date_str = game.get("date", "")
                if not game_date_str:
                    continue

                game_date = datetime.fromisoformat(game_date_str.replace('Z', '+00:00'))

                # Check if game is starting within the next 5 minutes
                time_diff = (game_date - current_time.replace(tzinfo=game_date.tzinfo)).total_seconds()

                if 0 <= time_diff <= 300:  # Game starting in next 5 minutes
                    games_starting_soon.append(game)  # Store full game object
                    game_names.append(game.get('name', 'Unknown Game'))

            except Exception as e:
                logger.error(f"Error processing game {game}: {e}")

        # Manage the ending scheduler based on live games
        manage_ending_scheduler(has_live_games)

        # If we have games starting soon, filter users and notify only those with players in the games
        if games_starting_soon:
            game_names_message = ", ".join(game_names)
            logger.info(f"Games starting soon: {game_names_message}")

            # Get only users who have players in these games
            users_to_notify = get_users_with_players_in_games(games_starting_soon)

            # Handle filtered users
            for device_id in users_to_notify:
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

def manage_ending_scheduler(has_live_games: bool):
    """Dynamically start/stop the ending scheduler based on whether games are live."""
    try:
        from apscheduler.jobstores.base import JobLookupError

        # Check if ending scheduler is currently running
        try:
            scheduler.get_job("game_end_checker")
            ending_scheduler_exists = True
        except JobLookupError:
            ending_scheduler_exists = False

        if has_live_games and not ending_scheduler_exists:
            # Start the ending scheduler - games are live
            logger.info("Live games detected, starting game ending scheduler")
            scheduler.add_job(
                func=check_and_end_live_activities,
                trigger="interval",
                seconds=GAME_END_CHECK_INTERVAL,
                id="game_end_checker"
            )
        elif not has_live_games and ending_scheduler_exists:
            # Stop the ending scheduler - no live games
            logger.info("No live games, stopping game ending scheduler")
            scheduler.remove_job("game_end_checker")

    except Exception as e:
        logger.error(f"Error managing ending scheduler: {e}")

def check_live_games_on_startup():
    """Check for live games on startup and initialize ending scheduler if needed."""
    try:
        has_live_games = False

        for game in app_state.nfl_games:
            if game.get("status", "") == "in":
                has_live_games = True
                break

        if has_live_games:
            logger.info("Live games detected on startup, starting game ending scheduler")
            scheduler.add_job(
                func=check_and_end_live_activities,
                trigger="interval",
                seconds=GAME_END_CHECK_INTERVAL,
                id="game_end_checker"
            )
        else:
            logger.info("No live games detected on startup")

    except Exception as e:
        logger.error(f"Error checking live games on startup: {e}")

def get_users_to_end_live_activities() -> List[str]:
    """Find users whose live activities should end (no players in live games). Optimized for multiple users."""
    try:
        # 1. Get teams from finished games (status: "post")
        finished_teams = set()
        live_teams = set()

        for game in app_state.nfl_games:
            status = game.get("status", "")
            competitors = game.get("competitors", [])

            for competitor in competitors:
                team_abbr = competitor.get("abbreviation", "")
                if team_abbr:
                    if status == "post":
                        finished_teams.add(team_abbr)
                    elif status == "in":  # Live game
                        live_teams.add(team_abbr)

        logger.debug(f"Finished teams: {finished_teams}, Live teams: {live_teams}")

        # 2. Group active users by league to batch API calls
        users_by_league = {}
        for device_id in app_state.active_live_activities.keys():
            if device_id in app_state.user_configs:
                user_config = app_state.user_configs[device_id]
                league_id = user_config.get("league_id")
                if league_id:
                    users_by_league.setdefault(league_id, []).append((device_id, user_config))

        users_to_end = []

        # 3. Process each league once
        for league_id, league_users in users_by_league.items():
            try:
                rosters = get_cached_league_rosters(league_id)  # One call per league
                week = league_users[0][1].get("week", 1)
                matchups = sleeper_client.get_matchups(league_id, week)

                # 4. Check each user in this league
                for device_id, user_config in league_users:
                    user_id = user_config.get("user_id")
                    if not user_id:
                        continue

                    # Find user's roster
                    user_roster = None
                    for roster in rosters:
                        if roster.get("owner_id") == user_id:
                            user_roster = roster
                            break

                    if not user_roster:
                        continue

                    # Find opponent roster
                    opponent_roster = None
                    for matchup in matchups:
                        if matchup.get("roster_id") == user_roster.get("roster_id"):
                            for opponent_matchup in matchups:
                                if (opponent_matchup.get("matchup_id") == matchup.get("matchup_id") and
                                    opponent_matchup.get("roster_id") != user_roster.get("roster_id")):
                                    opponent_roster_id = opponent_matchup.get("roster_id")
                                    for roster in rosters:
                                        if roster.get("roster_id") == opponent_roster_id:
                                            opponent_roster = roster
                                            break
                                    break
                            break

                    # Collect all player IDs from both user and opponent
                    all_player_ids = []
                    if user_roster and "starters" in user_roster:
                        all_player_ids.extend(user_roster.get("starters", []))
                    if opponent_roster and "starters" in opponent_roster:
                        all_player_ids.extend(opponent_roster.get("starters", []))

                    # Check if ALL players are from teams with finished games (no live games)
                    has_live_players = False
                    for player_id in all_player_ids:
                        if player_id in app_state.nfl_players:
                            player_team = app_state.nfl_players[player_id].get("team", "")
                            # Handle team abbreviation mismatch: Sleeper uses WAS, ESPN uses WSH
                            normalized_team = "WSH" if player_team == "WAS" else player_team
                            if normalized_team in live_teams:
                                has_live_players = True
                                break

                    # End live activity if no players have live games
                    if not has_live_players:
                        users_to_end.append(device_id)
                        logger.debug(f"User {device_id} has no players in live games, marking for end")

            except Exception as e:
                logger.error(f"Error processing league {league_id} for ending: {e}")

        logger.info(f"Found {len(users_to_end)} users to end live activities out of {len(app_state.active_live_activities)} active")
        return users_to_end

    except Exception as e:
        logger.error(f"Error in get_users_to_end_live_activities: {e}")
        return []

def check_and_end_live_activities():
    """Check if any live activities should end and end them."""
    try:
        logger.info("Checking for live activities to end")

        users_to_end = get_users_to_end_live_activities()

        for device_id in users_to_end:
            try:
                logger.info(f"Ending live activity for device {device_id}")
                stop_live_activity_by_id(device_id)
            except Exception as e:
                logger.error(f"Failed to end live activity for {device_id}: {e}")

    except Exception as e:
        logger.error(f"Error in check_and_end_live_activities: {e}")

def cleanup_expired_live_activities():
    """Clean up live activities that have exceeded their TTL (Time To Live)."""
    try:
        now = datetime.now()
        current_day = now.weekday()  # 0=Monday, 6=Sunday

        # Set TTL based on day of week
        if current_day == 6:  # Sunday - big football day
            max_age_hours = 16  # 6:30am-8:20pm + 2 hour buffer
        elif current_day in [0, 3]:  # Monday, Thursday - some games
            max_age_hours = 8
        else:  # Other days - minimal games
            max_age_hours = 6

        max_age = timedelta(hours=max_age_hours)
        logger.info(f"Running TTL cleanup with max age: {max_age_hours} hours")

        expired_devices = []
        for device_id, activity in app_state.active_live_activities.items():
            started_at = activity.get("started_at")
            if started_at and (now - started_at) > max_age:
                expired_devices.append(device_id)
                logger.info(f"Device {device_id} live activity expired (started {started_at}, age: {now - started_at})")

        # Clean up expired activities
        for device_id in expired_devices:
            try:
                logger.info(f"Cleaning up expired live activity for device {device_id}")
                stop_live_activity_by_id(device_id)
            except Exception as e:
                logger.error(f"Failed to cleanup expired activity for {device_id}: {e}")

        if expired_devices:
            logger.info(f"TTL cleanup completed: removed {len(expired_devices)} expired activities")
        else:
            logger.debug("TTL cleanup completed: no expired activities found")

    except Exception as e:
        logger.error(f"Error in cleanup_expired_live_activities: {e}")

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

    async def send_live_activity_update(self, push_token: str, activity_data: Dict, needs_alert: bool = False):
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

                # Add alert for big plays (3+ points)
                if needs_alert and activity_data.get("message"):
                    payload["aps"]["alert"] = {
                        "title": "Big Play!",
                        "body": activity_data["message"],
                        "sound": "default"
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
            # Get current week from cache (no API call needed!)
            current_week = get_current_nfl_week()

            # Fetch data - using cached functions where appropriate
            matchups = await asyncio.to_thread(sleeper_client.get_matchups, user_config["league_id"], current_week)
            rosters = await asyncio.to_thread(get_cached_league_rosters, user_config["league_id"])
            league_users = await asyncio.to_thread(get_cached_league_users, user_config["league_id"])
            league_info = await asyncio.to_thread(get_cached_league_info, user_config["league_id"])

            # find user roster
            user_roster = None
            opponent_roster = None
            for roster in rosters:
                if roster.get("owner_id") == user_config["user_id"]:
                    user_roster = roster
                    break

            if not user_roster:
                # Get league name even for fallback
                fallback_league_name = league_info.get("name", "Fantasy Football")
                return {
                    "totalPoints": 0.0,
                    "activePlayersCount": 0,
                    "teamName": "Your Team",
                    "opponentPoints": 0.0,
                    "opponentTeamName": "Opponent",
                    "leagueName": fallback_league_name,
                    "userID": user_config["user_id"],
                    "opponentUserID": "",
                    "gameStatus": "Live",
                    "lastUpdate": int(datetime.now().timestamp()),
                    "message": "",
                    "userProjectedScore": 0.0,
                    "opponentProjectedScore": 0.0
                }

            # find matchup for this roster
            user_matchup = None
            for m in matchups:
                if m.get("roster_id") == user_roster.get("roster_id"):
                    user_matchup = m
                    break

            if not user_matchup:
                # Get league name and user info even for fallback
                fallback_league_name = league_info.get("name", "Fantasy Football")
                user_lookup = {user.get("user_id"): user for user in league_users}
                user_info = user_lookup.get(user_config["user_id"], {})
                fallback_user_name = (user_info.get("metadata", {}).get("team_name") or
                                    user_info.get("display_name") or
                                    user_info.get("username") or
                                    f"Team {user_roster.get('roster_id', 'Unknown')}")
                return {
                    "totalPoints": 0.0,
                    "activePlayersCount": len(user_roster.get("starters", [])),
                    "teamName": fallback_user_name,
                    "opponentPoints": 0.0,
                    "opponentTeamName": "Opponent",
                    "leagueName": fallback_league_name,
                    "userID": user_config["user_id"],
                    "opponentUserID": "",
                    "gameStatus": "Live",
                    "lastUpdate": int(datetime.now().timestamp()),
                    "message": "",
                    "userProjectedScore": 0.0,
                    "opponentProjectedScore": 0.0
                }

            opponent_points = 0.0
            opponent_name = "Opponent"
            opponent_user_id = ""

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

            # Create lookup dict for user info from league users (much more efficient!)
            user_lookup = {user.get("user_id"): user for user in league_users}

            # Get user info from league users
            user_info = user_lookup.get(user_config["user_id"], {})

            # Get opponent info from league users
            if opponent_roster:
                opponent_owner_id = opponent_roster.get("owner_id")
                if opponent_owner_id:
                    opponent_user_id = opponent_owner_id
                    opponent_info = user_lookup.get(opponent_owner_id, {})
                    # Use team_name from metadata if available, otherwise display_name
                    opponent_name = (opponent_info.get("metadata", {}).get("team_name") or
                                   opponent_info.get("display_name") or
                                   opponent_info.get("username", opponent_name))

            total_points = user_matchup.get("points", 0.0)
            # Use team_name from metadata if available, otherwise display_name
            user_name = (user_info.get("metadata", {}).get("team_name") or
                        user_info.get("display_name") or
                        user_info.get("username") or
                        f"Team {user_roster.get('roster_id', 'Unknown')}")

            # Get actual league name
            league_name = league_info.get("name", "Fantasy Football")

            # Get projected scores for user and opponent
            user_projected_score = 0.0
            opponent_projected_score = 0.0

            # Get user projected score from optimized manager
            try:
                _, user_projected_score = optimized_player_manager.get_user_totals(user_config.get("device_id", ""))
            except Exception as e:
                logger.error(f"Error getting user projected score: {e}")

            # Get opponent projected score if we have opponent roster
            if opponent_roster and opponent_user_id:
                try:
                    # Find opponent's device_id from user_configs
                    opponent_device_id = None
                    for device_id, config in app_state.user_configs.items():
                        if config.get("user_id") == opponent_user_id:
                            opponent_device_id = device_id
                            break

                    if opponent_device_id:
                        _, opponent_projected_score = optimized_player_manager.get_user_totals(opponent_device_id)
                    else:
                        logger.info(f"No device found for opponent {opponent_user_id}")
                except Exception as e:
                    logger.error(f"Error getting opponent projected score: {e}")

            activity_data = {
                "totalPoints": total_points,
                "activePlayersCount": len(user_roster.get("starters", [])),
                "teamName": user_name,
                "opponentPoints": opponent_points,
                "opponentTeamName": opponent_name,
                "leagueName": league_name,
                "userID": user_config["user_id"],
                "opponentUserID": opponent_user_id,
                "gameStatus": "Live",
                "lastUpdate": int(datetime.now().timestamp()),
                "message": "",
                "userProjectedScore": user_projected_score,
                "opponentProjectedScore": opponent_projected_score
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
                "userID": "",
                "opponentUserID": "",
                "gameStatus": "Live",
                "lastUpdate": int(datetime.now().timestamp()),
                "message": "",
                "userProjectedScore": 0.0,
                "opponentProjectedScore": 0.0
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
                    "userID": "",
                    "opponentUserID": "",
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
# Combined player and team score updater (runs on apns_loop)
# -----------------------
async def update_all_live_activities():
    """Combined function that updates both player stats and team scores for all live activities"""
    logger.info(f"Running combined player and team score update for {len(app_state.active_live_activities)} active activities")

    # First update all player stats using the optimized manager
    await optimized_player_manager.update_all_player_stats()

    # Then update team scores (this is the old check_and_update_live_activities logic)
    await check_and_update_live_activities()

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
                "user_id": activity_data.get("userID", ""),
                "opponent_user_id": activity_data.get("opponentUserID", "")
            }

            last_data = app_state.last_scores.get(device_id, {})
            has_changed = (
                last_data.get("total_points") != current_data["total_points"] or
                last_data.get("opponent_points") != current_data["opponent_points"] or
                last_data.get("user_id") != current_data["user_id"] or
                last_data.get("opponent_user_id") != current_data["opponent_user_id"]
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
        user_id = data.get("user_id")
        league_id = data.get("league_id")
        push_token = data["push_token"]
        device_id = data["device_id"]

        # Only validate user exists if user_id is provided
        if user_id:
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

@app.route("/league/<league_id>/avatars", methods=["GET"])
def get_league_avatars(league_id):
    """
    Get avatar URLs for all users in a league
    Returns: {"avatars": {"user_id": "avatar_url", ...}}
    """
    try:
        # Check cache first (30 minute cache)
        cached_avatars = app_state.league_avatar_cache.get(league_id)

        if cached_avatars:
            cache_time, avatars = cached_avatars
            # Cache for 30 minutes
            if time.time() - cache_time < 30 * 60:
                logger.debug(f"Returning cached avatars for league {league_id}")
                return jsonify({"avatars": avatars})

        # Get league users from cache (shares cache with comprehensive activity data)
        users = get_cached_league_users(league_id)
        avatars = {}

        for user in users:
            user_id = user.get("user_id")
            if not user_id:
                continue

            avatar_url = None

            # Priority 1: Check metadata.avatar (full URL)
            metadata = user.get("metadata", {})
            if metadata and "avatar" in metadata:
                avatar_url = metadata["avatar"]
                logger.debug(f"Using metadata avatar for user {user_id}: {avatar_url}")

            # Priority 2: Use top-level avatar (needs thumb URL construction)
            elif "avatar" in user and user["avatar"]:
                avatar_hash = user["avatar"]
                avatar_url = f"https://sleepercdn.com/avatars/{avatar_hash}"
                logger.debug(f"Using top-level avatar for user {user_id}: {avatar_url}")

            if avatar_url:
                avatars[user_id] = avatar_url
            else:
                logger.debug(f"No avatar found for user {user_id}")

        # Cache the result
        app_state.league_avatar_cache[league_id] = (time.time(), avatars)

        logger.info(f"Found avatars for {len(avatars)} users in league {league_id}")
        return jsonify({"avatars": avatars})
    except Exception as e:
        logger.exception(f"Failed to get avatars for league {league_id}")
        return jsonify({"error": str(e)}), 400



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
            submit_to_apns_loop(live_activity_manager.send_live_activity_start(push_to_start_token, user_config, "Game starting soon"))
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

@app.route("/live-activity/heartbeat/<device_id>", methods=["POST"])
def live_activity_heartbeat(device_id):
    """Called when app is opened - verify live activity state synchronization"""
    try:
        data = request.get_json() or {}
        ios_has_active_activity = data.get("has_active_activity", False)

        backend_has_active = device_id in app_state.active_live_activities

        logger.info(f"Heartbeat from {device_id}: iOS active={ios_has_active_activity}, Backend active={backend_has_active}")

        # Case 1: iOS has activity but backend doesn't - register with backend
        if ios_has_active_activity and not backend_has_active:
            logger.info(f"iOS reports active activity but backend doesn't have it - registering for {device_id}")
            if device_id in app_state.user_configs:
                user_config = app_state.user_configs[device_id]
                app_state.active_live_activities[device_id] = {
                    "user_config": user_config,
                    "started_at": datetime.now(),
                    "last_update": datetime.now()
                }
                return jsonify({
                    "status": "registered",
                    "message": "Backend now tracking iOS activity"
                })
            else:
                return jsonify({"error": "Device not configured"}), 400

        # Case 2: Backend has activity but iOS doesn't - clean up backend
        elif not ios_has_active_activity and backend_has_active:
            logger.info(f"Backend thinks activity is active but iOS doesn't - cleaning up for {device_id}")
            stop_live_activity_by_id(device_id)
            return jsonify({
                "status": "cleaned",
                "message": "Backend cleaned up - no activity on iOS"
            })

        # Case 3: States already match
        else:
            status_msg = "active" if ios_has_active_activity else "inactive"
            return jsonify({
                "status": "synced",
                "message": f"States match - both {status_msg}"
            })

    except Exception as e:
        logger.exception(f"Error in live_activity_heartbeat for {device_id}: {e}")
        return jsonify({"error": "Heartbeat failed", "details": str(e)}), 500


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

    # Schedule the combined live activity update job
    def schedule_combined_update():
        try:
            submit_to_apns_loop(update_all_live_activities())
        except Exception:
            logger.exception("Failed to run scheduled update_all_live_activities")

    # Use APScheduler to call our combined update function every LIVE_ACTIVITY_UPDATE_INTERVAL
    scheduler.add_job(func=schedule_combined_update, trigger="interval", seconds=LIVE_ACTIVITY_UPDATE_INTERVAL, id="live_activity_updates", next_run_time=datetime.now())

    # Schedule daily NFL games fetch at NFL_GAMES_REFRESH_HOUR AM
    scheduler.add_job(func=update_nfl_games, trigger="cron", hour=NFL_GAMES_REFRESH_HOUR, minute=0, id="daily_games_fetch")

    # Schedule daily NFL players fetch at NFL_PLAYERS_REFRESH_HOUR AM
    scheduler.add_job(func=update_nfl_players, trigger="cron", hour=NFL_PLAYERS_REFRESH_HOUR, minute=NFL_PLAYERS_REFRESH_MINUTE, id="daily_players_fetch")

    # Schedule game start checker every GAME_START_CHECK_INTERVAL
    scheduler.add_job(func=check_and_start_live_activities, trigger="interval", seconds=GAME_START_CHECK_INTERVAL, id="game_start_checker")

    # Schedule TTL cleanup for dismissed live activities every 30 minutes
    scheduler.add_job(func=cleanup_expired_live_activities, trigger="interval", minutes=30, id="ttl_cleanup")

    # Load players data on startup (from file if exists, otherwise fetch from API)
    load_players_on_startup()

    # Fetch games immediately on startup
    update_nfl_games()

    # Check for live games on startup and start ending scheduler if needed
    check_live_games_on_startup()

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

    # Check if we have fresh cached data
    cache_age_seconds = 0
    if optimized_player_manager.last_fetch_time:
        cache_age_seconds = (datetime.now() - optimized_player_manager.last_fetch_time).total_seconds()

    # If cache is empty or old (>PLAYER_CACHE_MAX_AGE seconds), fetch fresh data
    if not optimized_player_manager.player_stats_cache or cache_age_seconds > PLAYER_CACHE_MAX_AGE:
        try:
            logger.info(f"Cache empty or stale ({cache_age_seconds}s old), fetching fresh data for {device_id}")
            # Trigger immediate cache update
            submit_to_apns_loop(optimized_player_manager.update_all_player_stats())
            # Small delay to allow cache population
            import time
            time.sleep(1)
        except Exception as e:
            logger.error(f"Failed to update cache on-demand: {e}")

    # Get data from optimized manager (will use cache if available)
    try:
        current_pts_ppr, current_projections = optimized_player_manager.get_user_totals(device_id)
    except Exception as e:
        logger.error(f"Error getting user totals from optimized manager: {e}")
        # Fallback to app_state values
        current_pts_ppr = app_state.user_previous_pts_ppr.get(device_id, 0.0)
        current_projections = app_state.last_projection_totals.get(device_id, 0.0)

    starter_ids = app_state.user_starter_player_ids.get(device_id, [])
    if not starter_ids:
        starter_ids = get_user_starter_player_ids(device_id)

    return jsonify({
        "device_id": device_id,
        "starter_player_ids": starter_ids,
        "current_pts_ppr": current_pts_ppr,
        "current_projections": current_projections,
        "total_starters": len(starter_ids),
        "cache_age_seconds": cache_age_seconds,
        "data_source": "optimized_cache" if optimized_player_manager.player_stats_cache else "fallback"
    })

@app.route("/player-scores", methods=["GET"])
def get_all_player_scores():
    """Get player scoring data for all devices"""
    # Check cache freshness
    cache_age_seconds = 0
    if optimized_player_manager.last_fetch_time:
        cache_age_seconds = (datetime.now() - optimized_player_manager.last_fetch_time).total_seconds()

    # Trigger cache update if needed
    if not optimized_player_manager.player_stats_cache or cache_age_seconds > PLAYER_CACHE_MAX_AGE:
        try:
            logger.info(f"Cache empty or stale ({cache_age_seconds}s old), fetching fresh data for all devices")
            submit_to_apns_loop(optimized_player_manager.update_all_player_stats())
            import time
            time.sleep(1)
        except Exception as e:
            logger.error(f"Failed to update cache on-demand: {e}")

    scores_data = []
    for device_id in app_state.user_configs.keys():
        # Try to get from optimized manager first
        try:
            current_pts_ppr, current_projections = optimized_player_manager.get_user_totals(device_id)
            data_source = "optimized_cache"
        except Exception as e:
            logger.error(f"Error getting user totals for {device_id}: {e}")
            # Fallback to app_state
            current_pts_ppr = app_state.user_previous_pts_ppr.get(device_id, 0.0)
            current_projections = app_state.last_projection_totals.get(device_id, 0.0)
            data_source = "fallback"

        starter_ids = app_state.user_starter_player_ids.get(device_id, [])
        if not starter_ids:
            starter_ids = get_user_starter_player_ids(device_id)

        scores_data.append({
            "device_id": device_id,
            "starter_player_ids": starter_ids,
            "current_pts_ppr": current_pts_ppr,
            "current_projections": current_projections,
            "total_starters": len(starter_ids),
            "has_live_activity": device_id in app_state.active_live_activities,
            "data_source": data_source
        })

    return jsonify({
        "player_scores": scores_data,
        "total_devices": len(scores_data),
        "cache_age_seconds": cache_age_seconds,
        "cache_populated": bool(optimized_player_manager.player_stats_cache)
    })

@app.route("/player-scores/refresh/<device_id>", methods=["POST"])
def refresh_player_scores(device_id):
    """Manually refresh player scores for a specific device"""
    if device_id not in app_state.user_configs:
        return jsonify({"error": "Device not found"}), 404

    try:
        # Submit the update task to the APNS loop using optimized manager
        submit_to_apns_loop(optimized_player_manager.update_single_live_activity_from_cache(device_id))
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
        # Submit the update task to the APNS loop using optimized manager
        submit_to_apns_loop(optimized_player_manager.update_all_player_stats())
        return jsonify({
            "status": "success",
            "message": "Optimized player scores refresh initiated for all active live activities"
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