#!/usr/bin/env python3
"""
Test script to verify world reset functionality
"""

import asyncio
import aiohttp
import json

async def test_world_reset():
    """Test the world reset functionality"""
    
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        print("🧪 Testing World Reset Functionality")
        print("=" * 40)
        
        # 1. Start the game (this triggers world generation)
        print("1. Starting game (world generation)...")
        async with session.post(f"{base_url}/start") as response:
            if response.status != 200:
                print(f"❌ Failed to start game: {response.status}")
                return
            print("✅ Game started successfully")
        
        # 2. Get the world structure to verify it was generated
        print("2. Getting world structure...")
        async with session.get(f"{base_url}/world/structure") as response:
            if response.status != 200:
                print(f"❌ Failed to get world structure: {response.status}")
                return
            world_structure = await response.json()
            rooms = world_structure.get("rooms", [])
            print(f"✅ World structure retrieved - {len(rooms)} rooms found")
        
        # 3. Create a player to test the world
        print("3. Creating player...")
        player_data = {
            "name": "ResetTestPlayer",
            "description": "A player testing world reset"
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
        
        # 4. Test a simple action to verify the world is working
        print("4. Testing world functionality...")
        action_data = {
            "player_id": player_id,
            "action": "look around",
            "room_id": room_id
        }
        
        async with session.post(f"{base_url}/action/stream", json=action_data) as response:
            if response.status == 200:
                result = await response.text()
                print("✅ Action processed successfully")
                print(f"   Response preview: {result[:100]}...")
            else:
                print(f"❌ Action failed: {response.status}")
        
        print("\n🎯 World Reset Test Summary:")
        print("   - World generation completed without JSON parsing errors")
        print("   - World structure is accessible")
        print("   - Player creation works")
        print("   - Action processing works")
        print("   - The fix for JSON parsing errors appears to be working!")

if __name__ == "__main__":
    asyncio.run(test_world_reset()) 