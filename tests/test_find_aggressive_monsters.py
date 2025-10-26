#!/usr/bin/env python3
"""
Test script to find aggressive monsters and test their behavior
"""

import asyncio
import aiohttp
import json

async def find_aggressive_monsters():
    """Find aggressive monsters in the world"""
    
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        print("🔍 Finding Aggressive Monsters")
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
            "name": "MonsterHunter",
            "description": "A player hunting for aggressive monsters"
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
        
        # 3. Get world structure to understand the layout
        print("3. Getting world structure...")
        async with session.get(f"{base_url}/world/structure") as response:
            if response.status != 200:
                print(f"❌ Failed to get world structure: {response.status}")
                return
            world_structure = await response.json()
            rooms = world_structure.get("rooms", [])
            print(f"   Found {len(rooms)} rooms in the world")
        
        # 4. Check each room for aggressive monsters
        print("4. Searching for aggressive monsters...")
        aggressive_monster_rooms = []
        
        for room in rooms[:10]:  # Check first 10 rooms to avoid too many requests
            room_id = room.get("id")
            print(f"   Checking room: {room_id}")
            
            async with session.get(f"{base_url}/room/{room_id}") as response:
                if response.status == 200:
                    room_info = await response.json()
                    monsters = room_info.get("monsters", [])
                    
                    if monsters:
                        print(f"     Found {len(monsters)} monsters")
                        # Check if any are aggressive
                        for monster_id in monsters:
                            # We can't directly check monster aggressiveness from room info
                            # But we can note rooms with monsters
                            print(f"     Room {room_id} has monsters: {monsters}")
                            aggressive_monster_rooms.append((room_id, monsters))
                            break  # Just note the first room with monsters
                else:
                    print(f"     Failed to get room info: {response.status}")
            
            await asyncio.sleep(0.1)  # Small delay between requests
        
        if not aggressive_monster_rooms:
            print("❌ No rooms with monsters found in first 10 rooms")
            return
        
        # 5. Test aggressive monster behavior in the first room with monsters
        print("5. Testing aggressive monster behavior...")
        test_room_id, monster_ids = aggressive_monster_rooms[0]
        print(f"   Testing in room: {test_room_id} with monsters: {monster_ids}")
        
        # Move the player to this room (simulate being there)
        # For now, let's just test the action processing logic
        
        # Test different actions that should be blocked by aggressive monsters
        test_actions = [
            "look around",
            "search the room",
            "examine the wall",
            "pick up something"
        ]
        
        for action in test_actions:
            print(f"   Testing action: '{action}'")
            action_data = {"player_id": player_id, "action": action}
            
            async with session.post(f"{base_url}/action/stream", json=action_data) as response:
                if response.status == 200:
                    result = await response.text()
                    print(f"     Result: {result[:100]}...")
                    
                    # Check if combat was initiated
                    if "⚔️" in result:
                        print(f"     ✅ Combat initiated for action '{action}'")
                    else:
                        print(f"     ❌ No combat initiated for action '{action}'")
                else:
                    print(f"     ❌ Action failed: {response.status}")
            
            await asyncio.sleep(0.5)
        
        print("\n🎯 Summary:")
        print(f"   - Found {len(aggressive_monster_rooms)} rooms with monsters")
        print("   - Tested action blocking behavior")
        print("   - Check server logs for detailed monster behavior")

if __name__ == "__main__":
    asyncio.run(find_aggressive_monsters()) 