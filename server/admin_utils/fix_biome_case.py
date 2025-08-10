#!/usr/bin/env python3

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent / '..'))

from app.database import Database, redis_client

async def fix_biome_case():
    """Fix case sensitivity issues in existing biomes"""
    print("=== Fixing Biome Case Sensitivity ===")
    
    db = Database()
    
    # Get all chunk biomes and fix case
    try:
        print("\nFixing chunk biome case sensitivity...")
        
        # Get all chunk biome keys
        chunk_keys = redis_client.keys("chunk_biome:*")
        fixed_count = 0
        
        for key in chunk_keys:
            chunk_id = key.decode('utf-8').replace("chunk_biome:", "")
            biome_data = await db.get_chunk_biome(chunk_id)
            
            if biome_data and biome_data.get("name"):
                original_name = biome_data["name"]
                normalized_name = original_name.lower()
                
                if original_name != normalized_name:
                    print(f"Fixing {chunk_id}: '{original_name}' -> '{normalized_name}'")
                    biome_data["name"] = normalized_name
                    await db.set_chunk_biome(chunk_id, biome_data)
                    fixed_count += 1
        
        print(f"Fixed {fixed_count} chunk biomes")
        
    except Exception as e:
        print(f"Error fixing chunk biomes: {e}")
    
    # Fix saved biomes
    try:
        print("\nFixing saved biome case sensitivity...")
        
        saved_biomes = await db.get_all_saved_biomes()
        fixed_count = 0
        
        for biome in saved_biomes:
            if biome.get("name"):
                original_name = biome["name"]
                normalized_name = original_name.lower()
                
                if original_name != normalized_name:
                    print(f"Fixing saved biome: '{original_name}' -> '{normalized_name}'")
                    biome["name"] = normalized_name
                    await db.save_biome(biome)
                    fixed_count += 1
        
        print(f"Fixed {fixed_count} saved biomes")
        
    except Exception as e:
        print(f"Error fixing saved biomes: {e}")
    
    # Clear all biomes to start fresh
    try:
        print("\nClearing all existing biomes to start fresh...")
        
        # Clear chunk biomes
        chunk_keys = redis_client.keys("chunk_biome:*")
        for key in chunk_keys:
            redis_client.delete(key)
        
        # Clear saved biomes
        biome_keys = redis_client.keys("biome:*")
        for key in biome_keys:
            redis_client.delete(key)
        
        print(f"Cleared {len(chunk_keys)} chunk biomes and {len(biome_keys)} saved biomes")
        
    except Exception as e:
        print(f"Error clearing biomes: {e}")
    
    print("\nBiome case sensitivity fix completed!")

if __name__ == "__main__":
    asyncio.run(fix_biome_case()) 