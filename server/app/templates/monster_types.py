"""
Monster type management for AI generation
"""
from typing import Dict, Any, List, Optional
import json
import random
from dataclasses import dataclass


@dataclass
class MonsterType:
    """Represents a monster archetype with specific characteristics"""
    name: str
    description: str
    aggressiveness: str  # passive, aggressive, neutral, territorial
    intelligence: str    # human, subhuman, animal, omnipotent
    size: str           # colossal, dinosaur, horse, human, chicken, insect
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "name": self.name,
            "description": self.description,
            "aggressiveness": self.aggressiveness,
            "intelligence": self.intelligence,
            "size": self.size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MonsterType':
        """Create from dictionary"""
        return cls(
            name=data["name"],
            description=data["description"],
            aggressiveness=data["aggressiveness"],
            intelligence=data["intelligence"],
            size=data["size"]
        )


class MonsterTypeManager:
    """Manages monster types for the game world"""
    
    def __init__(self):
        self.monster_types: List[MonsterType] = []
    
    async def generate_world_monster_types(self, world_seed: str, world_context: Dict[str, Any] = None, ai_handler=None) -> List[MonsterType]:
        """Generate monster types for a specific world"""
        try:
            # Create context for AI generation
            context_info = self._create_world_context(world_seed, world_context)
            
            if ai_handler:
                # Use AI to generate contextual monster types
                prompt = self._create_monster_type_generation_prompt(context_info)
                
                response = await ai_handler.generate_response(
                    prompt=prompt,
                    context={"world_seed": world_seed, "context": world_context or {}}
                )
                
                try:
                    monster_data = json.loads(response)
                    if isinstance(monster_data, list):
                        generated_types = []
                        for monster_info in monster_data:
                            if all(key in monster_info for key in ["name", "description", "aggressiveness", "intelligence", "size"]):
                                monster_type = MonsterType(
                                    name=monster_info["name"],
                                    description=monster_info["description"],
                                    aggressiveness=monster_info["aggressiveness"],
                                    intelligence=monster_info["intelligence"],
                                    size=monster_info["size"]
                                )
                                generated_types.append(monster_type)
                        
                        if len(generated_types) >= 8:  # Ensure we have enough types
                            self.monster_types = generated_types[:10]  # Keep only first 10
                            return self.monster_types
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Failed to parse AI monster types: {e}")
            
            # Fallback to default types if AI generation fails
            return await self.generate_default_monster_types()
            
        except Exception as e:
            print(f"Error generating monster types: {str(e)}")
            # Fallback to defaults
            return await self.generate_default_monster_types()
    
    def _create_world_context(self, world_seed: str, world_context: Dict[str, Any] = None) -> str:
        """Create context information for monster generation"""
        context_parts = [f"World seed: {world_seed}"]
        
        if world_context:
            if "main_quest" in world_context:
                context_parts.append(f"Main quest: {world_context['main_quest']}")
            if "theme" in world_context:
                context_parts.append(f"Theme: {world_context['theme']}")
            if "biome" in world_context:
                context_parts.append(f"Primary biome: {world_context['biome']}")
        
        return "\n".join(context_parts)
    
    def _create_monster_type_generation_prompt(self, context_info: str) -> str:
        """Create AI prompt for generating monster types"""
        
        prompt = f"""You are an expert game designer creating monster archetypes for a text-based adventure game.

WORLD CONTEXT:
{context_info}

TASK:
Generate exactly 10 distinct monster archetypes that would be commonly found in this type of world. These should be diverse monsters that fit the world's theme and environment.

REQUIREMENTS:
1. Each monster must be DISTINCT and serve a different role in the ecosystem
2. Include a mix of threat levels and behaviors
3. Monsters should fit the world theme and environment
4. Each monster should have a clear description of appearance and behavior
5. Use realistic combinations of the specified attributes

ATTRIBUTES TO ASSIGN:
- aggressiveness: Must be one of ["passive", "aggressive", "neutral", "territorial"]
- intelligence: Must be one of ["human", "subhuman", "animal", "omnipotent"]  
- size: Must be one of ["colossal", "dinosaur", "horse", "human", "chicken", "insect"]

FORMAT:
Return a JSON array with exactly 10 objects. Each object must have:
- "name": A simple, clear name for the monster type (1-3 words)
- "description": A brief description of the monster's appearance and basic behavior
- "aggressiveness": One of the four aggressiveness levels
- "intelligence": One of the four intelligence levels
- "size": One of the six size categories

EXAMPLES FOR DIFFERENT WORLD TYPES:

For a medieval fantasy world:
- Dragon: "A massive reptilian creature with scales and wings", "aggressive", "human", "colossal"
- Goblin: "A small green humanoid with sharp teeth and claws", "aggressive", "subhuman", "chicken"
- Deer: "A graceful forest animal with antlers", "passive", "animal", "horse"

For a cyberpunk world:
- Security Drone: "A flying mechanical guardian with scanning equipment", "territorial", "subhuman", "human"
- Cyber Rat: "A genetically modified rodent with glowing implants", "neutral", "animal", "chicken"
- AI Construct: "A digital entity made of pure information", "neutral", "omnipotent", "human"

For a post-apocalyptic world:
- Mutant Bear: "A radiation-twisted bear with extra limbs", "aggressive", "animal", "dinosaur"
- Scavenger Bot: "A small robot that collects useful materials", "passive", "subhuman", "chicken"
- Rad Roach: "A giant cockroach adapted to radioactive environments", "neutral", "animal", "human"

IMPORTANT:
- Ensure good variety in all attributes (don't make everything aggressive/human/human-sized)
- Include at least one monster of each aggressiveness type
- Include at least one monster of each intelligence type
- Include at least one monster of each size category
- Make sure monsters are appropriate for the world theme
- Keep names simple and descriptive
- Descriptions should be 1-2 sentences maximum

Return only the JSON array, no other text."""
        
        return prompt
    
    async def generate_default_monster_types(self) -> List[MonsterType]:
        """Generate default monster types for worlds without AI"""
        default_types = [
            MonsterType("Wolf", "A fierce canine predator with sharp fangs", "aggressive", "animal", "human"),
            MonsterType("Giant Spider", "A massive arachnid with venomous bite", "territorial", "animal", "horse"),
            MonsterType("Goblin", "A small green humanoid with crude weapons", "aggressive", "subhuman", "chicken"),
            MonsterType("Ancient Dragon", "A colossal reptile with devastating breath", "territorial", "human", "colossal"),
            MonsterType("Forest Sprite", "A tiny magical being that avoids conflict", "passive", "human", "insect"),
            MonsterType("Dire Bear", "An enormous bear with incredible strength", "territorial", "animal", "dinosaur"),
            MonsterType("Rabbit", "A small harmless creature that flees danger", "passive", "animal", "chicken"),
            MonsterType("Lich", "An undead sorcerer of immense magical power", "aggressive", "omnipotent", "human"),
            MonsterType("Orc Warrior", "A brutal humanoid fighter seeking combat", "aggressive", "subhuman", "human"),
            MonsterType("Wise Owl", "An intelligent bird that observes quietly", "neutral", "animal", "chicken")
        ]
        
        self.monster_types = default_types
        return default_types
    
    def get_random_monster_type(self) -> MonsterType:
        """Get a random monster type for generation"""
        if not self.monster_types:
            raise Exception("No monster types available. Generate types first.")
        
        return random.choice(self.monster_types)
    
    def get_monster_type_by_name(self, name: str) -> MonsterType:
        """Get a monster type by name"""
        for monster_type in self.monster_types:
            if monster_type.name.lower() == name.lower():
                return monster_type
        raise ValueError(f"Monster type '{name}' not found")
    
    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convert all monster types to a list of dictionaries for storage"""
        return [monster_type.to_dict() for monster_type in self.monster_types]
    
    def from_dict_list(self, data: List[Dict[str, Any]]):
        """Load monster types from a list of dictionaries"""
        self.monster_types = []
        for item_data in data:
            try:
                monster_type = MonsterType.from_dict(item_data)
                self.monster_types.append(monster_type)
            except Exception as e:
                print(f"Error loading monster type: {e}")
                continue
    
    def has_types(self) -> bool:
        """Check if monster types are loaded"""
        return len(self.monster_types) > 0 