from openai import OpenAI
from typing import Dict, List, Optional, Tuple, AsyncGenerator, Union
import json
from datetime import datetime
from .config import settings
from .models import Room, NPC, Player, GameState
import asyncio
import logging
from .logger import setup_logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.OPENAI_API_KEY)

class AIHandler:
    @staticmethod
    async def generate_room_description(
        context: Dict[str, any],
        style: str = "fantasy"
    ) -> Tuple[str, str, str]:
        """Generate a room title and description"""
        json_template = '''
{
    "title": "A short, evocative title",
    "description": "A rich, atmospheric description",
    "image_prompt": "A detailed prompt for image generation"
}
'''
        prompt = f"""Generate a detailed room description for a fantasy MUD game.
        Context: {json.dumps(context)}
        Style: {style}

        Return a JSON object with these exact fields:
        {json_template}
        """

        logger.debug(f"[Room Description] Sending prompt to OpenAI: {prompt}")
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-nano-2025-04-14",
                messages=[
                    {"role": "system", "content": "You are a creative writer for a fantasy MUD game. Always return clean JSON without any comments. Focus on describing ONLY the immediate room the player is entering."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            content = response.choices[0].message.content
            logger.debug(f"[Room Description] Received response from OpenAI: {content}")

            result = json.loads(content)
            return result["title"], result["description"], result["image_prompt"]
        except Exception as e:
            logger.error(f"[Room Description] Error generating room description: {str(e)}")
            raise

    @staticmethod
    async def generate_room_image(prompt: str) -> str:
        """Generate an image for a room using DALL-E"""
        if not settings.IMAGE_GENERATION_ENABLED:
            logger.info("[Image Generation] Image generation is disabled")
            return ""

        try:
            logger.info(f"[Image Generation] Generating image with prompt: {prompt}")

            # Add retry logic for image generation
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = client.images.generate(
                        model="dall-e-3",
                        prompt=f"A detailed, atmospheric fantasy game scene: {prompt}",
                        size="1024x1024",
                        quality="standard",
                        n=1
                    )
                    url = response.data[0].url

                    # Verify the URL is valid and unique
                    if url and isinstance(url, str) and len(url) > 0:
                        logger.info(f"[Image Generation] Generated image URL: {url}")
                        return url
                    else:
                        raise ValueError("Invalid image URL received")

                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"[Image Generation] Attempt {attempt + 1} failed: {str(e)}")
                        await asyncio.sleep(1)  # Wait before retrying
                    else:
                        raise

            raise Exception("Failed to generate valid image after all retries")

        except Exception as e:
            logger.error(f"[Image Generation] Error generating image: {str(e)}")
            return ""

    @staticmethod
    async def stream_action(
        action: str,
        player: Player,
        room: Room,
        game_state: GameState,
        npcs: List[NPC]
    ) -> AsyncGenerator[Union[str, Dict[str, any]], None]:
        """Process a player's action using the LLM with streaming"""
        context = {
            "player": player.dict(),
            "room": room.dict(),
            "game_state": game_state.dict(),
            "npcs": [npc.dict() for npc in npcs],
            "action": action,
            "timestamp": datetime.utcnow().isoformat()
        }

        json_template = '''
{
    "response": "Copy of the narrative response above",
    "updates": {
        "player": {
            "current_room": "new_room_id",
            "inventory": ["item1", "item2"]
        },
        "room": {
            "id": "room_id",
            "title": "Room Title",
            "description": "Room description",
            "connections": {},
            "npcs": [],
            "items": [],
            "players": [],
            "visited": true,
            "properties": {}
        },
        "npcs": [
            {
                "id": "npc_id",
                "name": "NPC Name",
                "dialogue_history": [],
                "memory_log": []
            }
        ]
    }
}
'''

        prompt = f"""Process this player action in a fantasy MUD game.
        Context: {json.dumps(context)}

        IMPORTANT: Your response MUST follow this EXACT format:
        1. First, write a narrative response describing what happens.
        2. Then, add TWO newlines.
        3. Finally, provide a JSON object with this exact structure:
        {json_template}

        Only include fields in updates that need to be changed. The updates object is optional.
        Do not include any comments in the JSON.
        """

        logger.debug(f"[Stream Action] Sending prompt to OpenAI: {prompt}")
        try:
            stream = client.chat.completions.create(
                model="gpt-4.1-nano-2025-04-14",
                messages=[
                    {"role": "system", "content": "You are the game master of a fantasy MUD game. Always format responses exactly as requested, with clean JSON and no comments."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                stream=True
            )

            buffer = ""
            narrative = ""
            narrative_complete = False

            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    buffer += content
                    #logger.debug(f"[Stream Action] Received chunk: {content}")

                    # Check if we've hit the JSON part (after two newlines)
                    if not narrative_complete and "\n\n{" in buffer:
                        narrative_complete = True
                        # Split at the JSON start and yield the narrative
                        parts = buffer.split("\n\n{", 1)
                        if len(parts) == 2:
                            narrative = parts[0].strip()
                            yield narrative
                            buffer = "{" + parts[1]
                    elif not narrative_complete:
                        # Still in narrative part, yield the content
                        narrative += content
                        yield content

                    # Try to parse as JSON to see if it's complete
                    if narrative_complete:
                        try:
                            result = json.loads(buffer)
                            # Validate the JSON structure
                            if "response" not in result or "updates" not in result:
                                raise ValueError("Invalid response format: missing required fields")

                            # Validate room updates if present
                            if "updates" in result and "room" in result["updates"]:
                                room_updates = result["updates"]["room"]
                                required_fields = ["id", "title", "description"]
                                missing_fields = [field for field in required_fields if field not in room_updates]
                                if missing_fields:
                                    raise ValueError(f"Room update missing required fields: {', '.join(missing_fields)}")

                            logger.debug(f"[Stream Action] Final parsed result: {json.dumps(result, indent=2)}")

                            # If we successfully parsed JSON, this is the final message
                            yield {
                                "response": narrative,  # Use the stored narrative
                                "updates": result.get("updates", {})
                            }
                            break
                        except json.JSONDecodeError:
                            continue
                        except ValueError as e:
                            logger.error(f"[Stream Action] Validation error: {str(e)}")
                            yield {"error": str(e)}
                            break
                await asyncio.sleep(0)

            # If we never got a complete response, yield an error
            if not narrative_complete:
                logger.error("[Stream Action] Incomplete response from AI")
                yield {"error": "Incomplete response from AI"}
            elif buffer and not any(key in buffer for key in ['"response":', '"updates":']):
                logger.error("[Stream Action] Invalid response format from AI")
                yield {"error": "Invalid response format from AI"}
        except Exception as e:
            logger.error(f"[Stream Action] Error processing action: {str(e)}")
            yield {"error": f"Error processing action: {str(e)}"}

    @staticmethod
    async def process_action(
        action: str,
        player: Player,
        room: Room,
        game_state: GameState,
        npcs: List[NPC]
    ) -> Tuple[str, Dict[str, any]]:
        """Process a player's action"""
        json_template = '''
{
    "response": "The narrative response to show the player",
    "updates": {
        "player": {
            "current_room": "new_room_id",
            "inventory": ["item1", "item2"]
        },
        "room": {
            "id": "room_id",
            "title": "Room Title",
            "description": "Room description",
            "connections": {},
            "npcs": [],
            "items": [],
            "players": [],
            "visited": true,
            "properties": {}
        },
        "npcs": [
            {
                "id": "npc_id",
                "name": "NPC Name",
                "dialogue_history": [],
                "memory_log": []
            }
        ]
    }
}
'''
        context = {
            "player": player.dict(),
            "room": room.dict(),
            "game_state": game_state.dict(),
            "npcs": [npc.dict() for npc in npcs],
            "action": action,
            "timestamp": datetime.utcnow().isoformat()
        }

        prompt = f"""Process this player action in a fantasy MUD game.
        Context: {json.dumps(context)}

        IMPORTANT RULES:
        1. If the player is moving to a new room that doesn't exist yet, ONLY include the player's new room ID in updates.player.current_room
        2. DO NOT include any details about the new room in the updates - it will be generated separately
        3. Only include updates for existing rooms, players, and NPCs that need to be changed
        4. When moving to a new room, ONLY generate ONE new room ID - do not create or reference multiple new rooms
        5. The new room ID should follow the format: room_<descriptive_name> (e.g., room_cave, room_forest)

        Return a JSON object with this exact structure:
        {json_template}

        Only include fields in updates that need to be changed. The updates object is optional.
        Do not include any comments in the JSON.
        """

        logger.debug(f"[Process Action] Sending prompt to OpenAI: {prompt}")
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-nano-2025-04-14",
                messages=[
                    {"role": "system", "content": "You are the game master of a fantasy MUD game. Always format responses exactly as requested, with clean JSON and no comments. When moving to a new room, only generate ONE new room."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            content = response.choices[0].message.content
            logger.debug(f"[Process Action] Received response from OpenAI: {content}")

            result = json.loads(content)

            # Validate room updates if present
            if "updates" in result and "room" in result["updates"]:
                room_updates = result["updates"]["room"]
                required_fields = ["id", "title", "description"]
                missing_fields = [field for field in required_fields if field not in room_updates]
                if missing_fields:
                    raise ValueError(f"Room update missing required fields: {', '.join(missing_fields)}")

            return result["response"], result["updates"]
        except Exception as e:
            logger.error(f"[Process Action] Error processing action: {str(e)}")
            raise

    @staticmethod
    async def process_npc_interaction(
        message: str,
        npc: NPC,
        player: Player,
        room: Room,
        relevant_memories: List[Dict[str, any]]
    ) -> Tuple[str, str]:
        """Process NPC dialogue using the LLM"""
        context = {
            "npc": npc.dict(),
            "player": player.dict(),
            "room": room.dict(),
            "message": message,
            "memories": relevant_memories,
            "timestamp": datetime.utcnow().isoformat()
        }

        json_template = '''
{
    "response": "The NPC's response",
    "memory": "A new memory to store about this interaction"
}
'''

        prompt = f"""Process this player's interaction with an NPC in a fantasy MUD game.
        Context: {json.dumps(context)}

        Return a JSON object with this exact structure:
        {json_template}
        """

        response = client.chat.completions.create(
            model="gpt-4.1-nano-2025-04-14",
            messages=[
                {"role": "system", "content": "You are an NPC in a fantasy MUD game. Always return clean JSON without any comments."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        result = json.loads(response.choices[0].message.content)
        return result["response"], result["memory"]

    @staticmethod
    async def generate_world_seed() -> GameState:
        """Generate initial world state and main quest"""
        json_template = '''
{
    "world_seed": "A unique identifier for this world",
    "main_quest_summary": "A description of the main quest",
    "starting_state": {
        "quest_stage": "beginning",
        "world_time": "dawn",
        "weather": "clear"
    }
}
'''

        prompt = f"""Create a new fantasy world and main quest for a MUD game.

        Return a JSON object with this exact structure:
        {json_template}
        """

        response = client.chat.completions.create(
            model="gpt-4.1-nano-2025-04-14",
            messages=[
                {"role": "system", "content": "You are a fantasy world creator. Always return clean JSON without any comments."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        result = json.loads(response.choices[0].message.content)

        # Convert all values in starting_state to strings
        starting_state = {
            k: str(v) if not isinstance(v, (list, dict)) else json.dumps(v)
            for k, v in result["starting_state"].items()
        }

        return GameState(
            world_seed=result["world_seed"],
            main_quest_summary=result["main_quest_summary"],
            global_state=starting_state
        )