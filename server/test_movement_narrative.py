#!/usr/bin/env python3
"""
Test to verify that movement actions generate rich narrative responses
"""

import asyncio
import sys
import os
import time
import json

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.game_manager import GameManager
from app.models import Player, Room

async def test_movement_narrative():
    """Test that movement actions generate rich narrative responses"""
    print("🎭 Testing Movement Narrative Generation")
    print("=" * 50)
    
    # Initialize game manager
    game_manager = GameManager()
    
    # Create a test player
    test_player = Player(
        id="narrative_test_player",
        name="NarrativeTestPlayer",
        current_room="room_narrative_start",
        inventory=[],
        quest_progress={},
        memory_log=["Narrative test started"]
    )
    
    # Create a test room at origin
    test_room = Room(
        id="room_narrative_start",
        title="Ancient Library",
        description="A grand library filled with dusty tomes and ancient knowledge. Tall bookshelves line the walls, and a warm fire crackles in the hearth.",
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
    
    print(f"📍 Test room: {test_room.title}")
    print(f"   Description: {test_room.description[:100]}...")
    
    # Save the test room to database
    await game_manager.db.set_room(test_room.id, test_room.dict())
    await game_manager.db.set_room_coordinates(test_room.id, test_room.x, test_room.y)
    await game_manager.db.mark_coordinate_discovered(test_room.x, test_room.y, test_room.id)
    
    # Save the player
    await game_manager.db.set_player(test_player.id, test_player.dict())
    
    print("💾 Test data saved to database")
    
    # Test movement actions that should now generate rich narratives
    movement_actions = [
        "go north",
        "venture into the northern passage",
        "explore the dark corridor to the east",
        "climb the winding staircase upward"
    ]
    
    for action in movement_actions:
        print(f"\n🔍 Testing action: '{action}'")
        print("-" * 40)
        
        start_time = time.time()
        
        try:
            # Process the action through AI
            response_text = ""
            updates = {}
            
            # Get game state
            game_state_data = await game_manager.db.get_game_state()
            from app.models import GameState
            game_state = GameState(**game_state_data)
            
            async for chunk in game_manager.ai.stream_action(
                action=action,
                player=test_player,
                room=test_room,
                game_state=game_state,
                npcs=[]
            ):
                if isinstance(chunk, dict):
                    # This is the final message with updates
                    response_text = chunk.get("response", "")
                    updates = chunk.get("updates", {})
                    break
                else:
                    # This is a text chunk - collect it
                    response_text += chunk
            
            processing_time = time.time() - start_time
            
            print(f"⏱️  Processing time: {processing_time:.2f}s")
            print(f"📝 Response length: {len(response_text)} characters")
            print(f"🎯 Response preview: {response_text[:200]}...")
            
            # Check if it's a rich narrative (not just "You move north")
            if len(response_text) > 50 and not response_text.startswith("You move"):
                print("✅ Rich narrative generated!")
                print(f"   Direction detected: {updates.get('player', {}).get('direction', 'None')}")
            else:
                print("❌ Simple response generated")
                print(f"   Response: {response_text}")
            
            # Check for movement direction
            if "direction" in updates.get("player", {}):
                direction = updates["player"]["direction"]
                print(f"🎯 Movement direction: {direction}")
                
                # Test the actual movement
                actual_room_id, new_room = await game_manager.handle_room_movement_by_direction(
                    test_player, test_room, direction
                )
                print(f"📍 Moved to: {new_room.title} at ({new_room.x}, {new_room.y})")
                
        except Exception as e:
            processing_time = time.time() - start_time
            print(f"❌ Error after {processing_time:.2f}s: {str(e)}")
    
    print(f"\n🎉 Movement narrative test completed!")

if __name__ == "__main__":
    asyncio.run(test_movement_narrative()) 