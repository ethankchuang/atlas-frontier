#!/usr/bin/env python3
"""
Admin utility to view all biomes, their 3-star items, and coordinates.
Shows the preallocated 3-star room for each biome.
"""
import sys
import os
import asyncio
import json
from typing import Dict, List, Optional, Any

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.hybrid_database import HybridDatabase as Database

async def get_all_biomes_with_three_star_info() -> List[Dict[str, Any]]:
    """Get all biomes with their 3-star room information"""
    db = Database()
    
    # Get all saved biomes
    all_biomes = await db.get_all_saved_biomes()
    
    biome_info = []
    
    for biome in all_biomes:
        biome_name = biome.get('name', 'Unknown')
        
        # Get the 3-star room for this biome
        three_star_room_id = await db.get_biome_three_star_room(biome_name)
        
        # Parse coordinates from room ID if it exists
        coordinates = None
        if three_star_room_id:
            try:
                # Extract coordinates from room_id format: "room_x_y"
                if three_star_room_id.startswith('room_'):
                    coord_part = three_star_room_id[5:]  # Remove "room_" prefix
                    if '_' in coord_part:
                        x_str, y_str = coord_part.split('_', 1)
                        coordinates = (int(x_str), int(y_str))
            except (ValueError, IndexError):
                coordinates = None
        
        # Get the actual 3-star item if the room exists
        three_star_item = None
        if three_star_room_id:
            try:
                room_data = await db.get_room(three_star_room_id)
                if room_data and room_data.get('items'):
                    # Check if any item in the room is rarity 3
                    for item_id in room_data['items']:
                        item_data = await db.get_item(item_id)
                        if item_data and item_data.get('rarity') == 3:
                            three_star_item = {
                                'id': item_id,
                                'name': item_data.get('name', 'Unknown'),
                                'description': item_data.get('description', 'No description'),
                                'capabilities': item_data.get('capabilities', [])
                            }
                            break
            except Exception as e:
                print(f"Warning: Could not load room/item data for {three_star_room_id}: {e}")
        
        biome_info.append({
            'name': biome_name,
            'description': biome.get('description', 'No description'),
            'color': biome.get('color', '#808080'),
            'three_star_room_id': three_star_room_id,
            'coordinates': coordinates,
            'three_star_item': three_star_item,
            'has_three_star_room': three_star_room_id is not None,
            'has_three_star_item': three_star_item is not None
        })
    
    return biome_info

async def display_biome_three_star_summary():
    """Display a summary of all biomes and their 3-star items"""
    print("=" * 80)
    print("🌟 BIOME 3-STAR ITEM SUMMARY")
    print("=" * 80)
    
    biome_info = await get_all_biomes_with_three_star_info()
    
    if not biome_info:
        print("No biomes found in the database.")
        return
    
    # Sort biomes by name for consistent display
    biome_info.sort(key=lambda x: x['name'])
    
    # Summary statistics
    total_biomes = len(biome_info)
    biomes_with_rooms = sum(1 for b in biome_info if b['has_three_star_room'])
    biomes_with_items = sum(1 for b in biome_info if b['has_three_star_item'])
    
    print(f"📊 SUMMARY:")
    print(f"   Total biomes: {total_biomes}")
    print(f"   Biomes with 3-star rooms: {biomes_with_rooms}")
    print(f"   Biomes with 3-star items: {biomes_with_items}")
    print(f"   Coverage: {biomes_with_rooms/total_biomes*100:.1f}% have 3-star rooms")
    print()
    
    # Display each biome
    for biome in biome_info:
        print(f"🌍 {biome['name'].upper()}")
        print(f"   Description: {biome['description']}")
        print(f"   Color: {biome['color']}")
        
        if biome['has_three_star_room']:
            print(f"   ✅ 3-star room: {biome['three_star_room_id']}")
            if biome['coordinates']:
                x, y = biome['coordinates']
                print(f"   📍 Coordinates: ({x}, {y})")
            
            if biome['has_three_star_item']:
                item = biome['three_star_item']
                print(f"   ⭐ 3-star item: {item['name']}")
                print(f"      Description: {item['description']}")
                print(f"      Capabilities: {', '.join(item['capabilities'])}")
            else:
                print(f"   ⚠️  Room exists but no 3-star item found")
        else:
            print(f"   ❌ No 3-star room allocated")
        
        print()

async def display_detailed_biome_info():
    """Display detailed information about each biome"""
    print("=" * 80)
    print("📋 DETAILED BIOME INFORMATION")
    print("=" * 80)
    
    biome_info = await get_all_biomes_with_three_star_info()
    
    if not biome_info:
        print("No biomes found in the database.")
        return
    
    # Sort biomes by name
    biome_info.sort(key=lambda x: x['name'])
    
    for biome in biome_info:
        print(f"Biome: {biome['name']}")
        print(f"  Description: {biome['description']}")
        print(f"  Color: {biome['color']}")
        print(f"  3-star room ID: {biome['three_star_room_id'] or 'None'}")
        
        if biome['coordinates']:
            x, y = biome['coordinates']
            print(f"  Coordinates: ({x}, {y})")
        else:
            print(f"  Coordinates: None")
        
        if biome['three_star_item']:
            item = biome['three_star_item']
            print(f"  3-star item:")
            print(f"    ID: {item['id']}")
            print(f"    Name: {item['name']}")
            print(f"    Description: {item['description']}")
            print(f"    Capabilities: {item['capabilities']}")
        else:
            print(f"  3-star item: None")
        
        print("-" * 40)

async def export_biome_data_to_json():
    """Export biome data to JSON file"""
    print("=" * 80)
    print("💾 EXPORTING BIOME DATA TO JSON")
    print("=" * 80)
    
    biome_info = await get_all_biomes_with_three_star_info()
    
    if not biome_info:
        print("No biomes found to export.")
        return
    
    # Sort biomes by name
    biome_info.sort(key=lambda x: x['name'])
    
    # Create export data
    export_data = {
        'export_timestamp': asyncio.get_event_loop().time(),
        'total_biomes': len(biome_info),
        'biomes': biome_info
    }
    
    # Write to file
    filename = 'biome_three_star_items_export.json'
    with open(filename, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    print(f"✅ Exported {len(biome_info)} biomes to {filename}")
    print(f"📁 File location: {os.path.abspath(filename)}")

async def main():
    """Main function to run the admin utility"""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'summary':
            await display_biome_three_star_summary()
        elif command == 'detailed':
            await display_detailed_biome_info()
        elif command == 'export':
            await export_biome_data_to_json()
        elif command == 'all':
            await display_biome_three_star_summary()
            print("\n" + "=" * 80 + "\n")
            await display_detailed_biome_info()
            print("\n" + "=" * 80 + "\n")
            await export_biome_data_to_json()
        else:
            print(f"Unknown command: {command}")
            print("Available commands: summary, detailed, export, all")
    else:
        # Default: show summary
        await display_biome_three_star_summary()

if __name__ == "__main__":
    asyncio.run(main())
