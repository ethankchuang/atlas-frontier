#!/usr/bin/env python3
"""
Test script to verify rate limiting functionality
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
from app.rate_limiter import RateLimiter
from app.database import Database

async def test_rate_limiting():
    """Test that rate limiting works correctly"""
    print("🚦 Testing Rate Limiting System")
    print("=" * 50)
    
    # Initialize components
    db = Database()
    rate_limiter = RateLimiter(db)
    game_manager = GameManager()
    
    # Test player
    test_player_id = "rate_limit_test_player"
    test_limit = 3  # Small limit for testing
    test_interval = 1  # 1 minute for testing
    
    print(f"🧪 Testing with limit: {test_limit} actions per {test_interval} minute")
    print()
    
    # Test 1: Check initial status
    print("📊 Test 1: Initial rate limit status")
    status = await rate_limiter.get_rate_limit_status(test_player_id, test_limit, test_interval)
    print(f"   Actions: {status['action_count']}/{status['limit']}")
    print(f"   Allowed: {status['is_allowed']}")
    print()
    
    # Test 2: Process actions up to the limit
    print("🎮 Test 2: Processing actions up to limit")
    for i in range(test_limit):
        print(f"   Action {i+1}: Processing...")
        
        # Check rate limit before processing
        is_allowed, info = await rate_limiter.check_rate_limit(test_player_id, test_limit, test_interval)
        
        if is_allowed:
            # Simulate processing an action
            response, updates = await game_manager.process_action(test_player_id, f"test action {i+1}")
            print(f"   ✅ Action {i+1} processed successfully")
            print(f"   Response: {response[:50]}...")
        else:
            print(f"   ❌ Action {i+1} blocked by rate limit")
            print(f"   Reason: {info}")
            break
    
    print()
    
    # Test 3: Check status after actions
    print("📊 Test 3: Rate limit status after actions")
    status = await rate_limiter.get_rate_limit_status(test_player_id, test_limit, test_interval)
    print(f"   Actions: {status['action_count']}/{status['limit']}")
    print(f"   Allowed: {status['is_allowed']}")
    print(f"   Time until reset: {status['time_until_reset']} seconds")
    print()
    
    # Test 4: Try to exceed the limit
    print("🚫 Test 4: Attempting to exceed rate limit")
    is_allowed, info = await rate_limiter.check_rate_limit(test_player_id, test_limit, test_interval)
    
    if not is_allowed:
        print(f"   ✅ Rate limit correctly blocked action")
        print(f"   Message: {info.get('message', 'No message')}")
        print(f"   Time until reset: {info['time_until_reset']} seconds")
    else:
        print(f"   ❌ Rate limit failed to block action")
    
    print()
    
    # Test 5: Wait for reset (simulate)
    print("⏰ Test 5: Simulating time passage")
    print("   (In real scenario, would wait for time to pass)")
    print("   Current cutoff time: {status['cutoff_time']}")
    print()
    
    # Test 6: Check with different limits
    print("🔧 Test 6: Testing different rate limit configurations")
    
    # Test with higher limit
    high_limit_status = await rate_limiter.get_rate_limit_status(test_player_id, 100, 30)
    print(f"   High limit (100/30min): {high_limit_status['action_count']}/{high_limit_status['limit']} - Allowed: {high_limit_status['is_allowed']}")
    
    # Test with lower limit
    low_limit_status = await rate_limiter.get_rate_limit_status(test_player_id, 1, 30)
    print(f"   Low limit (1/30min): {low_limit_status['action_count']}/{low_limit_status['limit']} - Allowed: {low_limit_status['is_allowed']}")
    
    print()
    
    # Test 7: Test with different player
    print("👤 Test 7: Testing with different player")
    different_player_id = "different_test_player"
    diff_status = await rate_limiter.get_rate_limit_status(different_player_id, test_limit, test_interval)
    print(f"   Different player: {diff_status['action_count']}/{diff_status['limit']} - Allowed: {diff_status['is_allowed']}")
    
    print()
    print("✅ Rate limiting test completed!")

async def test_api_endpoints():
    """Test the API endpoints for rate limiting"""
    print("🌐 Testing Rate Limit API Endpoints")
    print("=" * 50)
    
    base_url = "http://localhost:8000"
    test_player_id = "api_test_player"
    
    try:
        # Test rate limit status endpoint
        print("📊 Testing rate limit status endpoint")
        response = requests.get(f"{base_url}/rate-limit/status/{test_player_id}")
        if response.status_code == 200:
            status = response.json()
            print(f"   ✅ Status endpoint working")
            print(f"   Actions: {status['action_count']}/{status['limit']}")
            print(f"   Allowed: {status['is_allowed']}")
        else:
            print(f"   ❌ Status endpoint failed: {response.status_code}")
        
        print()
        
        # Test rate limit config endpoint
        print("⚙️ Testing rate limit config endpoint")
        new_config = {"limit": 25, "interval_minutes": 15}
        response = requests.post(f"{base_url}/rate-limit/config", json=new_config)
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Config endpoint working")
            print(f"   New config: {result['config']}")
        else:
            print(f"   ❌ Config endpoint failed: {response.status_code}")
        
        print()
        print("✅ API endpoint tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("   ⚠️ Server not running - skipping API tests")
    except Exception as e:
        print(f"   ❌ API test error: {str(e)}")

if __name__ == "__main__":
    print("🚦 RATE LIMITING SYSTEM TEST")
    print("=" * 60)
    
    # Run the tests
    asyncio.run(test_rate_limiting())
    print()
    asyncio.run(test_api_endpoints())
    
    print()
    print("🎉 All tests completed!") 