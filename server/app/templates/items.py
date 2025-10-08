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
    For example sword, axe, bow, magic wand, etc. 
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
    - These items should NOT have any magical properties or abilities
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
- Be a tool that the player has to actively use

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

    async def _get_recent_items_context(self, context: Dict[str, Any]) -> str:
        """Get context about recently generated 2/3 star items to help AI vary item generation"""
        try:
            # Get database instance from context or create new one
            db = context.get('database')
            if not db:
                from ..hybrid_database import HybridDatabase
                db = HybridDatabase()
            
            # Get recent 2/3 star items
            recent_items = await db.get_recent_high_rarity_items(min_rarity=2, limit=15)
            
            if not recent_items:
                return ""
            
            # Format the context
            context_text = "\n**RECENTLY GENERATED ITEMS (for variety reference):**\n"
            context_text += "Here are some recently generated 2/3 star items to help you create something different:\n\n"
            
            for item in recent_items[:10]:  # Show up to 10 recent items
                name = item.get('name', 'Unknown Item')
                rarity = item.get('rarity', 1)
                description = item.get('description', 'No description')
                capabilities = item.get('capabilities', [])
                
                # Truncate long descriptions
                if len(description) > 100:
                    description = description[:100] + "..."
                
                context_text += f"- **{name}** (Rarity {rarity}): {description}\n"
                if capabilities:
                    context_text += f"  Capabilities: {', '.join(capabilities[:3])}\n"  # Show first 3 capabilities
                context_text += "\n"
            
            context_text += "**IMPORTANT:** Use this list to ensure your new item is unique and different from these recent items. Avoid similar names, themes, or capabilities.\n"
            
            return context_text
            
        except Exception as e:
            # If there's an error getting recent items, continue without context
            return ""

    async def generate_prompt(self, context: Dict[str, Any]) -> str:
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
        
        # Handle item combination context
        combination_items = context.get('combination_items', [])
        combination_description = context.get('combination_description', '')
        
        if combination_items and situation_context == 'item_combination':
            combination_context = f"""
**ITEM COMBINATION CRAFTING:**
You are creating a new item by combining {len(combination_items)} existing items:

ITEMS TO COMBINE:
"""
            for i, item in enumerate(combination_items, 1):
                name = item.get('name', 'Unknown Item')
                description = item.get('description', 'No description')
                capabilities = item.get('capabilities', [])
                rarity = item.get('rarity', 1)
                
                combination_context += f"{i}. **{name}** (Rarity {rarity}): {description}\n"
                if capabilities:
                    combination_context += f"   Capabilities: {', '.join(capabilities)}\n"
                combination_context += "\n"
            
            if combination_description:
                combination_context += f"PLAYER'S INTENT: {combination_description}\n\n"
            
            combination_context += """
**COMBINATION RULES:**
- The new item MUST be at least rarity 2 (2-star minimum)
- The new item should logically combine the properties of the input items
- Create a new, unique item that makes sense as a combination
- The name should reflect that it's a crafted/combined item
- Capabilities should be enhanced or combined from the input items
- Make it feel like a meaningful upgrade from the individual components
"""
            
            world_context_text += combination_context
        
        # Add recent items context for variety
        recent_items_context = await self._get_recent_items_context(context)
        
        prompt = f"{self.system_prompt}\n{world_context_text}{recent_items_context}"
        return prompt
    
    async def parse_response(self, response: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Parse the AI response into structured data"""
        if context is None:
            context = {}
        
        # Retry mechanism for JSON parsing
        max_retries = 3
        for attempt in range(max_retries):
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
                
            except json.JSONDecodeError as e:
                logger.warning(f"[Item Generation] JSON parsing failed on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    # Final attempt failed, raise the error
                    logger.error(f"[Item Generation] All {max_retries} attempts failed, raising error")
                    raise
                else:
                    # Wait a bit before retrying
                    await asyncio.sleep(0.5)
                    continue
                    
            except Exception as e:
                logger.error(f"[Item Generation] Unexpected error on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    # Final attempt failed, raise the error
                    logger.error(f"[Item Generation] All {max_retries} attempts failed due to unexpected error, raising error")
                    raise
                else:
                    # Wait a bit before retrying
                    await asyncio.sleep(0.5)
                    continue
        
        # If we get here, all retries failed - return fallback item
        logger.error(f"[Item Generation] All retry attempts failed, returning fallback item")
        return {
            'name': 'Mysterious Item',
            'rarity': 1,
            'description': 'An unknown object that appeared from the void.',
            'capabilities': ['unknown capability']
        }
    
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
        
        prompt = await self.generate_prompt(context)
        
        try:
            # Generate item using AI
            ai_response = await ai_handler.generate_text(prompt)
            item_data = await self.parse_response(ai_response, context)
            
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