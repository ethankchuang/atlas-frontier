#!/usr/bin/env python3
"""
Admin utility to regenerate items for existing rooms.
This can be used to fix rooms that were created without items.
"""
import sys
import os
import asyncio
from typing import Dict, List, Optional, Any

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.hybrid_database import HybridDatabase as Database
from app.game_manager import GameManager

async def regenerate_items_for_room(room_id: str) -> bool:
    """Regenerate items for a specific room"""
    try:
        db = Database()
        gm = GameManager()
        
        # Get room data
        room_data = await db.get_room(room_id)
        if not room_data:
            print(f"❌ Room {room_id} not found")
            return False
        
        print(f"🔄 Regenerating items for room {room_id}")
        print(f"   Title: {room_data.get('title', 'Unknown')}")
        print(f"   Biome: {room_data.get('biome', 'unknown')}")
        print(f"   Coordinates: ({room_data.get('x', '?')}, {room_data.get('y', '?')})")
        print(f"   Current items: {len(room_data.get('items', []))}")
        
        # Get item distribution
        biome = room_data.get('biome', 'unknown')
        x = room_data.get('x', 0)
        y = room_data.get('y', 0)
        
        item_distribution = await gm._assign_room_item_distribution(biome, x, y)
        print(f"   Item distribution: {item_distribution}")
        
        # Generate new items
        room_items = await gm._generate_room_items(
            room_id, 
            item_distribution, 
            biome, 
            room_data.get('title', 'Unknown Room'), 
            room_data.get('description', 'No description')
        )
        
        print(f"   Generated {len(room_items)} items: {room_items}")
        
        # Update room with new items
        room_data['items'] = room_items
        success = await db.set_room(room_id, room_data)
        
        if success:
            print(f"✅ Successfully updated room {room_id} with {len(room_items)} items")
            return True
        else:
            print(f"❌ Failed to update room {room_id}")
            return False
            
    except Exception as e:
        print(f"❌ Error regenerating items for room {room_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def regenerate_items_for_biome_three_star_rooms():
    """Regenerate items for all 3-star rooms"""
    try:
        db = Database()
        
        # Get all biomes
        all_biomes = await db.get_all_saved_biomes()
        print(f"Found {len(all_biomes)} biomes")
        
        success_count = 0
        total_count = 0
        
        for biome in all_biomes:
            biome_name = biome.get('name', 'Unknown')
            three_star_room_id = await db.get_biome_three_star_room(biome_name)
            
            if three_star_room_id:
                total_count += 1
                print(f"\n🌍 Processing biome: {biome_name}")
                success = await regenerate_items_for_room(three_star_room_id)
                if success:
                    success_count += 1
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total 3-star rooms processed: {total_count}")
        print(f"   Successfully updated: {success_count}")
        print(f"   Failed: {total_count - success_count}")
        
    except Exception as e:
        print(f"❌ Error processing biomes: {str(e)}")
        import traceback
        traceback.print_exc()

async def regenerate_items_for_specific_rooms(room_ids: List[str]):
    """Regenerate items for specific rooms"""
    success_count = 0
    
    for room_id in room_ids:
        print(f"\n{'='*60}")
        success = await regenerate_items_for_room(room_id)
        if success:
            success_count += 1
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total rooms processed: {len(room_ids)}")
    print(f"   Successfully updated: {success_count}")
    print(f"   Failed: {len(room_ids) - success_count}")

async def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 regenerate_room_items.py all                    # Regenerate all 3-star rooms")
        print("  python3 regenerate_room_items.py room_0_0 room_-3_0     # Regenerate specific rooms")
        return
    
    command = sys.argv[1].lower()
    
    if command == "all":
        await regenerate_items_for_biome_three_star_rooms()
    else:
        # Treat all arguments as room IDs
        room_ids = sys.argv[1:]
        await regenerate_items_for_specific_rooms(room_ids)

if __name__ == "__main__":
    asyncio.run(main())
