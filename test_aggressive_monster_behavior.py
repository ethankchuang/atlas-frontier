#!/usr/bin/env python3
"""
Test script to verify aggressive monster behavior:
- Aggressive monsters should block ALL actions except retreat
- Combat should be properly initiated when blocked
"""

import asyncio
import aiohttp
import json
import time

async def test_aggressive_monster_behavior():
    """Test that aggressive monsters block all actions except retreat"""
    
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        print("🧪 Testing Aggressive Monster Behavior")
        print("=" * 50)
        
        # 1. Start the game
        print("1. Starting game...")
        async with session.post(f"{base_url}/start") as response:
            if response.status != 200:
                print(f"❌ Failed to start game: {response.status}")
                return
            print("✅ Game started")
        
        # 2. Create a player
        print("2. Creating player...")
        player_data = {
            "name": "TestPlayer",
            "description": "A test player for aggressive monster testing"
        }
        async with session.post(f"{base_url}/player", json=player_data) as response:
            if response.status != 200:
                print(f"❌ Failed to create player: {response.status}")
                return
            player_info = await response.json()
            player_id = player_info.get("id")
            room_id = player_info.get("current_room")
            print(f"✅ Player created: {player_id}")
            print(f"   Starting room: {room_id}")
        
        # 3. Check if there are aggressive monsters in the room
        print("3. Checking room for aggressive monsters...")
        async with session.get(f"{base_url}/room/{room_id}") as response:
            if response.status != 200:
                print(f"❌ Failed to get room info: {response.status}")
                return
            room_info = await response.json()
            monsters = room_info.get("monsters", [])
            print(f"   Monsters in room: {monsters}")
            
            if not monsters:
                print("⚠️  No monsters in starting room - need to move to find aggressive monsters")
                # Try to move to find monsters
                print("   Moving to find monsters...")
                move_action = {"player_id": player_id, "action": "move north"}
                async with session.post(f"{base_url}/action/stream", json=move_action) as response:
                    if response.status == 200:
                        result = await response.text()
                        print(f"   Move result: {result[:200]}...")
                    else:
                        print(f"   Move failed: {response.status}")
                return
        
        # 4. Test that aggressive monsters block non-retreat actions
        print("4. Testing action blocking by aggressive monsters...")
        
        # Test different types of actions that should be blocked
        test_actions = [
            "look around",
            "search the room", 
            "pick up item",
            "examine wall",
            "move east",
            "move west",
            "move south"
        ]
        
        for action in test_actions:
            print(f"   Testing action: '{action}'")
            action_data = {"player_id": player_id, "action": action}
            
            async with session.post(f"{base_url}/action/stream", json=action_data) as response:
                if response.status == 200:
                    result = await response.text()
                    # Check if the result indicates combat initiation
                    if "⚔️" in result and ("charges at you aggressively" in result or "engages you in combat" in result):
                        print(f"   ✅ Action '{action}' correctly blocked - combat initiated")
                    else:
                        print(f"   ❌ Action '{action}' not blocked as expected")
                        print(f"      Result: {result[:200]}...")
                else:
                    print(f"   ❌ Action '{action}' failed: {response.status}")
            
            # Small delay between tests
            await asyncio.sleep(0.5)
        
        # 5. Test that retreat actions are allowed
        print("5. Testing that retreat actions are allowed...")
        
        # Get the player's last room (simulate having moved from a previous room)
        # For this test, we'll assume the player came from a specific direction
        retreat_action = {"player_id": player_id, "action": "move back the way I came"}
        
        async with session.post(f"{base_url}/action/stream", json=retreat_action) as response:
            if response.status == 200:
                result = await response.text()
                if "⚔️" in result and "charges at you aggressively" in result:
                    print("   ❌ Retreat action incorrectly blocked")
                else:
                    print("   ✅ Retreat action allowed (no combat initiated)")
            else:
                print(f"   ❌ Retreat action failed: {response.status}")
        
        print("\n🎯 Test Summary:")
        print("   - Aggressive monsters should block ALL actions except retreat")
        print("   - Combat should be initiated when actions are blocked")
        print("   - Retreat actions should be allowed")

if __name__ == "__main__":
    asyncio.run(test_aggressive_monster_behavior()) 