#!/usr/bin/env python3
"""
Script to fix coordinate conflicts in the database.
This will reset all coordinate mappings and rebuild them correctly.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from app.database import Database, redis_client
from app.models import Room
import logging

logger = logging.getLogger(__name__)

async def fix_coordinates():
    """Fix coordinate conflicts by resetting and rebuilding coordinate mappings"""
    print("🧹 IMPLEMENTING DISCOVERY SYSTEM")
    print("=" * 50)
    
    db = Database()
    
    # Step 1: Clear all coordinate and discovery mappings
    print("1. Clearing all coordinate and discovery mappings...")
    coord_keys = redis_client.keys("coord:*")
    discovery_keys = redis_client.keys("discovered:*")
    all_keys = coord_keys + discovery_keys
    if all_keys:
        redis_client.delete(*all_keys)
        print(f"   ✅ Cleared {len(coord_keys)} coordinate mappings")
        print(f"   ✅ Cleared {len(discovery_keys)} discovery mappings")
    else:
        print("   ✅ No mappings found to clear")
    
    # Step 2: Get all rooms and mark as discovered
    print("\n2. Marking all existing rooms as discovered...")
    room_keys = [key.decode() if isinstance(key, bytes) else key 
                for key in redis_client.keys("room:*")]
    
    rebuilt_count = 0
    conflicts = []
    
    for room_key in room_keys:
        room_id = room_key.replace("room:", "")
        try:
            room_data = await db.get_room(room_id)
            if room_data:
                room = Room(**room_data)
                
                # Check if coordinates already exist
                existing_room_id = redis_client.get(f"coord:{room.x}:{room.y}")
                if existing_room_id:
                    existing_room_id = existing_room_id.decode('utf-8') if isinstance(existing_room_id, bytes) else existing_room_id
                    if existing_room_id != room_id:
                        conflicts.append((room.x, room.y, existing_room_id, room_id))
                        print(f"   ⚠️  CONFLICT: Coordinates ({room.x}, {room.y}) claimed by both {existing_room_id} and {room_id}")
                        continue
                
                # Mark coordinate as discovered (for existing rooms)
                await db.mark_coordinate_discovered(room.x, room.y, room_id)
                rebuilt_count += 1
                print(f"   ✅ Marked coordinates ({room.x}, {room.y}) as discovered for room {room_id}")
                
        except Exception as e:
            print(f"   ❌ Error processing room {room_id}: {str(e)}")
    
    print(f"\n   ✅ Rebuilt {rebuilt_count} coordinate mappings")
    
    # Step 3: Report conflicts
    if conflicts:
        print(f"\n3. Found {len(conflicts)} coordinate conflicts:")
        for x, y, existing_id, conflicting_id in conflicts:
            print(f"   ⚠️  ({x}, {y}): {existing_id} vs {conflicting_id}")
            
        print("\n   🔧 Resolving conflicts by reassigning coordinates...")
        
        # Resolve conflicts by reassigning coordinates to conflicting rooms
        for x, y, existing_id, conflicting_id in conflicts:
            # Find a new coordinate for the conflicting room
            new_x, new_y = find_free_coordinates(x, y)
            
            # Update the conflicting room's coordinates
            conflicting_room_data = await db.get_room(conflicting_id)
            if conflicting_room_data:
                conflicting_room = Room(**conflicting_room_data)
                conflicting_room.x = new_x
                conflicting_room.y = new_y
                await db.set_room(conflicting_id, conflicting_room.dict())
                await db.mark_coordinate_discovered(new_x, new_y, conflicting_id)
                print(f"   ✅ Moved room {conflicting_id} to discovered coordinates ({new_x}, {new_y})")
    else:
        print("\n3. ✅ No coordinate conflicts found!")
    
    print("\n" + "=" * 50)
    print("🎉 DISCOVERY SYSTEM IMPLEMENTED!")
    print("🗺️  All existing rooms marked as discovered")
    print("❓ New coordinates will be undiscovered until explored")
    print("=" * 50)

def find_free_coordinates(start_x, start_y):
    """Find the next available coordinates starting from a given position"""
    # Start with adjacent coordinates
    candidates = [
        (start_x + 1, start_y),
        (start_x - 1, start_y),
        (start_x, start_y + 1),
        (start_x, start_y - 1),
        (start_x + 1, start_y + 1),
        (start_x - 1, start_y - 1),
        (start_x + 1, start_y - 1),
        (start_x - 1, start_y + 1),
    ]
    
    # Expand search if needed
    for distance in range(2, 10):
        for dx in range(-distance, distance + 1):
            for dy in range(-distance, distance + 1):
                if abs(dx) == distance or abs(dy) == distance:
                    candidates.append((start_x + dx, start_y + dy))
    
    # Find first free coordinate
    for x, y in candidates:
        if not redis_client.exists(f"coord:{x}:{y}"):
            return x, y
    
    # Fallback to a high number if we can't find anything
    return start_x + 100, start_y + 100

if __name__ == "__main__":
    asyncio.run(fix_coordinates()) 