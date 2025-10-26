#!/usr/bin/env python3
"""
Debug test to see what's happening with player_last_room tracking
"""

import asyncio
import aiohttp
import json

async def debug_retreat():
    """Debug the retreat functionality"""
    
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        print("🔍 Debugging Retreat Functionality")
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
            "name": "DebugPlayer",
            "description": "A player for debugging"
        }
        async with session.post(f"{base_url}/players", json=player_data) as response:
            if response.status != 200:
                print(f"❌ Failed to create player: {response.status}")
                return
            player_info = await response.json()
            player_id = player_info.get("id")
            room_id = player_info.get("current_room")
            print(f"✅ Player created: {player_id}")
            print(f"   Starting room: {room_id}")
        
        # 3. Try a simple action first to see if aggressive monsters are present
        print("3. Testing simple action...")
        action_data = {
            "player_id": player_id,
            "action": "look around",
            "room_id": room_id
        }
        
        async with session.post(f"{base_url}/action/stream", json=action_data) as response:
            if response.status == 200:
                result = await response.text()
                if "⚔️" in result and "attacks you" in result:
                    print("❌ Aggressive monster is blocking simple actions")
                    print(f"   Response: {result}")
                else:
                    print("✅ No aggressive monster blocking simple actions")
            else:
                print(f"❌ Action failed: {response.status}")
        
        # 4. Try to move west
        print("4. Moving west...")
        move_data = {
            "player_id": player_id,
            "action": "move west",
            "room_id": room_id
        }
        
        async with session.post(f"{base_url}/action/stream", json=move_data) as response:
            if response.status == 200:
                result = await response.text()
                if "⚔️" in result and "attacks you" in result:
                    print("❌ Aggressive monster blocked movement west")
                    print(f"   Response: {result}")
                    return
                else:
                    print("✅ Moved west successfully")
                    # Extract new room ID
                    if '"current_room"' in result:
                        import re
                        match = re.search(r'"current_room":\s*"([^"]+)"', result)
                        if match:
                            new_room_id = match.group(1)
                            print(f"   New room: {new_room_id}")
                        else:
                            print("   Could not extract new room ID")
                            return
                    else:
                        print("   No room change detected")
                        return
            else:
                print(f"❌ Move failed: {response.status}")
                return
        
        # 5. Try to retreat (move east)
        print("5. Attempting retreat (move east)...")
        retreat_data = {
            "player_id": player_id,
            "action": "move east",
            "room_id": new_room_id
        }
        
        async with session.post(f"{base_url}/action/stream", json=retreat_data) as response:
            if response.status == 200:
                result = await response.text()
                if "⚔️" in result and "attacks you" in result:
                    print("❌ Retreat was blocked by aggressive monster")
                    print(f"   Response: {result}")
                else:
                    print("✅ Retreat was successful")
                    print(f"   Response preview: {result[:100]}...")
            else:
                print(f"❌ Retreat failed: {response.status}")
        
        print("\n🎯 Debug Summary:")
        print("   - Checked if aggressive monsters block simple actions")
        print("   - Attempted movement to establish last room")
        print("   - Attempted retreat")
        print("   - Retreat should be allowed even with aggressive monsters")

if __name__ == "__main__":
    asyncio.run(debug_retreat()) 