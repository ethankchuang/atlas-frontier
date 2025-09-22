"""
AI-driven item generation
"""
from typing import Dict, Any
import json
import re
import random
from .base import ItemTemplate


class AIItemGenerator(ItemTemplate):
    """Fully AI-driven item generator"""
    
    def __init__(self):
        super().__init__("ai_item")
        
        # Different naming approaches for variety
        self.naming_styles = [
            "descriptive",      # Crimson Sand Amulet, Thornwood Staff
            "material_based",   # Obsidian Blade, Silkweave Cloak
            "elemental",        # Emberstone, Frostbite Dagger
            "location_based",   # Wasteland Relic, Deepwood Charm
            "mysterious",       # The Whisperer's Token, Shadow's Edge
            "crafted",          # Artisan's Hammer, Masterwork Bow
            "ancient",          # Relic of the Old Ones, Forgotten Artifact
            "biome_specific"    # Desert Wind Stone, Forest Spirit Branch
        ]
        
        self.system_prompt = """You are an expert at creating items for a text-based adventure game. 
Generate a unique item that fits perfectly with the world and situation provided.

CRITICAL REQUIREMENTS:
1. NAME: Creative, thematic name (1-4 words) that clearly indicates what the item is
    Vary the type of the item, favor items that are tools / able to actively be used
2. RARITY: Choose 1-4 based on situation importance and world context
3. DESCRIPTION: Brief, focused description of what it is and looks like  
4. CAPABILITIES: List of things the player can do with this item (be creative but logical)

IMPORTANT: Players can grab ANY object and turn it into an item. Use your creativity and judgment:
- Mundane objects can stay mundane (e.g., "Smooth Rock" with basic capabilities like "throw")
- Consider the world context, location, and narrative situation to decide

RARITY GUIDELINES:
- Rarity 1: Random junk items with no restrictions - give these out whenever you feel like it (rocks, sticks, fish, basic mundane objects)
    - Examples: "Smooth Rock", "Broken Stick", "Dead Fish", "Rusty Coin", "Pebble"
    - These are common items players can find anywhere by grabbing random objects
- Rarity 2: Normal items with moderate utility - distributed based on room data (0-4 items per room)
    - Examples: crafted tools, useful materials, basic magical items, quality equipment
    - These require some effort or exploration to find and are tied to specific room locations
- Rarity 3: Special items found only in designated rooms - one special room per biome gets these
    - Examples: powerful magical artifacts, ancient relics, legendary weapons, biome-specific treasures
    - These are rare and tied to specific special locations within each biome
- Rarity 4: Legendary items (not yet implemented - placeholder for future use)
    - Reserved for future implementation of ultra-rare legendary items

CAPABILITY EXAMPLES:
- Simple physical: "throw", "poke", "mark territory", "create noise"
- Utility actions: "unlock doors", "navigate", "heal wounds", "communicate", "light fires"
- Magical/Tech actions: "hack systems", "cast spells", "phase through walls"
- Special powers: "become invisible", "fly", "teleport", "control elements"

The item should:
- Fit the world's theme and technology level
- Be reasonable to find in the given situation
- Have capabilities that make sense for what it is
- Be appropriately powerful for its rarity
- Can be mundane or magical based on your creative judgment

Respond in JSON format with exactly these fields: "name", "rarity", "description", "capabilities"

EXAMPLE RESPONSES:

Mundane item:
{
    "name": "Smooth River Stone",
    "rarity": 1,
    "description": "A perfectly rounded gray stone worn smooth by water",
    "capabilities": ["throw at targets", "mark paths", "create noise", "skip on water"]
}"""

    def _get_naming_guidance(self, style: str, biome: str) -> str:
        """Get specific naming guidance for the selected style and biome"""
        guidance_map = {
            "descriptive": f"NAMING STYLE: Use descriptive adjectives that evoke the item's appearance or nature (e.g., 'Thornwood Staff', 'Crimson Sand Amulet'). Focus on {biome} themes.",
            "material_based": f"NAMING STYLE: Emphasize the primary material or construction (e.g., 'Obsidian Blade', 'Silkweave Cloak'). Consider {biome}-appropriate materials.",
            "elemental": f"NAMING STYLE: Incorporate elemental or magical properties (e.g., 'Emberstone', 'Frostbite Dagger'). Use {biome}-relevant elements.",
            "location_based": f"NAMING STYLE: Reference the origin or discovery location (e.g., 'Wasteland Relic', 'Deepwood Charm'). Connect to {biome} geography.",
            "mysterious": f"NAMING STYLE: Create enigmatic, mystical names (e.g., 'The Whisperer's Token', 'Shadow's Edge'). Add {biome} mystery elements.",
            "crafted": f"NAMING STYLE: Suggest skilled craftsmanship (e.g., 'Artisan's Hammer', 'Masterwork Bow'). Include {biome} cultural crafting traditions.",
            "ancient": f"NAMING STYLE: Evoke age and forgotten knowledge (e.g., 'Relic of the Old Ones', 'Forgotten Artifact'). Reference {biome} ancient history.",
            "biome_specific": f"NAMING STYLE: Directly incorporate {biome} elements (e.g., 'Desert Wind Stone', 'Forest Spirit Branch'). Make it uniquely {biome}."
        }
        return guidance_map.get(style, guidance_map["descriptive"])

    def generate_prompt(self, context: Dict[str, Any]) -> str:
        """Generate the prompt for the AI with world and situational context"""
        # Extract world context
        world_seed = context.get('world_seed', 'Unknown World')
        world_theme = context.get('world_theme', 'fantasy')
        main_quest = context.get('main_quest', 'Unknown quest')
        
        # Extract situational context
        room_description = context.get('room_description', 'a mysterious location')
        room_biome = context.get('room_biome', 'unknown')
        player_action = context.get('player_action', 'searching')
        situation_context = context.get('situation_context', 'exploring')
        room_availability = context.get('room_item_availability', {})
        
        # Build contextual prompt
        world_context_text = f"""
WORLD CONTEXT:
- World: {world_seed}
- Theme: {world_theme}
- Main Quest: {main_quest}

SITUATION CONTEXT:
- Location: {room_description}
- Biome: {room_biome}
- Player Action: {player_action}
- Situation: {situation_context}

Generate an item that:
1. Fits perfectly with the {world_theme} world theme
2. Makes sense to find in this {room_biome} location
3. Is reasonable to obtain from "{player_action}"
4. Has capabilities appropriate for this world's technology/magic level
5. **Choose appropriate rarity based on what the player is trying to grab and room availability**
"""

        # Handle desired rarity (for room generation)
        desired_rarity = context.get('desired_rarity')
        if desired_rarity:
            world_context_text += f"""
**REQUIRED RARITY: {desired_rarity}**
- You MUST generate an item with exactly rarity {desired_rarity}
- Create an item appropriate for this rarity level
"""
            
            # Apply naming styles for 2+ star items
            if desired_rarity >= 2:
                selected_style = random.choice(self.naming_styles)
                naming_guidance = self._get_naming_guidance(selected_style, room_biome)
                world_context_text += f"\n{naming_guidance}\n"
        else:
            # Handle basic item detection for player actions
            basic_items = ['rock', 'stone', 'stick', 'branch', 'twig', 'leaf', 'dirt', 'mud', 'pebble', 'sand', 'grass', 'bone', 'shell']
            is_basic_item = any(item in player_action.lower() for item in basic_items)
            
            if is_basic_item:
                world_context_text += """
**BASIC ITEM DETECTED**
- Player is grabbing a basic/mundane object (rock, stick, etc.)
- You MUST use rarity 1 for basic items like rocks, sticks, leaves, etc.
- Keep it simple and mundane - no magical properties
"""
            else:
                # Add room availability context for non-basic items
                if room_availability:
                    has_3star = room_availability.get('has_three_star_item', False)
                    available_2star = room_availability.get('two_star_items_available', 0)
                    
                    world_context_text += f"""
ROOM ITEM AVAILABILITY:
- 3-star special item available: {has_3star}
- 2-star normal items available: {available_2star}
- 1-star basic items: Always available

**RARITY SELECTION GUIDANCE:**
- If player is grabbing something that sounds like a special/magical/rare item AND room has 3-star available → use rarity 3
- If player is grabbing something useful/crafted/moderate AND room has 2-star available → use rarity 2  
- If player is grabbing basic/mundane objects OR room has no higher items → use rarity 1
- Let the player's specific action and the item's nature guide the rarity choice

**NAMING STYLE FOR 2+ STAR ITEMS:**
- If you choose rarity 2 or 3, use creative naming with thematic elements
- Consider the biome and world context for naming inspiration
- Make names evocative and memorable for higher rarity items
"""
                    
                    # Add specific naming style guidance if 2+ star items are available
                    if has_3star or available_2star > 0:
                        selected_style = random.choice(self.naming_styles)
                        naming_guidance = self._get_naming_guidance(selected_style, room_biome)
                        world_context_text += f"\n{naming_guidance}\n"
        
        prompt = f"{self.system_prompt}\n{world_context_text}"
        return prompt
    
    def parse_response(self, response: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Parse the AI response into structured data"""
        if context is None:
            context = {}
        
        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
            else:
                # Fallback: try to parse the entire response as JSON
                data = json.loads(response)
            
            # Ensure required fields exist
            required_fields = ['name', 'rarity', 'description', 'capabilities']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate rarity is in correct range
            rarity = data['rarity']
            if not isinstance(rarity, int) or rarity < 1 or rarity > 4:
                rarity = 2  # Default to common if invalid
            
            # Ensure capabilities is a list
            capabilities = data['capabilities']
            if isinstance(capabilities, str):
                # If it's a string, split it into a list
                capabilities = [cap.strip() for cap in capabilities.split(',')]
            elif not isinstance(capabilities, list):
                capabilities = ["unknown capability"]
            
            # Build clean item data
            item_data = {
                'name': data['name'].strip(),
                'rarity': rarity,
                'description': data['description'].strip(),
                'capabilities': capabilities
            }
            
            return item_data
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Fallback parsing for malformed responses
            lines = response.strip().split('\n')
            name = "Mysterious Item"
            description = "An unknown object"
            capabilities = ["unknown capability"]
            rarity = 1
            
            for line in lines:
                line = line.strip()
                if 'name' in line.lower() and ':' in line:
                    name = line.split(':', 1)[1].strip().strip('"\'{}')
                elif 'description' in line.lower() and ':' in line:
                    description = line.split(':', 1)[1].strip().strip('"\'{}')
                elif 'rarity' in line.lower() and ':' in line:
                    try:
                        rarity = int(line.split(':', 1)[1].strip())
                        if rarity < 1 or rarity > 4:
                            rarity = 1
                    except:
                        rarity = 1
            
            item_data = {
                'name': name,
                'rarity': rarity,
                'description': description,
                'capabilities': capabilities
            }
            
            return item_data
    
    def validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate that the output meets template requirements"""
        required_fields = ['name', 'rarity', 'description', 'capabilities']
        
        # Check all required fields exist
        for field in required_fields:
            if field not in output:
                return False
        
        # Validate field types
        if not isinstance(output['name'], str) or len(output['name']) == 0:
            return False
        
        if not isinstance(output['description'], str) or len(output['description']) == 0:
            return False
        
        if not isinstance(output['rarity'], int) or output['rarity'] < 1 or output['rarity'] > 4:
            return False
        
        if not isinstance(output['capabilities'], list) or len(output['capabilities']) == 0:
            return False
        
        return True
    
    async def generate_item(self, ai_handler, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate a complete item using AI"""
        if context is None:
            context = {}
        
        prompt = self.generate_prompt(context)
        
        try:
            # Generate item using AI
            ai_response = await ai_handler.generate_text(prompt)
            item_data = self.parse_response(ai_response, context)
            
            # Validate the output
            if self.validate_output(item_data):
                return item_data
            else:
                # Return fallback item if validation fails
                return {
                    'name': 'Unknown Item',
                    'rarity': 1,
                    'description': 'A mysterious object',
                    'capabilities': ['unknown capability']
                }
                
        except Exception as e:
            # Return fallback item if generation fails
            return {
                'name': 'Mysterious Item',
                'rarity': 1,
                'description': 'An enigmatic object',
                'capabilities': ['unknown capability']
            } 