"""
Item types and their capabilities for the game world
"""
from typing import Dict, List, Any
import random


class ItemType:
    """Represents an item type with its capabilities and description"""
    
    def __init__(self, name: str, description: str, capabilities: List[str]):
        self.name = name
        self.description = description
        self.capabilities = capabilities
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'name': self.name,
            'description': self.description,
            'capabilities': self.capabilities
        }


class ItemTypeManager:
    """Manages item types for the game world"""
    
    def __init__(self):
        self.item_types: List[ItemType] = []
    
    async def generate_world_item_types(self, world_seed: str, world_context: Dict[str, Any] = None, ai_handler=None) -> List[ItemType]:
        """Generate 10 distinct item types for a specific world using AI"""
        import logging
        logger = logging.getLogger(__name__)
        
        if not ai_handler:
            logger.error("[Item Type Generation] No AI handler provided")
            raise Exception("AI handler is required for item type generation")
        
        # Use the world seed to ensure consistent item types for each world
        seed_hash = hash(world_seed) % (2**32)
        random.seed(seed_hash)
        logger.info(f"[Item Type Generation] Using seed hash: {seed_hash}")
        
        # Build context for AI prompt
        context_info = f"World Seed: {world_seed}"
        if world_context and 'main_quest_summary' in world_context:
            context_info += f"\nMain Quest: {world_context['main_quest_summary']}"
        
        # Create strong prompt for AI-generated item types
        prompt = self._create_item_type_generation_prompt(context_info)
        
        try:
            logger.info(f"[Item Type Generation] Generating item types with AI")
            ai_response = await ai_handler.generate_text(prompt)
            
            # Parse AI response into item types
            generated_types = self._parse_ai_generated_types(ai_response)
            
            if len(generated_types) >= 10:
                # Select exactly 10 types
                selected_types = self._select_diverse_types(generated_types, 10)
                logger.info(f"[Item Type Generation] Successfully generated {len(selected_types)} AI item types")
            else:
                logger.warning(f"[Item Type Generation] AI only generated {len(generated_types)} types, retrying...")
                # Try again with a simpler prompt
                retry_prompt = self._create_simple_fallback_prompt(context_info)
                retry_response = await ai_handler.generate_text(retry_prompt)
                retry_types = self._parse_ai_generated_types(retry_response)
                
                if len(retry_types) >= 10:
                    selected_types = self._select_diverse_types(retry_types, 10)
                    logger.info(f"[Item Type Generation] Retry successful: {len(selected_types)} types")
                else:
                    logger.error(f"[Item Type Generation] Failed to generate sufficient types after retry")
                    raise Exception("Failed to generate sufficient item types")
            
            self.item_types = selected_types
            return selected_types
            
        except Exception as e:
            logger.error(f"[Item Type Generation] Failed to generate item types with AI: {str(e)}")
            raise Exception(f"Failed to generate item types: {str(e)}")
    
    def _create_item_type_generation_prompt(self, context_info: str) -> str:
        """Create a strong prompt for AI-generated item types"""
        
        prompt = f"""You are an expert game designer creating item archetypes for a text-based adventure game.

WORLD CONTEXT:
{context_info}

TASK:
Generate exactly 10 distinct item archetypes that would be commonly found in this type of world. These should be the basic, fundamental item types that players would expect to find in any game set in this world.

REQUIREMENTS:
1. Each item type must be DISTINCT and serve a different purpose
2. Items should be COMMON, FUNDAMENTAL, and RECOGNIZABLE
3. Focus on essential item types that every player would expect
4. Include a mix of weapons, armor, and utility items
5. Each item should have a clear, simple description of what it is
6. Each item should have 3-4 logical capabilities that describe what it can do

FORMAT:
Return a JSON array with exactly 10 objects. Each object must have:
- "name": A simple, clear name for the item type (1-3 words)
- "description": A brief description of what the item is and its basic purpose
- "capabilities": An array of 3-4 simple, logical capabilities

EXAMPLES OF GOOD, FUNDAMENTAL ITEMS:
For a medieval world:
- Sword: "A sharp blade for cutting and stabbing enemies", ["slash", "stab", "cut", "defend"]
- Bow: "A weapon that fires arrows at distant targets", ["shoot arrows", "hit from afar", "hunt", "defend"]
- Shield: "A protective barrier that blocks attacks", ["block", "deflect", "protect", "defend"]
- Armor: "Protective clothing that guards against injury", ["protect", "defend", "guard", "shield from harm"]
- Staff: "A staff that can be used for walking and support", ["walking aid", "support", "balance", "reach high places"]
- Potion: "A magical liquid that provides healing or enhancement", ["heal", "enhance", "restore", "boost"]
- Map: "A map that shows locations and helps with navigation", ["navigate", "find paths", "locate places", "guide direction"]
- Key: "A key that can unlock doors and containers", ["unlock", "open", "access", "enter"]
- Torch: "A portable source of light for exploring dark areas", ["illuminate", "light", "signal", "burn"]
- Amulet: "A pendant that provides protection and good fortune", ["protect", "bring luck", "ward off harm", "enhance senses"]

For a cyberpunk world:
- Gun: "A firearm for shooting at targets", ["shoot", "aim", "fire", "defend"]
- Knife: "A small blade for close combat and utility", ["stab", "cut", "slice", "utility tool"]
- Armor: "Protective gear that guards against injury", ["protect", "defend", "guard", "shield"]
- Cyberdeck: "A computer interface for hacking systems", ["hack", "access", "control", "analyze"]
- Medkit: "Medical supplies for healing and treatment", ["heal", "treat", "stabilize", "restore"]
- Scanner: "A device that analyzes and detects information", ["scan", "detect", "analyze", "identify"]
- Tool: "A multi-purpose tool for various tasks", ["repair", "craft", "modify", "assemble"]
- Implant: "A cybernetic enhancement for the body", ["enhance", "upgrade", "modify", "improve"]
- Grenade: "An explosive device for area attacks", ["explode", "damage", "stun", "clear area"]
- Shield: "A portable energy barrier for protection", ["block", "deflect", "protect", "defend"]

IMPORTANT:
- Focus on FUNDAMENTAL, RECOGNIZABLE item types
- Avoid overly specific or niche items
- Include classic items that every player expects (swords, bows, armor, etc.)
- Keep descriptions simple and logical
- Make sure items are appropriate for the world theme
- Ensure all 10 items are distinct from each other
- Use GENERIC names only (e.g., "Sword", not "Rusty Sword" or "Crystal Blade")
- The AI will later generate specific item names when creating actual items

Return only the JSON array, no other text."""
        
        return prompt
    
    def _create_simple_fallback_prompt(self, context_info: str) -> str:
        """Create a simple fallback prompt for retry attempts"""
        prompt = f"""Generate exactly 10 basic item types for this world:

{context_info}

Return a JSON array with 10 objects, each with:
- "name": A simple item name (1-2 words)
- "description": Brief description
- "capabilities": Array of 3-4 capabilities

Examples: Sword, Bow, Shield, Armor, Staff, Potion, Map, Key, Torch, Amulet

Return only the JSON array."""
        
        return prompt
    
    def _parse_ai_generated_types(self, ai_response: str) -> List[ItemType]:
        """Parse AI response into ItemType objects"""
        import json
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\[.*\]', ai_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # Fallback: try to parse the entire response as JSON
                data = json.loads(ai_response)
            
            generated_types = []
            for item_data in data:
                try:
                    name = item_data.get('name', 'Unknown Item')
                    description = item_data.get('description', 'An unknown item')
                    capabilities = item_data.get('capabilities', [])
                    
                    # Ensure capabilities is a list
                    if not isinstance(capabilities, list):
                        capabilities = [str(capabilities)]
                    
                    item_type = ItemType(name, description, capabilities)
                    generated_types.append(item_type)
                    logger.debug(f"[Item Type Generation] Parsed: {name}")
                    
                except Exception as e:
                    logger.warning(f"[Item Type Generation] Failed to parse item: {str(e)}")
                    continue
            
            logger.info(f"[Item Type Generation] Successfully parsed {len(generated_types)} item types")
            return generated_types
            
        except Exception as e:
            logger.error(f"[Item Type Generation] Failed to parse AI response: {str(e)}")
            return []
    
    def _select_diverse_types(self, all_types: List[ItemType], target_count: int) -> List[ItemType]:
        """Select diverse types from the available options"""
        import logging
        logger = logging.getLogger(__name__)
        
        if len(all_types) <= target_count:
            return all_types
        
        # Simply select the first target_count types and shuffle them
        selected_types = all_types[:target_count]
        random.shuffle(selected_types)
        
        logger.info(f"[Item Type Generation] Selected {len(selected_types)} types")
        return selected_types
    

    
    def get_random_item_type(self) -> ItemType:
        """Get a random item type from the current world's available types"""
        if not self.item_types:
            raise ValueError("No item types available. Call generate_world_item_types first.")
        return random.choice(self.item_types)
    
    async def generate_default_item_types(self) -> List[ItemType]:
        """Generate default item types for existing worlds without AI"""
        default_types = [
            ItemType("Sword", "A sharp blade designed for combat", ["slash", "stab", "parry", "block"]),
            ItemType("Shield", "A protective barrier for defense", ["block", "bash", "defend", "cover"]),
            ItemType("Bow", "A ranged weapon for distance attacks", ["shoot", "aim", "draw", "release"]),
            ItemType("Staff", "A magical implement for spellcasting", ["cast", "channel", "focus", "enhance"]),
            ItemType("Potion", "A magical liquid with healing properties", ["drink", "heal", "restore", "boost"]),
            ItemType("Amulet", "A protective charm with magical properties", ["protect", "ward", "bless", "shield"]),
            ItemType("Dagger", "A small, concealable blade", ["stab", "throw", "hide", "stealth"]),
            ItemType("Helmet", "Protective headgear", ["protect", "defend", "cover", "guard"]),
            ItemType("Ring", "A magical accessory with special powers", ["enhance", "boost", "protect", "charm"]),
            ItemType("Scroll", "A magical document with inscribed spells", ["read", "cast", "learn", "unlock"])
        ]
        
        self.item_types = default_types
        return default_types
    
    def get_item_type_by_name(self, name: str) -> ItemType:
        """Get an item type by name"""
        for item_type in self.item_types:
            if item_type.name.lower() == name.lower():
                return item_type
        raise ValueError(f"Item type '{name}' not found")
    

    
    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convert all item types to a list of dictionaries for storage"""
        return [item_type.to_dict() for item_type in self.item_types]
    
    def from_dict_list(self, data: List[Dict[str, Any]]):
        """Load item types from a list of dictionaries"""
        self.item_types = []
        for item_data in data:
            item_type = ItemType(
                name=item_data['name'],
                description=item_data['description'],
                capabilities=item_data['capabilities']
            )
            self.item_types.append(item_type) 