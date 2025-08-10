#!/usr/bin/env python3
"""
Script to synchronize coordinate mappings with room data.
Ensures coordinate mappings and room internal coordinates match.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from app.hybrid_database import HybridDatabase as Database
from app.models import Room

async def sync_coordinates():
    """Synchronize coordinate mappings with room data"""
    print("🔄 SYNCHRONIZING COORDINATES")
    print("=" * 40)
    
    db = Database()
    
    # Get all discovered coordinates
    discovered_coords = await db.get_discovered_coordinates()
    print(f"Found {len(discovered_coords)} discovered coordinates")
    
    fixed_count = 0
    
    for coord_str, room_id in discovered_coords.items():
        # Parse coordinates
        x, y = map(int, coord_str.split(':'))
        
        # Get room data
        room_data = await db.get_room(room_id)
        if room_data:
            room = Room(**room_data)
            
            # Check if room coordinates match mapping
            if room.x != x or room.y != y:
                print(f"❌ MISMATCH: {room_id}")
                print(f"   Mapping says: ({x}, {y})")
                print(f"   Room data says: ({room.x}, {room.y})")
                
                # Fix room coordinates to match mapping
                room.x = x
                room.y = y
                await db.set_room(room_id, room.dict())
                
                print(f"   ✅ Fixed: Updated room to ({x}, {y})")
                fixed_count += 1
            else:
                print(f"✅ OK: {room_id} at ({x}, {y})")
        else:
            print(f"❌ ERROR: Room {room_id} not found")
    
    print(f"\n📊 SUMMARY:")
    print(f"   Fixed: {fixed_count} rooms")
    print(f"   Total: {len(discovered_coords)} coordinates")
    print("✅ Coordinate synchronization complete!")

if __name__ == "__main__":
    asyncio.run(sync_coordinates()) 