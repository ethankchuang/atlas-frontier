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
        room_keys = [k for k in room_keys if b':players' not in k and b':generation' not in k and b':generation_lock' not in k]

        if not room_keys:
            logger.info("No rooms found in the database.")
            return

        # Store image URLs and their corresponding rooms
        image_urls = defaultdict(list)
        biome_distribution = defaultdict(list)
        rooms_by_id = {}

        print("\n=== Room Data ===\n")

        for key in room_keys:
            try:
                room_data = redis_client.get(key)
                if not room_data:
                    logger.warning("Empty data for key: {}".format(key))
                    continue
                
                # Decode bytes to string if necessary
                if isinstance(room_data, bytes):
                    room_data = room_data.decode('utf-8')
                
                # Skip empty strings
                if not room_data.strip():
                    logger.warning("Empty string data for key: {}".format(key))
                    continue
                
                # Parse JSON with error handling
                try:
                    room = json.loads(room_data)
                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON for key {}: {}".format(key, str(e)))
                    logger.error("Raw data: {}...".format(room_data[:200]))
                    continue
                
                # Validate room data structure
                if not isinstance(room, dict):
                    logger.warning("Room data is not a dictionary for key: {}".format(key))
                    continue
                
                room_id = room.get('id')
                if not room_id:
                    logger.warning("Room missing ID for key: {}".format(key))
                    continue
                
                rooms_by_id[room_id] = room

                # Get players in this room
                players_key = "room:{}:players".format(room_id)
                players = redis_client.smembers(players_key)
                players = [p.decode('utf-8') if isinstance(p, bytes) else p for p in players]

                image_url = room.get('image_url', 'No image')
                image_urls[image_url].append(room_id)
                
                # Track biome distribution
                biome = room.get('biome', 'No biome')
                biome_distribution[biome].append(room_id)

                print("Room: {}".format(room_id))
                print("Title: {}".format(room.get('title', 'No title')))
                description = room.get('description', 'No description')
                if len(description) > 100:
                    description = description[:100] + "..."
                print("Description: {}".format(description))
                print("Biome: {}".format(room.get('biome', 'No biome')))
                print("Connections: {}".format(room.get('connections', {})))
                print("Players: {}".format(players))
                print("Image URL: {}".format(image_url))
                print("Coordinates: ({}, {})".format(room.get('x', 'N/A'), room.get('y', 'N/A')))
                print("Visited: {}".format(room.get('visited', 'N/A')))
                print("-" * 80)
                
            except Exception as e:
                logger.error("Error processing room key {}: {}".format(key, str(e)))
                continue

        if not rooms_by_id:
            logger.warning("No valid rooms found after processing")
            return

        # Check for rooms with missing connections
        print("\n=== Room Connection Analysis ===\n")
        for room_id, room in rooms_by_id.items():
            connections = room.get('connections', {})
            for direction, connected_room_id in connections.items():
                if connected_room_id not in rooms_by_id:
                    print("Warning: Room {} has connection to non-existent room {} in direction {}".format(
                        room_id, connected_room_id, direction))
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
                            print("Warning: One-way connection detected from {} to {}".format(room_id, connected_room_id))
                            print("  {} --{}--> {}".format(room_id, direction, connected_room_id))
                            print("  But reverse connection {} is missing or incorrect".format(opposite))

        print("\n=== Biome Distribution ===\n")
        # Handle None values in biome sorting
        sorted_biomes = sorted(biome_distribution.items(), key=lambda x: (x[0] is None, x[0]))
        for biome, rooms in sorted_biomes:
            print("Biome: {} ({} rooms)".format(biome, len(rooms)))
            room_coords = []
            for room_id in rooms:
                room = rooms_by_id.get(room_id, {})
                x, y = room.get('x', '?'), room.get('y', '?')
                room_coords.append("{}({},{})".format(room_id, x, y))
            print("  Rooms: {}".format(', '.join(room_coords[:10])))  # Show up to 10 rooms
            if len(room_coords) > 10:
                print("  ... and {} more".format(len(room_coords) - 10))
            print()

        print("\n=== Duplicate Image URLs ===\n")
        for url, rooms in image_urls.items():
            if len(rooms) > 1:
                print("\nImage URL: {}".format(url))
                print("Used in rooms: {}".format(', '.join(rooms)))

        # Check coordinate consistency
        print("\n=== Coordinate Analysis ===\n")
        coordinates_map = {}
        for room_id, room in rooms_by_id.items():
            x, y = room.get('x'), room.get('y')
            if x is not None and y is not None:
                coord_key = (x, y)
                if coord_key in coordinates_map:
                    print("Warning: Duplicate coordinates ({}, {}) for rooms: {} and {}".format(
                        x, y, coordinates_map[coord_key], room_id))
                else:
                    coordinates_map[coord_key] = room_id

        print("\nTotal rooms processed: {}".format(len(rooms_by_id)))
        print("Unique coordinates: {}".format(len(coordinates_map)))

    except redis.RedisError as e:
        logger.error("Redis error: {}".format(str(e)))
    except Exception as e:
        logger.error("Unexpected error: {}".format(str(e)))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_rooms() 