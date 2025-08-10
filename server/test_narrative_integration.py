#!/usr/bin/env python3
"""
Test script to demonstrate narrative integration of invalid moves
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
                }
            }
            return items.get(item_id)
    
    def __init__(self):
        self.db = self.MockDB()

async def test_narrative_integration():
    """Test how invalid moves are incorporated into narrative"""
    game_manager = MockGameManager()
    
    print("🎭 Testing Narrative Integration of Invalid Moves")
    print("=" * 60)
    
    # Test scenarios that would create humorous narratives
    test_scenarios = [
        ("player_empty", "swing my mighty sword", "Peasant tries to swing a sword they don't have"),
        ("player_empty", "cast fireball", "Peasant tries to cast magic without any magical items"),
        ("player_empty", "fly off the cliff", "Peasant tries to fly without wings"),
        ("player_empty", "shoot my bow", "Peasant tries to shoot a bow they don't have"),
        ("player_with_sword", "cast lightning bolt", "Warrior tries to cast magic despite having only melee weapons"),
        ("player_with_sword", "fly into the sky", "Warrior tries to fly despite being grounded"),
    ]
    
    for player_id, move, description in test_scenarios:
        print(f"\n📝 Scenario: {description}")
        print(f"   Player: {player_id}")
        print(f"   Attempted Move: '{move}'")
        
        # Validate the move
        is_valid, reason, suggestion = await MoveValidator.validate_move(player_id, move, game_manager)
        
        if not is_valid:
            print(f"   ❌ Invalid Move: {reason}")
            print(f"   💡 Suggestion: {suggestion}")
            print(f"   🎭 Narrative Integration: The AI would now incorporate this into the combat story")
            print(f"      Example: 'Player tried to {move} but {reason.lower()}'")
        else:
            print(f"   ✅ Valid Move: {reason}")
        
        print("-" * 60)

def demonstrate_ai_prompt():
    """Show how the AI prompt would look with invalid move context"""
    print("\n🤖 AI Prompt Example with Invalid Move Context:")
    print("=" * 60)
    
    prompt_example = """
You are a fantasy duel referee analyzing Round 1 of an ongoing combat.

Current Conditions:
- Warrior: fighting
- Peasant: fighting

Round 1 Moves:
- Warrior: "stand still and do nothing"
- Peasant: "stand still and do nothing"

IMPORTANT CONTEXT - Invalid Move Attempts:
- Peasant tried to 'swing my mighty sword' but move requires equipment you don't have
- Warrior tried to 'cast lightning bolt' but cannot cast magic without magical items

Incorporate these failed attempts humorously into the narrative. For example:
- 'Player 1 tried to swing their sword before realizing they never had one in the first place.'
- 'Player 2 attempted to cast fireball but only managed to look foolish while waving their empty hands.'
- 'Player 1 tried to fly off the cliff but realized they never had wings and fell.'

Analyze this round and determine:
1. What happens to each player based on their moves and current condition
2. Whether either player can no longer continue fighting (due to injury, surrender, death, etc.)
3. A dramatic description of the round's events

Respond in this exact format:
PLAYER1_CONDITION: [new condition]
PLAYER2_CONDITION: [new condition]
COMBAT_END: true/false
DESCRIPTION: [dramatic description incorporating failed move attempts humorously]
"""
    
    print(prompt_example)
    print("\n🎯 Expected AI Response Example:")
    print("=" * 60)
    
    expected_response = """
PLAYER1_CONDITION: fighting
PLAYER2_CONDITION: fighting
COMBAT_END: false
DESCRIPTION: The combat begins with an awkward silence as both fighters attempt their moves. The Peasant dramatically reaches for their back, expecting to find a mighty sword, only to grasp at empty air with a look of utter confusion. Meanwhile, the Warrior begins an elaborate spell-casting gesture, waving their hands in mystical patterns, but nothing happens except for a few confused looks from the Peasant. Both fighters stand there, realizing their tactical errors, and the round ends with neither combatant gaining an advantage.
"""
    
    print(expected_response)

if __name__ == "__main__":
    asyncio.run(test_narrative_integration())
    demonstrate_ai_prompt() 