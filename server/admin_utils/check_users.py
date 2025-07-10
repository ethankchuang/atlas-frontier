#!/usr/bin/env python3

import redis
import json
from collections import defaultdict
import sys
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List

# Add the server directory to the Python path so we can import from app
server_dir = Path(__file__).parent.parent
sys.path.append(str(server_dir))

from app.logger import setup_logging
from app.config import settings

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse a timestamp string to a timezone-aware datetime object."""
    if not timestamp_str:
        return None
    try:
        # First try to parse as is
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        # Convert to naive UTC
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception as e:
        logger.debug(f"Error parsing timestamp {timestamp_str}: {str(e)}")
        return None

def format_timestamp(timestamp_str: str) -> str:
    """Format a timestamp string to a readable format with time elapsed."""
    if not timestamp_str:
        return "Never"
    try:
        timestamp = parse_timestamp(timestamp_str)
        if not timestamp:
            return timestamp_str

        now = datetime.utcnow()
        elapsed = now - timestamp

        if elapsed.total_seconds() < 60:
            return f"{int(elapsed.total_seconds())} seconds ago"
        elif elapsed.total_seconds() < 3600:
            return f"{int(elapsed.total_seconds() / 60)} minutes ago"
        else:
            return f"{int(elapsed.total_seconds() / 3600)} hours ago"
    except Exception as e:
        logger.debug(f"Error formatting timestamp {timestamp_str}: {str(e)}")
        return timestamp_str

def check_users():
    """Check all users in the database and their current status."""
    try:
        # Connect to Redis
        redis_client = redis.Redis.from_url(settings.REDIS_URL)

        # Get all player keys
        player_keys = [key.decode('utf-8') for key in redis_client.keys('player:*')]
        if not player_keys:
            logger.info("No players found in the database.")
            return

        # Group players by room
        players_by_room: Dict[str, List[Dict]] = defaultdict(list)
        all_players = []

        print("\n=== Player Data ===\n")

        for key in player_keys:
            player_data = redis_client.get(key)
            if player_data:
                try:
                    player = json.loads(player_data)
                    all_players.append(player)

                    print(f"Player: {player['name']} (ID: {player['id']})")
                    print(f"Current Room: {player['current_room']}")
                    print(f"Last Action: {format_timestamp(player.get('last_action', ''))}")
                    print(f"Last Action Text: {player.get('last_action_text', 'None')}")
                    print(f"Inventory Items: {len(player.get('inventory', []))}")
                    print(f"Quest Progress: {len(player.get('quest_progress', {}))}")
                    print(f"Memory Log Entries: {len(player.get('memory_log', []))}")
                    print("-" * 80)

                    players_by_room[player['current_room']].append(player)
                except json.JSONDecodeError:
                    logger.warning(f"Could not decode player data for key: {key}")
                    continue

        print("\n=== Players by Room ===\n")

        # Get room data for better display
        for room_id, players in players_by_room.items():
            room_data = redis_client.get(f'room:{room_id}')
            room_title = "Unknown Room"
            if room_data:
                try:
                    room = json.loads(room_data)
                    room_title = room.get('title', 'Unknown Room')
                except json.JSONDecodeError:
                    pass

            print(f"\nRoom: {room_id} ({room_title})")
            print(f"Number of players: {len(players)}")
            for player in players:
                last_action = format_timestamp(player.get('last_action', ''))
                print(f"  - {player['name']} (Last action: {last_action})")

        print("\n=== Activity Summary ===\n")

        # Calculate activity statistics
        now = datetime.utcnow()
        active_last_hour = 0

        for player in all_players:
            if player.get('last_action'):
                action_time = parse_timestamp(player['last_action'])
                if action_time and (now - action_time).total_seconds() < 3600:
                    active_last_hour += 1

        print(f"Total Players: {len(all_players)}")
        print(f"Active in Last Hour: {active_last_hour}")
        print(f"Number of Occupied Rooms: {len(players_by_room)}")

    except redis.RedisError as e:
        logger.error(f"Redis error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)

if __name__ == "__main__":
    check_users()