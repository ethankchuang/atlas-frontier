#!/usr/bin/env python3
"""
Admin utility to list all rooms in the database.
"""
import sys
import os
import asyncio
from typing import Dict, List, Optional, Any

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.hybrid_database import HybridDatabase as Database

async def list_all_rooms():
    """List all rooms in the database"""
    try:
        db = Database()
        
        # Get all rooms by checking coordinates
        # This is a bit of a hack since we don't have a direct "get all rooms" method
        print("🔍 Searching for rooms...")
        
        # Check a range of coordinates to find existing rooms
        rooms_found = []
        for x in range(-10, 11):
            for y in range(-10, 11):
                try:
                    room_id = await db.get_room_at_coordinates(x, y)
                    if room_id:
                        room_data = await db.get_room(room_id)
                        if room_data:
                            rooms_found.append({
                                'id': room_id,
                                'title': room_data.get('title', 'Unknown'),
                                'x': room_data.get('x', x),
                                'y': room_data.get('y', y),
                                'biome': room_data.get('biome', 'unknown'),
                                'items': len(room_data.get('items', [])),
                                'item_ids': room_data.get('items', [])
                            })
                except Exception as e:
                    # Ignore errors for non-existent coordinates
                    pass
        
        print(f"📊 Found {len(rooms_found)} rooms:")
        print()
        
        for room in rooms_found:
            print(f"🏠 {room['id']}")
            print(f"   Title: {room['title']}")
            print(f"   Coordinates: ({room['x']}, {room['y']})")
            print(f"   Biome: {room['biome']}")
            print(f"   Items: {room['items']} ({room['item_ids']})")
            print()
        
        # Check for the specific 3-star rooms
        print("🎯 Checking for 3-star rooms:")
        three_star_rooms = ['room_0_0', 'room_-3_0', 'room_0_-3']
        
        for room_id in three_star_rooms:
            room_data = await db.get_room(room_id)
            if room_data:
                print(f"✅ {room_id} exists")
                print(f"   Title: {room_data.get('title', 'Unknown')}")
                print(f"   Biome: {room_data.get('biome', 'unknown')}")
                print(f"   Items: {len(room_data.get('items', []))}")
            else:
                print(f"❌ {room_id} does not exist")
        
    except Exception as e:
        print(f"❌ Error listing rooms: {str(e)}")
        import traceback
        traceback.print_exc()

async def main():
    """Main function"""
    await list_all_rooms()

if __name__ == "__main__":
    asyncio.run(main())
