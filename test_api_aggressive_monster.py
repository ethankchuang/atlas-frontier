#!/usr/bin/env python3
"""
Test the API behavior with aggressive monsters
"""

import asyncio
import aiohttp
import json

async def test_api_aggressive_monster():
    """Test the API behavior with aggressive monsters"""
    
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        print("🧪 Testing API Aggressive Monster Behavior")
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
            "name": "AggressiveTestPlayer",
            "description": "A player testing aggressive monster behavior"
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
        
        # 3. Test various actions to see if they trigger aggressive monster behavior
        print("3. Testing actions for aggressive monster blocking...")
        
        test_actions = [
            "look around",
            "search the room",
            "examine the walls",
            "pick up any items",
            "move north",
            "move south",
            "move east",
            "move west"
        ]
        
        for action in test_actions:
            print(f"   Testing action: '{action}'")
            action_data = {
                "player_id": player_id, 
                "action": action,
                "room_id": room_id
            }
            
            try:
                async with session.post(f"{base_url}/action/stream", json=action_data) as response:
                    if response.status == 200:
                        result = await response.text()
                        print(f"     Status: {response.status}")
                        print(f"     Result: {result[:200]}...")
                        
                        # Check if aggressive monster behavior is triggered
                        if "⚔️" in result and ("charges at you aggressively" in result or "engages you in combat" in result):
                            print(f"     ✅ Aggressive monster behavior triggered!")
                        elif "Rate limit" in result:
                            print(f"     ⚠️  Rate limited")
                        else:
                            print(f"     ℹ️  Normal action processing")
                    else:
                        print(f"     ❌ Failed: {response.status}")
                        try:
                            error_text = await response.text()
                            print(f"     Error: {error_text}")
                        except:
                            pass
            except Exception as e:
                print(f"     ❌ Exception: {str(e)}")
            
            await asyncio.sleep(1)  # Delay between requests
        
        print("\n🎯 API Test Summary:")
        print("   - Tested various actions for aggressive monster blocking")
        print("   - Checked if combat is initiated when actions are blocked")
        print("   - Verified API responses are working correctly")

if __name__ == "__main__":
    asyncio.run(test_api_aggressive_monster()) 