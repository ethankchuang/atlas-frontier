#!/usr/bin/env python3
"""
Test the new loading behavior - only show loading spinner when rooms are being generated
"""

import asyncio
from app.game_manager import GameManager
from app.hybrid_database import HybridDatabase as Database
from app.models import Room

async def test_loading_behavior():
    """Test that loading behavior works correctly"""
    print("🧪 Testing new loading behavior...")
    
    # Reset the world first
    print("🔄 Resetting world...")
    db = Database()
    await db.reset_world()
    print("✅ World reset complete")
    
    # Initialize game manager
    game_manager = GameManager()
    
    # Initialize the game first
    print("🔄 Initializing game...")
    await game_manager.initialize_game()
    print("✅ Game initialized")
    
    # Create a test player
    player = await game_manager.create_player("TestPlayer")
    print(f"✅ Created test player: {player.name}")
    
    # Get starting room
    starting_room_data = await game_manager.db.get_room(player.current_room)
    starting_room = Room(**starting_room_data)
    print(f"✅ Starting room: {starting_room.title}")
    print(f"   Image status: {starting_room.image_status}")
    
    # Wait for initial preloading to complete
    print("\n⏳ Waiting for initial preloading to complete...")
    await asyncio.sleep(3)
    
    # Test movement to a preloaded room (should NOT show loading spinner)
    print("\n🚶 Testing movement to preloaded room...")
    response, updates = await game_manager.process_action(player.id, "move north")
    
    print(f"✅ Movement response: {response[:100]}...")
    print(f"✅ Updates keys: {list(updates.keys())}")
    
    if "room_generation" in updates:
        room_gen = updates["room_generation"]
        print(f"✅ Room generation status:")
        print(f"   Is generating: {room_gen['is_generating']}")
        print(f"   Room ID: {room_gen['room_id']}")
        print(f"   Image status: {room_gen['image_status']}")
        
        if not room_gen['is_generating']:
            print("✅ CORRECT: No loading spinner should show for preloaded room")
        else:
            print("⚠️  WARNING: Loading spinner will show for preloaded room")
    else:
        print("❌ ERROR: No room_generation info in updates")
    
    # Test movement to a new room (should show loading spinner)
    print("\n🚶 Testing movement to new room...")
    response, updates = await game_manager.process_action(player.id, "move east")
    
    print(f"✅ Movement response: {response[:100]}...")
    print(f"✅ Updates keys: {list(updates.keys())}")
    
    if "room_generation" in updates:
        room_gen = updates["room_generation"]
        print(f"✅ Room generation status:")
        print(f"   Is generating: {room_gen['is_generating']}")
        print(f"   Room ID: {room_gen['room_id']}")
        print(f"   Image status: {room_gen['image_status']}")
        
        if room_gen['is_generating']:
            print("✅ CORRECT: Loading spinner should show for new room")
        else:
            print("⚠️  WARNING: No loading spinner for new room")
    else:
        print("❌ ERROR: No room_generation info in updates")
    
    print("\n🎉 Loading behavior test completed!")

if __name__ == "__main__":
    asyncio.run(test_loading_behavior()) 