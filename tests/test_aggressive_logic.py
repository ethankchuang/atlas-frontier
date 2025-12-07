#!/usr/bin/env python3
"""
Test the aggressive monster logic directly
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))

import asyncio
from app.monster_behavior import monster_behavior_manager
from app.game_manager import GameManager
from app.database import Database

async def test_aggressive_monster_logic():
    """Test the aggressive monster logic directly"""
    
    print("🧪 Testing Aggressive Monster Logic")
    print("=" * 40)
    
    # Initialize game manager
    game_manager = GameManager()
    
    # Test data
    player_id = "test_player_123"
    room_id = "test_room_456"
    monster_id = "test_monster_789"
    
    # Create a test monster in the aggressive monsters tracking
    monster_behavior_manager.aggressive_monsters[room_id] = {
        monster_id: "Test Aggressive Monster"
    }
    
    # Set player's last room
    monster_behavior_manager.player_last_room[player_id] = "previous_room_123"
    
    print("1. Testing aggressive monster blocking for 'any_action'...")
    
    # Test that aggressive monsters block any action
    result = await monster_behavior_manager.check_aggressive_monster_blocking(
        player_id, room_id, "any_action", game_manager
    )
    
    if result:
        monster_id_result, monster_name_result = result
        print(f"   ✅ Aggressive monster correctly blocked action")
        print(f"   Monster: {monster_name_result} (ID: {monster_id_result})")
    else:
        print("   ❌ Aggressive monster did not block action")
    
    print("\n2. Testing aggressive monster blocking for movement...")
    
    # Test movement to new room (should be blocked)
    result = await monster_behavior_manager.check_aggressive_monster_blocking(
        player_id, room_id, "north", game_manager
    )
    
    if result:
        monster_id_result, monster_name_result = result
        print(f"   ✅ Movement to new room correctly blocked")
        print(f"   Monster: {monster_name_result} (ID: {monster_id_result})")
    else:
        print("   ❌ Movement to new room not blocked")
    
    print("\n3. Testing aggressive monster combat initiation...")
    
    # Test combat initiation
    combat_message = await monster_behavior_manager.handle_aggressive_combat_initiation(
        player_id, monster_id, room_id, "any_action", game_manager
    )
    
    print(f"   Combat message: {combat_message}")
    
    if "⚔️" in combat_message and "charges at you aggressively" in combat_message:
        print("   ✅ Combat initiation working correctly")
    else:
        print("   ❌ Combat initiation not working as expected")
    
    print("\n4. Testing room without aggressive monsters...")
    
    # Test room without aggressive monsters
    empty_room_id = "empty_room_123"
    result = await monster_behavior_manager.check_aggressive_monster_blocking(
        player_id, empty_room_id, "any_action", game_manager
    )
    
    if result is None:
        print("   ✅ Room without aggressive monsters correctly allows actions")
    else:
        print("   ❌ Room without aggressive monsters incorrectly blocked action")
    
    print("\n🎯 Test Summary:")
    print("   - Aggressive monsters should block ALL actions except retreat")
    print("   - Combat should be initiated when actions are blocked")
    print("   - Rooms without aggressive monsters should allow actions")

if __name__ == "__main__":
    asyncio.run(test_aggressive_monster_logic()) 