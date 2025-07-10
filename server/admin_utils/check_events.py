#!/usr/bin/env python3

import redis
import json
import sys
import os
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from typing import Dict, List, Any

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

def analyze_events():
    """Analyze game events, quests, and player interactions."""
    try:
        # Connect to Redis
        redis_client = redis.Redis.from_url(settings.REDIS_URL)

        print("\n=== Quest Analysis ===\n")

        # Analyze player quest progress
        player_keys = [key.decode('utf-8') for key in redis_client.keys('player:*')]
        quest_stats = defaultdict(lambda: {'total': 0, 'completed': 0, 'in_progress': 0})
        active_quests = defaultdict(list)

        for key in player_keys:
            player_data = redis_client.get(key)
            if player_data:
                try:
                    player = json.loads(player_data)
                    quest_progress = player.get('quest_progress', {})

                    for quest_id, progress in quest_progress.items():
                        quest_stats[quest_id]['total'] += 1
                        if progress.get('completed', False):
                            quest_stats[quest_id]['completed'] += 1
                        else:
                            quest_stats[quest_id]['in_progress'] += 1
                            active_quests[quest_id].append({
                                'player': player['name'],
                                'progress': progress
                            })
                except json.JSONDecodeError:
                    logger.warning(f"Could not decode player data for key: {key}")
                    continue

        if quest_stats:
            print("Quest Statistics:")
            for quest_id, stats in quest_stats.items():
                print(f"\nQuest ID: {quest_id}")
                print(f"  - Total Players: {stats['total']}")
                print(f"  - Completed: {stats['completed']}")
                print(f"  - In Progress: {stats['in_progress']}")

                if stats['in_progress'] > 0:
                    print("\n  Active Players:")
                    for quest_info in active_quests[quest_id]:
                        progress_str = json.dumps(quest_info['progress'], indent=2)
                        print(f"    - {quest_info['player']}:")
                        print(f"      {progress_str}")
        else:
            print("No active quests found.")

        print("\n=== Recent Events Analysis ===\n")

        # Analyze recent game events
        now = datetime.utcnow()
        event_windows = {
            'last_hour': timedelta(hours=1),
            'last_day': timedelta(days=1),
            'last_week': timedelta(weeks=1)
        }

        event_stats = {
            window: defaultdict(int) for window in event_windows.keys()
        }

        # Get all player actions and events
        for key in player_keys:
            player_data = redis_client.get(key)
            if player_data:
                try:
                    player = json.loads(player_data)

                    # Analyze player actions
                    if 'last_action' in player:
                        action_time = parse_timestamp(player['last_action'])
                        if action_time:
                            action_text = player.get('last_action_text', '').lower()

                            for window, delta in event_windows.items():
                                if now - action_time <= delta:
                                    if 'move' in action_text:
                                        event_stats[window]['movement'] += 1
                                    elif 'talk' in action_text or 'say' in action_text:
                                        event_stats[window]['conversation'] += 1
                                    elif 'take' in action_text or 'drop' in action_text:
                                        event_stats[window]['inventory'] += 1
                                    else:
                                        event_stats[window]['other'] += 1
                except json.JSONDecodeError:
                    logger.warning(f"Could not decode player data for key: {key}")
                    continue
                except Exception as e:
                    logger.warning(f"Error processing player {key}: {str(e)}")
                    continue

        print("Event Statistics by Time Window:")
        for window, stats in event_stats.items():
            total = sum(stats.values())
            if total > 0:
                print(f"\n{window.replace('_', ' ').title()}:")
                for event_type, count in stats.items():
                    percentage = (count / total * 100)
                    print(f"  - {event_type.title()}: {count} ({percentage:.1f}%)")
            else:
                print(f"\n{window.replace('_', ' ').title()}: No events")

        print("\n=== Player Interaction Hotspots ===\n")

        # Analyze room interaction frequency
        room_interactions = defaultdict(int)
        room_players = defaultdict(set)

        for key in player_keys:
            player_data = redis_client.get(key)
            if player_data:
                try:
                    player = json.loads(player_data)
                    current_room = player.get('current_room')
                    if current_room:
                        room_players[current_room].add(player['name'])
                        if 'last_action' in player:
                            room_interactions[current_room] += 1
                except json.JSONDecodeError:
                    continue

        if room_interactions:
            print("Most Active Rooms:")
            sorted_rooms = sorted(room_interactions.items(), key=lambda x: x[1], reverse=True)
            for room_id, interactions in sorted_rooms[:5]:  # Top 5 rooms
                room_data = redis_client.get(f'room:{room_id}')
                room_title = "Unknown Room"
                if room_data:
                    try:
                        room = json.loads(room_data)
                        room_title = room.get('title', 'Unknown Room')
                    except json.JSONDecodeError:
                        pass

                print(f"\nRoom: {room_title} (ID: {room_id})")
                print(f"  - Total Interactions: {interactions}")
                print(f"  - Current Players: {len(room_players[room_id])}")
                if room_players[room_id]:
                    print(f"  - Players: {', '.join(room_players[room_id])}")
        else:
            print("No room interactions found.")

    except redis.RedisError as e:
        logger.error(f"Redis error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)

if __name__ == "__main__":
    analyze_events()