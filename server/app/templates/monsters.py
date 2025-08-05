"""
Monster templates for AI generation - Simplified Direct Generation
"""
from typing import Dict, Any
import json
import re
import random
from .base import MonsterTemplate


class GenericMonsterTemplate(MonsterTemplate):
    """Template for generating monsters directly without types"""
    
    def __init__(self):
        super().__init__("generic_monster")
        
        # Different naming approaches for variety
        self.naming_styles = [
            "descriptive",  # Flame Wraith, Crystal Stalker
            "creature_type", # Ancient Dragon, Forest Sprite  
            "elemental",    # Shadowbeast, Frostling
            "location_based", # Swamp Crawler, Mountain Howler
            "mysterious"    # The Whisperer, Night's Edge
        ]
        
        self.system_prompt = """You are an expert at creating monsters for a text-based adventure game. 
Generate a unique monster with the following specifications:

1. NAME: Create a creative, thematic name for the monster (1-4 words) that fits the environment
2. DESCRIPTION: Describe what this creature looks like in vivid detail (2-3 sentences maximum)
3. SPECIAL_EFFECTS: Generate special effects/abilities that make the monster interesting

Special effects should be phrased as monster abilities, for example:
- "can breathe fire"
- "can turn invisible"
- "can teleport short distances"
- "can control minds"
- "can fly at high speeds"
- "has venomous bite"
- "can phase through walls"
- "regenerates health rapidly"
- "can summon shadow minions"
- "shoots lightning bolts"

The monster should fit the context provided and be appropriate for the world setting.
Respond in JSON format with exactly these fields: "name", "description", and "special_effects".

Example response:
{
    "name": "Flame Wraith",
    "description": "A ghostly figure wreathed in dancing flames with hollow eyes that burn like coals. Its ethereal form flickers between solid and smoke.",
    "special_effects": "can breathe fire and become intangible"
}"""

    def generate_prompt(self, context: Dict[str, Any]) -> str:
        """Generate the prompt for the AI with varied naming styles"""
        # Choose a random naming style for variety
        naming_style = random.choice(self.naming_styles)
        
        # Get environment context
        environment_info = ""
        if "room_title" in context:
            environment_info += f"LOCATION: {context['room_title']}\n"
        if "room_description" in context:
            environment_info += f"ENVIRONMENT: {context['room_description']}\n"
        if "biome" in context:
            environment_info += f"BIOME: {context['biome']}\n"
        
        # Get provided attributes
        attributes_info = ""
        if "aggressiveness" in context:
            attributes_info += f"AGGRESSIVENESS: {context['aggressiveness']}\n"
        if "intelligence" in context:
            attributes_info += f"INTELLIGENCE: {context['intelligence']}\n"
        if "size" in context:
            attributes_info += f"SIZE: {context['size']}\n"
        
        # Add naming style guidance
        naming_guidance = self._get_naming_guidance(naming_style, context.get('biome', 'unknown'))
        
        prompt = f"{self.system_prompt}\n\n{naming_guidance}\n\n{environment_info}{attributes_info}\nGenerate a monster that fits this context:"
        
        return prompt
    
    def _get_naming_guidance(self, style: str, biome: str) -> str:
        """Get specific naming guidance based on the chosen style"""
        guidance_map = {
            "descriptive": f"NAMING STYLE: Use descriptive adjectives that evoke the monster's appearance or nature (e.g., 'Thornhide Beast', 'Mistcloaked Hunter'). Focus on {biome} themes.",
            
            "creature_type": f"NAMING STYLE: Combine a descriptor with a creature type (e.g., 'Ancient Basilisk', 'Corrupted Stag'). Draw from {biome} ecosystem.",
            
            "elemental": f"NAMING STYLE: Use elemental or essence-based names (e.g., 'Voidtouched', 'Emberling', 'Frostmaw'). Connect to {biome} elements.",
            
            "location_based": f"NAMING STYLE: Include the location or habitat in the name (e.g., '{biome.title()} Prowler', 'Deep Cave Crawler'). Make it specific to this environment.",
            
            "mysterious": f"NAMING STYLE: Use mysterious, ominous names that suggest rather than describe (e.g., 'The Forgotten', 'Whisper of Dread'). Create atmosphere over clarity."
        }
        
        return guidance_map.get(style, guidance_map["descriptive"])

    def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the AI response into structured data"""
        try:
            # Clean up the response
            response = response.strip()
            
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                
                # Ensure required fields exist
                if "name" not in data:
                    data["name"] = "Unknown Monster"
                if "description" not in data:
                    data["description"] = "A mysterious creature."
                if "special_effects" not in data:
                    data["special_effects"] = ""
                
                return data
            else:
                raise ValueError("No JSON found in response")
                
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback parsing
            return {
                "name": "Generated Monster",
                "description": "A mysterious creature that appeared in the world.",
                "special_effects": ""
            }

    def validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate that the output meets template requirements"""
        required_fields = ["name", "description", "special_effects"]
        
        for field in required_fields:
            if field not in output:
                return False
            if not isinstance(output[field], str):
                return False
        
        # Validate name length
        if len(output["name"]) > 50:
            return False
            
        # Validate description length
        if len(output["description"]) > 500:
            return False
            
        return True

    def generate_monster_data(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate complete monster data including base attributes"""
        if context is None:
            context = {}
        
        # Randomly select attributes if not provided
        aggressiveness_options = ["passive", "aggressive", "neutral", "territorial"]
        intelligence_options = ["human", "subhuman", "animal", "omnipotent"]
        size_options = ["colossal", "dinosaur", "horse", "human", "chicken", "insect"]
        
        aggressiveness = context.get("aggressiveness", random.choice(aggressiveness_options))
        intelligence = context.get("intelligence", random.choice(intelligence_options))
        size = context.get("size", random.choice(size_options))
        
        # Calculate health based on size
        health = self._calculate_health(size)
        
        # Add attributes to context for AI generation
        context["aggressiveness"] = aggressiveness
        context["intelligence"] = intelligence
        context["size"] = size
        
        # Generate base monster data
        base_data = {
            "aggressiveness": aggressiveness,
            "intelligence": intelligence,
            "size": size,
            "health": health,
            "is_alive": True
        }
        
        return base_data
    
    def _calculate_health(self, size: str) -> int:
        """Calculate monster health based on size"""
        size_multipliers = {
            "insect": 0.2,
            "chicken": 0.5,
            "human": 1.0,
            "horse": 1.5,
            "dinosaur": 2.5,
            "colossal": 4.0
        }
        
        base_health = 50
        size_mult = size_multipliers.get(size, 1.0)
        
        return int(base_health * size_mult) 