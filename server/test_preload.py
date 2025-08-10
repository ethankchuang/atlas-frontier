#!/usr/bin/env python3
"""
Test script for room preloading functionality
"""

import asyncio
import sys
import os

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.game_manager import GameManager
from app.models import Player, Room
from app.hybrid_database import HybridDatabase as Database

async def test_preload_functionality():
    """Test the room preloading functionality"""
    print("🧪 Testing Room Preloading Functionality")
    print("=" * 50)
    
    # Initialize game manager
    game_manager = GameManager()
    
    # Create a test player
    test_player = Player(
        id="test_player_1",
        name="TestPlayer",
        current_room="room_start",
        inventory=[],
        quest_progress={},
        memory_log=["Test session started"]
    )
    
    # Create a test room at origin
    test_room = Room(
        id="room_start",
        title="Test Starting Room",
        description="A test room for preloading verification",
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
    
    # Test preloading adjacent rooms
    print("\n🚀 Starting preload of adjacent rooms...")
    try:
        await game_manager.preload_adjacent_rooms(
            test_room.x, test_room.y, test_room, test_player
        )
        print("✅ Preload completed successfully")
    except Exception as e:
        print(f"❌ Preload failed: {str(e)}")
        return
    
    # Check what rooms were created
    print("\n🔍 Checking created rooms...")
    adjacent_coords = [
        ("north", 0, 1),
        ("south", 0, -1),
        ("east", 1, 0),
        ("west", -1, 0)
    ]
    
    for direction, x, y in adjacent_coords:
        room_id = f"room_{x}_{y}"
        
        # Check if room exists
        room_data = await Database.get_room(room_id)
        if room_data:
            print(f"✅ {direction.upper()}: Room {room_id} exists")
            print(f"   Title: {room_data.get('title', 'N/A')}")
            print(f"   Status: {room_data.get('image_status', 'N/A')}")
        else:
            print(f"❌ {direction.upper()}: Room {room_id} not found")
        
        # Check generation status
        status = await Database.get_room_generation_status(room_id)
        print(f"   Generation Status: {status}")
        
        # Check if coordinate is discovered
        is_discovered = await Database.is_coordinate_discovered(x, y)
        print(f"   Discovered: {is_discovered}")
        print()
    
    print("🎉 Test completed!")

if __name__ == "__main__":
    asyncio.run(test_preload_functionality()) 