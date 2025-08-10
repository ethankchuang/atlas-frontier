#!/usr/bin/env python3

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.append(str(Path(__file__).parent / '..'))

from app.database import Database
from app.game_manager import get_chunk_id

async def update_room_biomes():
    """Update all existing rooms to use the new biome system"""
    print("=== Updating Room Biomes ===")
    
    db = Database()
    
    # Get all discovered coordinates
    try:
        discovered_coords = await db.get_discovered_coordinates()
        print(f"Found {len(discovered_coords)} discovered coordinates")
        
        updated_count = 0
        
        for coord_str, room_id in discovered_coords.items():
            try:
                # Parse coordinates
                x, y = map(int, coord_str.split(':'))
                
                # Get room data
                room_data = await db.get_room(room_id)
                if not room_data:
                    print(f"Room {room_id} not found, skipping")
                    continue
                
                # Get chunk ID and biome
                chunk_id = get_chunk_id(x, y)
                biome_data = await db.get_chunk_biome(chunk_id)
                
                if biome_data:
                    new_biome = biome_data["name"].lower()
                    old_biome = room_data.get("biome", "unknown")
                    
                    if old_biome != new_biome:
                        print(f"Updating {room_id} ({x},{y}): '{old_biome}' -> '{new_biome}'")
                        room_data["biome"] = new_biome
                        await db.set_room(room_id, room_data)
                        updated_count += 1
                    else:
                        print(f"Room {room_id} already has correct biome: '{new_biome}'")
                else:
                    print(f"No biome assigned to chunk {chunk_id} for room {room_id}")
                    
            except Exception as e:
                print(f"Error updating room {room_id}: {e}")
                continue
        
        print(f"\nUpdated {updated_count} rooms with new biomes")
        
    except Exception as e:
        print(f"Error updating room biomes: {e}")

if __name__ == "__main__":
    asyncio.run(update_room_biomes()) 