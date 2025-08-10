#!/usr/bin/env python3

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent / 'app'))

from app.ai_handler import AIHandler

async def test_biome_generation():
    """Test the biome generation system"""
    print("Testing biome generation system...")
    
    # Test 1: Biome generation at origin with no adjacent biomes
    print("\n1. Testing origin room (0,0) with no adjacent biomes:")
    biome1 = await AIHandler.generate_biome(
        x=0, 
        y=0, 
        adjacent_biomes=[],
        world_seed="test_world_123"
    )
    print(f"Generated biome: {biome1}")
    
    # Test 2: Adjacent room with one biome nearby
    print("\n2. Testing adjacent room (1,0) with one nearby biome:")
    biome2 = await AIHandler.generate_biome(
        x=1, 
        y=0, 
        adjacent_biomes=[biome1],
        world_seed="test_world_123"
    )
    print(f"Generated biome: {biome2}")
    
    # Test 3: Room with multiple adjacent biomes
    print("\n3. Testing room (2,0) with multiple nearby biomes:")
    biome3 = await AIHandler.generate_biome(
        x=2, 
        y=0, 
        adjacent_biomes=[biome1, biome2],
        world_seed="test_world_123"
    )
    print(f"Generated biome: {biome3}")
    
    # Test 4: Room generation with biome context
    print("\n4. Testing room description generation with biome:")
    try:
        title, description, image_prompt = await AIHandler.generate_room_description(
            context={
                "biome": biome1,
                "is_starting_room": True
            }
        )
        print(f"Room title: {title}")
        print(f"Room description: {description}")
        print(f"Image prompt: {image_prompt}")
    except Exception as e:
        print(f"Room description generation failed: {e}")
    
    print("\nBiome generation test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_biome_generation())