#!/usr/bin/env python3
"""
Test script to verify that AI responses are now concise (1-2 sentences)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.ai_handler import AIHandler
from app.models import Player, Room, GameState, NPC
import json

def count_sentences(text):
    """Count the number of sentences in a text"""
    if not text:
        return 0
    # Simple sentence counting - split by common sentence endings
    sentences = [s.strip() for s in text.replace('!', '.').replace('?', '.').split('.') if s.strip()]
    return len(sentences)

async def test_room_description_concise():
    """Test that room descriptions are concise"""
    print("Testing room description conciseness...")
    print("=" * 50)
    
    # Create a simple context
    context = {
        "is_starting_room": True,
        "theme": "fantasy"
    }
    
    try:
        # Generate a room description
        title, description, image_prompt = await AIHandler.generate_room_description(context)
        
        print(f"Title: {title}")
        print(f"Description: {description}")
        print(f"Image Prompt: {image_prompt}")
        
        # Count sentences
        sentence_count = count_sentences(description)
        print(f"\nSentence count: {sentence_count}")
        
        if sentence_count <= 2:
            print("✅ PASS: Room description is concise (1-2 sentences)")
            return True
        else:
            print(f"❌ FAIL: Room description has {sentence_count} sentences (should be 1-2)")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

async def test_action_response_concise():
    """Test that action responses are concise"""
    print("\nTesting action response conciseness...")
    print("=" * 50)
    
    # Create test data
    player = Player(
        id="test_player",
        name="TestPlayer",
        current_room="room_test",
        inventory=[],
        quest_progress={},
        memory_log=[]
    )
    
    room = Room(
        id="room_test",
        title="Test Room",
        description="A simple test room",
        image_url="",
        connections={},
        npcs=[],
        items=[],
        players=[],
        x=0,
        y=0,
        discovered=True
    )
    
    game_state = GameState(
        world_seed="test",
        main_quest_summary="Test quest",
        global_state={}
    )
    
    npcs = []
    
    try:
        # Test a simple action
        action = "look around"
        
        # Collect the narrative response
        narrative = ""
        async for chunk in AIHandler.stream_action(action, player, room, game_state, npcs):
            if isinstance(chunk, str):
                narrative += chunk
            elif isinstance(chunk, dict) and "response" in chunk:
                narrative = chunk["response"]
                break
        
        print(f"Action: {action}")
        print(f"Response: {narrative}")
        
        # Count sentences
        sentence_count = count_sentences(narrative)
        print(f"\nSentence count: {sentence_count}")
        
        if sentence_count <= 2:
            print("✅ PASS: Action response is concise (1-2 sentences)")
            return True
        else:
            print(f"❌ FAIL: Action response has {sentence_count} sentences (should be 1-2)")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

async def test_npc_response_concise():
    """Test that NPC responses are concise"""
    print("\nTesting NPC response conciseness...")
    print("=" * 50)
    
    # Create test data
    npc = NPC(
        id="test_npc",
        name="TestNPC",
        location="room_test",
        dialogue_history=[],
        memory_log=[],
        personality="friendly"
    )
    
    player = Player(
        id="test_player",
        name="TestPlayer",
        current_room="room_test",
        inventory=[],
        quest_progress={},
        memory_log=[]
    )
    
    room = Room(
        id="room_test",
        title="Test Room",
        description="A simple test room",
        image_url="",
        connections={},
        npcs=[],
        items=[],
        players=[],
        x=0,
        y=0,
        discovered=True
    )
    
    relevant_memories = []
    
    try:
        # Test NPC interaction
        message = "Hello"
        
        response, memory = await AIHandler.process_npc_interaction(
            message, npc, player, room, relevant_memories
        )
        
        print(f"Player message: {message}")
        print(f"NPC response: {response}")
        print(f"Memory: {memory}")
        
        # Count sentences
        response_sentences = count_sentences(response)
        memory_sentences = count_sentences(memory)
        
        print(f"\nResponse sentence count: {response_sentences}")
        print(f"Memory sentence count: {memory_sentences}")
        
        if response_sentences <= 2 and memory_sentences <= 2:
            print("✅ PASS: NPC response and memory are concise (1-2 sentences)")
            return True
        else:
            print(f"❌ FAIL: Response has {response_sentences} sentences, memory has {memory_sentences} sentences (should be 1-2 each)")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return False

async def main():
    """Run all tests"""
    print("Testing AI Response Conciseness")
    print("=" * 60)
    
    test1_passed = await test_room_description_concise()
    test2_passed = await test_action_response_concise()
    test3_passed = await test_npc_response_concise()
    
    print("\n" + "=" * 60)
    if test1_passed and test2_passed and test3_passed:
        print("🎉 ALL TESTS PASSED: AI responses are now concise!")
        sys.exit(0)
    else:
        print("💥 SOME TESTS FAILED: AI responses need to be more concise.")
        sys.exit(1)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 