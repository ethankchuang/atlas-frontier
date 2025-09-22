#!/usr/bin/env python3
"""
Simple debug script to test retreat functionality
"""

import asyncio
import aiohttp
import json

async def test_retreat():
    """Test retreat functionality with detailed logging"""
    
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        print("🔍 Testing Retreat Functionality")
        print("=" * 50)
        
        # 1. Start the game
        print("1. Starting game...")
        async with session.post(f"{base_url}/start") as response:
            if response.status != 200:
                print(f"❌ Failed to start game: {response.status}")
                return
            print("✅ Game started")
        
        # 2. Create a player (this will fail due to auth, but let's see what happens)
        print("2. Attempting to create player...")
        player_data = {
            "name": "RetreatTestPlayer",
            "description": "A player testing retreat functionality"
        }
        async with session.post(f"{base_url}/players", json=player_data) as response:
            print(f"   Response status: {response.status}")
            if response.status == 200:
                player_info = await response.json()
                player_id = player_info.get("id")
                print(f"✅ Player created: {player_id}")
            else:
                print(f"❌ Failed to create player: {response.status}")
                response_text = await response.text()
                print(f"   Response: {response_text}")
                return
        
        print("\n🎯 Test completed - check server logs for retreat debugging info")

if __name__ == "__main__":
    asyncio.run(test_retreat())
