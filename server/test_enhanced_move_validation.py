#!/usr/bin/env python3
"""
Test script for enhanced move validation system
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.move_validator import MoveValidator
from app.game_manager import GameManager
from app.models import Player, Item
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockGameManager:
    """Mock game manager for testing"""
    
    def __init__(self):
        self.db = MockDatabase()
    
    async def get_player(self, player_id: str):
        """Get a mock player"""
        if player_id == "player1":
            return Player(
                id="player1",
                name="TestPlayer1",
                current_room="room1",
                inventory=["sword1", "shield1", "potion1"]
            )
        elif player_id == "player2":
            return Player(
                id="player2", 
                name="TestPlayer2",
                current_room="room1",
                inventory=["bow1", "armor1"]
            )
        return None

class MockDatabase:
    """Mock database for testing"""
    
    async def get_item(self, item_id: str):
        """Get mock item data"""
        items = {
            "sword1": {
                "id": "sword1",
                "name": "Steel Sword",
                "item_type": "Sword",
                "type_capabilities": ["slash", "stab", "cut", "defend"],
                "special_effects": "No special effects",
                "rarity": 2
            },
            "shield1": {
                "id": "shield1", 
                "name": "Wooden Shield",
                "item_type": "Shield",
                "type_capabilities": ["block", "deflect", "protect", "defend"],
                "special_effects": "No special effects",
                "rarity": 1
            },
            "potion1": {
                "id": "potion1",
                "name": "Healing Potion",
                "item_type": "Potion", 
                "type_capabilities": ["heal", "restore", "boost"],
                "special_effects": "Restores 20 health points",
                "rarity": 3
            },
            "bow1": {
                "id": "bow1",
                "name": "Longbow",
                "item_type": "Bow",
                "type_capabilities": ["shoot", "aim", "hunt", "defend"],
                "special_effects": "No special effects", 
                "rarity": 2
            },
            "armor1": {
                "id": "armor1",
                "name": "Leather Armor",
                "item_type": "Armor",
                "type_capabilities": ["protect", "defend", "guard"],
                "special_effects": "No special effects",
                "rarity": 1
            }
        }
        return items.get(item_id)

async def test_basic_combat_actions():
    """Test that basic combat actions are always valid"""
    logger.info("=== Testing Basic Combat Actions ===")
    
    game_manager = MockGameManager()
    
    basic_actions = [
        "punch the enemy",
        "kick them in the stomach", 
        "tackle the opponent",
        "dodge to the side",
        "block with my arms",
        "grapple with the foe"
    ]
    
    for action in basic_actions:
        is_valid, reason, suggestion = await MoveValidator.validate_move("player1", action, game_manager)
        logger.info(f"Action: '{action}' -> Valid: {is_valid}, Reason: {reason}")
        assert is_valid, f"Basic combat action '{action}' should be valid"

async def test_equipment_validation():
    """Test equipment-based validation"""
    logger.info("=== Testing Equipment Validation ===")
    
    game_manager = MockGameManager()
    
    # Test valid equipment usage
    valid_equipment_tests = [
        ("slash with my sword", "player1", True),
        ("block with my shield", "player1", True), 
        ("shoot my bow", "player2", True),
        ("heal with my potion", "player1", True),
        ("protect with my armor", "player2", True)
    ]
    
    for action, player_id, expected_valid in valid_equipment_tests:
        is_valid, reason, suggestion = await MoveValidator.validate_move(player_id, action, game_manager)
        logger.info(f"Action: '{action}' (Player: {player_id}) -> Valid: {is_valid}, Reason: {reason}")
        if suggestion:
            logger.info(f"  Suggestion: {suggestion}")
        assert is_valid == expected_valid, f"Equipment action '{action}' should be {expected_valid}"
    
    # Test invalid equipment usage
    invalid_equipment_tests = [
        ("shoot with my sword", "player1", False),  # Sword can't shoot
        ("cast fireball", "player1", False),  # No magic items
        ("hack the system", "player1", False),  # No technology items
        ("stab with my bow", "player2", False),  # Bow can't stab
        ("heal with my armor", "player2", False)  # Armor can't heal
    ]
    
    for action, player_id, expected_valid in invalid_equipment_tests:
        is_valid, reason, suggestion = await MoveValidator.validate_move(player_id, action, game_manager)
        logger.info(f"Action: '{action}' (Player: {player_id}) -> Valid: {is_valid}, Reason: {reason}")
        if suggestion:
            logger.info(f"  Suggestion: {suggestion}")
        assert is_valid == expected_valid, f"Invalid equipment action '{action}' should be {expected_valid}"

async def test_special_effects_validation():
    """Test validation with special effects"""
    logger.info("=== Testing Special Effects Validation ===")
    
    game_manager = MockGameManager()
    
    # Test that healing potion can be used for healing
    is_valid, reason, suggestion = await MoveValidator.validate_move("player1", "heal my wounds", game_manager)
    logger.info(f"Action: 'heal my wounds' -> Valid: {is_valid}, Reason: {reason}")
    assert is_valid, "Healing potion should allow healing actions"

async def test_missing_equipment():
    """Test validation when equipment is missing"""
    logger.info("=== Testing Missing Equipment ===")
    
    game_manager = MockGameManager()
    
    missing_equipment_tests = [
        ("shoot my gun", "player1", False),  # No gun in inventory
        ("cast lightning bolt", "player1", False),  # No magic items
        ("hack the computer", "player1", False),  # No cyberdeck
        ("stab with my dagger", "player2", False),  # No dagger in inventory
    ]
    
    for action, player_id, expected_valid in missing_equipment_tests:
        is_valid, reason, suggestion = await MoveValidator.validate_move(player_id, action, game_manager)
        logger.info(f"Action: '{action}' (Player: {player_id}) -> Valid: {is_valid}, Reason: {reason}")
        if suggestion:
            logger.info(f"  Suggestion: {suggestion}")
        assert is_valid == expected_valid, f"Missing equipment action '{action}' should be {expected_valid}"

async def test_capability_mappings():
    """Test that capability mappings work correctly"""
    logger.info("=== Testing Capability Mappings ===")
    
    game_manager = MockGameManager()
    
    # Test that sword can be used for various cutting actions
    cutting_actions = ["slash", "cut", "hack", "chop"]
    for action in cutting_actions:
        is_valid, reason, suggestion = await MoveValidator.validate_move("player1", f"{action} with my sword", game_manager)
        logger.info(f"Action: '{action} with my sword' -> Valid: {is_valid}, Reason: {reason}")
        assert is_valid, f"Sword should support {action} action"

async def main():
    """Run all tests"""
    logger.info("Starting Enhanced Move Validation Tests")
    
    try:
        await test_basic_combat_actions()
        await test_equipment_validation()
        await test_special_effects_validation()
        await test_missing_equipment()
        await test_capability_mappings()
        
        logger.info("✅ All tests passed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 