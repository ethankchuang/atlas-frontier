#!/usr/bin/env python3

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent / '..'))

from app.hybrid_database import HybridDatabase as Database
from app.database import redis_client
from app.ai_handler import AIHandler
from app.biome_manager import BiomeManager

async def test_biome_manager():
    """Test the new BiomeManager system"""
    print("=== Testing BiomeManager ===")
    
    db = Database()
    ai_handler = AIHandler()
    biome_manager = BiomeManager(db, ai_handler)
    
    # Clear existing data
    print("\n1. Clearing existing biome data...")
    chunk_keys = redis_client.keys("chunk_biome:*")
    biome_keys = redis_client.keys("biome:*")
    for key in chunk_keys + biome_keys:
        redis_client.delete(key)
    print(f"Cleared {len(chunk_keys)} chunk biomes and {len(biome_keys)} saved biomes")
    
    # Test biome generation for different coordinates
    print("\n2. Testing biome generation for different coordinates:")
    
    test_coords = [
        (0, 0),    # Origin
        (10, 0),   # East
        (0, 10),   # North
        (-10, 0),  # West
        (0, -10),  # South
        (20, 0),   # Further east
        (0, 20),   # Further north
    ]
    
    for x, y in test_coords:
        print(f"\n   Testing coordinates ({x}, {y}):")
        try:
            biome_data = await biome_manager.get_biome_for_coordinates(x, y)
            if biome_data:
                print(f"   Generated biome: '{biome_data['name']}'")
                print(f"   Description: {biome_data['description']}")
                
                # Test room generation with this biome
                title, description, image_prompt = await AIHandler.generate_room_description(
                    context={
                        "biome": biome_data["name"],
                        "biome_description": biome_data["description"],
                        "direction": "north",
                        "discovering_new_area": True
                    }
                )
                print(f"   Room title: {title}")
                print(f"   Room description: {description}")
            else:
                print(f"   No biome generated")
                
        except Exception as e:
            print(f"   Error: {e}")
    
    # Test biome usage
    print("\n3. Testing biome usage:")
    saved_biomes = await db.get_all_saved_biomes()
    for biome in saved_biomes:
        cluster_info = await biome_manager.get_biome_cluster_info(biome["name"])
        print(f"   Biome '{biome['name']}': {cluster_info['chunk_count']} chunks, reused: {cluster_info['is_reused']}")
    
    print("\nBiomeManager test completed!")

if __name__ == "__main__":
    asyncio.run(test_biome_manager()) 