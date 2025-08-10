#!/usr/bin/env python3
"""
Test script to verify the discovery system is working correctly.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from app.game_manager import GameManager
from app.models import Player

async def test_discovery_system():
    """Test the discovery system with discovered and undiscovered coordinates"""
    print("🔍 TESTING DISCOVERY SYSTEM")
    print("=" * 50)
    
    gm = GameManager()
    
    # Create a test player
    player = await gm.create_player("DiscoveryTester")
    print(f"✅ Created player: {player.name}")
    
    # Get world structure to see discovered rooms
    world = await gm.get_world_structure()
    print(f"\n📊 CURRENT WORLD STATE:")
    print(f"   🗺️  Discovered rooms: {world['discovered_rooms']}")
    print(f"   ❓ Undiscovered rooms: {world['undiscovered_rooms']}")
    print(f"   📈 Discovery rate: {world['discovery_rate']}")
    
    print(f"\n🌍 WORLD MAP:")
    for coord, room_info in world['world_map'].items():
        print(f"   {coord}: {room_info}")
    
    # Test movement to discovered coordinate
    print(f"\n🧭 TESTING MOVEMENT:")
    
    # Get initial room
    room_info = await gm.get_room_info(player.current_room)
    initial_room = room_info["room"]
    print(f"   📍 Starting at: {initial_room['title']} ({initial_room['x']}, {initial_room['y']})")
    
    # Check if there are discovered coordinates we can move to
    discovered_coords = await gm.db.get_discovered_coordinates()
    print(f"   🗺️  Discovered coordinates: {list(discovered_coords.keys())}")
    
    # Test movement to undiscovered coordinate
    print(f"\n🚶 Testing movement to UNDISCOVERED coordinate...")
    
    # Try moving east (should be undiscovered)
    response, updates = await gm.process_action(player.id, "go east")
    print(f"   📝 Response: {response[:100]}...")
    
    if "player" in updates and "current_room" in updates["player"]:
        new_room_id = updates["player"]["current_room"]
        new_room_info = await gm.get_room_info(new_room_id)
        new_room = new_room_info["room"]
        
        # Check if this coordinate is now discovered
        is_discovered = await gm.db.is_coordinate_discovered(new_room['x'], new_room['y'])
        
        print(f"   🏠 Moved to: {new_room['title']} ({new_room['x']}, {new_room['y']})")
        print(f"   🔍 Coordinate now discovered: {'✅' if is_discovered else '❌'}")
    
    # Update player reference
    player_data = await gm.db.get_player(player.id)
    player = Player(**player_data)
    
    # Test movement back to discovered coordinate
    print(f"\n🔄 Testing movement back to DISCOVERED coordinate...")
    response, updates = await gm.process_action(player.id, "go west")
    print(f"   📝 Response: {response[:100]}...")
    
    # Final world state
    world = await gm.get_world_structure()
    print(f"\n📊 FINAL WORLD STATE:")
    print(f"   🗺️  Discovered rooms: {world['discovered_rooms']}")
    print(f"   ❓ Undiscovered rooms: {world['undiscovered_rooms']}")
    print(f"   📈 Discovery rate: {world['discovery_rate']}")
    
    print(f"\n🌍 UPDATED WORLD MAP:")
    for coord, room_info in world['world_map'].items():
        print(f"   {coord}: {room_info}")
    
    print("\n" + "=" * 50)
    print("🎉 DISCOVERY SYSTEM TEST COMPLETE!")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_discovery_system()) 