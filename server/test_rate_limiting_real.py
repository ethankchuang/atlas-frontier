#!/usr/bin/env python3
"""
Realistic test script to verify rate limiting functionality with actual player actions
"""

import asyncio
import sys
import os
import time
import json

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.game_manager import GameManager
from app.models import Player, Room, GameState
from app.rate_limiter import RateLimiter
from app.database import Database

async def test_real_rate_limiting():
    """Test rate limiting with a real player and actions"""
    print("🚦 Testing Real Rate Limiting System")
    print("=" * 50)
    
    # Initialize components
    game_manager = GameManager()
    
    # Create a test player
    print("👤 Creating test player...")
    test_player = await game_manager.create_player("RateLimitTestPlayer")
    test_player_id = test_player.id
    print(f"   ✅ Created player: {test_player_id}")
    print()
    
    # Set a very low rate limit for testing
    game_manager.rate_limit_config['limit'] = 3
    game_manager.rate_limit_config['interval_minutes'] = 1
    
    print(f"🧪 Testing with limit: {game_manager.rate_limit_config['limit']} actions per {game_manager.rate_limit_config['interval_minutes']} minute")
    print()
    
    # Test 1: Check initial status
    print("📊 Test 1: Initial rate limit status")
    status = await game_manager.rate_limiter.get_rate_limit_status(
        test_player_id, 
        game_manager.rate_limit_config['limit'], 
        game_manager.rate_limit_config['interval_minutes']
    )
    print(f"   Actions: {status['action_count']}/{status['limit']}")
    print(f"   Allowed: {status['is_allowed']}")
    print()
    
    # Test 2: Process actions up to the limit
    print("🎮 Test 2: Processing actions up to limit")
    actions = ["look around", "examine the room", "go north"]
    
    for i, action in enumerate(actions):
        print(f"   Action {i+1}: '{action}'")
        
        # Process the action
        response, updates = await game_manager.process_action(test_player_id, action)
        
        # Check if it was rate limited
        if updates.get('error') == 'rate_limit_exceeded':
            print(f"   ❌ Action {i+1} blocked by rate limit")
            print(f"   Message: {updates.get('message', 'No message')}")
            break
        else:
            print(f"   ✅ Action {i+1} processed successfully")
            print(f"   Response: {response[:50]}...")
        
        # Small delay between actions
        await asyncio.sleep(0.1)
    
    print()
    
    # Test 3: Check status after actions
    print("📊 Test 3: Rate limit status after actions")
    status = await game_manager.rate_limiter.get_rate_limit_status(
        test_player_id, 
        game_manager.rate_limit_config['limit'], 
        game_manager.rate_limit_config['interval_minutes']
    )
    print(f"   Actions: {status['action_count']}/{status['limit']}")
    print(f"   Allowed: {status['is_allowed']}")
    print(f"   Time until reset: {status['time_until_reset']} seconds")
    print()
    
    # Test 4: Try to exceed the limit
    print("🚫 Test 4: Attempting to exceed rate limit")
    response, updates = await game_manager.process_action(test_player_id, "try another action")
    
    if updates.get('error') == 'rate_limit_exceeded':
        print(f"   ✅ Rate limit correctly blocked action")
        print(f"   Message: {updates.get('message', 'No message')}")
        rate_info = updates.get('rate_limit_info', {})
        print(f"   Time until reset: {rate_info.get('time_until_reset', 0)} seconds")
    else:
        print(f"   ❌ Rate limit failed to block action")
        print(f"   Response: {response[:50]}...")
    
    print()
    
    # Test 5: Check with admin utility
    print("📊 Test 5: Checking with admin utility")
    try:
        from admin_utils.view_messages import MessageViewer
        viewer = MessageViewer()
        
        # Get action history for this player
        actions = await viewer.db.get_action_history(test_player_id, limit=10)
        print(f"   Total actions in database: {len(actions)}")
        
        # Get rate limit status
        status = await viewer.db.get_rate_limit_status(test_player_id, 3, 1)
        print(f"   Rate limit status: {status['action_count']}/{status['limit']}")
        
    except Exception as e:
        print(f"   ⚠️ Admin utility check failed: {str(e)}")
    
    print()
    print("✅ Real rate limiting test completed!")

if __name__ == "__main__":
    print("🚦 REAL RATE LIMITING SYSTEM TEST")
    print("=" * 60)
    
    # Run the test
    asyncio.run(test_real_rate_limiting())
    
    print()
    print("🎉 Test completed!") 