"""
Rate limiter for player actions
Checks database for recent actions and enforces limits
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, Tuple
from .database import Database
import logging

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, db: Database):
        self.db = db
    
    async def check_rate_limit(self, player_id: str, limit: int = 50, interval_minutes: int = 30) -> Tuple[bool, dict]:
        """
        Check if player has exceeded rate limit
        
        Args:
            player_id: The player to check
            limit: Maximum number of actions allowed (default: 50)
            interval_minutes: Time window in minutes to check (default: 30)
            
        Returns:
            Tuple of (allowed: bool, info: dict)
        """
        try:
            # Calculate the cutoff time (30 minutes ago)
            cutoff_time = datetime.utcnow() - timedelta(minutes=interval_minutes)
            cutoff_timestamp = cutoff_time.isoformat()
            
            # Get all actions for this player within the time window
            recent_actions_in_window = await self.db.get_actions_in_time_window(
                player_id=player_id, 
                cutoff_timestamp=cutoff_timestamp
            )
            
            action_count = len(recent_actions_in_window)
            is_allowed = action_count < limit
            
            # Calculate time until reset (when the oldest action will be 30 minutes old)
            if recent_actions_in_window:
                oldest_action_time = min(
                    datetime.fromisoformat(action['timestamp']) 
                    for action in recent_actions_in_window
                )
                reset_time = oldest_action_time + timedelta(minutes=interval_minutes)
                time_until_reset = (reset_time - datetime.utcnow()).total_seconds()
            else:
                time_until_reset = 0
            
            info = {
                'action_count': action_count,
                'limit': limit,
                'interval_minutes': interval_minutes,
                'time_until_reset': max(0, int(time_until_reset)),
                'cutoff_time': cutoff_timestamp,
                'is_allowed': is_allowed
            }
            
            logger.info(f"Rate limit check for {player_id}: {action_count}/{limit} actions in last {interval_minutes}min - {'ALLOWED' if is_allowed else 'BLOCKED'}")
            
            return is_allowed, info
            
        except Exception as e:
            logger.error(f"Error checking rate limit for {player_id}: {str(e)}")
            # On error, allow the action to prevent blocking legitimate users
            return True, {
                'action_count': 0,
                'limit': limit,
                'interval_minutes': interval_minutes,
                'time_until_reset': 0,
                'error': str(e),
                'is_allowed': True
            }
    
    async def get_rate_limit_status(self, player_id: str, limit: int = 50, interval_minutes: int = 30) -> dict:
        """
        Get current rate limit status without blocking
        
        Args:
            player_id: The player to check
            limit: Maximum number of actions allowed (default: 50)
            interval_minutes: Time window in minutes to check (default: 30)
        """
        _, info = await self.check_rate_limit(player_id, limit, interval_minutes)
        return info
    
    async def is_rate_limited(self, player_id: str, limit: int = 50, interval_minutes: int = 30) -> bool:
        """
        Simple check - returns True if player is rate limited
        
        Args:
            player_id: The player to check
            limit: Maximum number of actions allowed (default: 50)
            interval_minutes: Time window in minutes to check (default: 30)
        """
        is_allowed, _ = await self.check_rate_limit(player_id, limit, interval_minutes)
        return not is_allowed 