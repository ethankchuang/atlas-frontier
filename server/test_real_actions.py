#!/usr/bin/env python3
"""
Test script to verify that real player actions and AI responses are being stored
"""
import asyncio
import sys
import os
import time
import json
import requests

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.game_manager import GameManager
from app.models import Player, Room, GameState

async def test_real_action_storage():
    """Test that real player actions and AI responses are being stored"""
    print("🎮 Testing Real Action Storage")
    print("=" * 50)
    
    # Initialize game manager
    game_manager = GameManager()
    
    # Create a test player
    test_player = await game_manager.create_player("RealActionTestPlayer")
    print(f"✅ Created test player: {test_player.name} (ID: {test_player.id})")
    
    # Test actions that should trigger AI responses
    test_actions = [
        "look around",
        "examine the room",
        "go north",
        "talk to anyone here"
    ]
    
    print(f"\n🧪 Testing {len(test_actions)} real actions...")
    
    for i, action in enumerate(test_actions, 1):
        print(f"\n--- Action {i}: '{action}' ---")
        
        # Process the action through the game manager
        try:
            response, updates = await game_manager.process_action(test_player.id, action)
            print(f"✅ Action processed successfully")
            print(f"   AI Response: {response[:100]}...")
            print(f"   Updates: {list(updates.keys()) if updates else 'None'}")
            
            # Small delay to ensure proper timestamp separation
            await asyncio.sleep(0.1)
            
        except Exception as e:
            print(f"❌ Action failed: {str(e)}")
    
    # Wait a moment for any background processing
    await asyncio.sleep(1)
    
    # Check what was stored
    print(f"\n📊 Checking stored data...")
    
    # Get action history
    action_history = await game_manager.db.get_action_history(test_player.id, limit=10)
    print(f"✅ Found {len(action_history)} stored action records")
    
    for i, action_record in enumerate(action_history):
        print(f"   {i+1}. [{action_record['timestamp']}] '{action_record['action']}'")
        print(f"      AI: {action_record['ai_response'][:80]}...")
        print(f"      Room: {action_record['room_id']}")
        print(f"      Session: {action_record['session_id']}")
    
    # Get chat history for the starting room
    chat_history = await game_manager.db.get_chat_history("room_start", limit=10)
    print(f"\n✅ Found {len(chat_history)} stored chat messages")
    
    for i, chat_msg in enumerate(chat_history):
        print(f"   {i+1}. [{chat_msg['timestamp']}] {chat_msg['player_id']}: {chat_msg['message'][:60]}...")
    
    # Test API endpoints
    print(f"\n🌐 Testing API endpoints...")
    try:
        # Test action history API
        response = requests.get(f"http://localhost:8000/actions/history/{test_player.id}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API: Retrieved {len(data['actions'])} actions")
            
            # Show the most recent action
            if data['actions']:
                latest = data['actions'][0]
                print(f"   Latest via API: '{latest['action']}' at {latest['timestamp']}")
        else:
            print(f"❌ API: Action history returned {response.status_code}")
        
        # Test analytics API
        response = requests.get(f"http://localhost:8000/analytics/player/{test_player.id}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API: Analytics - {data['total_actions']} actions, {data['actions_per_day']:.1f} per day")
        else:
            print(f"❌ API: Analytics returned {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("⚠️  Server not running - skipping API tests")
    
    print(f"\n🎉 Real action storage test completed!")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_real_action_storage()) 