#!/usr/bin/env python3
"""
Quick test to verify rate limiting with 1 action per 10 seconds
"""

import asyncio
import sys
import os

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.database import Database
from app.rate_limiter import RateLimiter

async def test_rate_limiting():
    """Test the rate limiting with 1 action per 10 seconds"""
    
    # Initialize rate limiter with database
    db = Database()
    rate_limiter = RateLimiter(db)
    
    test_player_id = "player_test_rate_limit"
    
    print("🧪 Testing Rate Limiting (1 action per 10 seconds)")
    print("=" * 50)
    
    # Test 1: First action should be allowed
    print("\n1️⃣ Testing first action...")
    is_allowed, info = await rate_limiter.check_rate_limit(
        test_player_id, 
        limit=1, 
        interval_minutes=0.167  # 10 seconds
    )
    
    print(f"   Allowed: {is_allowed}")
    print(f"   Action count: {info['action_count']}")
    print(f"   Limit: {info['limit']}")
    print(f"   Interval: {info['interval_minutes']} minutes")
    
    if is_allowed:
        print("   ✅ First action allowed (expected)")
        
        # Store an action record to simulate a real action
        from app.models import ActionRecord
        from datetime import datetime
        
        action_record = ActionRecord(
            player_id=test_player_id,
            room_id="test_room",
            action="test action",
            ai_response="test response",
            updates={},
            session_id="test_session",
            metadata={}
        )
        
        await db.store_action_record(test_player_id, action_record)
        print("   📝 Stored action record")
    else:
        print("   ❌ First action blocked (unexpected)")
        return
    
    # Test 2: Second action should be blocked
    print("\n2️⃣ Testing second action (should be blocked)...")
    is_allowed, info = await rate_limiter.check_rate_limit(
        test_player_id, 
        limit=1, 
        interval_minutes=0.167
    )
    
    print(f"   Allowed: {is_allowed}")
    print(f"   Action count: {info['action_count']}")
    print(f"   Time until reset: {info['time_until_reset']} seconds")
    
    if not is_allowed:
        print("   ✅ Second action blocked (expected)")
        print(f"   ⏰ Must wait {info['time_until_reset']} seconds")
    else:
        print("   ❌ Second action allowed (unexpected)")
    
    # Test 3: Wait 10 seconds and try again
    print("\n3️⃣ Waiting 10 seconds and testing again...")
    print("   ⏳ Waiting 10 seconds...")
    await asyncio.sleep(10)
    
    is_allowed, info = await rate_limiter.check_rate_limit(
        test_player_id, 
        limit=1, 
        interval_minutes=0.167
    )
    
    print(f"   Allowed: {is_allowed}")
    print(f"   Action count: {info['action_count']}")
    
    if is_allowed:
        print("   ✅ Action allowed after waiting (expected)")
    else:
        print("   ❌ Action still blocked after waiting (unexpected)")
    
    print("\n" + "=" * 50)
    print("🏁 Rate limiting test completed!")

if __name__ == "__main__":
    asyncio.run(test_rate_limiting()) 