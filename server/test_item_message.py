#!/usr/bin/env python3
"""
Test script to verify item acquisition messages
"""
import asyncio
import json
import websockets
import requests
import time

async def test_item_acquisition_message():
    """Test that item acquisition messages are sent to players"""
    
    # Start the server (assuming it's running on localhost:8000)
    base_url = "http://localhost:8000"
    
    print("🧪 Testing item acquisition message functionality...")
    
    # Create a test player
    player_name = f"TestPlayer_{int(time.time())}"
    create_response = requests.post(f"{base_url}/player", json={"name": player_name})
    
    if create_response.status_code != 200:
        print(f"❌ Failed to create player: {create_response.status_code}")
        return False
    
    player_data = create_response.json()
    player_id = player_data["id"]
    room_id = player_data["current_room"]
    
    print(f"✅ Created player: {player_name} (ID: {player_id})")
    print(f"📍 Starting room: {room_id}")
    
    # Connect to WebSocket
    ws_url = f"ws://localhost:8000/ws/{room_id}/{player_id}"
    print(f"🔌 Connecting to WebSocket: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket connected")
            
            # Send an action to trigger item generation
            action_request = {
                "player_id": player_id,
                "action": "look around",
                "room_id": room_id
            }
            
            print("🎯 Sending action to trigger item generation...")
            
            # Send action via HTTP streaming endpoint
            response = requests.post(
                f"{base_url}/action/stream",
                json=action_request,
                headers={"Accept": "text/event-stream"}
            )
            
            if response.status_code != 200:
                print(f"❌ Failed to send action: {response.status_code}")
                return False
            
            print("✅ Action sent successfully")
            
            # Wait for WebSocket messages
            print("⏳ Waiting for item acquisition message...")
            timeout = 30  # 30 seconds timeout
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    
                    print(f"📨 Received message type: {data.get('type')}")
                    
                    if data.get('type') == 'item_obtained':
                        print("🎉 SUCCESS: Item acquisition message received!")
                        print(f"   Item: {data.get('item_name')}")
                        print(f"   Rarity: {data.get('item_rarity')}")
                        print(f"   Stars: {data.get('rarity_stars')}")
                        print(f"   Message: {data.get('message')}")
                        
                        # Verify the message format
                        required_fields = ['item_name', 'item_rarity', 'rarity_stars', 'message']
                        for field in required_fields:
                            if field not in data:
                                print(f"❌ Missing required field: {field}")
                                return False
                        
                        # Verify rarity stars format
                        rarity = data.get('item_rarity')
                        stars = data.get('rarity_stars')
                        expected_stars = "★" * rarity + "☆" * (4 - rarity)
                        
                        if stars != expected_stars:
                            print(f"❌ Incorrect stars format: expected {expected_stars}, got {stars}")
                            return False
                        
                        print("✅ All item acquisition message fields are correct!")
                        return True
                        
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"❌ Error receiving message: {e}")
                    break
            
            print("⏰ Timeout waiting for item acquisition message")
            return False
            
    except Exception as e:
        print(f"❌ WebSocket connection failed: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_item_acquisition_message())
    if result:
        print("\n🎉 Test PASSED: Item acquisition messages are working correctly!")
    else:
        print("\n❌ Test FAILED: Item acquisition messages are not working") 