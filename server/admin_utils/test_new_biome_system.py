#!/usr/bin/env python3

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent / '..'))

from app.hybrid_database import HybridDatabase as Database
from app.database import redis_client
from app.game_manager import get_chunk_id, assign_biome_to_chunk

async def test_new_biome_system():
    """Test the new biome system"""
    print("=== Testing New Biome System ===")
    
    db = Database()
    
    # Test chunk generation
    print("\n1. Testing chunk generation:")
    test_coords = [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1)]
    
    for x, y in test_coords:
        chunk_id = get_chunk_id(x, y)
        print(f"   Coordinates ({x}, {y}) -> Chunk: {chunk_id}")
    
    # Test biome generation for new chunks
    print("\n2. Testing biome generation for new chunks:")
    
    # Clear any existing biomes first
    chunk_keys = redis_client.keys("chunk_biome:*")
    for key in chunk_keys:
        redis_client.delete(key)
    
    # Generate biomes for test chunks
    for x, y in test_coords:
        chunk_id = get_chunk_id(x, y)
        try:
            # Create a simple GameManager-like object for testing
            class TestGameManager:
                def __init__(self, db):
                    self.db = db
                    from app.ai_handler import AIHandler
                    self.ai_handler = AIHandler()
            
            test_gm = TestGameManager(db)
            biome_data = await assign_biome_to_chunk(test_gm, chunk_id)
            
            if biome_data:
                biome_name = biome_data["name"]
                print(f"   Chunk {chunk_id}: '{biome_name}' (lowercase: {biome_name == biome_name.lower()})")
            else:
                print(f"   Chunk {chunk_id}: No biome generated")
                
        except Exception as e:
            print(f"   Error generating biome for {chunk_id}: {e}")
    
    # Test biome consistency
    print("\n3. Testing biome consistency:")
    for x, y in test_coords:
        chunk_id = get_chunk_id(x, y)
        biome_data = await db.get_chunk_biome(chunk_id)
        if biome_data:
            biome_name = biome_data["name"]
            print(f"   Chunk {chunk_id}: '{biome_name}' (consistent: {biome_name == biome_name.lower()})")
    
    print("\nNew biome system test completed!")

if __name__ == "__main__":
    asyncio.run(test_new_biome_system()) 