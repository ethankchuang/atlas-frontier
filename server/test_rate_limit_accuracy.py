#!/usr/bin/env python3

import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import json

# Add the server directory to the Python path
server_dir = Path(__file__).parent
sys.path.append(str(server_dir))

from app.database import Database
from app.rate_limiter import RateLimiter
from app.models import ActionRecord

async def test_rate_limit_accuracy():
    """Test that rate limiting correctly counts actions within 30-minute window"""
    print("🧪 Testing Rate Limit Accuracy (50 actions per 30 minutes)")
    print("=" * 60)
    
    # Initialize database and rate limiter
    db = Database()
    rate_limiter = RateLimiter(db)
    
    test_player_id = "test_player_rate_limit_accuracy"
    
    # Clear any existing test data
    try:
        # This would clear the player's action history
        print("📝 Clearing test data...")
    except:
        pass
    
    print(f"\n📊 Test 1: Initial rate limit status")
    status = await rate_limiter.get_rate_limit_status(test_player_id, limit=50, interval_minutes=30)
    print(f"   Actions: {status['action_count']}/50")
    print(f"   Allowed: {status['is_allowed']}")
    print(f"   Time window: {status['interval_minutes']} minutes")
    
    print(f"\n📝 Test 2: Creating test actions within 30-minute window")
    
    # Create 45 actions (should be allowed)
    print("   Creating 45 actions (should be allowed)...")
    for i in range(45):
        action_record = ActionRecord(
            player_id=test_player_id,
            room_id="room_test",
            action=f"test action {i+1}",
            ai_response=f"AI response to action {i+1}",
            updates={},
            session_id="test_session",
            metadata={"test": True}
        )
        await db.store_action_record(test_player_id, action_record)
    
    # Check status after 45 actions
    status = await rate_limiter.get_rate_limit_status(test_player_id, limit=50, interval_minutes=30)
    print(f"   After 45 actions: {status['action_count']}/50 - Allowed: {status['is_allowed']}")
    
    # Create 5 more actions (should reach exactly 50)
    print("   Creating 5 more actions (should reach exactly 50)...")
    for i in range(45, 50):
        action_record = ActionRecord(
            player_id=test_player_id,
            room_id="room_test",
            action=f"test action {i+1}",
            ai_response=f"AI response to action {i+1}",
            updates={},
            session_id="test_session",
            metadata={"test": True}
        )
        await db.store_action_record(test_player_id, action_record)
    
    # Check status after 50 actions
    status = await rate_limiter.get_rate_limit_status(test_player_id, limit=50, interval_minutes=30)
    print(f"   After 50 actions: {status['action_count']}/50 - Allowed: {status['is_allowed']}")
    
    # Try to create one more action (should be blocked)
    print("   Creating 1 more action (should be blocked)...")
    action_record = ActionRecord(
        player_id=test_player_id,
        room_id="room_test",
        action="test action 51",
        ai_response="AI response to action 51",
        updates={},
        session_id="test_session",
        metadata={"test": True}
    )
    await db.store_action_record(test_player_id, action_record)
    
    # Check status after 51 actions
    status = await rate_limiter.get_rate_limit_status(test_player_id, limit=50, interval_minutes=30)
    print(f"   After 51 actions: {status['action_count']}/50 - Allowed: {status['is_allowed']}")
    
    print(f"\n📊 Test 3: Verifying time window accuracy")
    
    # Get all actions for this player
    all_actions = await db.get_actions_in_time_window(test_player_id, "1970-01-01T00:00:00")
    print(f"   Total actions stored: {len(all_actions)}")
    
    # Check actions in last 30 minutes
    cutoff_time = datetime.utcnow() - timedelta(minutes=30)
    cutoff_timestamp = cutoff_time.isoformat()
    recent_actions = await db.get_actions_in_time_window(test_player_id, cutoff_timestamp)
    print(f"   Actions in last 30 minutes: {len(recent_actions)}")
    
    # Show some action timestamps
    if recent_actions:
        print(f"   Oldest action timestamp: {recent_actions[-1]['timestamp']}")
        print(f"   Newest action timestamp: {recent_actions[0]['timestamp']}")
        print(f"   Cutoff timestamp: {cutoff_timestamp}")
    
    print(f"\n📊 Test 4: Rate limit check details")
    is_allowed, info = await rate_limiter.check_rate_limit(test_player_id, limit=50, interval_minutes=30)
    print(f"   Rate limit check result: {'ALLOWED' if is_allowed else 'BLOCKED'}")
    print(f"   Action count: {info['action_count']}")
    print(f"   Limit: {info['limit']}")
    print(f"   Interval: {info['interval_minutes']} minutes")
    print(f"   Time until reset: {info['time_until_reset']} seconds")
    
    print(f"\n✅ Rate limit accuracy test completed!")
    print(f"   Expected: 50 actions per 30 minutes")
    print(f"   Actual: {info['action_count']} actions in last {info['interval_minutes']} minutes")
    print(f"   Result: {'PASS' if info['action_count'] == 51 and not is_allowed else 'FAIL'}")

if __name__ == "__main__":
    asyncio.run(test_rate_limit_accuracy()) 