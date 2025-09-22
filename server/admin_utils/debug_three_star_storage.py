#!/usr/bin/env python3
"""
Admin utility to debug the 3-star room storage and retrieval.
"""
import sys
import os
import asyncio
from typing import Dict, List, Optional, Any

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.hybrid_database import HybridDatabase as Database
from app.supabase_database import SupabaseDatabase

async def debug_three_star_storage():
    """Debug the 3-star room storage and retrieval"""
    try:
        db = Database()
        
        # Test different biome name variations
        test_biomes = [
            'bloodthorn thicket',
            'BLOODTHORN THICKET', 
            'Bloodthorn Thicket',
            'BLOODSHADE MARSH',
            'bloodshade marsh',
            'CRIMSON MIRE',
            'crimson mire'
        ]
        
        print("🔍 Testing 3-star room retrieval for different biome name variations:")
        print()
        
        for biome in test_biomes:
            # Test HybridDatabase
            result = await db.get_biome_three_star_room(biome)
            print(f"HybridDatabase.get_biome_three_star_room('{biome}') = {result}")
            
            # Test SupabaseDatabase directly
            try:
                result2 = await SupabaseDatabase.get_biome_three_star_room(biome)
                print(f"SupabaseDatabase.get_biome_three_star_room('{biome}') = {result2}")
            except Exception as e:
                print(f"SupabaseDatabase.get_biome_three_star_room('{biome}') = ERROR: {str(e)}")
            print()
        
        # Test setting and getting
        print("🔧 Testing set and get operations:")
        test_biome = 'TEST_BIOME'
        test_room = 'room_test_0'
        
        print(f"Setting 3-star room for '{test_biome}' to '{test_room}'")
        success = await db.set_biome_three_star_room(test_biome, test_room)
        print(f"Set result: {success}")
        
        result = await db.get_biome_three_star_room(test_biome)
        print(f"Get result: {result}")
        
        # Clean up
        print(f"Cleaning up test data...")
        # Note: We don't have a delete method, so this will remain in the database
        
    except Exception as e:
        print(f"❌ Error debugging 3-star storage: {str(e)}")
        import traceback
        traceback.print_exc()

async def main():
    """Main function"""
    await debug_three_star_storage()

if __name__ == "__main__":
    asyncio.run(main())
