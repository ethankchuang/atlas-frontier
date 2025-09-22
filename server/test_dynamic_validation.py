#!/usr/bin/env python3
"""
Test script for dynamic move validation system
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.move_validator import DynamicMoveValidator
from app.models import Player
import logging
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockGameManager:
    """Mock game manager for testing dynamic validation"""
    
    def __init__(self):
        self.db = MockDatabase()
        self.ai_handler = MockAIHandler()
    
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
    """Mock database for testing dynamic validation"""
    
    def __init__(self):
        self.validation_rules = {}
        self.game_state = {
            "world_seed": "test_world_123",
            "main_quest_summary": "A magical adventure in a fantasy realm"
        }
    
    async def get_item(self, item_id: str):
        """Get mock item data"""
        items = {
            "sword1": {
                "id": "sword1",
                "name": "Steel Sword",
                "item_type": "Sword",
                "special_effects": "No special effects",
                "rarity": 2
            },
            "shield1": {
                "id": "shield1", 
                "name": "Wooden Shield",
                "item_type": "Shield",
                "special_effects": "No special effects",
                "rarity": 1
            },
            "potion1": {
                "id": "potion1",
                "name": "Healing Potion",
                "item_type": "Potion", 
                "special_effects": "Restores 20 health points",
                "rarity": 3
            },
            "bow1": {
                "id": "bow1",
                "name": "Longbow",
                "item_type": "Bow",
                "special_effects": "No special effects", 
                "rarity": 2
            },
            "armor1": {
                "id": "armor1",
                "name": "Leather Armor",
                "item_type": "Armor",
                "special_effects": "No special effects",
                "rarity": 1
            }
        }
        return items.get(item_id)
    
    async def get_game_state(self):
        """Get mock game state"""
        return self.game_state
    
    async def get_world_validation_rules(self, world_seed: str):
        """Get mock validation rules"""
        if world_seed not in self.validation_rules:
            # Generate fantasy-themed rules for test world
            self.validation_rules[world_seed] = {
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
        return self.validation_rules[world_seed]
    
    async def set_world_validation_rules(self, world_seed: str, rules_data):
        """Set mock validation rules"""
        self.validation_rules[world_seed] = rules_data
        return True
    

class MockAIHandler:
    """Mock AI handler for testing"""
    
    async def generate_text(self, prompt: str):
        """Mock AI response generation"""
        if "Generate dynamic validation rules" in prompt:
            # Return fantasy-themed rules
            return json.dumps({
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
            })
        elif "Validate if this action is possible" in prompt:
            # Mock AI validation response
            return json.dumps({
                "valid": True,
                "reason": "AI determined this action is valid",
                "suggestion": None
            })
        else:
            return json.dumps({"valid": True, "reason": "Default AI response"})

async def test_dynamic_validation_basic():
    """Test basic dynamic validation functionality"""
    logger.info("=== Testing Dynamic Validation Basic Functionality ===")
    
    game_manager = MockGameManager()
    validator = DynamicMoveValidator(game_manager)
    
    # Test basic actions
    basic_actions = [
        "punch the enemy",
        "kick them in the stomach", 
        "tackle the opponent",
        "dodge to the side"
    ]
    
    for action in basic_actions:
        is_valid, reason, suggestion = await validator._validate_move_dynamic("player1", action)
        logger.info(f"Action: '{action}' -> Valid: {is_valid}, Reason: {reason}")
        assert is_valid, f"Basic action '{action}' should be valid"

async def test_dynamic_validation_equipment():
    """Test equipment-based dynamic validation"""
    logger.info("=== Testing Dynamic Validation Equipment ===")
    
    game_manager = MockGameManager()
    validator = DynamicMoveValidator(game_manager)
    
    # Test valid equipment usage
    valid_equipment_tests = [
        ("slash with my sword", "player1", True),
        ("block with my shield", "player1", True), 
        ("shoot my bow", "player2", True),
        ("heal with my potion", "player1", True)
    ]
    
    for action, player_id, expected_valid in valid_equipment_tests:
        is_valid, reason, suggestion = await validator._validate_move_dynamic(player_id, action)
        logger.info(f"Action: '{action}' (Player: {player_id}) -> Valid: {is_valid}, Reason: {reason}")
        if suggestion:
            logger.info(f"  Suggestion: {suggestion}")
        assert is_valid == expected_valid, f"Equipment action '{action}' should be {expected_valid}"
    
    # Test invalid equipment usage
    invalid_equipment_tests = [
        ("shoot with my sword", "player1", False),  # Sword can't shoot
        ("hack the system", "player1", False),  # No technology in fantasy world
        ("stab with my bow", "player2", False),  # Bow can't stab
        ("heal with my armor", "player2", False)  # Armor can't heal
    ]
    
    for action, player_id, expected_valid in invalid_equipment_tests:
        is_valid, reason, suggestion = await validator._validate_move_dynamic(player_id, action)
        logger.info(f"Action: '{action}' (Player: {player_id}) -> Valid: {is_valid}, Reason: {reason}")
        if suggestion:
            logger.info(f"  Suggestion: {suggestion}")
        assert is_valid == expected_valid, f"Invalid equipment action '{action}' should be {expected_valid}"

async def test_world_context_generation():
    """Test world context generation and theme inference"""
    logger.info("=== Testing World Context Generation ===")
    
    game_manager = MockGameManager()
    validator = DynamicMoveValidator(game_manager)
    
    # Test world context generation
    world_context = await validator._get_world_context()
    
    logger.info(f"World Context: {json.dumps(world_context, indent=2)}")
    
    # Verify world context structure
    assert 'world_seed' in world_context, "World context should have world_seed"
    assert 'world_rules' in world_context, "World context should have world_rules"
    assert 'world_theme' in world_context, "World context should have world_theme"
    
    # Verify fantasy theme inference
    assert world_context['world_theme'] == 'fantasy', "Should infer fantasy theme from quest"
    
    # Verify validation rules
    world_rules = world_context['world_rules']
    assert world_rules['validation_mode'] == 'adaptive', "Should have adaptive validation mode"
    assert world_rules['world_specific_rules']['magic_allowed'] == True, "Fantasy world should allow magic"
    assert world_rules['world_specific_rules']['technology_allowed'] == False, "Fantasy world should not allow technology"

async def test_ai_validation_fallback():
    """Test AI validation for ambiguous actions"""
    logger.info("=== Testing AI Validation Fallback ===")
    
    game_manager = MockGameManager()
    validator = DynamicMoveValidator(game_manager)
    
    # Test ambiguous actions that should trigger AI validation
    ambiguous_actions = [
        "whisper to the wind",
        "meditate on the ancient wisdom",
        "channel the energy of the forest"
    ]
    
    for action in ambiguous_actions:
        is_valid, reason, suggestion = await validator._validate_move_dynamic("player1", action)
        logger.info(f"Ambiguous Action: '{action}' -> Valid: {is_valid}, Reason: {reason}")
        # These should be handled by AI validation and allowed in a fantasy world
        assert is_valid, f"Ambiguous action '{action}' should be valid in fantasy world"

async def test_dynamic_rule_generation():
    """Test dynamic rule generation for different world types"""
    logger.info("=== Testing Dynamic Rule Generation ===")
    
    game_manager = MockGameManager()
    validator = DynamicMoveValidator(game_manager)
    
    # Test rule generation for fantasy world
    fantasy_rules = await validator._generate_world_validation_rules("fantasy_world")
    logger.info(f"Fantasy Rules: {json.dumps(fantasy_rules, indent=2)}")
    
    assert fantasy_rules['validation_mode'] == 'adaptive', "Should generate adaptive validation mode"
    assert fantasy_rules['world_specific_rules']['magic_allowed'] == True, "Fantasy world should allow magic"
    assert 'cast' in fantasy_rules['equipment_actions'], "Fantasy world should include magic actions"

async def test_validation_mode_adaptation():
    """Test how validation adapts to different modes"""
    logger.info("=== Testing Validation Mode Adaptation ===")
    
    game_manager = MockGameManager()
    validator = DynamicMoveValidator(game_manager)
    
    # Test permissive mode
    permissive_rules = {
        "validation_mode": "permissive",
        "basic_actions": ["punch", "kick"],
        "equipment_actions": ["slash", "stab"],
        "action_mappings": {},
        "world_specific_rules": {
            "magic_allowed": True,
            "technology_allowed": True,
            "firearms_allowed": True,
            "special_restrictions": []
        }
    }
    
    # Temporarily set permissive rules
    game_manager.db.validation_rules["test_world_123"] = permissive_rules
    
    # Test ambiguous action in permissive mode
    is_valid, reason, suggestion = await validator._validate_move_dynamic("player1", "use mysterious ancient power")
    logger.info(f"Permissive Mode Action: 'use mysterious ancient power' -> Valid: {is_valid}, Reason: {reason}")
    assert is_valid, "Permissive mode should allow ambiguous actions"

async def test_learning_and_adaptation():
    """Test learning and adaptation capabilities"""
    logger.info("=== Testing Learning and Adaptation ===")
    
    game_manager = MockGameManager()
    validator = DynamicMoveValidator(game_manager)
    
    # Simulate learning from player behavior
    learning_entry = {
        "action": "whisper to the wind",
        "player_inventory": ["staff1"],
        "was_valid": True,
        "world_context": "fantasy",
        "timestamp": "2024-01-01T00:00:00Z"
    }
    
    # This would normally be stored in the database
    logger.info(f"Learning Entry: {json.dumps(learning_entry, indent=2)}")
    
    # Test that the system can adapt to new patterns
    # In a real implementation, this would update the validation rules
    logger.info("System would learn from this interaction and adapt validation rules")

async def main():
    """Run all dynamic validation tests"""
    logger.info("Starting Dynamic Move Validation Tests")
    
    try:
        await test_dynamic_validation_basic()
        await test_dynamic_validation_equipment()
        await test_world_context_generation()
        await test_ai_validation_fallback()
        await test_dynamic_rule_generation()
        await test_validation_mode_adaptation()
        await test_learning_and_adaptation()
        
        logger.info("✅ All dynamic validation tests passed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 