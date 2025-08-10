#!/usr/bin/env python3
"""
Test script for the move validation system
"""

import asyncio
import sys
import os

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.move_validator import MoveValidator

class MockGameManager:
    """Mock game manager for testing"""
    
    class MockDB:
        async def get_player(self, player_id):
            # Mock player data
            if player_id == "player_with_sword":
                return {
                    'id': 'player_with_sword',
                    'name': 'Warrior',
                    'inventory': ['sword_1', 'shield_1']
                }
            elif player_id == "player_with_bow":
                return {
                    'id': 'player_with_bow',
                    'name': 'Archer',
                    'inventory': ['bow_1', 'arrows_1']
                }
            elif player_id == "player_with_magic":
                return {
                    'id': 'player_with_magic',
                    'name': 'Mage',
                    'inventory': ['wand_1', 'crystal_1']
                }
            elif player_id == "player_empty":
                return {
                    'id': 'player_empty',
                    'name': 'Peasant',
                    'inventory': []
                }
            else:
                return None
        
        async def get_item(self, item_id):
            # Mock item data
            items = {
                'sword_1': {
                    'id': 'sword_1',
                    'name': 'Steel Sword',
                    'description': 'A sharp steel sword',
                    'properties': {}
                },
                'shield_1': {
                    'id': 'shield_1',
                    'name': 'Wooden Shield',
                    'description': 'A sturdy wooden shield',
                    'properties': {}
                },
                'bow_1': {
                    'id': 'bow_1',
                    'name': 'Longbow',
                    'description': 'A powerful longbow',
                    'properties': {}
                },
                'arrows_1': {
                    'id': 'arrows_1',
                    'name': 'Iron Arrows',
                    'description': 'Sharp iron arrows',
                    'properties': {}
                },
                'wand_1': {
                    'id': 'wand_1',
                    'name': 'Magic Wand',
                    'description': 'A magical wand',
                    'properties': {
                        'combat_ability': 'cast,fire,enchant'
                    }
                },
                'crystal_1': {
                    'id': 'crystal_1',
                    'name': 'Mana Crystal',
                    'description': 'A crystal filled with magical energy',
                    'properties': {
                        'combat_ability': 'cast,summon'
                    }
                }
            }
            return items.get(item_id)
    
    def __init__(self):
        self.db = self.MockDB()

async def test_move_validation():
    """Test the move validation system"""
    game_manager = MockGameManager()
    
    test_cases = [
        # Player with sword
        ("player_with_sword", "swing my sword", "Should be valid"),
        ("player_with_sword", "slash with my blade", "Should be valid"),
        ("player_with_sword", "shoot an arrow", "Should be invalid - no bow"),
        ("player_with_sword", "cast fireball", "Should be invalid - no magic items"),
        
        # Player with bow
        ("player_with_bow", "shoot my bow", "Should be valid"),
        ("player_with_bow", "fire an arrow", "Should be valid"),
        ("player_with_bow", "swing my sword", "Should be invalid - no sword"),
        ("player_with_bow", "cast lightning", "Should be invalid - no magic items"),
        
        # Player with magic
        ("player_with_magic", "cast fireball", "Should be valid"),
        ("player_with_magic", "summon a demon", "Should be valid"),
        ("player_with_magic", "swing my sword", "Should be invalid - no sword"),
        ("player_with_magic", "shoot an arrow", "Should be invalid - no bow"),
        
        # Player with no equipment
        ("player_empty", "punch them", "Should be valid"),
        ("player_empty", "kick the opponent", "Should be valid"),
        ("player_empty", "dodge the attack", "Should be valid"),
        ("player_empty", "swing my sword", "Should be invalid - no sword"),
        ("player_empty", "cast magic", "Should be invalid - no magic items"),
        
        # Generic moves
        ("player_empty", "attack", "Should be valid"),
        ("player_empty", "defend", "Should be valid"),
        ("player_empty", "surrender", "Should be valid"),
        ("player_empty", "retreat", "Should be valid"),
    ]
    
    print("🧪 Testing Move Validation System")
    print("=" * 50)
    
    for player_id, move, description in test_cases:
        is_valid, reason, suggestion = await MoveValidator.validate_move(player_id, move, game_manager)
        
        status = "✅ VALID" if is_valid else "❌ INVALID"
        print(f"{status} | {description}")
        print(f"   Player: {player_id}")
        print(f"   Move: '{move}'")
        print(f"   Result: {reason}")
        if suggestion:
            print(f"   Suggestion: {suggestion}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(test_move_validation()) 