#!/usr/bin/env python3
"""
Admin utility to fix the 3-star room assignments for existing biomes.
This addresses the case mismatch issue and ensures all biomes have proper 3-star room assignments.
"""
import sys
import os
import asyncio
from typing import Dict, List, Optional, Any

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.hybrid_database import HybridDatabase as Database

async def fix_three_star_rooms():
    """Fix 3-star room assignments for all existing biomes"""
    try:
        db = Database()
        
        # Get all biomes
        all_biomes = await db.get_all_saved_biomes()
        print(f"Found {len(all_biomes)} biomes to fix")
        
        fixed_count = 0
        
        for biome in all_biomes:
            biome_name = biome.get('name', 'Unknown')
            print(f"\n🌍 Processing biome: {biome_name}")
            
            # Check if this biome already has a 3-star room
            existing_three_star_room = await db.get_biome_three_star_room(biome_name)
            print(f"   Current 3-star room: {existing_three_star_room}")
            
            if existing_three_star_room:
                print(f"   ✅ Already has 3-star room: {existing_three_star_room}")
                continue
            
            # Determine the 3-star room based on biome name
            # This is a simple mapping based on the admin utility output
            three_star_room_mapping = {
                'CRIMSON THICKET': 'room_0_-3',
                'CRIMSON VALE': 'room_-3_0', 
                'SHIMMERING MARSH': 'room_start'  # Starting room uses room_start, not room_0_0
            }
            
            if biome_name in three_star_room_mapping:
                three_star_room_id = three_star_room_mapping[biome_name]
                print(f"   🔧 Setting 3-star room to: {three_star_room_id}")
                
                # Set the 3-star room
                success = await db.set_biome_three_star_room(biome_name, three_star_room_id)
                
                if success:
                    print(f"   ✅ Successfully set 3-star room for {biome_name}")
                    fixed_count += 1
                else:
                    print(f"   ❌ Failed to set 3-star room for {biome_name}")
            else:
                print(f"   ⚠️  No mapping found for biome: {biome_name}")
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total biomes processed: {len(all_biomes)}")
        print(f"   Successfully fixed: {fixed_count}")
        print(f"   Already had 3-star rooms: {len(all_biomes) - fixed_count}")
        
    except Exception as e:
        print(f"❌ Error fixing 3-star rooms: {str(e)}")
        import traceback
        traceback.print_exc()

async def main():
    """Main function"""
    await fix_three_star_rooms()

if __name__ == "__main__":
    asyncio.run(main())
