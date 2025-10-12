"""
NPC templates for AI generation
"""
from typing import Dict, Any
import json
import re
import random
import asyncio
import logging
from .base import BaseTemplate

# Get logger for this module
logger = logging.getLogger(__name__)


class NPCTemplate(BaseTemplate):
    """Base class for NPC templates"""

    def __init__(self, name: str):
        super().__init__(name, "npc")


class GenericNPCTemplate(NPCTemplate):
    """Template for generating NPCs with personalities and backstories"""

    def __init__(self):
        super().__init__("generic_npc")

        # Different NPC archetypes for variety
        self.npc_archetypes = [
            "merchant",      # Traders, shopkeepers
            "traveler",      # Wanderers, adventurers
            "local",         # Residents, natives of the area
            "mystic",        # Wise figures, prophets, hermits
            "guard",         # Protectors, warriors
            "craftsperson",  # Artisans, craftspeople
            "scholar",       # Researchers, historians
            "outcast"        # Loners, exiles, mysterious figures
        ]

        # Personality trait categories
        self.personality_traits = {
            "friendly": ["cheerful", "warm", "welcoming", "jovial", "kind"],
            "grumpy": ["irritable", "stern", "gruff", "cantankerous", "surly"],
            "mysterious": ["cryptic", "enigmatic", "secretive", "elusive", "suspicious"],
            "wise": ["sage", "thoughtful", "philosophical", "knowledgeable", "insightful"],
            "nervous": ["anxious", "jittery", "paranoid", "timid", "skittish"],
            "bold": ["confident", "brash", "daring", "audacious", "fearless"]
        }

        self.system_prompt = """You are an expert at creating NPCs (Non-Player Characters) for a text-based adventure game.
Generate a unique NPC with the following specifications:

1. NAME: Create a fitting name for this NPC (1-3 words)
2. DESCRIPTION: Describe what this NPC looks like and what they're doing (2-3 sentences maximum)
3. BACKSTORY: A brief backstory that hints at their history or motivations (1-2 sentences)
4. DIALOGUE_STYLE: Describe how this NPC talks (e.g., "speaks in riddles", "uses sailor's jargon", "very formal and polite")
5. KNOWLEDGE: What this NPC knows about or can help with (e.g., "local geography", "ancient legends", "trade routes")
6. QUEST_HINT: Optional hint about a quest or interesting information they might share (1 sentence, can be empty)

The NPC should fit the context provided and be interesting to interact with.
Respond in JSON format with exactly these fields: "name", "description", "backstory", "dialogue_style", "knowledge", "quest_hint".

Example response:
{
    "name": "Old Grim",
    "description": "A weather-beaten man sits on a wooden crate, mending fishing nets with practiced hands. His eyes are the color of storm clouds and seem to look through you rather than at you.",
    "backstory": "Once a renowned sea captain, Grim lost his ship and crew to a mysterious storm twenty years ago. He's never been the same since.",
    "dialogue_style": "speaks in nautical metaphors and often trails off mid-sentence",
    "knowledge": "knows every inch of the coastline and the tides, remembers old shipwrecks",
    "quest_hint": "Sometimes mutters about 'the singing rocks' where his ship went down"
}"""

    def generate_prompt(self, context: Dict[str, Any]) -> str:
        """Generate the prompt for the AI with varied archetypes"""
        # Choose archetype and personality
        archetype = context.get('archetype', random.choice(self.npc_archetypes))
        personality_category = random.choice(list(self.personality_traits.keys()))
        personality_trait = random.choice(self.personality_traits[personality_category])

        # Get environment context
        environment_info = ""
        if "room_title" in context:
            environment_info += f"LOCATION: {context['room_title']}\n"
        if "room_description" in context:
            environment_info += f"ENVIRONMENT: {context['room_description']}\n"
        if "biome" in context:
            environment_info += f"BIOME: {context['biome']}\n"

        # Add archetype and personality guidance
        archetype_guidance = self._get_archetype_guidance(archetype, personality_trait)

        prompt = f"{self.system_prompt}\n\n{archetype_guidance}\n\n{environment_info}\nGenerate an NPC that fits this context:"

        return prompt

    def _get_archetype_guidance(self, archetype: str, personality: str) -> str:
        """Get specific guidance based on archetype"""
        guidance_map = {
            "merchant": f"ARCHETYPE: This NPC is a merchant or trader. They should be {personality} and focused on commerce, goods, or services.",
            "traveler": f"ARCHETYPE: This NPC is a traveler or wanderer. They should be {personality} and have stories from distant places.",
            "local": f"ARCHETYPE: This NPC is a local resident. They should be {personality} and know the area well, including local customs and gossip.",
            "mystic": f"ARCHETYPE: This NPC is a mystic or wise figure. They should be {personality} and speak about deeper meanings, prophecies, or spiritual matters.",
            "guard": f"ARCHETYPE: This NPC is a guard or warrior. They should be {personality} and concerned with security, duty, or combat.",
            "craftsperson": f"ARCHETYPE: This NPC is a craftsperson or artisan. They should be {personality} and passionate about their craft or trade.",
            "scholar": f"ARCHETYPE: This NPC is a scholar or researcher. They should be {personality} and interested in knowledge, history, or discoveries.",
            "outcast": f"ARCHETYPE: This NPC is an outcast or loner. They should be {personality} and have a sense of being apart from society."
        }

        return guidance_map.get(archetype, guidance_map["local"])

    async def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the AI response into structured data"""
        try:
            # Clean up the response
            response = response.strip()

            # Try to extract JSON from the response with retry mechanism
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        json_str = json_match.group()
                        data = json.loads(json_str)

                        # Ensure required fields exist with fallbacks
                        if "name" not in data:
                            data["name"] = "Mysterious Stranger"
                        if "description" not in data:
                            data["description"] = "A person stands here, watching you curiously."
                        if "backstory" not in data:
                            data["backstory"] = "Little is known about this person's past."
                        if "dialogue_style" not in data:
                            data["dialogue_style"] = "speaks plainly and directly"
                        if "knowledge" not in data:
                            data["knowledge"] = "local area and recent events"
                        if "quest_hint" not in data:
                            data["quest_hint"] = ""

                        return data
                    else:
                        if attempt == max_retries - 1:
                            raise ValueError("No JSON found in response")
                        else:
                            await asyncio.sleep(0.5)
                            continue

                except json.JSONDecodeError as e:
                    logger.warning(f"[NPC Generation] JSON parsing failed on attempt {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:
                        # Final attempt failed, return fallback NPC
                        logger.error(f"[NPC Generation] All {max_retries} attempts failed, using fallback NPC")
                        return {
                            "name": "Mysterious Stranger",
                            "description": "A figure stands here, shrouded in shadow.",
                            "backstory": "This person's origins are unknown.",
                            "dialogue_style": "speaks softly and carefully",
                            "knowledge": "unknown",
                            "quest_hint": ""
                        }
                    else:
                        await asyncio.sleep(0.5)
                        continue

                except Exception as e:
                    logger.error(f"[NPC Generation] Unexpected error on attempt {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:
                        logger.error(f"[NPC Generation] All {max_retries} attempts failed due to unexpected error, using fallback NPC")
                        return {
                            "name": "Mysterious Stranger",
                            "description": "A figure stands here, shrouded in shadow.",
                            "backstory": "This person's origins are unknown.",
                            "dialogue_style": "speaks softly and carefully",
                            "knowledge": "unknown",
                            "quest_hint": ""
                        }
                    else:
                        await asyncio.sleep(0.5)
                        continue

        except (json.JSONDecodeError, ValueError) as e:
            # Final fallback parsing
            return {
                "name": "Generated NPC",
                "description": "A person stands here.",
                "backstory": "Their past is a mystery.",
                "dialogue_style": "speaks plainly",
                "knowledge": "local area",
                "quest_hint": ""
            }

    def validate_output(self, output: Dict[str, Any]) -> bool:
        """Validate that the output meets template requirements"""
        required_fields = ["name", "description", "backstory", "dialogue_style", "knowledge"]

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

    def generate_npc_data(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate complete NPC data including base attributes"""
        import random

        if context is None:
            context = {}

        # Generate base NPC data
        base_data = {
            "is_active": True,
            "interaction_count": 0,
            "mood": random.choice(["neutral", "happy", "thoughtful", "worried", "excited"])
        }

        return base_data
