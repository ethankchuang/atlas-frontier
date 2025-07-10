#!/usr/bin/env python3

import sys
import os
import logging
from pathlib import Path

# Add the server directory to the Python path so we can import from app
server_dir = Path(__file__).parent.parent
sys.path.append(str(server_dir))

from app.logger import setup_logging
from app.config import settings
from app.database import Database
from app.game_manager import GameManager

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

async def reset_world():
    """Reset the entire game world and reinitialize it."""
    try:
        # Initialize database and game manager
        db = Database()
        game_manager = GameManager()

        print("\nResetting game world...")

        # Reset all data
        await db.reset_world()
        print("✓ Database cleared")

        # Initialize new game state
        game_state = await game_manager.initialize_game()
        print("✓ New game state initialized")

        # Print summary
        print("\n=== New Game State ===\n")
        print(f"World Seed: {game_state.world_seed}")
        print(f"Main Quest: {game_state.main_quest_summary}")
        print(f"Active Quests: {len(game_state.active_quests)}")
        print(f"Global State Variables: {len(game_state.global_state)}")

        print("\nWorld reset complete!")

    except Exception as e:
        logger.error(f"Error resetting world: {str(e)}")
        print(f"\nError: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(reset_world())