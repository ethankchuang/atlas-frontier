#!/usr/bin/env python3
"""
Test script for combat impact and move failure explanations
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import analyze_combat_outcome
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockGameManager:
    """Mock game manager for testing combat impact"""
    
    def __init__(self):
        self.ai_handler = MockAIHandler()

class MockAIHandler:
    """Mock AI handler for testing"""
    
    async def generate_text(self, prompt: str):
        """Mock AI response for combat analysis"""
        # Debug logging
        logger.info(f"Mock AI received prompt: {prompt[:200]}...")
        
        # Check for different scenarios
        if "Move: \"shoot\"" in prompt and "Equipment Valid: False" in prompt:
            logger.info("Mock AI: Detected shoot scenario")
            # Invalid equipment action
            return """{
                "player1_result": {
                    "condition": "healthy",
                    "can_continue": true,
                    "reason": "Player 1 tried to shoot but had no gun or bow, so the attack had no effect."
                },
                "player2_result": {
                    "condition": "injured",
                    "can_continue": true,
                    "reason": "Player 2 was struck by a valid attack and took damage."
                }
            }"""
        elif "Move: \"use magic\"" in prompt and "Equipment Valid: False" in prompt:
            logger.info("Mock AI: Detected magic scenario")
            # Invalid magic action
            return """{
                "player1_result": {
                    "condition": "healthy",
                    "can_continue": true,
                    "reason": "Player 1 tried to use magic but had no magical items, so the spell fizzled out."
                },
                "player2_result": {
                    "condition": "injured",
                    "can_continue": true,
                    "reason": "Player 2 was struck by a valid attack and took damage."
                }
            }"""
        elif "Move: \"punch\"" in prompt and "Move: \"kick\"" in prompt and "Equipment Valid: True" in prompt:
            logger.info("Mock AI: Detected punch/kick scenario")
            # Valid basic actions
            return """{
                "player1_result": {
                    "condition": "injured",
                    "can_continue": true,
                    "reason": "Player 1 was struck by a powerful kick to the midsection, leaving them bruised and winded."
                },
                "player2_result": {
                    "condition": "injured",
                    "can_continue": true,
                    "reason": "Player 2 took a solid punch to the jaw, causing them to stagger back."
                }
            }"""
        elif "block" in prompt and "punch" in prompt:
            # Defensive action
            return """{
                "player1_result": {
                    "condition": "healthy",
                    "can_continue": true,
                    "reason": "Player 1 successfully blocked the attack, avoiding damage."
                },
                "player2_result": {
                    "condition": "injured",
                    "can_continue": true,
                    "reason": "Player 2 was struck by a valid attack and took damage."
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

async def test_invalid_equipment_explanation():
    """Test that AI explains why invalid equipment moves fail"""
    logger.info("=== Testing Invalid Equipment Move Explanations ===")
    
    game_manager = MockGameManager()
    
    # Test invalid equipment actions
    player1_name = "Alice"
    player1_move = "shoot"
    player1_condition = "healthy"
    player1_equipment_valid = False  # Invalid - no gun/bow
    
    player2_name = "Bob"
    player2_move = "punch"
    player2_condition = "healthy"
    player2_equipment_valid = True  # Valid basic action
    
    player1_invalid_move = {
        'move': 'shoot',
        'reason': 'Missing required equipment: firearm'
    }
    player2_invalid_move = None
    
    player1_inventory = ["sword1"]
    player2_inventory = []
    
    room_name = "Blightfield Verge"
    room_description = "A barren, twisted landscape"
    
    logger.info(f"Testing invalid equipment explanation:")
    logger.info(f"Player 1 ({player1_name}): '{player1_move}' (valid: {player1_equipment_valid})")
    logger.info(f"Player 2 ({player2_name}): '{player2_move}' (valid: {player2_equipment_valid})")
    
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
    
    # Assert that invalid move is explained
    assert "no gun" in result['player1_result']['reason'].lower() or "no effect" in result['player1_result']['reason'].lower(), "Should explain why shoot failed"
    assert result['player1_result']['condition'] == 'healthy', "Invalid move should cause no damage"
    assert result['player2_result']['condition'] == 'injured', "Valid move should cause damage"
    
    logger.info("✅ Invalid equipment moves properly explained!")

async def test_invalid_magic_explanation():
    """Test that AI explains why invalid magic moves fail"""
    logger.info("=== Testing Invalid Magic Move Explanations ===")
    
    game_manager = MockGameManager()
    
    # Test invalid magic actions
    player1_name = "Alice"
    player1_move = "use magic"
    player1_condition = "healthy"
    player1_equipment_valid = False  # Invalid - no magic items
    
    player2_name = "Bob"
    player2_move = "punch"
    player2_condition = "healthy"
    player2_equipment_valid = True  # Valid basic action
    
    player1_invalid_move = {
        'move': 'use magic',
        'reason': 'Missing required equipment: magical items'
    }
    player2_invalid_move = None
    
    player1_inventory = ["sword1"]
    player2_inventory = []
    
    room_name = "Blightfield Verge"
    room_description = "A barren, twisted landscape"
    
    logger.info(f"Testing invalid magic explanation:")
    logger.info(f"Player 1 ({player1_name}): '{player1_move}' (valid: {player1_equipment_valid})")
    logger.info(f"Player 2 ({player2_name}): '{player2_move}' (valid: {player2_equipment_valid})")
    
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
    
    # Assert that invalid move is explained
    assert "magic" in result['player1_result']['reason'].lower() and ("fizzled" in result['player1_result']['reason'].lower() or "no effect" in result['player1_result']['reason'].lower()), "Should explain why magic failed"
    assert result['player1_result']['condition'] == 'healthy', "Invalid move should cause no damage"
    assert result['player2_result']['condition'] == 'injured', "Valid move should cause damage"
    
    logger.info("✅ Invalid magic moves properly explained!")

async def test_valid_moves_always_impact():
    """Test that valid moves always have impact unless countered"""
    logger.info("=== Testing Valid Moves Always Have Impact ===")
    
    game_manager = MockGameManager()
    
    # Test valid basic actions
    player1_name = "Alice"
    player1_move = "punch"
    player1_condition = "healthy"
    player1_equipment_valid = True  # Valid basic action
    
    player2_name = "Bob"
    player2_move = "kick"
    player2_condition = "healthy"
    player2_equipment_valid = True  # Valid basic action
    
    player1_invalid_move = None
    player2_invalid_move = None
    
    player1_inventory = []
    player2_inventory = []
    
    room_name = "Blightfield Verge"
    room_description = "A barren, twisted landscape"
    
    logger.info(f"Testing valid moves impact:")
    logger.info(f"Player 1 ({player1_name}): '{player1_move}' (valid: {player1_equipment_valid})")
    logger.info(f"Player 2 ({player2_name}): '{player2_move}' (valid: {player2_equipment_valid})")
    
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
    
    # Assert that valid moves cause damage
    assert result['player1_result']['condition'] == 'injured', "Valid attack should cause damage"
    assert result['player2_result']['condition'] == 'injured', "Valid attack should cause damage"
    assert "struck" in result['player1_result']['reason'].lower() or "damage" in result['player1_result']['reason'].lower() or "punch" in result['player1_result']['reason'].lower(), "Should describe the impact"
    assert "struck" in result['player2_result']['reason'].lower() or "damage" in result['player2_result']['reason'].lower() or "punch" in result['player2_result']['reason'].lower(), "Should describe the impact"
    
    logger.info("✅ Valid moves properly cause impact!")

async def test_defensive_actions():
    """Test that defensive actions can counter attacks"""
    logger.info("=== Testing Defensive Actions Counter Attacks ===")
    
    game_manager = MockGameManager()
    
    # Test defensive action
    player1_name = "Alice"
    player1_move = "block"
    player1_condition = "healthy"
    player1_equipment_valid = True  # Valid defensive action
    
    player2_name = "Bob"
    player2_move = "punch"
    player2_condition = "healthy"
    player2_equipment_valid = True  # Valid attack
    
    player1_invalid_move = None
    player2_invalid_move = None
    
    player1_inventory = []
    player2_inventory = []
    
    room_name = "Blightfield Verge"
    room_description = "A barren, twisted landscape"
    
    logger.info(f"Testing defensive actions:")
    logger.info(f"Player 1 ({player1_name}): '{player1_move}' (valid: {player1_equipment_valid})")
    logger.info(f"Player 2 ({player2_name}): '{player2_move}' (valid: {player2_equipment_valid})")
    
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
    
    # Assert that defensive action prevented damage
    assert result['player1_result']['condition'] == 'healthy', "Defensive action should prevent damage"
    assert "blocked" in result['player1_result']['reason'].lower(), "Should explain the successful block"
    
    logger.info("✅ Defensive actions properly counter attacks!")

async def main():
    """Run all combat impact tests"""
    logger.info("Starting Combat Impact Tests")
    
    try:
        await test_invalid_equipment_explanation()
        await test_invalid_magic_explanation()
        await test_valid_moves_always_impact()
        await test_defensive_actions()
        
        logger.info("✅ All combat impact tests passed!")
        logger.info("🎉 The AI now properly explains why moves fail and ensures valid moves have impact!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 