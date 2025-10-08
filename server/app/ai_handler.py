from openai import AsyncOpenAI
from typing import Dict, List, Optional, Tuple, AsyncGenerator, Union
import json
from datetime import datetime
from .config import settings
from .models import Room, NPC, Player, GameState
import asyncio
import logging
from .logger import setup_logging
import replicate
import os
from .image_storage import upload_image_to_supabase

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
        context: Dict[str, any],
        style: str = "medieval fantasy"
    ) -> Tuple[str, str, str]:
        """Generate a room title and description"""
        json_template = '''
{
    "title": "A short, evocative title",
    "description": "A concise, creative, atmospheric description with randomly generated elements that fit the biome. (1-2 sentences max)",
    "image_prompt": "A detailed prompt for image generation of this new room based on the context, surrounding rooms, biome, monsters, etc. It's important that it generally fits in with the biome. Be creative. (3-4 sentences)"
}
'''
        # Check if monsters will be present in the room
        monsters_info = ""
        monster_count = context.get("monster_count", 0)
        if monster_count > 0:
            monsters_info = f"\nMonsters: {monster_count} creatures will inhabit this area. Show them as exactly {monster_count} hidden shadowy creatures."
        
        prompt = f"""Generate a concise room description and detailed image prompt for a medieval fantasy MUD game.
        Context: {json.dumps(context)}
        Style: {style}
        {monsters_info}

        CRITICAL: Keep descriptions to 1-2 sentences maximum. Focus only on the most important visual and atmospheric details. Remove all fluff and unnecessary elaboration.

        Return a JSON object with these exact fields:
        {json_template}
        """

        logger.debug(f"[Room Description] Sending prompt to OpenAI: {prompt}")
        try:
            response = await client.chat.completions.create(
                model="gpt-4.1-nano-2025-04-14",
                messages=[
                    {"role": "system", "content": "You are a concise writer for a medieval fantasy MUD game. Always return clean JSON without comments. Focus only on essential details and remove all fluff. Avoid modern, sci-fi, or futuristic elements."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )

            content = response.choices[0].message.content
            logger.debug(f"[Room Description] Received response from OpenAI: {content}")

            # Retry mechanism for JSON parsing
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    result = json.loads(content)
                    return result["title"], result["description"], result["image_prompt"]
                except json.JSONDecodeError as e:
                    logger.warning(f"[Room Description] JSON parsing failed on attempt {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:
                        # Final attempt failed, raise the error
                        logger.error(f"[Room Description] All {max_retries} attempts failed, raising error")
                        raise
                    else:
                        # Wait a bit before retrying
                        await asyncio.sleep(0.5)
                        continue
                except Exception as e:
                    logger.error(f"[Room Description] Unexpected error on attempt {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:
                        # Final attempt failed, raise the error
                        logger.error(f"[Room Description] All {max_retries} attempts failed due to unexpected error, raising error")
                        raise
                    else:
                        # Wait a bit before retrying
                        await asyncio.sleep(0.5)
                        continue
        except Exception as e:
            logger.error(f"[Room Description] Error generating room description: {str(e)}")
            raise

    @staticmethod
    async def generate_room_image(prompt: str, room_id: Optional[str] = None) -> str:
        """Generate an image for a room using the configured provider and upload to Supabase"""
        if not settings.IMAGE_GENERATION_ENABLED:
            logger.info("[Image Generation] Image generation is disabled")
            return ""

        import time
        img_gen_start = time.time()
        try:
            logger.info(f"[Image Generation] Generating image with prompt: {prompt}")
            logger.info(f"⏱️ [TIMING] Starting image generation...")

            # Generate the image (returns temporary URL)
            gen_start = time.time()
            if settings.IMAGE_PROVIDER == "replicate":
                temp_url = await AIHandler._generate_image_replicate(prompt)
            else:
                temp_url = await AIHandler._generate_image_openai(prompt)
            logger.info(f"⏱️ [TIMING] Image generation API: {(time.time() - gen_start)*1000:.2f}ms")

            if not temp_url:
                logger.warning("[Image Generation] No image URL returned from provider")
                return ""

            # Upload to Supabase Storage if room_id is provided
            if room_id:
                logger.info(f"[Image Generation] Uploading image to Supabase for room {room_id}")
                upload_start = time.time()
                supabase_url = await upload_image_to_supabase(temp_url, room_id)
                logger.info(f"⏱️ [TIMING] Image upload to Supabase: {(time.time() - upload_start)*1000:.2f}ms")

                if supabase_url:
                    total_time = time.time() - img_gen_start
                    logger.info(f"[Image Generation] Successfully stored image in Supabase: {supabase_url}")
                    logger.info(f"⏱️ [TIMING] Total image generation + upload: {total_time*1000:.2f}ms")
                    return supabase_url
                else:
                    logger.warning(f"[Image Generation] Failed to upload to Supabase, falling back to temporary URL")
                    return temp_url
            else:
                # No room_id provided, return temporary URL
                total_time = time.time() - img_gen_start
                logger.info("[Image Generation] No room_id provided, returning temporary URL")
                logger.info(f"⏱️ [TIMING] Total image generation: {total_time*1000:.2f}ms")
                return temp_url

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
                
                # Enhanced prompt for better medieval fantasy game images
                enhanced_prompt = f"A detailed, atmospheric medieval fantasy game backdrop, cinematic lighting, high quality, medieval architecture: {prompt}"
                
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
                        prompt=f"A detailed, atmospheric medieval fantasy game scene: {prompt}",
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
        npcs: List[NPC],
        monsters: List[Dict[str, any]] = None,
        chat_history: Optional[List[Dict[str, any]]] = None
    ) -> AsyncGenerator[Union[str, Dict[str, any]], None]:
        """Process a player's action using the LLM with streaming"""
        # Load actual room items for AI context
        room_items = []
        logger.info(f"[AI Context] Room has {len(room.items)} items: {room.items}")
        if room.items:
            from .hybrid_database import HybridDatabase as Database
            db = Database()
            for item_id in room.items:
                try:
                    item_data = await db.get_item(item_id)
                    if item_data:
                        logger.info(f"[AI Context] Loaded room item: {item_data.get('name', 'Unknown')} (ID: {item_id})")
                        room_items.append(item_data)
                    else:
                        logger.warning(f"[AI Context] Room item {item_id} not found in database!")
                except Exception as e:
                    logger.warning(f"[AI Context] Failed to load room item {item_id}: {str(e)}")
        
        logger.info(f"[AI Context] Final room_items for AI: {[item.get('name', 'Unknown') for item in room_items]}")
        
        # Debug: Log the full room items data
        for item in room_items:
            logger.info(f"[AI Context] Room item details: {item}")
        
        # Calculate item availability dynamically from actual room items
        has_three_star = any(item.get('rarity') == 3 for item in room_items)
        two_star_count = sum(1 for item in room_items if item.get('rarity') == 2)
        
        item_availability = {
            "has_three_star_item": has_three_star,
            "two_star_items_available": two_star_count,
            "one_star_items_always_available": True
        }
        
        # Debug: Log the full context being sent to AI
        logger.info(f"[AI Context] Sending context to AI with {len(room_items)} room items")
        
        context = {
            "player": player.dict(),
            "room": room.dict(),
            "game_state": game_state.dict(),
            "npcs": [npc.dict() for npc in npcs],
            "monsters": monsters or [],
            "room_items": room_items,  # Include actual room items
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            "item_availability": item_availability
        }

        # Include recent player messages (last 20 messages, newest first) for continuity
        if chat_history:
            try:
                safe_chat = []
                for m in chat_history[:20]:
                    # Sanitize and keep only relevant fields
                    safe_chat.append({
                        "player_id": m.get("player_id"),
                        "message_type": m.get("message_type"),
                        "message": m.get("message"),
                        "timestamp": m.get("timestamp")
                    })
                context["recent_chat"] = safe_chat
            except Exception as e:
                logger.warning(f"[Stream Action] Failed to include recent chat: {str(e)}")

        json_template = '''
{
    "response": "Copy of the narrative response above",
    "updates": {
        "player": {
            "direction": "optional, possible values: north, south, east, west, up, down",
            "inventory": ["item1", "item2"],
            "memory_log": ["memory entry"]
        },
        "monster_interaction": {
            "monster_id": "optional id of the target monster (if multiple present)",
            "message": "the player's spoken message directed at the monster"
        },
        "combat": {
            "monster_id": "optional id of the target monster (if multiple present)",
            "action": "short natural-language summary of the intended attack"
        },
        "npcs": [
            {
                "id": "npc_id",
                "name": "NPC Name",
                "dialogue_history": [],
                "memory_log": []
            }
        ],
        "item_award": {
            "type": "room_item",
            "item_name": "EXACT name of the room item to award (must match room items list exactly)"
        }
    }
}
'''

        # Build the prompt without nested f-strings to avoid syntax errors
        prompt_parts = [
            f"Process this player action in a fantasy MUD game.",
            f"Context: {json.dumps(context)}",
            "",
            "Use the last 20 player messages in context.recent_chat (newest first) for continuity. Only reference them if relevant to the current action; do not restate them verbatim.",
            "",
        ]
        
        # Add monster description context if there are NON-AGGRESSIVE monsters in the room
        non_aggressive_monsters = [m for m in monsters if m.get('aggressiveness') != 'aggressive'] if monsters else []
        if non_aggressive_monsters and len(non_aggressive_monsters) > 0:
            prompt_parts.extend([
                "ROOM CREATURES:",
                "- The following creatures inhabit this room:",
            ])
            
            # Add creature details similar to items
            for monster in non_aggressive_monsters:
                creature_desc = f"  * {monster.get('name', 'Unknown')}: {monster.get('description', 'A mysterious creature')}"
                if monster.get('aggressiveness') == 'territorial':
                    # Add blocking direction if available
                    creature_desc += f" (guarding a passage)"
                prompt_parts.append(creature_desc)
        
        prompt_parts.extend([
            "",
            "BASIC MOVE VALIDATION:",
            "- If the player attempts an action requiring equipment they don't have, explain why it fails",
            "- Basic physical actions (punch, kick, dodge, block, etc.) are always valid",
            "- Equipment-based actions (slash, shoot, cast spells) require appropriate items",
            "- If unsure about equipment requirements, err on the side of allowing the action",
            "- Keep validation explanations brief and helpful",
            "",
            "CRITICAL RULES FOR CONCISE RESPONSES:",
            "1. Keep narrative responses to 2-4 sentences maximum",
            "2. Focus only on the most important details of what happens",
            "3. Remove all fluff, unnecessary elaboration, and flowery language",
            "4. For movement: Describe only the essential transition and arrival",
            "5. For actions: Focus on the immediate result and key details only",
            "6. You handle ONLY narrative responses and simple state changes",
            "",
            "MOVEMENT INTENT POLICY (CRITICAL):",
            "- If the player clearly intends to move in a direction (north/south/east/west/up/down):",
            "  - Set updates.player.direction to one of: north, south, east, west, up, down.",
            "  - Keep narrative concise and focused on the movement/arrival; do not include extra exposition.",
            "  - Do NOT modify room state directly; the server handles movement and room updates.",
            "",
            "MONSTER DIALOGUE GUIDELINES:",
            "- If the player clearly speaks to a monster/creature (e.g., addresses it, asks it something, tries to converse):",
            "  - Set updates.monster_interaction with the player's spoken message and the target monster_id (if multiple present).",
            "  - Enemies should talk back to player with intelligence according to their data",
            "  - For rooms with exactly one monster, you may omit monster_id; the server will resolve it.",
            "  - Keep the narrative response concise; the server will produce the creature's actual reply.",
            "",
            "COMBAT INTENT POLICY (CRITICAL):",
            "- If the player clearly intends to fight/attack/engage a creature:",
            "  - Set updates.combat with the target monster_id (omit if exactly one monster present) and a short action summary.",
            "  - Do NOT simulate the duel outcome here; the server will initiate combat and handle resolution.",
            "  - Keep the narrative to the immediate pre-fight moment (no long analyses).",
            "",
            "ITEM COMBINATION POLICY (CRITICAL):",
            "- If the player clearly intends to craft/combine 2 or more items:",
            "  - Set updates.item_combination with the item_ids array and optional combination_description.",
            "  - The server will handle the actual item combination and creation.",
            "  - Keep the narrative focused on the crafting process and intent.",
            "",
            "ROOM ITEMS:",
            "- The following items are available in this room:",
        ])
        
        # Add actual room items to the prompt
        if context.get("room_items"):
            for item in context["room_items"]:
                rarity_stars = "★" * item.get('rarity', 1) + "☆" * (4 - item.get('rarity', 1))
                prompt_parts.append(f"  * {rarity_stars} {item['name']}: {item['description']}")
            prompt_parts.append("")
            prompt_parts.append("NOTE: These items exist in the room. Describe them naturally when relevant to the player's action.")
        else:
            prompt_parts.append("  * No specific items have been placed in this room yet")
            prompt_parts.append("")
            prompt_parts.append("NOTE: This room has no pre-existing items. Only describe basic environmental objects when relevant.")
        
        prompt_parts.extend([
            "ITEM AVAILABILITY AND REWARD POLICY (CRITICAL):",
            "- Use context.item_availability to understand what items are available in this room:",
            "  * has_three_star_item: true/false - room has a special rare item",
            "  * two_star_items_available: number - how many normal items remain",
            "  * one_star_items_always_available: always true - basic junk items",
            "- Players can always grab basic environmental objects (rocks, sticks, etc.) for 1-star items",
            "",
            "- **OBSERVATION ACTIONS** (look, examine, search, etc.):",
            "  * Think about how broad the players search is. Are they getting a general survey of the land? Are they investigating a specific point of interest? The amount of information you reveal will depend on this",
            "  * The monsters and items exist in the room, but do not reference them directly",
            "  * The rooms are big, the player cannot see everything at once. If the player doesn't specify a specific search, assume they are searching broadly and just give them an overview of the area. Do not give details like specific items and medium - small sized creatures in broad searches, only give those details in specific searches",
            "  * For example if they just say look around, describe the room very broadly, like what the secenery looks like and maybe some big monsters in the room",
            "  * Do not give precise details for broad inspection, instead give points of interest for the player to specifically search",
            "  * Compare the size of details to size of search. A broad search would reveal overall description of the land and maybe some big creatures standing out. A specific search would reveal specific items and smaller creatures to the player",            "  * Use the chat logs, make sure that the player eventually knows about all of the items and monsters",
            "  * For example: player says 'look around' -> 'you see large trees and mountains in the back. A large dragon is flying around to you left",
            "  * For example: player says 'investigate the trees' -> 'you see a rusty sword leaning against the tree. You also spot a small animal watching you form the distance",
            "  * Describe the room based off the biome and room name"
            "  * DESCRIBE the specific room items NOT by their actual names and instead JUST their descriptions",
            "  * DO NOT say 'no items besides the one listed' or reference game data",
            "  * DO NOT directly refer to items as items, integrate them naturally into the scene. keep the immersion",
            "  * Do NOT include item_award for observation actions",
            "  * ONLY reward items if the player explicitly tries to grab them",
            "  * DO NOT LIST OUT ALL OF THE ITEMS AND / OR MONSTERS IN THE ROOM"
            "",
            "- **UNIFIED ITEM AWARD SYSTEM - CRITICAL INSTRUCTIONS:**",
            "  * ANALYZE player intent to determine what item they want",
            "  * If player says 'grab sword' and there's only one sword-type item → award that room item",
            "  * If player says 'take the crystal' and there's a 'Crystal Shard' → award that room item",
            "  * If player says 'grab a rock' → generate a basic environmental item",
            "  * Use your intelligence to match player intent to available room items",
            "",
            "- **TO AWARD A ROOM ITEM (CRITICAL - MUST DO THIS):**",
            "  * When player grabs a room item, you MUST include item_award in your JSON",
            "  * Set updates.item_award.type to \"room_item\"",
            "  * Set updates.item_award.item_name to the EXACT name from the room items list",
            "  * Example: if room has '★★★ Sword of Blossoming Dawn' and player says 'grab sword'",
            "  * Set: \"item_award\": {\"type\": \"room_item\", \"item_name\": \"Sword of Blossoming Dawn\"}",
            "  * WITHOUT this, the player will NOT receive the item!",
            "",
            "- **TO GENERATE A BASIC ENVIRONMENTAL ITEM:**",
            "  * When player grabs basic environmental objects (rock, stick, branch, leaf, etc.)",
            "  * AND verigiy if the object is reasonable to find in the current environment. If it isn't then do not award the player the item",
            "  * Set updates.item_award.type to \"generate_item\"",
            "  * Optionally set updates.item_award.rarity to 1 (defaults to 1 if not specified)",
            "  * Example: player says 'grab a rock'",
            "  * Set: \"item_award\": {\"type\": \"generate_item\", \"rarity\": 1}",
            "",
            "- **IF ITEM DOESN'T EXIST:**",
            "  * Tell player the item is not there",
            "  * Do NOT include item_award in updates",
            "  * Example: 'grab golden crown' but no crown → 'You don't see any golden crown here'",
            "",
            "UNIFIED ITEM AWARD SYSTEM:",
            "- **For room items**: {\"type\": \"room_item\", \"item_name\": \"Exact Item Name\"}",
            "- **For generated items**: {\"type\": \"generate_item\", \"rarity\": 1}",
            "- **For no item**: Don't include item_award at all",
            "- Focus on analyzing player intent and matching to available room items",
            "- Be intelligent about matching: 'sword' could match 'Blade of Storms', 'crystal' could match 'Crystal Shard'",
            "- CRITICAL: Match player descriptions to item descriptions, not just names!",
            "- Example: 'dark pendant' should match 'Cinderthorn Amulet' because it's described as 'dark, ash-encrusted pendant'",
            "",
            "CRITICAL JSON RULES:",
            "- item_award.type must be either \"room_item\" or \"generate_item\"",
            "- All JSON must be valid and properly formatted",
            "- Do not include any comments or extra text in the JSON",
            "- Only include the updates object if there are actual updates to make",
            "",
            "IMPORTANT: Your response MUST follow this EXACT format:",
            "1. First, write a concise narrative response (1-2 sentences max).",
            "2. Then, add TWO newlines.",
            "3. Finally, provide a JSON object with this exact structure:",
            json_template,
            "",
            "**CRITICAL: ALWAYS include the reward_item field in your JSON response!**",
            "**CRITICAL: Room items → item_award.item_name + deserves_item=false!**",
            "**CRITICAL: Basic environmental items → deserves_item=true (no item_award)!**",
            "",
            "Only include fields in updates that need to be changed. The updates object is optional.",
            "Do not include any comments in the JSON.",
            "",
            "CRITICAL - NEVER DO THIS:",
            "❌ BAD: 'You see no new items besides the one already listed in the room'",
            "❌ BAD: 'There are no additional items besides what's listed'", 
            "❌ BAD: 'No items besides the item already in the room'",
            "❌ BAD: Describing items that aren't in the room items list (like 'a small pouch')",
            "❌ BAD: Making up items that don't exist in the room",
            "❌ BAD: {\"item_award\": {\"item_name\": \"Item\"}} ← MISSING type field!",
            "❌ BAD: {\"item_award\": {\"type\": \"wrong_type\"}} ← type must be room_item or generate_item!",
            "✅ GOOD: Only describe the exact items from the room items list above",
            "✅ GOOD: {\"item_award\": {\"type\": \"room_item\", \"item_name\": \"Item Name\"}}",
            "✅ GOOD: {\"item_award\": {\"type\": \"generate_item\", \"rarity\": 1}}",
            "",
            "FINAL REMINDERS:",
            "- **Room items**: Use {\"type\": \"room_item\", \"item_name\": \"Exact Name\"}",
            "- **Basic environmental items**: Use {\"type\": \"generate_item\", \"rarity\": 1}",
            "- **Non-existent items**: Tell player it's not there, no item_award",
            "- **Always describe items by their actual names, never reference game data**"
        ])
        
        prompt = "\n".join(prompt_parts)

        logger.debug(f"[Stream Action] Sending prompt to OpenAI: {prompt}")
        import time
        ai_request_start = time.time()
        try:
            logger.info(f"⏱️ [TIMING] AI request starting...")
            stream = await client.chat.completions.create(
                model="gpt-4.1-nano-2025-04-14",
                messages=[
                    {"role": "system", "content": "You are the game master of a fantasy MUD game. Keep all responses concise (1-2 sentences maximum). Focus only on environmental details but remove all fluff. Make actions clear and direct. Be generous with item generation - when players grab/take anything, turn it into an item."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                stream=True
            )

            buffer = ""
            narrative = ""
            narrative_complete = False
            chunk_count = 0
            max_chunks = 1000  # Prevent infinite loops
            first_token_time = None

            # Buffering to reduce number of yields and transport overhead
            text_buffer = ""
            buffer_size = 5  # Send chunks of ~5 characters for maximum responsiveness

            async for chunk in stream:
                if first_token_time is None:
                    first_token_time = time.time()
                    logger.info(f"⏱️ [TIMING] First AI token received: {(first_token_time - ai_request_start)*1000:.2f}ms")
                chunk_count += 1
                if chunk_count > max_chunks:
                    logger.warning(f"[Stream] Too many chunks received ({chunk_count}), breaking to prevent infinite loop")
                    break
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    buffer += content

                    # Check if we've hit the JSON part (after two newlines)
                    if not narrative_complete and "\n\n{" in buffer:
                        narrative_complete = True
                        # Flush any remaining text buffer before switching to JSON mode
                        if text_buffer:
                            yield text_buffer
                            text_buffer = ""
                        # Split at the JSON start - don't yield the narrative since it was already streamed
                        parts = buffer.split("\n\n{", 1)
                        if len(parts) == 2:
                            narrative = parts[0].strip()
                            # Don't yield narrative here - it was already streamed character by character
                            buffer = "{" + parts[1]
                    elif not narrative_complete:
                        # Still in narrative part, buffer the content
                        narrative += content
                        text_buffer += content

                        # Only yield when buffer reaches threshold
                        if len(text_buffer) >= buffer_size:
                            yield text_buffer
                            text_buffer = ""

                    # Try to parse as JSON to see if it's complete
                    try:
                        # This will raise if not complete JSON yet
                        parsed = json.loads(buffer)
                        if isinstance(parsed, dict) and "response" in parsed:
                            # Replace response with the already streamed narrative
                            parsed["response"] = narrative.strip()

                            # Set the type field for the main.py message storage logic
                            parsed["type"] = "final"

                            total_ai_time = time.time() - ai_request_start
                            logger.info(f"⏱️ [TIMING] Complete AI response received: {total_ai_time*1000:.2f}ms (TTFT: {(first_token_time - ai_request_start)*1000:.2f}ms)")

                            # Debug: Log the AI response to see if item_award is included
                            logger.info(f"[AI Response] Full AI response: {parsed}")
                            if "updates" in parsed and "item_award" in parsed["updates"]:
                                logger.info(f"[AI Response] Item award found: {parsed['updates']['item_award']}")
                            else:
                                logger.warning(f"[AI Response] No item_award found in AI response!")

                            # OPTIMIZATION: Yield room data immediately for instant UI updates
                            # This allows the client to update the room/image before background tasks complete
                            room_data_payload = {
                                "type": "room_data",
                                "updates": parsed.get("updates", {}),
                                "response": parsed["response"]
                            }
                            logger.info(f"⏱️ [TIMING] Yielding room_data for immediate UI update")
                            yield room_data_payload

                            # Then yield the final response for background processing
                            yield parsed
                            break
                    except json.JSONDecodeError as e:
                        # Not yet complete JSON - this is normal during streaming
                        logger.debug(f"[Stream] JSON not complete yet: {str(e)}")
                        pass
                    except Exception as e:
                        # Other parsing errors - log and continue
                        logger.warning(f"[Stream] JSON parsing error: {str(e)}")
                        pass

        except Exception as e:
            logger.error(f"[Stream Action] Error during streaming: {str(e)}")
            # Yield a fallback response to prevent the client from hanging
            yield {
                "type": "final",
                "content": "An error occurred while processing your action. Please try again.",
                "updates": {}
            }
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

        # Clean the response content to handle potential control characters
        response_content = response.choices[0].message.content
        
        # Remove or replace problematic control characters
        import re
        cleaned_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', response_content)
        
        try:
            result = json.loads(cleaned_content)
        except json.JSONDecodeError as e:
            logger.error(f"[process_npc_interaction] JSON parsing failed: {str(e)}")
            logger.error(f"[process_npc_interaction] Problematic content: {repr(cleaned_content)}")
            
            # Try to extract JSON from the response if it's embedded in other text
            json_match = re.search(r'\{.*\}', cleaned_content, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    logger.info("[process_npc_interaction] Successfully extracted JSON from response")
                except json.JSONDecodeError:
                    logger.error("[process_npc_interaction] Failed to parse extracted JSON, using fallback")
                    # Fallback response
                    result = {
                        "response": "I'm having trouble understanding right now. Could you try asking again?",
                        "memory": "Player attempted interaction but response parsing failed."
                    }
            else:
                logger.error("[process_npc_interaction] No JSON found in response, using fallback")
                result = {
                    "response": "I'm having trouble understanding right now. Could you try asking again?",
                    "memory": "Player attempted interaction but no valid JSON response received."
                }
        
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

        prompt = f"""Create a new classic medieval fantasy world and main quest for a MUD game.

        CRITICAL: Keep the main quest summary to 1-2 sentences maximum. Focus only on the essential quest details. Remove all fluff and unnecessary elaboration.

        Return a JSON object with this exact structure:
        {json_template}
        """

        response = await client.chat.completions.create(
            model="gpt-4.1-nano-2025-04-14",
            messages=[
                {"role": "system", "content": "You are a medieval fantasy world creator. Keep descriptions concise (1-2 sentences maximum). Focus only on essential details and remove all fluff. Avoid modern or sci-fi elements. Always return clean JSON without any comments."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        # Clean the response content to handle potential control characters
        response_content = response.choices[0].message.content
        
        # Remove or replace problematic control characters
        import re
        import time
        
        # Log the raw content for debugging
        logger.debug(f"[generate_world_seed] Raw response: {repr(response_content)}")
        
        # Retry mechanism for JSON parsing
        max_retries = 3
        result = None
        
        for attempt in range(max_retries):
            try:
                # First, try to parse the JSON as-is
                result = json.loads(response_content)
                logger.debug(f"[generate_world_seed] Successfully parsed JSON on attempt {attempt + 1}")
                break  # Success, exit retry loop
                
            except json.JSONDecodeError as e:
                logger.warning(f"[generate_world_seed] JSON parsing failed on attempt {attempt + 1}: {str(e)}")
                
                if attempt == max_retries - 1:
                    # Final attempt failed, use fallback
                    logger.error(f"[generate_world_seed] All {max_retries} attempts failed, using fallback")
                    result = {
                        "world_seed": f"Fallback World {hash(str(time.time())) % 10000}",
                        "main_quest_summary": "Explore this mysterious realm and uncover its secrets.",
                        "starting_state": {
                            "quest_stage": "beginning",
                            "world_time": "dawn", 
                            "weather": "clear"
                        }
                    }
                    break
                else:
                    # Clean the content and try again
                    # Remove control characters except for newlines, tabs, and carriage returns
                    cleaned_content = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', response_content)
                    
                    # Fix escaped newlines that might be causing issues
                    # Replace \\n with \n in the cleaned content
                    cleaned_content = cleaned_content.replace('\\n', '\n')
                    
                    # Then properly escape newlines within string values
                    cleaned_content = re.sub(r'(".*?)\n(.*?")', r'\1\\n\2', cleaned_content, flags=re.DOTALL)
                    
                    logger.debug(f"[generate_world_seed] Cleaned response (attempt {attempt + 1}): {repr(cleaned_content)}")
                    
                    try:
                        result = json.loads(cleaned_content)
                        logger.debug(f"[generate_world_seed] Successfully parsed JSON after cleaning on attempt {attempt + 1}")
                        break  # Success, exit retry loop
                    except json.JSONDecodeError as e2:
                        logger.warning(f"[generate_world_seed] JSON parsing failed after cleaning on attempt {attempt + 1}: {str(e2)}")
                        
                        # Try to extract JSON from the response if it's embedded in other text
                        json_match = re.search(r'\{.*\}', cleaned_content, re.DOTALL)
                        if json_match:
                            try:
                                result = json.loads(json_match.group())
                                logger.info(f"[generate_world_seed] Successfully extracted JSON from response on attempt {attempt + 1}")
                                break  # Success, exit retry loop
                            except json.JSONDecodeError:
                                logger.warning(f"[generate_world_seed] Failed to parse extracted JSON on attempt {attempt + 1}")
                                if attempt == max_retries - 1:
                                    # Final attempt failed, use fallback
                                    logger.error(f"[generate_world_seed] All {max_retries} attempts failed, using fallback")
                                    result = {
                                        "world_seed": f"Fallback World {hash(str(time.time())) % 10000}",
                                        "main_quest_summary": "Explore this mysterious realm and uncover its secrets.",
                                        "starting_state": {
                                            "quest_stage": "beginning",
                                            "world_time": "dawn", 
                                            "weather": "clear"
                                        }
                                    }
                                    break
                                else:
                                    # Wait a bit before retrying
                                    await asyncio.sleep(0.5)
                                    continue
                        else:
                            logger.warning(f"[generate_world_seed] No JSON found in response on attempt {attempt + 1}")
                            if attempt == max_retries - 1:
                                # Final attempt failed, use fallback
                                logger.error(f"[generate_world_seed] All {max_retries} attempts failed, using fallback")
                                result = {
                                    "world_seed": f"Fallback World {hash(str(time.time())) % 10000}",
                                    "main_quest_summary": "Explore this mysterious realm and uncover its secrets.",
                                    "starting_state": {
                                        "quest_stage": "beginning",
                                        "world_time": "dawn",
                                        "weather": "clear"
                                    }
                                }
                                break
                            else:
                                # Wait a bit before retrying
                                await asyncio.sleep(0.5)
                                continue
                                
            except Exception as e:
                logger.error(f"[generate_world_seed] Unexpected error on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    # Final attempt failed, use fallback
                    logger.error(f"[generate_world_seed] All {max_retries} attempts failed due to unexpected error, using fallback")
                    result = {
                        "world_seed": f"Fallback World {hash(str(time.time())) % 10000}",
                        "main_quest_summary": "Explore this mysterious realm and uncover its secrets.",
                        "starting_state": {
                            "quest_stage": "beginning",
                            "world_time": "dawn",
                            "weather": "clear"
                        }
                    }
                    break
                else:
                    # Wait a bit before retrying
                    await asyncio.sleep(0.5)
                    continue

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

    @staticmethod
    async def analyze_duel(prompt: str) -> str:
        """Analyze a duel between two players and determine the outcome"""
        try:
            response = await client.chat.completions.create(
                model="gpt-4.1-nano-2025-04-14",
                messages=[
                    {"role": "system", "content": "You are a fantasy duel referee. Analyze the moves of two players and determine who wins. Be dramatic and engaging, but keep the analysis concise (2-3 sentences). Consider the effectiveness, creativity, and interaction of the moves. Always clearly state who wins."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"[Analyze Duel] Error analyzing duel: {str(e)}")
            return "The duel ended in a draw due to an error in analysis."

    @staticmethod
    async def generate_biome_chunk(chunk_id: str, adjacent_biomes: set) -> Dict[str, str]:
        """Prompt the LLM to generate a new biome name, description, and color for a chunk."""
        # adjacent_biomes is a set of biome names; get their descriptions if possible
        # For now, just join names, but you could pass descriptions if available
        adj_biome_list = list(adjacent_biomes)
        adj_biome_str = ', '.join(sorted(adj_biome_list)) if adj_biome_list else 'None'
        json_template = '''
{
    "name": "A short, generic biome name (e.g., 'forest', 'tundra', 'mountain')",
    "description": "A concise, evocative 1-2 sentence description of the biome.",
    "color": "A hex color code that represents this biome visually (e.g., '#228B22' for forest green, '#D2B48C' for desert tan)"
}
'''
        prompt = f"""
You are inventing a biome for a new region of a medieval fantasy world. The region is a contiguous block of land (a chunk).
- The new biome must be visually and thematically DISTINCT from all adjacent biomes: {adj_biome_str}.
- The biome must have a large, obvious impact on the image and name of all rooms within it (not just subtle differences).
- The biome name must be short, evocative, and creative (e.g., 'crimson forest', 'ashen tundra', 'misty mountain', 'sunken swamp').
- The description should be 1-2 sentences, concise, and evocative.
- The color should be a hex code that visually represents the biome's appearance and feel.
- Choose colors that are visually distinct from typical adjacent biomes (e.g., green for forests, brown/tan for deserts, blue for water, etc.).
- IMPORTANT: Keep all details firmly medieval fantasy (no technology, no sci-fi, no modern references).
- Do not use elaborate or overly specific names.
- Do not use any of these names for the biome: {adj_biome_str}.
Return a JSON object with these exact fields:
{json_template}
"""
        logger.debug(f"[Biome Generation] Sending biome chunk prompt to OpenAI: {prompt}")
        try:
            response = await client.chat.completions.create(
                model="gpt-4.1-nano-2025-04-14",
                messages=[
                    {"role": "system", "content": "You are a worldbuilder for a medieval fantasy MUD game. Always return clean JSON without comments. Keep all content medieval fantasy (no modern/sci-fi). Biome names must be short and generic. Descriptions must be concise and evocative. Colors must be valid hex codes that visually represent the biome. Biomes must be visually and thematically distinct from neighbors, and must have a large impact on the image and name of all rooms within them."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            content = response.choices[0].message.content
            logger.debug(f"[Biome Generation] Received biome chunk response: {content}")
            
            # Retry mechanism for JSON parsing
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    result = json.loads(content)
                    return {"name": result["name"], "description": result["description"], "color": result["color"]}
                except json.JSONDecodeError as e:
                    logger.warning(f"[Biome Generation] JSON parsing failed on attempt {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:
                        # Final attempt failed, raise the error
                        logger.error(f"[Biome Generation] All {max_retries} attempts failed, raising error")
                        raise
                    else:
                        # Wait a bit before retrying
                        await asyncio.sleep(0.5)
                        continue
                except Exception as e:
                    logger.error(f"[Biome Generation] Unexpected error on attempt {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:
                        # Final attempt failed, raise the error
                        logger.error(f"[Biome Generation] All {max_retries} attempts failed due to unexpected error, raising error")
                        raise
                    else:
                        # Wait a bit before retrying
                        await asyncio.sleep(0.5)
                        continue
        except Exception as e:
            logger.error(f"[Biome Generation] Error generating biome chunk: {str(e)}")
            # Generate a simple fallback biome without hardcoded names
            import random
            fallback_biomes = [
                {"name": "forest", "description": "A dense forest with towering trees and dappled sunlight.", "color": "#228B22"},
                {"name": "desert", "description": "A vast expanse of rolling sand dunes under a scorching sun.", "color": "#D2B48C"},
                {"name": "mountain", "description": "Rugged peaks and rocky terrain with thin air and stunning vistas.", "color": "#696969"},
                {"name": "swamp", "description": "A murky wetland with twisted trees and mysterious waters.", "color": "#556B2F"},
                {"name": "tundra", "description": "A frozen landscape of ice and snow stretching to the horizon.", "color": "#F0F8FF"},
                {"name": "plains", "description": "Endless grasslands swaying gently in the wind.", "color": "#90EE90"},
                {"name": "volcano", "description": "A fiery landscape of molten rock and ash-covered slopes.", "color": "#8B0000"}
            ]
            biome = random.choice(fallback_biomes)
            biome["name"] = biome["name"].lower()  # Ensure lowercase
            return biome