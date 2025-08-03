#!/usr/bin/env python3
"""
Test script for combat validation system
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import validate_equipment
from app.game_manager import GameManager
from app.models import Player
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockGameManager:
    """Mock game manager for testing combat validation"""
    
    def __init__(self):
        self.db = MockDatabase()
        self.connection_manager = MockConnectionManager()
    
    async def get_player(self, player_id: str):
        """Get a mock player"""
        if player_id == "player_2":
            return Player(
                id="player_2",
                name="2",
                current_room="room_start",
                inventory=["sword1", "shield1", "potion1"]
            )
        elif player_id == "player_1":
            return Player(
                id="player_1", 
                name="1",
                current_room="room_start",
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
    
    async def get_game_state(self):
        """Get mock game state"""
        return {
            "world_seed": "voidscape_world",
            "main_quest_summary": "A surreal adventure in the voidscape expanse"
        }
    
    async def get_world_validation_rules(self, world_seed: str):
        """Get mock validation rules"""
        return {
            "validation_mode": "adaptive",
            "basic_actions": ["punch", "kick", "tackle", "dodge", "block", "parry", "grapple", "wrestle", "headbutt", "elbow", "knee", "shoulder", "charge", "sidestep", "duck", "jump", "roll", "crawl", "climb", "run", "walk", "sneak", "hide"],
            "equipment_actions": ["slash", "stab", "cut", "thrust", "swing", "strike", "hack", "chop", "shoot", "fire", "aim", "draw", "release", "throw", "launch", "blast", "cast", "spell", "magic", "enchant", "summon", "teleport", "levitate", "heal", "restore", "boost", "enhance", "protect", "ward", "shield"],
            "action_mappings": {
                "slash": ["slash", "cut", "hack", "chop"],
                "stab": ["stab", "thrust", "pierce"],
                "shoot": ["shoot", "fire", "aim", "launch"],
                "cast": ["cast", "spell", "magic", "enchant"],
                "heal": ["heal", "restore", "cure"],
                "protect": ["protect", "defend", "guard", "shield"]
            },
            "world_specific_rules": {
                "magic_allowed": True,
                "technology_allowed": False,
                "firearms_allowed": False,
                "special_restrictions": []
            }
        }
    
    async def get_item_types(self):
        """Get mock item types"""
        return [
            {"name": "Sword", "capabilities": ["slash", "stab", "cut", "defend"]},
            {"name": "Shield", "capabilities": ["block", "deflect", "protect", "defend"]},
            {"name": "Bow", "capabilities": ["shoot", "aim", "hunt", "defend"]},
            {"name": "Staff", "capabilities": ["cast", "channel", "focus", "enhance"]},
            {"name": "Potion", "capabilities": ["heal", "restore", "boost"]},
            {"name": "Amulet", "capabilities": ["protect", "ward", "bless", "shield"]}
        ]

class MockConnectionManager:
    """Mock connection manager"""
    
    def __init__(self):
        self.active_connections = {
            "room_start": ["player_2", "player_1"]
        }

async def test_basic_combat_actions():
    """Test that basic combat actions are properly validated"""
    logger.info("=== Testing Basic Combat Actions in Combat System ===")
    
    game_manager = MockGameManager()
    
    # Test the exact scenario from the logs
    player1_name = "2"
    player1_move = "kick"
    player1_inventory = ["sword1", "shield1", "potion1"]
    
    player2_name = "1"
    player2_move = "punch"
    player2_inventory = ["bow1", "armor1"]
    
    logger.info(f"Testing combat validation:")
    logger.info(f"Player 1 ({player1_name}): '{player1_move}' with inventory: {player1_inventory}")
    logger.info(f"Player 2 ({player2_name}): '{player2_move}' with inventory: {player2_inventory}")
    
    # Call the validate_equipment function
    result = await validate_equipment(
        player1_name, player1_move, player1_inventory,
        player2_name, player2_move, player2_inventory,
        game_manager
    )
    
    logger.info(f"Validation Results:")
    logger.info(f"Player 1 ({player1_name}): {result['player1_valid']} - {result['player1_reason']}")
    logger.info(f"Player 2 ({player2_name}): {result['player2_valid']} - {result['player2_reason']}")
    
    # Assert that both basic actions should be valid
    assert result['player1_valid'], f"Player 1's '{player1_move}' should be valid"
    assert result['player2_valid'], f"Player 2's '{player2_move}' should be valid"
    
    logger.info("✅ Basic combat actions correctly validated!")

async def test_equipment_actions():
    """Test equipment-based actions"""
    logger.info("=== Testing Equipment-Based Actions ===")
    
    game_manager = MockGameManager()
    
    # Test equipment actions
    player1_name = "2"
    player1_move = "slash with my sword"
    player1_inventory = ["sword1", "shield1", "potion1"]
    
    player2_name = "1"
    player2_move = "shoot my bow"
    player2_inventory = ["bow1", "armor1"]
    
    logger.info(f"Testing equipment validation:")
    logger.info(f"Player 1 ({player1_name}): '{player1_move}' with inventory: {player1_inventory}")
    logger.info(f"Player 2 ({player2_name}): '{player2_move}' with inventory: {player2_inventory}")
    
    result = await validate_equipment(
        player1_name, player1_move, player1_inventory,
        player2_name, player2_move, player2_inventory,
        game_manager
    )
    
    logger.info(f"Validation Results:")
    logger.info(f"Player 1 ({player1_name}): {result['player1_valid']} - {result['player1_reason']}")
    logger.info(f"Player 2 ({player2_name}): {result['player2_valid']} - {result['player2_reason']}")
    
    # Assert that equipment actions should be valid when player has the equipment
    assert result['player1_valid'], f"Player 1's '{player1_move}' should be valid with sword"
    assert result['player2_valid'], f"Player 2's '{player2_move}' should be valid with bow"
    
    logger.info("✅ Equipment actions correctly validated!")

async def test_invalid_equipment_actions():
    """Test invalid equipment actions"""
    logger.info("=== Testing Invalid Equipment Actions ===")
    
    game_manager = MockGameManager()
    
    # Test invalid equipment actions
    player1_name = "2"
    player1_move = "shoot with my sword"
    player1_inventory = ["sword1", "shield1", "potion1"]
    
    player2_name = "1"
    player2_move = "stab with my bow"
    player2_inventory = ["bow1", "armor1"]
    
    logger.info(f"Testing invalid equipment validation:")
    logger.info(f"Player 1 ({player1_name}): '{player1_move}' with inventory: {player1_inventory}")
    logger.info(f"Player 2 ({player2_name}): '{player2_move}' with inventory: {player2_inventory}")
    
    result = await validate_equipment(
        player1_name, player1_move, player1_inventory,
        player2_name, player2_move, player2_inventory,
        game_manager
    )
    
    logger.info(f"Validation Results:")
    logger.info(f"Player 1 ({player1_name}): {result['player1_valid']} - {result['player1_reason']}")
    logger.info(f"Player 2 ({player2_name}): {result['player2_valid']} - {result['player2_reason']}")
    
    # Assert that invalid equipment actions should be invalid
    assert not result['player1_valid'], f"Player 1's '{player1_move}' should be invalid (sword can't shoot)"
    assert not result['player2_valid'], f"Player 2's '{player2_move}' should be invalid (bow can't stab)"
    
    logger.info("✅ Invalid equipment actions correctly rejected!")

async def main():
    """Run all combat validation tests"""
    logger.info("Starting Combat Validation Tests")
    
    try:
        await test_basic_combat_actions()
        await test_equipment_actions()
        await test_invalid_equipment_actions()
        
        logger.info("✅ All combat validation tests passed!")
        logger.info("🎉 The combat system now correctly validates basic actions like 'punch' and 'kick'!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 