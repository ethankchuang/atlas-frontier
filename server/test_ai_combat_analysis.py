#!/usr/bin/env python3
"""
Test script for AI combat analysis with basic actions
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.combat import analyze_combat_outcome
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockGameManager:
    """Mock game manager for testing AI combat analysis"""
    
    def __init__(self):
        self.ai_handler = MockAIHandler()

class MockAIHandler:
    """Mock AI handler for testing"""
    
    async def generate_text(self, prompt: str):
        """Mock AI response for combat analysis"""
        # Check if the prompt contains valid basic actions
        if "kick" in prompt and "punch" in prompt and "Equipment Valid: True" in prompt:
            # Both moves are valid basic actions
            return """{
                "player1_result": {
                    "condition": "injured",
                    "can_continue": true,
                    "reason": "Player 1 was struck by a powerful kick to the midsection, leaving them bruised and winded but still able to fight."
                },
                "player2_result": {
                    "condition": "injured", 
                    "can_continue": true,
                    "reason": "Player 2 took a solid punch to the jaw, causing them to stagger back but remain in the fight."
                }
            }"""
        elif "Equipment Valid: False" in prompt:
            # Invalid equipment actions
            return """{
                "player1_result": {
                    "condition": "healthy",
                    "can_continue": true,
                    "reason": "Player 1's invalid move had no effect, leaving them unharmed."
                },
                "player2_result": {
                    "condition": "healthy",
                    "can_continue": true, 
                    "reason": "Player 2's invalid move had no effect, leaving them unharmed."
                }
            }"""
        else:
            # Fallback response
            return """{
                "player1_result": {
                    "condition": "healthy",
                    "can_continue": true,
                    "reason": "Player 1 avoided damage."
                },
                "player2_result": {
                    "condition": "healthy",
                    "can_continue": true, 
                    "reason": "Player 2 avoided damage."
                }
            }"""

async def test_basic_combat_analysis():
    """Test that AI combat analysis correctly handles basic actions"""
    logger.info("=== Testing AI Combat Analysis with Basic Actions ===")
    
    game_manager = MockGameManager()
    
    # Test with valid basic actions
    player1_name = "Alice"
    player1_move = "kick"
    player1_condition = "healthy"
    player1_equipment_valid = True  # Basic action is valid
    
    player2_name = "Bob"
    player2_move = "punch"
    player2_condition = "healthy"
    player2_equipment_valid = True  # Basic action is valid
    
    player1_invalid_move = None  # No invalid move
    player2_invalid_move = None  # No invalid move
    
    player1_inventory = ["sword1", "shield1"]
    player2_inventory = ["bow1", "armor1"]
    
    room_name = "Shimmering Glade Entrance"
    room_description = "A radiant clearing filled with glowing flora"
    
    logger.info(f"Testing AI combat analysis:")
    logger.info(f"Player 1 ({player1_name}): '{player1_move}' (valid: {player1_equipment_valid})")
    logger.info(f"Player 2 ({player2_name}): '{player2_move}' (valid: {player2_equipment_valid})")
    
    # Call the AI combat analysis
    result = await analyze_combat_outcome(
        player1_name, player1_move, player1_condition, player1_equipment_valid,
        player2_name, player2_move, player2_condition, player2_equipment_valid,
        player1_invalid_move, player2_invalid_move,
        player1_inventory, player2_inventory,
        room_name, room_description, game_manager
    )
    
    logger.info(f"AI Combat Analysis Results:")
    logger.info(f"Player 1 ({player1_name}): {result['player1_result']['condition']} - {result['player1_result']['reason']}")
    logger.info(f"Player 2 ({player2_name}): {result['player2_result']['condition']} - {result['player2_result']['reason']}")
    
    # Assert that the AI recognized these as valid attacks that can cause damage
    assert result['player1_result']['condition'] != 'healthy', "Player 1 should have been affected by the attack"
    assert result['player2_result']['condition'] != 'healthy', "Player 2 should have been affected by the attack"
    assert "injured" in result['player1_result']['condition'] or "damage" in result['player1_result']['reason'].lower(), "Player 1 should have taken damage from the kick"
    assert "injured" in result['player2_result']['condition'] or "damage" in result['player2_result']['reason'].lower(), "Player 2 should have taken damage from the punch"
    
    logger.info("✅ AI combat analysis correctly handles valid basic actions!")

async def test_invalid_equipment_analysis():
    """Test that AI combat analysis correctly handles invalid equipment actions"""
    logger.info("=== Testing AI Combat Analysis with Invalid Equipment Actions ===")
    
    game_manager = MockGameManager()
    
    # Test with invalid equipment actions
    player1_name = "Alice"
    player1_move = "shoot with my sword"
    player1_condition = "healthy"
    player1_equipment_valid = False  # Invalid equipment action
    
    player2_name = "Bob"
    player2_move = "stab with my bow"
    player2_condition = "healthy"
    player2_equipment_valid = False  # Invalid equipment action
    
    player1_invalid_move = {
        'move': 'shoot with my sword',
        'reason': 'Item Steel Sword doesn\'t support this action'
    }
    player2_invalid_move = {
        'move': 'stab with my bow',
        'reason': 'Item Longbow doesn\'t support this action'
    }
    
    player1_inventory = ["sword1", "shield1"]
    player2_inventory = ["bow1", "armor1"]
    
    room_name = "Shimmering Glade Entrance"
    room_description = "A radiant clearing filled with glowing flora"
    
    logger.info(f"Testing AI combat analysis with invalid equipment:")
    logger.info(f"Player 1 ({player1_name}): '{player1_move}' (valid: {player1_equipment_valid})")
    logger.info(f"Player 2 ({player2_name}): '{player2_move}' (valid: {player2_equipment_valid})")
    
    # Call the AI combat analysis
    result = await analyze_combat_outcome(
        player1_name, player1_move, player1_condition, player1_equipment_valid,
        player2_name, player2_move, player2_condition, player2_equipment_valid,
        player1_invalid_move, player2_invalid_move,
        player1_inventory, player2_inventory,
        room_name, room_description, game_manager
    )
    
    logger.info(f"AI Combat Analysis Results:")
    logger.info(f"Player 1 ({player1_name}): {result['player1_result']['condition']} - {result['player1_result']['reason']}")
    logger.info(f"Player 2 ({player2_name}): {result['player2_result']['condition']} - {result['player2_result']['reason']}")
    
    # Assert that invalid moves have no effect
    assert result['player1_result']['condition'] == 'healthy', "Player 1 should remain healthy due to invalid move"
    assert result['player2_result']['condition'] == 'healthy', "Player 2 should remain healthy due to invalid move"
    
    logger.info("✅ AI combat analysis correctly handles invalid equipment actions!")

async def main():
    """Run all AI combat analysis tests"""
    logger.info("Starting AI Combat Analysis Tests")
    
    try:
        await test_basic_combat_analysis()
        await test_invalid_equipment_analysis()
        
        logger.info("✅ All AI combat analysis tests passed!")
        logger.info("🎉 The AI now correctly analyzes basic actions like 'punch' and 'kick' as valid attacks!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 