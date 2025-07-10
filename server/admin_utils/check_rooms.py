#!/usr/bin/env python3

import redis
import json
from collections import defaultdict
import sys
import os
import logging
from pathlib import Path

# Add the server directory to the Python path so we can import from app
server_dir = Path(__file__).parent.parent
sys.path.append(str(server_dir))

from app.logger import setup_logging
from app.config import settings

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

def check_rooms():
    """Check all rooms in the database and analyze their data."""
    try:
        # Connect to Redis
        redis_client = redis.Redis.from_url(settings.REDIS_URL)

        # Get all room keys
        room_keys = redis_client.keys('room:*')
        # Filter out room:*:players keys which store the player sets
        room_keys = [k for k in room_keys if b':players' not in k]

        if not room_keys:
            logger.info("No rooms found in the database.")
            return

        # Store image URLs and their corresponding rooms
        image_urls = defaultdict(list)
        rooms_by_id = {}

        print("\n=== Room Data ===\n")

        for key in room_keys:
            room_data = redis_client.get(key)
            if room_data:
                room = json.loads(room_data)
                room_id = room['id']
                rooms_by_id[room_id] = room

                # Get players in this room
                players_key = f"room:{room_id}:players"
                players = redis_client.smembers(players_key)
                players = [p.decode('utf-8') for p in players]

                image_url = room.get('image_url', 'No image')
                image_urls[image_url].append(room_id)

                print(f"Room: {room_id}")
                print(f"Title: {room.get('title', 'No title')}")
                print(f"Description: {room.get('description', 'No description')[:100]}...")
                print(f"Connections: {room.get('connections', {})}")
                print(f"Players: {players}")
                print(f"Image URL: {image_url}")
                print("-" * 80)

        # Check for rooms with missing connections
        print("\n=== Room Connection Analysis ===\n")
        for room_id, room in rooms_by_id.items():
            connections = room.get('connections', {})
            for direction, connected_room_id in connections.items():
                if connected_room_id not in rooms_by_id:
                    print(f"Warning: Room {room_id} has connection to non-existent room {connected_room_id} in direction {direction}")
                else:
                    # Check if the connection is bidirectional
                    connected_room = rooms_by_id[connected_room_id]
                    connected_room_connections = connected_room.get('connections', {})
                    opposite_directions = {
                        'north': 'south',
                        'south': 'north',
                        'east': 'west',
                        'west': 'east',
                        'up': 'down',
                        'down': 'up'
                    }
                    if direction in opposite_directions:
                        opposite = opposite_directions[direction]
                        if connected_room_connections.get(opposite) != room_id:
                            print(f"Warning: One-way connection detected from {room_id} to {connected_room_id}")
                            print(f"  {room_id} --{direction}--> {connected_room_id}")
                            print(f"  But reverse connection {opposite} is missing or incorrect")

        print("\n=== Duplicate Image URLs ===\n")
        for url, rooms in image_urls.items():
            if len(rooms) > 1:
                print(f"\nImage URL: {url}")
                print(f"Used in rooms: {', '.join(rooms)}")

    except redis.RedisError as e:
        logger.error(f"Redis error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    check_rooms()