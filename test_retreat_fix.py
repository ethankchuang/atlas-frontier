#!/usr/bin/env python3
"""
Test script to verify retreat functionality works correctly
"""

import asyncio
import aiohttp
import json

async def test_retreat_functionality():
    """Test that retreat functionality works correctly"""
    
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        print("🧪 Testing Retreat Functionality")
        print("=" * 40)
        
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
            "name": "RetreatTestPlayer",
            "description": "A player testing retreat functionality"
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
        
        # 3. Move to a new room to establish a "last room"
        print("3. Moving to establish last room...")
        action_data = {
            "player_id": player_id,
            "action": "move west",
            "room_id": room_id
        }
        
        async with session.post(f"{base_url}/action/stream", json=action_data) as response:
            if response.status == 200:
                result = await response.text()
                print("✅ Moved to new room successfully")
                # Extract the new room ID from the response
                if '"current_room"' in result:
                    import re
                    match = re.search(r'"current_room":\s*"([^"]+)"', result)
                    if match:
                        new_room_id = match.group(1)
                        print(f"   New room: {new_room_id}")
                    else:
                        print("   Could not extract new room ID")
                else:
                    print("   No room change detected")
            else:
                print(f"❌ Move failed: {response.status}")
                return
        
        # 4. Try to retreat (move back to the original room)
        print("4. Testing retreat...")
        print(f"   Current room: {new_room_id}")
        print(f"   Original room: {room_id}")
        print(f"   Attempting to move east (back to {room_id})")
        
        retreat_action_data = {
            "player_id": player_id,
            "action": "move east",
            "room_id": new_room_id
        }
        
        async with session.post(f"{base_url}/action/stream", json=retreat_action_data) as response:
            if response.status == 200:
                result = await response.text()
                print("✅ Retreat action processed")
                
                # Check if retreat was successful (no combat initiated)
                if "⚔️" in result and "attacks you" in result:
                    print("❌ Retreat was blocked by aggressive monster")
                    print(f"   Full response: {result}")
                else:
                    print("✅ Retreat was successful (no combat initiated)")
                    print(f"   Response preview: {result[:100]}...")
            else:
                print(f"❌ Retreat action failed: {response.status}")
        
        # 5. Debug: Check player info to see current room
        print("5. Debug: Checking player info...")
        async with session.get(f"{base_url}/players/{player_id}") as response:
            if response.status == 200:
                player_info = await response.json()
                current_room = player_info.get("current_room")
                print(f"   Player current room: {current_room}")
            else:
                print(f"   Failed to get player info: {response.status}")
        
        print("\n🎯 Retreat Test Summary:")
        print("   - Player moved to establish a 'last room'")
        print("   - Retreat action was attempted")
        print("   - Retreat should be allowed even with aggressive monsters")

if __name__ == "__main__":
    asyncio.run(test_retreat_functionality()) 