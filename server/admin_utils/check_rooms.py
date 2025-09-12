#!/usr/bin/env python3

import redis
import json
from collections import defaultdict
import sys
import os
import logging
import asyncio

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Redis connection URL - adjust if needed
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

def check_rooms():
    """Check all rooms in the database and analyze their data."""
    try:
        # Connect to Redis
        redis_client = redis.Redis.from_url(REDIS_URL)

        # Get all room keys
        room_keys = redis_client.keys('room:*')
        # Filter out room:*:players keys which store the player sets
        room_keys = [k for k in room_keys if b':players' not in k and b':generation' not in k and b':generation_lock' not in k]

        if not room_keys:
            logger.info("No rooms found in Redis. Falling back to app database (HybridDatabase/Supabase)...")
            return asyncio.run(check_rooms_hybrid())

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

                # Get monsters in this room with full data
                monsters = []
                monster_ids = room.get('monsters', [])
                for monster_id in monster_ids:
                    try:
                        monster_key = "monster:{}".format(monster_id)
                        monster_data = redis_client.get(monster_key)
                        if monster_data:
                            if isinstance(monster_data, bytes):
                                monster_data = monster_data.decode('utf-8')
                            monster = json.loads(monster_data)
                            monsters.append(monster)
                    except Exception as e:
                        logger.error("Error loading monster {}: {}".format(monster_id, str(e)))
                        monsters.append({"id": monster_id, "error": "Failed to load"})

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
                
                # Show territorial blocking if persisted in room properties
                props = room.get('properties', {}) or {}
                terr_blocks = props.get('territorial_blocks') or {}
                if terr_blocks:
                    print("Territorial Blocks:")
                    for m_id, dir_blocked in terr_blocks.items():
                        print("  - Monster {} blocks {}".format(m_id, dir_blocked))

                # Display monster information
                if monsters:
                    print("Monsters ({} total):".format(len(monsters)))
                    for monster in monsters:
                        if "error" in monster:
                            print("  - {} (ERROR: {})".format(monster.get('id', 'Unknown'), monster['error']))
                        else:
                            print("  - {} (ID: {})".format(monster.get('name', 'Unnamed Monster'), monster.get('id', 'No ID')))
                            print("    Aggressiveness: {} | Intelligence: {} | Size: {}".format(
                                monster.get('aggressiveness', 'Unknown'),
                                monster.get('intelligence', 'Unknown'),
                                monster.get('size', 'Unknown')
                            ))
                            print("    Health: {} | Alive: {}".format(
                                monster.get('health', 'Unknown'),
                                monster.get('is_alive', 'Unknown')
                            ))
                            if monster.get('description'):
                                desc = monster['description']
                                if len(desc) > 80:
                                    desc = desc[:80] + "..."
                                print("    Description: {}".format(desc))
                            if monster.get('special_effects'):
                                effects = monster['special_effects']
                                if len(effects) > 60:
                                    effects = effects[:60] + "..."
                                print("    Special Effects: {}".format(effects))
                            
                            # If territorial, show persisted blocking direction if available
                            if monster.get('aggressiveness') == 'territorial':
                                blocked = terr_blocks.get(monster.get('id')) if isinstance(terr_blocks, dict) else None
                                if blocked:
                                    print("    🛡️ TERRITORIAL: Blocking {} exit".format(blocked))
                                else:
                                    print("    🛡️ TERRITORIAL: Not currently blocking (no persisted info)")
                else:
                    print("Monsters: None")
                
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

        # Monster statistics
        print("\n=== Monster Statistics ===\n")
        total_monsters = 0
        aggressiveness_stats = defaultdict(int)
        intelligence_stats = defaultdict(int)
        size_stats = defaultdict(int)
        alive_monsters = 0
        dead_monsters = 0
        rooms_with_monsters = 0
        
        for room_id, room in rooms_by_id.items():
            monster_ids = room.get('monsters', [])
            if monster_ids:
                rooms_with_monsters += 1
                
            for monster_id in monster_ids:
                try:
                    monster_key = "monster:{}".format(monster_id)
                    monster_data = redis_client.get(monster_key)
                    if monster_data:
                        if isinstance(monster_data, bytes):
                            monster_data = monster_data.decode('utf-8')
                        monster = json.loads(monster_data)
                        
                        total_monsters += 1
                        aggressiveness_stats[monster.get('aggressiveness', 'Unknown')] += 1
                        intelligence_stats[monster.get('intelligence', 'Unknown')] += 1
                        size_stats[monster.get('size', 'Unknown')] += 1
                        
                        if monster.get('is_alive', True):
                            alive_monsters += 1
                        else:
                            dead_monsters += 1
                except Exception as e:
                    logger.error("Error processing monster {} for stats: {}".format(monster_id, str(e)))
        
        print("Total monsters: {}".format(total_monsters))
        print("Alive: {} | Dead: {}".format(alive_monsters, dead_monsters))
        rooms_percentage = (float(rooms_with_monsters) / len(rooms_by_id) * 100) if rooms_by_id else 0
        print("Rooms with monsters: {} / {} ({:.1f}%)".format(
            rooms_with_monsters, len(rooms_by_id), rooms_percentage
        ))
        
        print("\nAggressiveness Distribution:")
        for aggressiveness, count in sorted(aggressiveness_stats.items()):
            percentage = (float(count) / total_monsters * 100) if total_monsters > 0 else 0
            print("  {}: {} ({:.1f}%)".format(aggressiveness, count, percentage))
        
        print("\nIntelligence Distribution:")
        for intelligence, count in sorted(intelligence_stats.items()):
            percentage = (float(count) / total_monsters * 100) if total_monsters > 0 else 0
            print("  {}: {} ({:.1f}%)".format(intelligence, count, percentage))
        
        print("\nSize Distribution:")
        for size, count in sorted(size_stats.items()):
            percentage = (float(count) / total_monsters * 100) if total_monsters > 0 else 0
            print("  {}: {} ({:.1f}%)".format(size, count, percentage))

        print("\nTotal rooms processed: {}".format(len(rooms_by_id)))
        print("Unique coordinates: {}".format(len(coordinates_map)))

    except redis.RedisError as e:
        logger.error("Redis error: {}".format(str(e)))
    except Exception as e:
        logger.error("Unexpected error: {}".format(str(e)))
        import traceback
        traceback.print_exc()

# HybridDatabase fallback (Supabase)
async def check_rooms_hybrid():
    try:
        # Ensure app path is importable
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from app.hybrid_database import HybridDatabase as Database

        db = Database()

        # Use discovered coordinates to enumerate rooms
        discovered = await db.get_discovered_coordinates()
        if not discovered:
            print("No discovered coordinates found in app database.")
            return

        rooms_by_id = {}
        image_urls = defaultdict(list)
        biome_distribution = defaultdict(list)

        print("\n=== Room Data (HybridDatabase) ===\n")

        # discovered is a dict like {"x,y": room_id}
        for coord_key, room_id in discovered.items():
            try:
                room_data = await db.get_room(room_id)
                if not room_data:
                    continue
                room = room_data
                rooms_by_id[room_id] = room

                # Players via Redis set (HybridDatabase proxies to Redis)
                players = await db.get_room_players(room_id)

                # Monsters via app DB (HybridDatabase proxies to Supabase)
                monsters = []
                for monster_id in room.get('monsters', []) or []:
                    try:
                        m = await db.get_monster(monster_id)
                        if m:
                            monsters.append(m)
                    except Exception:
                        monsters.append({"id": monster_id, "error": "Failed to load"})

                image_url = room.get('image_url', 'No image')
                image_urls[image_url].append(room_id)
                biome = room.get('biome', 'No biome')
                biome_distribution[biome].append(room_id)

                print("Room: {}".format(room_id))
                print("Title: {}".format(room.get('title', 'No title')))
                description = room.get('description', 'No description')
                if len(description) > 100:
                    description = description[:100] + "..."
                print("Description: {}".format(description))
                print("Biome: {}".format(biome))
                print("Connections: {}".format(room.get('connections', {})))
                print("Players: {}".format(players))

                # Display monster information
                if monsters:
                    print("Monsters ({} total):".format(len(monsters)))
                    for monster in monsters:
                        if "error" in monster:
                            print("  - {} (ERROR: {})".format(monster.get('id', 'Unknown'), monster['error']))
                        else:
                            print("  - {} (ID: {})".format(monster.get('name', 'Unnamed Monster'), monster.get('id', 'No ID')))
                else:
                    print("Monsters: None")

                print("Image URL: {}".format(image_url))
                print("Coordinates: ({}, {})".format(room.get('x', 'N/A'), room.get('y', 'N/A')))
                print("Visited: {}".format(room.get('visited', 'N/A')))
                print("-" * 80)
            except Exception as e:
                logger.error(f"Error processing room {room_id}: {str(e)}")
                continue

        print("\nTotal rooms processed: {}".format(len(rooms_by_id)))
    except Exception as e:
        logger.error(f"HybridDatabase fallback error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_rooms() 