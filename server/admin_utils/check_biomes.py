#!/usr/bin/env python3
"""
Check biomes stored in the database
"""

import asyncio
import sys
import os

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.hybrid_database import HybridDatabase as Database

async def check_biomes():
    """Check biomes stored in the database"""
    print("=== Biome Database Check ===")
    
    # Get all saved biomes
    saved_biomes = await Database.get_all_saved_biomes()
    print(f"\nTotal saved biomes: {len(saved_biomes)}")
    
    if saved_biomes:
        print("\nSaved biomes:")
        for i, biome in enumerate(saved_biomes, 1):
            print(f"{i}. Name: '{biome.get('name', 'Unknown')}'")
            print(f"   Description: {biome.get('description', 'No description')}")
            print(f"   Color: {biome.get('color', 'No color')}")
            print()
    
    # Check chunk biome assignments
    print("=== Chunk Biome Check ===")
    test_chunks = ["chunk_0_0", "chunk_-1_0", "chunk_1_0", "chunk_0_-1", "chunk_0_1"]
    
    for chunk_id in test_chunks:
        biome_data = await Database.get_chunk_biome(chunk_id)
        if biome_data:
            biome_name = biome_data.get('name', 'Unknown')
            biome_color = biome_data.get('color', 'No color')
            print(f"Chunk {chunk_id}: '{biome_name}' (Color: {biome_color})")
        else:
            print(f"Chunk {chunk_id}: No biome assigned")

if __name__ == "__main__":
    asyncio.run(check_biomes()) 