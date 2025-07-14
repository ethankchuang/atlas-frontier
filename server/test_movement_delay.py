#!/usr/bin/env python3
"""
Test to debug movement delay issues
"""

import asyncio
import sys
import os
import time
import json

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.game_manager import GameManager
from app.models import Player, Room, ActionRequest
from app.main import process_action_stream

async def test_movement_delay():
    """Test movement delay by simulating the actual action"""
    print("🚶 Testing Movement Delay")
    print("=" * 50)
    
    # Initialize game manager
    game_manager = GameManager()
    
    # Create a test player
    test_player = Player(
        id="movement_test_player",
        name="MovementTestPlayer",
        current_room="room_movement_start",
        inventory=[],
        quest_progress={},
        memory_log=["Movement test started"]
    )
    
    # Create a test room at origin
    test_room = Room(
        id="room_movement_start",
        title="Movement Test Room",
        description="A test room for movement testing",
        x=0,
        y=0,
        image_url="",
        connections={},
        npcs=[],
        items=[],
        players=[test_player.id],
        visited=True,
        properties={}
    )
    
    print(f"📍 Test room: {test_room.title} at ({test_room.x}, {test_room.y})")
    
    # Save the test room to database
    await game_manager.db.set_room(test_room.id, test_room.dict())
    await game_manager.db.set_room_coordinates(test_room.id, test_room.x, test_room.y)
    await game_manager.db.mark_coordinate_discovered(test_room.x, test_room.y, test_room.id)
    
    # Save the player
    await game_manager.db.set_player(test_player.id, test_player.dict())
    
    print("💾 Test data saved to database")
    
    # Test different movement actions
    movement_actions = [
        "go north",
        "move north", 
        "north",
        "walk north",
        "travel north",
        "head north"
    ]
    
    for action in movement_actions:
        print(f"\n🔍 Testing action: '{action}'")
        
        # Create action request
        action_request = ActionRequest(
            player_id=test_player.id,
            action=action,
            room_id=test_room.id
        )
        
        # Check if this would be detected as movement
        is_movement = any(direction in action_request.action.lower() for direction in ['north', 'south', 'east', 'west', 'up', 'down', 'move'])
        print(f"  Detected as movement: {is_movement}")
        
        if is_movement:
            # Extract direction
            direction = None
            for dir_name in ['north', 'south', 'east', 'west', 'up', 'down']:
                if dir_name in action_request.action.lower():
                    direction = dir_name
                    break
            print(f"  Extracted direction: {direction}")
            
            # Test the actual movement processing
            start_time = time.time()
            try:
                actual_room_id, new_room = await game_manager.handle_room_movement_by_direction(
                    test_player, test_room, direction
                )
                movement_time = time.time() - start_time
                
                print(f"  ✅ Movement successful in {movement_time:.3f}s")
                print(f"    Destination: {actual_room_id}")
                print(f"    Room title: {new_room.title}")
                print(f"    Coordinates: ({new_room.x}, {new_room.y})")
                
                # Check if this was preloaded
                if new_room.title.startswith("Unexplored Area"):
                    print(f"    ⚠️  NOT preloaded - generated on demand")
                else:
                    print(f"    ✅ Preloaded room")
                    
            except Exception as e:
                movement_time = time.time() - start_time
                print(f"  ❌ Movement failed after {movement_time:.3f}s: {str(e)}")
    
    # Test the streaming endpoint simulation
    print(f"\n🌊 Testing streaming endpoint simulation...")
    
    # Create a mock connection manager
    class MockConnectionManager:
        def __init__(self):
            self.active_connections = {}
        
        def disconnect(self, room_id, player_id):
            pass
        
        async def broadcast_to_room(self, room_id, message):
            pass
    
    manager = MockConnectionManager()
    game_manager.set_connection_manager(manager)
    
    # Test with a simple movement action
    action_request = ActionRequest(
        player_id=test_player.id,
        action="go north",
        room_id=test_room.id
    )
    
    print(f"Testing streaming endpoint with action: '{action_request.action}'")
    
    start_time = time.time()
    try:
        # Simulate the streaming endpoint logic
        is_movement = any(direction in action_request.action.lower() for direction in ['north', 'south', 'east', 'west', 'up', 'down', 'move'])
        
        if is_movement:
            print("  Using fast movement path")
            
            # Extract direction
            direction = None
            for dir_name in ['north', 'south', 'east', 'west', 'up', 'down']:
                if dir_name in action_request.action.lower():
                    direction = dir_name
                    break
            
            if direction:
                # Process movement immediately
                actual_room_id, new_room = await game_manager.handle_room_movement_by_direction(
                    test_player, test_room, direction
                )
                
                # Create response
                response_content = f"You move {direction} from {test_room.title}."
                updates = {
                    "player": {
                        "current_room": actual_room_id,
                        "memory_log": [f"Moved {direction} from {test_room.title}"]
                    }
                }
                
                # Trigger preloading in background
                asyncio.create_task(game_manager.preload_adjacent_rooms(
                    new_room.x, new_room.y, new_room, test_player
                ))
                
                # Update player in database
                test_player.current_room = actual_room_id
                test_player.memory_log.append(f"Moved {direction} from {test_room.title}")
                await game_manager.db.set_player(test_player.id, test_player.dict())
                
                streaming_time = time.time() - start_time
                print(f"  ✅ Streaming endpoint completed in {streaming_time:.3f}s")
                print(f"    Response: {response_content}")
                print(f"    Updates: {updates}")
        else:
            print("  Would use AI processing path")
            
    except Exception as e:
        streaming_time = time.time() - start_time
        print(f"  ❌ Streaming endpoint failed after {streaming_time:.3f}s: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_movement_delay()) 