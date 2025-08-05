#!/usr/bin/env python3
"""
Admin tool to generate example monsters using the monster blueprint system.
This demonstrates the monster type system and generates sample monsters.
"""

import asyncio
import sys
import os
import uuid
import json
from typing import Dict, Any

# Add the server directory to the path so we can import the app modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.database import Database
from app.templates.monsters import GenericMonsterTemplate
from app.ai_handler import AIHandler


class MockAIHandler:
    """Mock AI handler for testing without making real AI calls"""
    
    def __init__(self):
        # Predefined diverse monster examples
        self.monster_examples = [
            {
                "name": "Flame Wraith",
                "description": "A ghostly figure wreathed in dancing flames with hollow eyes that burn like coals. Its ethereal form flickers between solid and smoke.",
                "special_effects": "can breathe fire and become intangible"
            },
            {
                "name": "Crystal Stalker",
                "description": "A wolf-like creature with a body made of living crystal that refracts light into deadly rainbow beams. Sharp crystal shards jut from its spine.",
                "special_effects": "can shoot prismatic light beams"
            },
            {
                "name": "Moss Shambler",
                "description": "A hulking humanoid covered in thick green moss and tiny flowering vines. Ancient tree roots serve as its arms and legs.",
                "special_effects": "can control plant growth and camouflage perfectly"
            },
            {
                "name": "Storm Raven",
                "description": "A massive black bird with feathers that crackle with electricity. Its eyes glow white-hot like lightning strikes.",
                "special_effects": "can summon lightning bolts and fly at incredible speeds"
            },
            {
                "name": "Bone Rattler",
                "description": "A serpentine creature made entirely of yellowed bones held together by dark magic. Its skull head has glowing red eye sockets.",
                "special_effects": "can reassemble after being destroyed"
            },
            {
                "name": "Mist Walker",
                "description": "A tall, gaunt figure that seems to be made of swirling fog. Only its glowing blue eyes are clearly visible through the mist.",
                "special_effects": "can turn into mist and pass through walls"
            },
            {
                "name": "Iron Beetle",
                "description": "A massive beetle with a metallic carapace that gleams like polished steel. Steam vents from its joints as it moves.",
                "special_effects": "has impenetrable armor and can ram through obstacles"
            },
            {
                "name": "Echo Howler",
                "description": "A spectral wolf with a translucent body that phases in and out of visibility. Its howl reverberates with supernatural power.",
                "special_effects": "can disorient enemies with sonic howls"
            },
            {
                "name": "Thorn Sprite",
                "description": "A tiny humanoid with bark-like skin and hair made of thorny vines. Despite its small size, it radiates natural menace.",
                "special_effects": "can grow razor-sharp thorns from its body"
            },
            {
                "name": "Void Creeper",
                "description": "A spider-like creature that seems to absorb light around it, creating an aura of darkness. Its many eyes reflect like black mirrors.",
                "special_effects": "can create zones of magical darkness"
            }
        ]
        self.current_index = 0
    
    async def generate_response(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Generate a mock response with varied monster examples"""
        # Return a different monster each time
        monster_data = self.monster_examples[self.current_index % len(self.monster_examples)]
        self.current_index += 1
        
        return json.dumps(monster_data)


async def generate_monster_examples():
    """Generate and display example monsters"""
    
    print("🎮 Monster Generation System - Example Generator")
    print("=" * 50)
    
    # Initialize the monster template
    print("\n📋 Step 1: Initializing Monster Template...")
    monster_template = GenericMonsterTemplate()
    
    # Use mock AI handler for demonstration
    mock_ai = MockAIHandler()
    
    # Generate individual monsters directly
    print("\n🐲 Step 2: Generating Individual Monster Examples...")
    
    environments = [
        {"room_title": "Dark Forest Clearing", "biome": "forest"},
        {"room_title": "Crystal Cavern", "biome": "underground"},
        {"room_title": "Misty Swampland", "biome": "swamp"},
        {"room_title": "Rocky Mountain Peak", "biome": "mountain"},
        {"room_title": "Ancient Ruins", "biome": "ruins"},
        {"room_title": "Burning Desert", "biome": "desert"},
        {"room_title": "Frozen Tundra", "biome": "arctic"},
        {"room_title": "Haunted Graveyard", "biome": "undead"},
        {"room_title": "Enchanted Garden", "biome": "magical"},
        {"room_title": "Shadowy Void", "biome": "otherworldly"}
    ]
    
    # Generate 10 example monsters
    for i in range(10):
        print(f"\n--- Example Monster {i+1} ---")
        
        # Use different environments for variety
        environment = environments[i % len(environments)]
        
        # Create context for monster generation
        context = {
            'room_title': environment['room_title'],
            'biome': environment['biome']
        }
        
        # Generate base monster data (randomly selects attributes)
        base_data = monster_template.generate_monster_data(context)
        
        # Generate monster appearance and special effects with mock AI
        ai_response = await mock_ai.generate_response(
            prompt="Generate a unique monster",
            context=context
        )
        
        generated_data = monster_template.parse_response(ai_response)
        
        # Create complete monster data
        monster_data = {
            'id': f"monster_{uuid.uuid4()}",
            'name': generated_data['name'],
            'description': generated_data['description'],
            'aggressiveness': base_data['aggressiveness'],
            'intelligence': base_data['intelligence'],
            'size': base_data['size'],
            'special_effects': generated_data['special_effects'],
            'location': f"{environment['biome']}_area_{i+1}",
            'health': base_data['health'],
            'is_alive': True
        }
        
        # Display the generated monster
        print(f"🏷️  Name: {monster_data['name']}")
        print(f"📝  Description: {monster_data['description']}")
        print(f"🌍  Environment: {environment['room_title']} ({environment['biome']})")
        print(f"😤  Aggressiveness: {monster_data['aggressiveness']}")
        print(f"🧠  Intelligence: {monster_data['intelligence']}")
        print(f"📏  Size: {monster_data['size']}")
        print(f"❤️  Health: {monster_data['health']}")
        if monster_data['special_effects']:
            print(f"✨  Special Effects: {monster_data['special_effects']}")
        else:
            print(f"✨  Special Effects: None")
    
    print("\n" + "=" * 50)
    print("🎉 Monster generation examples completed!")
    print("\nℹ️  This demonstrates the simplified monster system:")
    print("   • Monsters are generated directly with random attributes")
    print("   • AI creates unique names, descriptions, and abilities")
    print("   • Health is calculated based on size")
    print("   • Each monster is contextual to its environment")
    print("   • No complex type system - just pure variety!")


async def show_system_statistics():
    """Show statistics about the monster system"""
    print("\n📊 Monster System Statistics")
    print("-" * 30)
    
    # Show attribute distributions
    aggressiveness_options = ["passive", "aggressive", "neutral", "territorial"]
    intelligence_options = ["human", "subhuman", "animal", "omnipotent"]
    size_options = ["colossal", "dinosaur", "horse", "human", "chicken", "insect"]
    
    print(f"Aggressiveness levels: {len(aggressiveness_options)} ({', '.join(aggressiveness_options)})")
    print(f"Intelligence levels: {len(intelligence_options)} ({', '.join(intelligence_options)})")
    print(f"Size categories: {len(size_options)} ({', '.join(size_options)})")
    
    total_combinations = len(aggressiveness_options) * len(intelligence_options) * len(size_options)
    print(f"\nTotal possible combinations: {total_combinations}")
    print(f"Direct generation: Each monster is unique")
    print(f"Health calculation: Base 50 × size multiplier")


if __name__ == "__main__":
    print("Starting Monster Blueprint System Demo...")
    
    try:
        # Run the main demo
        asyncio.run(generate_monster_examples())
        
        # Show system statistics
        asyncio.run(show_system_statistics())
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
    except Exception as e:
        print(f"\n❌ Error running demo: {str(e)}")
        import traceback
        traceback.print_exc() 