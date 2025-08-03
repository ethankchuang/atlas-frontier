"""
Item templates for AI generation
"""
from typing import Dict, Any
import json
import re
from .base import ItemTemplate


class GenericItemTemplate(ItemTemplate):
    """Template for generating generic items"""
    
    def __init__(self, item_type_manager=None):
        super().__init__("generic_item")
        self.item_type_manager = item_type_manager
        
        self.system_prompt = """You are an expert at creating fantasy items for a text-based adventure game. 
Generate a unique item with the following specifications:

1. NAME: Create a creative, thematic name for the item (1-4 words) that clearly indicates what type of item it is
2. SPECIAL_EFFECTS: Generate special effects that allow the player to perform actions in combat.

IMPORTANT: Special effects are ONLY allowed for rarity 3 and 4 items. For rarity 1 and 2 items, you MUST NOT generate any special effects.

CRITICAL: Keep all descriptions concise and focused. Remove all fluff and unnecessary elaboration.
CRITICAL: The item name MUST contain the actual item type word. A sword MUST be named like "Iron Sword" or "Steel Sword", not "metallic fragment" or "crystal shard".

The special effects should be phrased as "allows player to [action]" and should be appropriate for the item's rarity level:
- Rarity 3: Generate 1 powerful special effect
- Rarity 4: Generate 2 extremely powerful special effects
- Rarity 1 & 2: NO special effects allowed

Examples of special effects:
- "allows player to fly"
- "allows player to become invisible"
- "allows player to teleport"
- "allows player to control fire"
- "allows player to walk through walls"
- "allows player to jump super high"
- "allows player to slice through metal"

The item should fit the context provided and be appropriate for a fantasy setting.
Respond in JSON format with exactly these fields: "name" and "special_effects".

Example response for rarity 3+:
{
    "name": "Staff of Eternal Light",
    "special_effects": "allows player to fly freely and allows player to become completely invisible"
}

Example response for rarity 1-2:
{
    "name": "Simple Wooden Staff",
    "special_effects": ""
}"""

    def generate_prompt(self, context: Dict[str, Any]) -> str:
        """Generate the prompt for the AI"""
        location_context = context.get('location', 'a mysterious location')
        theme_context = context.get('theme', 'fantasy')
        
        # Generate rarity first so we can tell the AI how many special effects to create
        rarity = self.generate_rarity()
        
        # Store rarity in context for later use
        context['rarity'] = rarity
        
        # Get item type if available
        item_type = None
        # Use item_type from context if provided, otherwise get random one
        if 'item_type' in context and context['item_type']:
            # If item_type is already a string (from item_type.name), we need to get the actual object
            if isinstance(context['item_type'], str):
                # Try to find the item type by name
                try:
                    item_type = self.item_type_manager.get_item_type_by_name(context['item_type'])
                except ValueError:
                    # If not found, get a random one
                    if self.item_type_manager and self.item_type_manager.item_types:
                        item_type = self.item_type_manager.get_random_item_type()
            else:
                # If it's already an object, use it directly
                item_type = context['item_type']
        elif self.item_type_manager and self.item_type_manager.item_types:
            # No item_type in context, get random one
            item_type = self.item_type_manager.get_random_item_type()
            context['item_type'] = item_type
        
        # Add rarity-specific instructions
        if rarity == 3:
            rarity_instruction = "This is a RARITY 3 item. Generate exactly 1 powerful special effect."
        elif rarity == 4:
            rarity_instruction = "This is a RARITY 4 item. Generate exactly 2 extremely powerful special effects."
        else:
            rarity_instruction = "This is a RARITY 1 or 2 item. No special effects needed."
        
        # Add item type information if available
        if item_type and hasattr(item_type, 'name') and item_type.name:
            type_instruction = f"\n\nITEM TYPE: {item_type.name}\nDESCRIPTION: {item_type.description}\nCAPABILITIES: {', '.join(item_type.capabilities)}\n\nCRITICAL: The item name MUST contain the word '{item_type.name}' or a clear synonym. For example:\n- If type is 'Sword', name MUST be like 'Iron Sword', 'Steel Sword', 'Crystal Sword', 'Ancient Sword'\n- If type is 'Map', name MUST be like 'Treasure Map', 'Ancient Map', 'Navigation Map', 'Secret Map'\n- If type is 'Potion', name MUST be like 'Healing Potion', 'Magic Potion', 'Restoration Potion', 'Elixir Potion'\n- If type is 'Key', name MUST be like 'Ancient Key', 'Crystal Key', 'Mystic Key', 'Golden Key'\n- If type is 'Shield', name MUST be like 'Iron Shield', 'Steel Shield', 'Magic Shield', 'Ancient Shield'\n- If type is 'Bow', name MUST be like 'Wooden Bow', 'Elven Bow', 'Magic Bow', 'Ancient Bow'\n\nDO NOT create generic names like 'metallic fragment' or 'crystal shard'. The name MUST clearly indicate it is a {item_type.name.lower()}."
        else:
            type_instruction = ""
        
        prompt = f"{self.system_prompt}\n\n{rarity_instruction}{type_instruction}\n\nGenerate an item that would be found in {location_context} with a {theme_context} theme."
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
            if 'name' not in data:
                raise ValueError("Missing required fields")
            
            # Use rarity from context if available, otherwise generate
            rarity = context.get('rarity', self.generate_rarity())
            
            # ENFORCE RARITY RESTRICTION: Only allow special effects for rarity 3 and 4
            if rarity >= 3:
                # Use AI-generated special effects for rarity 3 and 4
                if 'special_effects' in data and data['special_effects']:
                    special_effects = data['special_effects']
                else:
                    # No special effects if AI didn't generate them
                    special_effects = "No special effects"
            else:
                # FORCE no special effects for rarity 1 and 2, regardless of AI output
                special_effects = "No special effects"
            
            # Include item type information if available
            item_data = {
                'name': data['name'],
                'special_effects': special_effects,
                'rarity': rarity
            }
            
            # Add item type information if available
            if 'item_type' in context and context['item_type']:
                item_type = context['item_type']
                if hasattr(item_type, 'name') and item_type.name:
                    item_data['type'] = item_type.name
                    item_data['type_description'] = item_type.description
                    item_data['type_capabilities'] = item_type.capabilities

            
            return item_data
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Fallback parsing for malformed responses
            lines = response.strip().split('\n')
            name = "Mysterious Item"
            special_effects = "No special effects"
            
            for line in lines:
                line = line.strip()
                if 'name' in line.lower() and ':' in line:
                    name = line.split(':', 1)[1].strip().strip('"\'{}')
                elif 'special_effects' in line.lower() and ':' in line:
                    special_effects = line.split(':', 1)[1].strip().strip('"\'{}')
            
            rarity = context.get('rarity', self.generate_rarity())
            
            # ENFORCE RARITY RESTRICTION: Only allow special effects for rarity 3 and 4
            if rarity < 3:
                special_effects = "No special effects"
            
            # Include item type information if available
            item_data = {
                'name': name,
                'special_effects': special_effects,
                'rarity': rarity
            }
            
            # Add item type information if available
            if 'item_type' in context and context['item_type']:
                item_type = context['item_type']
                if hasattr(item_type, 'name') and item_type.name:
                    item_data['type'] = item_type.name
                    item_data['type_description'] = item_type.description
                    item_data['type_capabilities'] = item_type.capabilities

            
            return item_data
    
    def validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate that the output meets template requirements"""
        required_fields = ['name', 'special_effects', 'rarity']
        
        # Check all required fields exist
        for field in required_fields:
            if field not in output:
                return False
        
        # Validate field types
        if not isinstance(output['name'], str) or len(output['name']) == 0:
            return False
        
        if not isinstance(output['special_effects'], str) or len(output['special_effects']) == 0:
            return False
        
        if not isinstance(output['rarity'], int) or output['rarity'] < 1 or output['rarity'] > 4:
            return False
        
        # ENFORCE RARITY RESTRICTION: Validate that special effects are only present for rarity 3 and 4
        if not self._validate_rarity_restriction(output):
            return False
        
        return True
    
    def _validate_rarity_restriction(self, output: Dict[str, Any]) -> bool:
        """Validate that special effects are only present for rarity 3 and 4 items"""
        rarity = output.get('rarity', 0)
        special_effects = output.get('special_effects', '')
        
        # For rarity 1 and 2, special effects must be empty or "No special effects"
        if rarity < 3:
            if special_effects and special_effects.lower() not in ['', 'no special effects', 'none']:
                return False
        
        # For rarity 3 and 4, special effects should be present
        if rarity >= 3:
            if not special_effects or special_effects.lower() in ['', 'no special effects', 'none']:
                return False
        
        return True
    

    
    def generate_item(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate a complete item using this template"""
        if context is None:
            context = {}
        
        prompt = self.generate_prompt(context)
        # This would be called by the AI handler
        # For now, return a placeholder
        rarity = self.generate_rarity()
        return {
            'name': 'Placeholder Item',
            'special_effects': 'No special effects',
            'rarity': rarity
        } 