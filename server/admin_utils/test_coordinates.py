#!/usr/bin/env python3
"""
Test script to verify the coordinate system is working correctly.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from app.game_manager import GameManager
from app.models import Player

async def test_coordinate_system():
    """Test that coordinate system prevents overlapping locations"""
    print("=" * 60)
    print("🧪 COORDINATE SYSTEM TEST")
    print("=" * 60)
    
    gm = GameManager()
    
    # Create a test player
    player = await gm.create_player("TestPlayer")
    print(f"✅ Created player: {player.name}")
    
    # Get initial room state
    room_info = await gm.get_room_info(player.current_room)
    initial_room = room_info["room"]
    start_coords = (initial_room['x'], initial_room['y'])
    print(f"🏠 Starting room: {initial_room['title']} at {start_coords}")
    
    # Test movements that should demonstrate coordinate consistency
    movements = [
        ("go north", "Should create new room at (0, 1)"),
        ("go south", "Should return to starting room at (0, 0)"),
        ("go east", "Should create new room at (1, 0)"),
        ("go west", "Should return to starting room at (0, 0)"),
        ("go north", "Should return to existing room at (0, 1)"),
        ("go south", "Should return to starting room at (0, 0)"),
    ]
    
    visited_coordinates = {start_coords}
    coordinate_log = []
    
    for i, (action, expectation) in enumerate(movements, 1):
        print(f"\n--- Step {i}: {action} ---")
        print(f"Expected: {expectation}")
        
        try:
            # Process the action
            response, updates = await gm.process_action(player.id, action)
            
            # Get current room info
            current_room_info = await gm.get_room_info(player.current_room)
            current_room = current_room_info["room"]
            coordinates = (current_room["x"], current_room["y"])
            
            # Check coordinate behavior
            if coordinates in visited_coordinates:
                status = "✅ REUSED EXISTING"
                print(f"🔄 Returned to existing room: {current_room['title']} at {coordinates}")
            else:
                status = "🆕 CREATED NEW"
                print(f"🆕 Created new room: {current_room['title']} at {coordinates}")
                visited_coordinates.add(coordinates)
            
            coordinate_log.append({
                "step": i,
                "action": action,
                "room_id": current_room["id"],
                "room_title": current_room["title"],
                "coordinates": coordinates,
                "status": status
            })
                
        except Exception as e:
            print(f"❌ ERROR: {str(e)}")
            coordinate_log.append({
                "step": i,
                "action": action,
                "error": str(e),
                "status": "❌ FAILED"
            })
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 COORDINATE SYSTEM TEST SUMMARY")
    print("=" * 60)
    
    print(f"Total unique coordinates visited: {len(visited_coordinates)}")
    print(f"Coordinates: {sorted(visited_coordinates)}")
    
    print("\n📋 Movement Log:")
    for entry in coordinate_log:
        if "error" not in entry:
            print(f"  {entry['step']}. {entry['action']} → {entry['coordinates']} {entry['status']}")
        else:
            print(f"  {entry['step']}. {entry['action']} → {entry['status']}")
    
    # Test world structure (with error handling)
    print("\n🗺️  World Structure:")
    try:
        world_structure = await gm.get_world_structure()
        
        if "error" in world_structure:
            print(f"⚠️  Warning: {world_structure['error']}")
        else:
            print(f"Total rooms in world: {world_structure.get('total_rooms', 'Unknown')}")
            
            # Check for duplicates
            duplicates = [coord for coord, room_id in world_structure.get("world_map", {}).items() 
                         if "AND" in str(room_id)]
            
            if duplicates:
                print(f"❌ FAILED: Found {len(duplicates)} duplicate coordinates!")
                for coord in duplicates:
                    print(f"  Duplicate at {coord}")
            else:
                print("✅ SUCCESS: No duplicate coordinates found!")
                
    except Exception as e:
        print(f"⚠️  Could not get world structure: {str(e)}")
    
    # Final assessment
    print("\n" + "=" * 60)
    reused_count = sum(1 for entry in coordinate_log if entry.get("status") == "✅ REUSED EXISTING")
    new_count = sum(1 for entry in coordinate_log if entry.get("status") == "🆕 CREATED NEW")
    
    print(f"🎯 FINAL RESULT:")
    print(f"   • Rooms reused: {reused_count}")
    print(f"   • New rooms created: {new_count}")
    print(f"   • Total unique coordinates: {len(visited_coordinates)}")
    
    if reused_count > 0:
        print("✅ COORDINATE SYSTEM IS WORKING - Players return to existing rooms!")
    else:
        print("❌ COORDINATE SYSTEM FAILED - No rooms were reused!")
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_coordinate_system()) 