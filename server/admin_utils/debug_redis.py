#!/usr/bin/env python3
"""
Debug script to check Redis storage
"""

import asyncio
import sys
import os
import json

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database import redis_client

async def debug_redis():
    print("🔍 DEBUGGING REDIS STORAGE")
    print("=" * 50)
    
    # Check all keys
    all_keys = redis_client.keys("*")
    print(f"📊 Total Redis keys: {len(all_keys)}")
    
    # Look for action data in the correct format
    print("\n🎮 ACTION DATA:")
    action_list_keys = [k for k in all_keys if k.startswith(b'actions:player:')]
    print(f"Found {len(action_list_keys)} action list keys")
    
    for key in action_list_keys:
        print(f"\n📝 {key.decode('utf-8')}:")
        try:
            actions = redis_client.lrange(key, 0, -1)
            print(f"   Total actions: {len(actions)}")
            
            for i, action_data in enumerate(actions[:3]):  # Show first 3
                try:
                    action = json.loads(action_data.decode('utf-8'))
                    print(f"   Action {i+1}:")
                    print(f"      ID: {action.get('id', 'N/A')}")
                    print(f"      Player: {action.get('player_id', 'N/A')}")
                    print(f"      Room: {action.get('room_id', 'N/A')}")
                    print(f"      Action: {action.get('action', 'N/A')[:50]}...")
                    print(f"      AI Response: {action.get('ai_response', 'N/A')[:50]}...")
                    print(f"      Timestamp: {action.get('timestamp', 'N/A')}")
                except json.JSONDecodeError as e:
                    print(f"      Error parsing action {i+1}: {e}")
                    print(f"      Raw data: {action_data.decode('utf-8')[:100]}...")
        except Exception as e:
            print(f"   Error reading key: {e}")
    
    # Also check for any hash-based action records
    print("\n🔍 CHECKING FOR HASH-BASED ACTION RECORDS:")
    action_hash_keys = [k for k in all_keys if k.startswith(b'action:')]
    print(f"Found {len(action_hash_keys)} action hash keys")
    
    for key in action_hash_keys:
        print(f"\n📝 {key.decode('utf-8')}:")
        try:
            data = redis_client.hgetall(key)
            print(f"   Data: {data}")
        except Exception as e:
            print(f"   Error reading: {e}")

if __name__ == "__main__":
    asyncio.run(debug_redis()) 