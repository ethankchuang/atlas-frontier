#!/usr/bin/env python3
"""
Test script to verify action and chat storage functionality
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
from app.models import Player, Room, GameState, ActionRecord, ChatMessage
from app.hybrid_database import HybridDatabase as Database

async def test_storage_functionality():
    """Test that action and chat storage is working correctly"""
    print("🗄️ Testing Action and Chat Storage")
    print("=" * 50)
    
    # Initialize game manager
    game_manager = GameManager()
    
    # Test player
    test_player_id = "storage_test_player"
    test_room_id = "room_start"
    
    # Create test player
    test_player = Player(
        id=test_player_id,
        name="StorageTestPlayer",
        current_room=test_room_id,
        inventory=[],
        quest_progress={},
        memory_log=["Storage test started"]
    )
    
    # Save player to database
    await game_manager.db.set_player(test_player_id, test_player.dict())
    print(f"✅ Created test player: {test_player.name}")
    
    # Test 1: Store action record
    print("\n🧪 Test 1: Storing action record")
    action_record = ActionRecord(
        player_id=test_player_id,
        room_id=test_room_id,
        action="look around",
        ai_response="You see a mysterious room with ancient artifacts.",
        updates={"player": {"memory_log": ["Looked around the room"]}},
        session_id="test_session_1",
        metadata={
            "room_title": "Ancient Chamber",
            "npcs_present": ["Guardian"],
            "ai_model": "gpt-4o"
        }
    )
    
    await game_manager.db.store_action_record(test_player_id, action_record)
    print(f"✅ Stored action record: {action_record.id}")
    
    # Test 2: Store chat message
    print("\n🧪 Test 2: Storing chat message")
    chat_message = ChatMessage(
        player_id=test_player_id,
        room_id=test_room_id,
        message="Hello everyone!",
        message_type="chat",
        is_ai_response=False
    )
    
    await game_manager.db.store_chat_message(test_room_id, chat_message)
    print(f"✅ Stored chat message: {chat_message.id}")
    
    # Test 3: Store AI response as chat
    print("\n🧪 Test 3: Storing AI response as chat")
    ai_chat_message = ChatMessage(
        player_id="system",
        room_id=test_room_id,
        message="The Guardian nods in greeting.",
        message_type="system",
        is_ai_response=True,
        ai_context={"npc_id": "guardian_1", "interaction_type": "greeting"}
    )
    
    await game_manager.db.store_chat_message(test_room_id, ai_chat_message)
    print(f"✅ Stored AI chat message: {ai_chat_message.id}")
    
    # Test 4: Retrieve action history
    print("\n🧪 Test 4: Retrieving action history")
    action_history = await game_manager.db.get_action_history(test_player_id, limit=10)
    print(f"✅ Retrieved {len(action_history)} action records")
    
    if action_history:
        latest_action = action_history[0]
        print(f"   Latest action: '{latest_action['action']}'")
        print(f"   AI response: '{latest_action['ai_response'][:50]}...'")
        print(f"   Timestamp: {latest_action['timestamp']}")
    
    # Test 5: Retrieve chat history
    print("\n🧪 Test 5: Retrieving chat history")
    chat_history = await game_manager.db.get_chat_history(test_room_id, limit=10)
    print(f"✅ Retrieved {len(chat_history)} chat messages")
    
    if chat_history:
        for msg in chat_history:
            print(f"   [{msg['timestamp']}] {msg['player_id']}: {msg['message']}")
    
    # Test 6: Test API endpoints (if server is running)
    print("\n🧪 Test 6: Testing API endpoints")
    try:
        # Test action history endpoint
        response = requests.get(f"http://localhost:8000/actions/history/{test_player_id}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API: Retrieved {len(data['actions'])} actions via API")
        else:
            print(f"❌ API: Action history endpoint returned {response.status_code}")
        
        # Test chat history endpoint
        response = requests.get(f"http://localhost:8000/chat/history/{test_room_id}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API: Retrieved {len(data['messages'])} messages via API")
        else:
            print(f"❌ API: Chat history endpoint returned {response.status_code}")
        
        # Test analytics endpoint
        response = requests.get(f"http://localhost:8000/analytics/player/{test_player_id}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API: Retrieved analytics - {data['total_actions']} total actions")
        else:
            print(f"❌ API: Analytics endpoint returned {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("⚠️  Server not running - skipping API tests")
    
    print("\n🎉 Storage functionality test completed!")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(test_storage_functionality()) 