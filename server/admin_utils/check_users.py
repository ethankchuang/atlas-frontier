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

def get_item_details(redis_client, item_id: str) -> Dict:
    """Get detailed information about an item."""
    try:
        item_data = redis_client.get(f'item:{item_id}')
        if item_data:
            return json.loads(item_data)
        return None
    except Exception as e:
        logger.debug(f"Error getting item {item_id}: {str(e)}")
        return None

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
                    
                    # Display detailed inventory information
                    inventory = player.get('inventory', [])
                    if inventory:
                        print("  Inventory Details:")
                        for i, item_id in enumerate(inventory, 1):
                            item_details = get_item_details(redis_client, item_id)
                            if item_details:
                                rarity_stars = "★" * item_details.get('rarity', 1)
                                print(f"    {i}. {item_details['name']} (Rarity: {rarity_stars})")
                                print(f"       Effects: {item_details.get('special_effects', 'None')}")
                            else:
                                print(f"    {i}. {item_id} (Item data not found)")
                    else:
                        print("  Inventory: Empty")
                    
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

        print("\n=== Item Statistics ===\n")

        # Calculate item statistics
        total_items = 0
        rarity_counts = {1: 0, 2: 0, 3: 0, 4: 0}
        all_items = []

        for player in all_players:
            inventory = player.get('inventory', [])
            total_items += len(inventory)
            
            for item_id in inventory:
                item_details = get_item_details(redis_client, item_id)
                if item_details:
                    rarity = item_details.get('rarity', 1)
                    rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
                    all_items.append(item_details)

        print(f"Total Items in Game: {total_items}")
        print(f"Items by Rarity:")
        for rarity in range(1, 5):
            stars = "★" * rarity
            count = rarity_counts.get(rarity, 0)
            print(f"  Rarity {rarity} ({stars}): {count} items")
        
        if all_items:
            print(f"\nSample Items:")
            for i, item in enumerate(all_items[:5], 1):  # Show first 5 items
                rarity_stars = "★" * item.get('rarity', 1)
                print(f"  {i}. {item['name']} (Rarity: {rarity_stars})")
                print(f"     Effects: {item.get('special_effects', 'None')}")

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