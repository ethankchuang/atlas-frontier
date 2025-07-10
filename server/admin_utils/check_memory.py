#!/usr/bin/env python3

import redis
import json
import sys
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, List, Any
import chromadb
from chromadb.config import Settings

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

def analyze_memory():
    """Analyze the game's memory usage and AI interactions."""
    try:
        # Connect to Redis
        redis_client = redis.Redis.from_url(settings.REDIS_URL)

        # Connect to ChromaDB
        chroma_client = chromadb.PersistentClient(
            path=str(Path(server_dir) / "data" / "chroma"),
            settings=Settings(anonymized_telemetry=False)
        )

        print("\n=== Memory Analysis ===\n")

        # Analyze ChromaDB collections
        collections = chroma_client.list_collections()
        print(f"Number of ChromaDB collections: {len(collections)}")

        for collection in collections:
            count = collection.count()
            print(f"\nCollection '{collection.name}':")
            print(f"  - Number of entries: {count}")

            if count > 0:
                # Get a sample of entries
                sample = collection.get(limit=5)
                print("  - Sample entries:")
                for i, (metadata, doc) in enumerate(zip(sample['metadatas'], sample['documents'])):
                    print(f"    {i+1}. {metadata.get('type', 'unknown')} - {doc[:100]}...")

        print("\n=== Player Memory Analysis ===\n")

        # Analyze player memory logs
        player_keys = [key.decode('utf-8') for key in redis_client.keys('player:*')]
        memory_stats = defaultdict(int)
        memory_types = defaultdict(int)
        total_memory_size = 0

        for key in player_keys:
            player_data = redis_client.get(key)
            if player_data:
                try:
                    player = json.loads(player_data)
                    memory_log = player.get('memory_log', [])

                    # Count memory entries
                    memory_stats['total_entries'] += len(memory_log)

                    # Analyze memory types
                    for entry in memory_log:
                        if isinstance(entry, dict):
                            memory_type = entry.get('type', 'unknown')
                            memory_types[memory_type] += 1

                    # Calculate approximate memory size
                    total_memory_size += len(str(memory_log))
                except json.JSONDecodeError:
                    logger.warning(f"Could not decode player data for key: {key}")
                    continue

        print("Memory Statistics:")
        print(f"Total memory entries: {memory_stats['total_entries']}")
        print(f"Approximate memory size: {total_memory_size / 1024:.2f} KB")

        print("\nMemory Types Distribution:")
        for memory_type, count in memory_types.items():
            percentage = (count / memory_stats['total_entries'] * 100) if memory_stats['total_entries'] > 0 else 0
            print(f"  - {memory_type}: {count} ({percentage:.1f}%)")

        print("\n=== AI Interaction Analysis ===\n")

        # Analyze recent AI interactions
        interaction_keys = [key.decode('utf-8') for key in redis_client.keys('ai_interaction:*')]
        total_interactions = len(interaction_keys)

        print(f"Total AI interactions recorded: {total_interactions}")

        if total_interactions > 0:
            recent_interactions = []
            for key in interaction_keys[-5:]:  # Get last 5 interactions
                interaction_data = redis_client.get(key)
                if interaction_data:
                    try:
                        interaction = json.loads(interaction_data)
                        recent_interactions.append(interaction)
                    except json.JSONDecodeError:
                        logger.warning(f"Could not decode interaction data for key: {key}")
                        continue

            print("\nRecent AI Interactions:")
            for interaction in recent_interactions:
                try:
                    timestamp = parse_timestamp(interaction.get('timestamp', ''))
                    if timestamp:
                        print(f"\nTime: {timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                    else:
                        print("\nTime: Unknown")
                    print(f"Type: {interaction.get('type', 'unknown')}")
                    print(f"Player: {interaction.get('player_name', 'unknown')}")
                    print(f"Context Length: {len(interaction.get('context', ''))}")
                    print(f"Response Length: {len(interaction.get('response', ''))}")
                except Exception as e:
                    logger.warning(f"Error processing interaction: {str(e)}")
                    continue

    except redis.RedisError as e:
        logger.error(f"Redis error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)

if __name__ == "__main__":
    analyze_memory()