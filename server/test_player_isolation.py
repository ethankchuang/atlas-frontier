#!/usr/bin/env python3
"""
Test script to verify player action isolation
"""
import asyncio
import sys
import os
import time
import json

# Add the server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.game_manager import GameManager
from app.models import Player, Room, GameState

async def test_player_isolation():
    """Test that player actions only affect the player who performed them"""
    print("👥 Testing Player Action Isolation")
    print("=" * 50)
    
    # Initialize game manager
    game_manager = GameManager()
    
    # Create test players
    test_player1 = Player(
        id="isolation_test_player1",
        name="IsolationTestPlayer1",
        current_room="room_start",
        inventory=[],
        quest_progress={},
        memory_log=[],
        last_action="2025-07-14T20:00:00.000000",
        last_action_text=""
    )
    
    test_player2 = Player(
        id="isolation_test_player2", 
        name="IsolationTestPlayer2",
        current_room="room_start",
        inventory=[],
        quest_progress={},
        memory_log=[],
        last_action="2025-07-14T20:00:00.000000",
        last_action_text=""
    )
    
    # Save players to database
    await game_manager.db.set_player(test_player1.id, test_player1.dict())
    await game_manager.db.set_player(test_player2.id, test_player2.dict())
    
    # Get the starting room
    room_data = await game_manager.db.get_room("room_start")
    if not room_data:
        print("❌ Starting room not found")
        return
    
    room = Room(**room_data)
    print(f"📍 Starting room: {room.id} at coordinates ({room.x}, {room.y})")
    
    # Add both players to the room
    await game_manager.db.add_to_room_players(room.id, test_player1.id)
    await game_manager.db.add_to_room_players(room.id, test_player2.id)
    
    print(f"👥 Added players to room: {test_player1.name}, {test_player2.name}")
    
    # Test 1: Player 1 moves north
    print("\n🧪 Test 1: Player 1 moves north")
    print("-" * 30)
    
    # Process action for player 1
    response1, updates1 = await game_manager.process_action(
        player_id=test_player1.id,
        action="move north"
    )
    
    print(f"Player 1 action response: {response1[:100]}...")
    print(f"Player 1 updates: {updates1}")
    
    # Check player 1's new position
    player1_data = await game_manager.db.get_player(test_player1.id)
    player1 = Player(**player1_data)
    print(f"Player 1 new room: {player1.current_room}")
    
    # Check player 2's position (should be unchanged)
    player2_data = await game_manager.db.get_player(test_player2.id)
    player2 = Player(**player2_data)
    print(f"Player 2 room (should be unchanged): {player2.current_room}")
    
    # Verify isolation
    if player1.current_room != player2.current_room:
        print("✅ Player isolation working: Player 1 moved, Player 2 stayed")
    else:
        print("❌ Player isolation failed: Both players moved")
    
    # Test 2: Player 2 moves east from starting room
    print("\n🧪 Test 2: Player 2 moves east")
    print("-" * 30)
    
    # Process action for player 2
    response2, updates2 = await game_manager.process_action(
        player_id=test_player2.id,
        action="move east"
    )
    
    print(f"Player 2 action response: {response2[:100]}...")
    print(f"Player 2 updates: {updates2}")
    
    # Check player 2's new position
    player2_data = await game_manager.db.get_player(test_player2.id)
    player2 = Player(**player2_data)
    print(f"Player 2 new room: {player2.current_room}")
    
    # Check player 1's position (should be unchanged)
    player1_data = await game_manager.db.get_player(test_player1.id)
    player1 = Player(**player1_data)
    print(f"Player 1 room (should be unchanged): {player1.current_room}")
    
    # Verify isolation
    if player1.current_room != player2.current_room:
        print("✅ Player isolation working: Player 2 moved, Player 1 stayed")
    else:
        print("❌ Player isolation failed: Both players moved")
    
    # Test 3: Check that both players are in different rooms
    print("\n🧪 Test 3: Final positions")
    print("-" * 30)
    
    print(f"Player 1 final room: {player1.current_room}")
    print(f"Player 2 final room: {player2.current_room}")
    
    if player1.current_room != player2.current_room:
        print("✅ SUCCESS: Players are in different rooms - isolation working!")
    else:
        print("❌ FAILURE: Players are in the same room - isolation broken!")
    
    # Cleanup - remove players from rooms
    await game_manager.db.remove_from_room_players(player1.current_room, test_player1.id)
    await game_manager.db.remove_from_room_players(player2.current_room, test_player2.id)
    print("\n🧹 Cleanup completed")

if __name__ == "__main__":
    asyncio.run(test_player_isolation()) 