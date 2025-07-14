#!/usr/bin/env python3
"""
Debug test for room preloading functionality
"""

import asyncio
import sys
import os
import time

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.game_manager import GameManager
from app.models import Player, Room
from app.database import Database

async def test_preload_debug():
    """Debug the room preloading functionality"""
    print("🔍 Debugging Room Preloading System")
    print("=" * 50)
    
    # Initialize game manager
    game_manager = GameManager()
    
    # Create a test player
    test_player = Player(
        id="debug_player_1",
        name="DebugPlayer",
        current_room="room_debug_start",
        inventory=[],
        quest_progress={},
        memory_log=["Debug session started"]
    )
    
    # Create a test room at origin
    test_room = Room(
        id="room_debug_start",
        title="Debug Starting Room",
        description="A debug room for testing preloading",
        x=0,
        y=0,
        image_url="",
        connections={},
        npcs=[],
        items=[],
        players=[test_player.id],
        visited=True,
        properties={}
    )
    
    print(f"📍 Test room: {test_room.title} at ({test_room.x}, {test_room.y})")
    
    # Save the test room to database
    await game_manager.db.set_room(test_room.id, test_room.dict())
    await game_manager.db.set_room_coordinates(test_room.id, test_room.x, test_room.y)
    await game_manager.db.mark_coordinate_discovered(test_room.x, test_room.y, test_room.id)
    
    print("💾 Test room saved to database")
    
    # Check what rooms exist before preloading
    print("\n🔍 Checking existing rooms before preloading...")
    adjacent_coords = [
        ("north", 0, 1),
        ("south", 0, -1),
        ("east", 1, 0),
        ("west", -1, 0)
    ]
    
    for direction, x, y in adjacent_coords:
        room_id = f"room_{x}_{y}"
        
        # Check if room exists in database
        room_data = await game_manager.db.get_room(room_id)
        exists_in_db = room_data is not None
        
        # Check if coordinate is discovered
        is_discovered = await game_manager.db.is_coordinate_discovered(x, y)
        
        # Check if room is locked
        is_locked = await game_manager.db.is_room_generation_locked(room_id)
        
        # Check generation status
        gen_status = await game_manager.db.get_room_generation_status(room_id)
        
        print(f"  {direction.upper()}: ({x}, {y}) - Room: {room_id}")
        print(f"    Exists in DB: {exists_in_db}")
        print(f"    Coordinate discovered: {is_discovered}")
        print(f"    Generation locked: {is_locked}")
        print(f"    Generation status: {gen_status}")
        
        if room_data:
            print(f"    Title: {room_data.get('title', 'N/A')}")
            print(f"    Description: {room_data.get('description', 'N/A')[:50]}...")
    
    # Test preloading adjacent rooms
    print("\n🚀 Starting preload of adjacent rooms...")
    preload_start = time.time()
    
    try:
        await game_manager.preload_adjacent_rooms(
            test_room.x, test_room.y, test_room, test_player
        )
        preload_time = time.time() - preload_start
        print(f"✅ Preload completed in {preload_time:.2f}s")
    except Exception as e:
        preload_time = time.time() - preload_start
        print(f"❌ Preload failed after {preload_time:.2f}s: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    # Wait a moment for any background tasks
    print("\n⏳ Waiting for background tasks to complete...")
    await asyncio.sleep(2)
    
    # Check what rooms exist after preloading
    print("\n🔍 Checking rooms after preloading...")
    
    for direction, x, y in adjacent_coords:
        room_id = f"room_{x}_{y}"
        
        # Check if room exists in database
        room_data = await game_manager.db.get_room(room_id)
        exists_in_db = room_data is not None
        
        # Check if coordinate is discovered
        is_discovered = await game_manager.db.is_coordinate_discovered(x, y)
        
        # Check if room is locked
        is_locked = await game_manager.db.is_room_generation_locked(room_id)
        
        # Check generation status
        gen_status = await game_manager.db.get_room_generation_status(room_id)
        
        print(f"  {direction.upper()}: ({x}, {y}) - Room: {room_id}")
        print(f"    Exists in DB: {exists_in_db}")
        print(f"    Coordinate discovered: {is_discovered}")
        print(f"    Generation locked: {is_locked}")
        print(f"    Generation status: {gen_status}")
        
        if room_data:
            print(f"    Title: {room_data.get('title', 'N/A')}")
            print(f"    Description: {room_data.get('description', 'N/A')[:50]}...")
            print(f"    Image URL: {room_data.get('image_url', 'N/A')[:30]}...")
        else:
            print(f"    ❌ Room not found in database!")
    
    # Test moving to a preloaded room
    print("\n🚶 Testing movement to preloaded room...")
    
    # Try to move north to the preloaded room
    try:
        actual_room_id, new_room = await game_manager.handle_room_movement_by_direction(
            test_player, test_room, "north"
        )
        
        print(f"✅ Movement successful!")
        print(f"  Destination room: {actual_room_id}")
        print(f"  Room title: {new_room.title}")
        print(f"  Room coordinates: ({new_room.x}, {new_room.y})")
        print(f"  Room description: {new_room.description[:100]}...")
        
        # Check if this was a preloaded room or newly generated
        if new_room.title.startswith("Unexplored Area"):
            print("  ⚠️  This was NOT a preloaded room - it was generated on demand!")
        else:
            print("  ✅ This was a preloaded room!")
            
    except Exception as e:
        print(f"❌ Movement failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_preload_debug()) 