#!/usr/bin/env python3
"""
Test script to verify fast movement path
"""
import asyncio
import aiohttp
import json
import time

async def test_fast_movement():
    """Test fast movement path"""
    base_url = "http://localhost:8000"
    
    print("=== Testing Fast Movement Path ===")
    
    async with aiohttp.ClientSession() as session:
        # Create player
        player_data = {"name": "FastTest"}
        
        print("1. Creating player...")
        async with session.post(f"{base_url}/player", json=player_data) as response:
            if response.status != 200:
                print(f"Failed to create player: {response.status}")
                return
            player = await response.json()
            player_id = player["id"]
            room_id = player["current_room"]
            print(f"Player created: {player_id} in {room_id}")
        
        # Test movement north
        print(f"\n2. Testing fast movement north from {room_id}...")
        print("This should be INSTANT (no AI processing)...")
        
        start_time = time.time()
        
        action_data = {
            "player_id": player_id,
            "action": "move north",
            "room_id": room_id
        }
        
        async with session.post(f"{base_url}/action/stream", json=action_data) as response:
            if response.status != 200:
                print(f"Failed to process action: {response.status}")
                return
                
            # Read streaming response
            async for line in response.content:
                if line:
                    try:
                        line_text = line.decode('utf-8').strip()
                        if line_text.startswith('data: '):
                            json_str = line_text[6:]  # Remove 'data: ' prefix
                            data = json.loads(json_str)
                            if data.get("type") == "final":
                                elapsed = time.time() - start_time
                                print(f"Movement completed in {elapsed:.3f}s")
                                print(f"Response: {data['content']}")
                                print(f"New room: {data['updates']['player']['current_room']}")
                                break
                    except json.JSONDecodeError:
                        continue
        
        # Test movement east
        print(f"\n3. Testing fast movement east...")
        start_time = time.time()
        
        action_data = {
            "player_id": player_id,
            "action": "move east",
            "room_id": data['updates']['player']['current_room']
        }
        
        async with session.post(f"{base_url}/action/stream", json=action_data) as response:
            if response.status != 200:
                print(f"Failed to process action: {response.status}")
                return
                
            async for line in response.content:
                if line:
                    try:
                        line_text = line.decode('utf-8').strip()
                        if line_text.startswith('data: '):
                            json_str = line_text[6:]
                            data = json.loads(json_str)
                            if data.get("type") == "final":
                                elapsed = time.time() - start_time
                                print(f"Movement completed in {elapsed:.3f}s")
                                print(f"Response: {data['content']}")
                                break
                    except json.JSONDecodeError:
                        continue

if __name__ == "__main__":
    asyncio.run(test_fast_movement()) 