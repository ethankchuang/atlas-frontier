from openai import AsyncOpenAI
from typing import Dict, List, Optional, Tuple, AsyncGenerator, Union, Any
import json
from datetime import datetime
from .config import settings
from .models import Room, NPC, Player, GameState
import asyncio
import logging
from .logger import setup_logging
import replicate
import os

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Set up Replicate API token
if settings.REPLICATE_API_TOKEN:
    os.environ["REPLICATE_API_TOKEN"] = settings.REPLICATE_API_TOKEN

class AIHandler:
    @staticmethod
    async def generate_room_description(
        context: Dict[str, Any],
        style: str = "fantasy"
    ) -> Tuple[str, str, str]:
        """Generate a room title and description"""
        json_template = '''
{
    "title": "A short, evocative title",
    "description": "A concise, atmospheric description (1-2 sentences max)",
    "image_prompt": "A detailed prompt for image generation"
}
'''
        prompt = f"""Generate a concise room description for a fantasy MUD game.
        Context: {json.dumps(context)}
        Style: {style}

        CRITICAL: Keep descriptions to 1-2 sentences maximum. Focus only on the most important visual and atmospheric details. Remove all fluff and unnecessary elaboration.

        Return a JSON object with these exact fields:
        {json_template}
        """

        logger.debug(f"[Room Description] Sending prompt to OpenAI: {prompt}")
        try:
            response = await client.chat.completions.create(
                model="gpt-4.1-nano-2025-04-14",
                messages=[
                    {"role": "system", "content": "You are a concise writer for a fantasy MUD game. Always return clean JSON without comments. Keep descriptions to 1-2 sentences maximum. Focus only on essential details and remove all fluff."},
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
        """Generate an image for a room using the configured provider"""
        if not settings.IMAGE_GENERATION_ENABLED:
            logger.info("[Image Generation] Image generation is disabled")
            return ""

        try:
            logger.info(f"[Image Generation] Generating image with prompt: {prompt}")

            if settings.IMAGE_PROVIDER == "replicate":
                return await AIHandler._generate_image_replicate(prompt)
            else:
                return await AIHandler._generate_image_openai(prompt)

        except Exception as e:
            logger.error(f"[Image Generation] Error generating image: {str(e)}")
            return ""

    @staticmethod
    async def _generate_image_replicate(prompt: str) -> str:
        """Generate an image using Replicate"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.info(f"[Replicate] Starting image generation with prompt: {prompt} (attempt {attempt + 1})")
                
                # Ensure API token is set
                if not settings.REPLICATE_API_TOKEN:
                    raise ValueError("REPLICATE_API_TOKEN not configured")
                
                # Set environment variable for Replicate client
                os.environ["REPLICATE_API_TOKEN"] = settings.REPLICATE_API_TOKEN
                
                # Enhanced prompt for better fantasy game images
                enhanced_prompt = f"A detailed, atmospheric fantasy game scene, cinematic lighting, high quality: {prompt}"
                
                logger.info(f"[Replicate] Using model: {settings.REPLICATE_MODEL}")
                logger.info(f"[Replicate] Image dimensions: {settings.REPLICATE_IMAGE_WIDTH}x{settings.REPLICATE_IMAGE_HEIGHT}")
                
                # Run the prediction with Flux Schnell parameters
                output = replicate.run(
                    settings.REPLICATE_MODEL,
                    input={
                        "prompt": enhanced_prompt,
                        "aspect_ratio": "16:9",  # Flux Schnell uses aspect_ratio instead of width/height
                        "num_outputs": 1,
                        "num_inference_steps": 4,  # Flux Schnell recommends 4 steps
                        "go_fast": True,  # Enable fast inference
                        "output_format": "webp",
                        "output_quality": 80
                    }
                )
                
                if output and len(output) > 0:
                    image_url = output[0]
                    # Convert FileOutput object to string URL if needed
                    if hasattr(image_url, 'url'):
                        image_url = image_url.url
                    elif hasattr(image_url, '__str__'):
                        image_url = str(image_url)
                    
                    logger.info(f"[Replicate] Generated image URL: {image_url}")
                    return image_url
                else:
                    raise ValueError("No image URL received from Replicate")
                    
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[Replicate] Error generating image (attempt {attempt + 1}): {error_msg}")
                
                # If it's an NSFW content error, try with a modified prompt
                if "NSFW content detected" in error_msg and attempt < max_retries - 1:
                    logger.info(f"[Replicate] NSFW content detected, trying with modified prompt")
                    # Modify the prompt to be more family-friendly
                    prompt = f"A family-friendly fantasy game scene, suitable for all ages: {prompt.replace('magical', 'peaceful').replace('mystical', 'beautiful')}"
                    await asyncio.sleep(1)  # Wait before retrying
                    continue
                elif attempt < max_retries - 1:
                    # For other errors, wait and retry
                    await asyncio.sleep(1)
                    continue
                else:
                    # Last attempt failed
                    raise

    @staticmethod
    async def _generate_image_openai(prompt: str) -> str:
        """Generate an image using OpenAI DALL-E"""
        try:
            logger.info(f"[OpenAI] Starting image generation with prompt: {prompt}")

            # Add retry logic for image generation
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = await client.images.generate(
                        model="dall-e-3",
                        prompt=f"A detailed, atmospheric fantasy game scene: {prompt}",
                        size="1024x1024",
                        quality="standard",
                        n=1
                    )
                    url = response.data[0].url

                    # Verify the URL is valid and unique
                    if url and isinstance(url, str) and len(url) > 0:
                        logger.info(f"[OpenAI] Generated image URL: {url}")
                        return url
                    else:
                        raise ValueError("Invalid image URL received")

                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"[OpenAI] Attempt {attempt + 1} failed: {str(e)}")
                        await asyncio.sleep(1)  # Wait before retrying
                    else:
                        raise

            raise Exception("Failed to generate valid image after all retries")

        except Exception as e:
            logger.error(f"[OpenAI] Error generating image: {str(e)}")
            raise

    @staticmethod
    async def stream_action(
        action: str,
        player: Player,
        room: Room,
        game_state: GameState,
        npcs: List[NPC]
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
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
            "direction": "optional, possible values: north, south, east, west, up, down",
            "inventory": ["item1", "item2"],
            "memory_log": ["memory entry"]
        },
        "npcs": [
            {
                "id": "npc_id",
                "name": "NPC Name",
                "dialogue_history": [],
                "memory_log": []
            }
        ],
        "reward_item": {
            "deserves_item": true/false,
            "item_name": "optional: creative name for the item if deserves_item is true"
        }
    }
}
'''

        prompt = f"""Process this player action in a fantasy MUD game.
        Context: {json.dumps(context)}

        CRITICAL RULES FOR CONCISE RESPONSES:
        1. Keep narrative responses to 1-2 sentences maximum
        2. Focus only on the most important details of what happens
        3. Remove all fluff, unnecessary elaboration, and flowery language
        4. For movement: Describe only the essential transition and arrival
        5. For actions: Focus on the immediate result and key details only
        6. You handle ONLY narrative responses and simple state changes
        7. Determine if the player is inputting a movement command, if so add it to updates.player.direction
        8. Focus on movement direction, inventory changes, quest progress, and NPC interactions

        ITEM REWARD EVALUATION:
        - Evaluate if the player's action deserves an item reward based on creativity and engagement
        - Simple movement commands (like "move north", "go south") should NOT reward items
        - Thoughtful exploration actions (like "investigate the area", "examine the surroundings", "search for clues") SHOULD have a chance at items
        - Creative interactions, problem-solving, and detailed investigations deserve higher chances
        - If deserves_item is true, provide a creative item name that fits the action and location context

        IMPORTANT: Your response MUST follow this EXACT format:
        1. First, write a concise narrative response (1-2 sentences max).
        2. Then, add TWO newlines.
        3. Finally, provide a JSON object with this exact structure:
        {json_template}

        Only include fields in updates that need to be changed. The updates object is optional.
        Do not include any comments in the JSON.
        """

        logger.debug(f"[Stream Action] Sending prompt to OpenAI: {prompt}")
        try:
            stream = await client.chat.completions.create(
                model="gpt-4.1-nano-2025-04-14",
                messages=[
                    {"role": "system", "content": "You are the game master of a fantasy MUD game. Keep all responses concise (1-2 sentences maximum). Focus only on essential details and remove all fluff. Make actions clear and direct."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                stream=True
            )

            buffer = ""
            narrative = ""
            narrative_complete = False

            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    buffer += content
                    #logger.debug(f"[Stream Action] Received chunk: {content}")

                    # Check if we've hit the JSON part (after two newlines)
                    if not narrative_complete and "\n\n{" in buffer:
                        narrative_complete = True
                        # Split at the JSON start - don't yield the narrative since it was already streamed
                        parts = buffer.split("\n\n{", 1)
                        if len(parts) == 2:
                            narrative = parts[0].strip()
                            # Don't yield narrative here - it was already streamed character by character
                            buffer = "{" + parts[1]
                    elif not narrative_complete:
                        # Still in narrative part, yield the content
                        narrative += content
                        yield content

                    # Try to parse as JSON to see if it's complete
                    if buffer.strip().startswith('{') and buffer.count('{') == buffer.count('}'):
                        try:
                            result = json.loads(buffer)
                            
                            # Validate that no room updates are included
                            if "updates" in result and "room" in result["updates"]:
                                logger.warning("[Stream Action] AI tried to include room updates - removing them")
                                del result["updates"]["room"]
                            
                            yield result
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
    async def process_npc_interaction(
        message: str,
        npc: NPC,
        player: Player,
        room: Room,
        relevant_memories: List[Dict[str, Any]]
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
    "response": "The NPC's concise response (1-2 sentences max)",
    "memory": "A brief memory to store about this interaction"
}
'''

        prompt = f"""Process this player's interaction with an NPC in a fantasy MUD game.
        Context: {json.dumps(context)}

        CRITICAL: Keep NPC responses to 1-2 sentences maximum. Focus only on the most important information. Remove all fluff and unnecessary elaboration.

        Return a JSON object with this exact structure:
        {json_template}
        """

        response = await client.chat.completions.create(
            model="gpt-4.1-nano-2025-04-14",
            messages=[
                {"role": "system", "content": "You are an NPC in a fantasy MUD game. Keep responses concise (1-2 sentences maximum). Focus only on essential information and remove all fluff. Always return clean JSON without any comments."},
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
    "main_quest_summary": "A concise description of the main quest (1-2 sentences max)",
    "starting_state": {
        "quest_stage": "beginning",
        "world_time": "dawn",
        "weather": "clear"
    }
}
'''

        prompt = f"""Create a new fantasy world and main quest for a MUD game.

        CRITICAL: Keep the main quest summary to 1-2 sentences maximum. Focus only on the essential quest details. Remove all fluff and unnecessary elaboration.

        Return a JSON object with this exact structure:
        {json_template}
        """

        response = await client.chat.completions.create(
            model="gpt-4.1-nano-2025-04-14",
            messages=[
                {"role": "system", "content": "You are a fantasy world creator. Keep descriptions concise (1-2 sentences maximum). Focus only on essential details and remove all fluff. Always return clean JSON without any comments."},
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

    @staticmethod
    async def generate_text(prompt: str) -> str:
        """Generate text using OpenAI"""
        try:
            response = await client.chat.completions.create(
                model="gpt-4.1-nano-2025-04-14",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Keep responses concise (1-2 sentences maximum). Focus only on essential information and remove all fluff. Always return clean, valid responses."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"[Generate Text] Error generating text: {str(e)}")
            raise