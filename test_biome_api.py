#!/usr/bin/env python3

import asyncio
import aiohttp
import json

async def test_biome_system_via_api():
    """Test the biome system through the API"""
    print("Testing biome system via API...")
    
    base_url = "http://localhost:8000"
    
    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Start the game
            print("1. Starting game...")
            async with session.post(f"{base_url}/start") as response:
                if response.status == 200:
                    game_data = await response.json()
                    print(f"   Game started successfully")
                else:
                    print(f"   Failed to start game: {response.status}")
                    return

            # Step 2: Create a player
            print("2. Creating player...")
            async with session.post(f"{base_url}/player", json={"name": "TestPlayer"}) as response:
                if response.status == 200:
                    player_data = await response.json()
                    player_id = player_data["player"]["id"]
                    room_id = player_data["player"]["current_room"]
                    print(f"   Player created: {player_id}")
                    print(f"   Starting room: {room_id}")
                else:
                    print(f"   Failed to create player: {response.status}")
                    return

            # Step 3: Get room information to see if biome is present
            print("3. Checking starting room for biome...")
            async with session.get(f"{base_url}/room/{room_id}") as response:
                if response.status == 200:
                    room_data = await response.json()
                    room = room_data["room"]
                    biome = room.get("biome", "No biome")
                    print(f"   Room title: {room.get('title', 'No title')}")
                    print(f"   Room biome: {biome}")
                    print(f"   Coordinates: ({room.get('x', '?')}, {room.get('y', '?')})")
                else:
                    print(f"   Failed to get room info: {response.status}")
                    return

            # Step 4: Try to move to trigger room generation
            print("4. Moving north to trigger new room generation...")
            async with session.post(f"{base_url}/action/stream", json={
                "player_id": player_id,
                "action": "go north",
                "room_id": room_id
            }) as response:
                if response.status == 200:
                    print("   Move action initiated")
                    # The response is streaming, so we'll just confirm it started
                else:
                    print(f"   Failed to initiate move: {response.status}")

            # Step 5: Wait a moment for room generation, then check rooms
            print("5. Waiting for room generation...")
            await asyncio.sleep(3)

            # Step 6: Check player's current room
            print("6. Checking new room after movement...")
            async with session.get(f"{base_url}/room/current/{player_id}") as response:
                if response.status == 200:
                    room_data = await response.json()
                    room = room_data["room"]
                    biome = room.get("biome", "No biome")
                    print(f"   New room title: {room.get('title', 'No title')}")
                    print(f"   New room biome: {biome}")
                    print(f"   New coordinates: ({room.get('x', '?')}, {room.get('y', '?')})")
                else:
                    print(f"   Failed to get current room: {response.status}")

            print("\nBiome API test completed!")
            
        except Exception as e:
            print(f"Error during testing: {e}")

if __name__ == "__main__":
    asyncio.run(test_biome_system_via_api())