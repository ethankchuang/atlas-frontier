#!/usr/bin/env python3
"""
Test parallel room preloading functionality
"""

import asyncio
import sys
import os
import time

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.game_manager import GameManager
from app.models import Player, Room
from app.hybrid_database import HybridDatabase as Database

async def test_parallel_preload():
    """Test parallel room preloading functionality"""
    print("🚀 Testing Parallel Room Preloading")
    print("=" * 50)
    
    # Initialize game manager
    game_manager = GameManager()
    
    # Create a test player
    test_player = Player(
        id="parallel_test_player",
        name="ParallelTestPlayer",
        current_room="room_test_parallel",
        inventory=[],
        quest_progress={},
        memory_log=["Parallel test session started"]
    )
    
    # Create a test room at coordinates (10, 10) to avoid conflicts
    test_room = Room(
        id="room_test_parallel",
        title="Parallel Test Starting Room",
        description="A test room for parallel preloading verification",
        x=10,
        y=10,
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
    await game_manager.db.set_room(test_room.id, test_room.model_dump())
    await game_manager.db.set_room_coordinates(test_room.id, test_room.x, test_room.y)
    await game_manager.db.mark_coordinate_discovered(test_room.x, test_room.y, test_room.id)
    
    print("💾 Test room saved to database")
    
    # Check what rooms exist before preloading
    print("\n🔍 Checking existing rooms before preloading...")
    adjacent_coords = [
        ("north", 10, 11),
        ("south", 10, 9),
        ("east", 11, 10),
        ("west", 9, 10)
    ]
    
    for direction, x, y in adjacent_coords:
        room_id = f"room_{x}_{y}"
        
        # Check if room exists in database
        room_data = await game_manager.db.get_room(room_id)
        exists_in_db = room_data is not None
        
        # Check if coordinate is discovered
        is_discovered = await game_manager.db.is_coordinate_discovered(x, y)
        
        print(f"  {direction.upper()}: ({x}, {y}) - Room: {room_id}")
        print(f"    Exists in DB: {exists_in_db}")
        print(f"    Coordinate discovered: {is_discovered}")
        
        if room_data:
            print(f"    Title: {room_data.get('title', 'N/A')}")
        else:
            print(f"    ❌ Room not found - will be generated!")
        print()
    
    # Test preloading adjacent rooms
    print("\n🚀 Starting parallel preload of adjacent rooms...")
    preload_start = time.time()
    
    try:
        await game_manager.preload_adjacent_rooms(
            test_room.x, test_room.y, test_room, test_player
        )
        preload_time = time.time() - preload_start
        print(f"✅ Preload completed in {preload_time:.2f}s")
        
        # If preload was fast (under 5 seconds), it likely means rooms were skipped
        if preload_time < 5:
            print("⚠️  Preload was very fast - rooms may have been skipped or already existed")
        else:
            print("✅ Preload took reasonable time - parallel generation likely working")
            
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
        
        # Check generation status
        gen_status = await game_manager.db.get_room_generation_status(room_id)
        
        print(f"  {direction.upper()}: ({x}, {y}) - Room: {room_id}")
        print(f"    Exists in DB: {exists_in_db}")
        print(f"    Coordinate discovered: {is_discovered}")
        print(f"    Generation status: {gen_status}")
        
        if room_data:
            print(f"    Title: {room_data.get('title', 'N/A')}")
            print(f"    Description: {room_data.get('description', 'N/A')[:50]}...")
            print(f"    Image URL: {room_data.get('image_url', 'N/A')[:30]}...")
            print(f"    ✅ Room successfully generated!")
        else:
            print(f"    ❌ Room not found in database!")
        print()
    
    print("🎉 Parallel preload test completed!")

if __name__ == "__main__":
    asyncio.run(test_parallel_preload()) 