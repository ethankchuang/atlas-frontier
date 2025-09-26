from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import time
import uuid
import asyncio
import random
import logging
import noise  # Perlin noise library, make sure it's in requirements.txt
import os # Added for local image saving

from .models import Room, Player, NPC, GameState, Direction, ActionRecord
from .hybrid_database import HybridDatabase as Database
from .ai_handler import AIHandler
from .rate_limiter import RateLimiter
from .biome_manager import BiomeManager

# Helper to get chunk id using Perlin noise
CHUNK_SIZE = 13  # Slightly larger chunk size for bigger biomes
PERLIN_SCALE = 0.09  # Lower scale for less frequent biome changes
CHUNK_QUANTIZATION = 0.35  # Larger quantization for bigger chunks

def get_chunk_id(x, y):
    """Generate chunk ID using Perlin noise for natural biome boundaries"""
    nx = x * PERLIN_SCALE
    ny = y * PERLIN_SCALE
    # Use Perlin noise to get a value, then quantize to chunk grid
    val = noise.pnoise2(nx, ny)
    chunk_x = int(nx // CHUNK_QUANTIZATION)
    chunk_y = int(ny // CHUNK_QUANTIZATION)
    return f"chunk_{chunk_x}_{chunk_y}"

# Super-chunk logic disabled to prevent recursion issues
# def get_super_chunk_id(x, y):
#     """Create super-chunks (clusters of chunks) for even larger biome regions"""
#     # Use a much larger scale for super-chunks
#     nx = x * 0.02  # Much smaller scale for larger regions
#     ny = y * 0.02
#     val = noise.pnoise2(nx, ny)
#     # Very large quantization for super-chunks
#     super_chunk_x = int(nx // 1.0)
#     super_chunk_y = int(ny // 1.0)
#     return f"super_chunk_{super_chunk_x}_{super_chunk_y}"

# Helper to get/set biome for a chunk in Redis
async def get_chunk_biome(self, chunk_id):
    biome_data = await self.db.get_chunk_biome(chunk_id)
    if biome_data:
        return biome_data
    return None

async def set_chunk_biome(self, chunk_id, biome_data):
    await self.db.set_chunk_biome(chunk_id, biome_data)

# Helper to get adjacent chunk ids
def get_adjacent_chunk_ids(chunk_id):
    # chunk_id format: chunk_{x}_{y}
    _, cx, cy = chunk_id.split('_')
    cx, cy = int(cx), int(cy)
    adj = []
    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
        adj.append(f"chunk_{cx+dx}_{cy+dy}")
    return adj

# Helper to get all saved biomes from the database
async def get_all_saved_biomes(self):
    # Should return a list of biome dicts: [{"name": ..., "description": ...}, ...]
    return await self.db.get_all_biomes()

# Helper to save a new biome to the database
async def save_new_biome(self, biome_data):
    await self.db.save_biome(biome_data)

# Update assign_biome_to_chunk to use all saved biomes and equal probability
async def assign_biome_to_chunk(self, chunk_id):
    # Get adjacent chunk biomes
    adj_biomes = set()
    for adj_id in get_adjacent_chunk_ids(chunk_id):
        adj_biome = await get_chunk_biome(self, adj_id)
        if adj_biome:
            adj_biomes.add(adj_biome["name"])
    
    # Temporarily disabled super-chunk logic to debug recursion issues
    # # Also check super-chunk biome for larger regions
    # # Extract coordinates from chunk_id to get super-chunk
    # try:
    #     _, cx, cy = chunk_id.split('_')
    #     cx, cy = int(cx), int(cy)
    #     # Convert chunk coordinates back to approximate world coordinates
    #     world_x = cx * CHUNK_QUANTIZATION / PERLIN_SCALE
    #     world_y = cy * CHUNK_QUANTIZATION / PERLIN_SCALE
    #     super_chunk_id = get_super_chunk_id(world_x, world_y)
    #     super_chunk_biome = await get_chunk_biome(self, super_chunk_id)
    #     if super_chunk_biome:
    #         # If super-chunk has a biome, prefer it (70% chance)
    #         if random.random() < 0.7:
    #             await set_chunk_biome(self, chunk_id, super_chunk_biome)
    #             return super_chunk_biome
    # except:
    #     pass  # Fall back to normal logic if super-chunk lookup fails
    
    # Get all saved biomes
    saved_biomes = await get_all_saved_biomes(self)
    # Exclude biomes used by adjacent chunks
    available_biomes = [b for b in saved_biomes if b["name"] not in adj_biomes]
    choices = available_biomes + ["new"]
    weights = [1] * len(available_biomes) + [1]  # Equal chance for each + new
    # If all saved biomes are adjacent, must generate new
    if not available_biomes:
        chosen = "new"
    else:
        chosen = random.choices(choices, weights=weights, k=1)[0]
    if chosen == "new":
        # Ask LLM for a new biome name/desc
        biome_data = await self.ai_handler.generate_biome_chunk(chunk_id, adj_biomes)
        biome_data["name"] = biome_data["name"].lower()  # Normalize to lowercase
        await save_new_biome(self, biome_data)
    else:
        biome_data = chosen
        biome_data["name"] = biome_data["name"].lower()  # Normalize to lowercase
    await set_chunk_biome(self, chunk_id, biome_data)
    return biome_data

logger = logging.getLogger(__name__)

class GameManager:
    def __init__(self):
        self.db = Database()
        self.ai_handler = AIHandler()
        self.rate_limiter = RateLimiter(self.db)
        self.biome_manager = BiomeManager(self.db, self.ai_handler)
        self.connection_manager = None
        self.logger = logging.getLogger(__name__)
        
        # Rate limiting configuration
        self.rate_limit_config = {
            'limit': 50,  # Maximum actions per interval
            'interval_minutes': 30  # Time window in minutes
        }
        

    def set_connection_manager(self, manager):
        """Set the connection manager instance"""
        self.connection_manager = manager
    
    async def get_player(self, player_id: str) -> Optional[Player]:
        """Get a player by ID"""
        try:
            player_data = await self.db.get_player(player_id)
            if player_data:
                return Player(**player_data)
            return None
        except Exception as e:
            self.logger.error(f"[GameManager] Error getting player {player_id}: {str(e)}")
            return None
    



    async def initialize_game(self) -> GameState:
        """Initialize a new game world"""
        start_time = time.time()
        logger.info(f"[Performance] Starting game initialization")
        
        game_state = await self.ai_handler.generate_world_seed()
        await self.db.set_game_state(game_state.dict())
        
        # Items are now generated on-demand by AI with full context
        logger.info(f"[Item System] Using AI-driven item generation for world: {game_state.world_seed}")
        
        
        elapsed = time.time() - start_time
        logger.info(f"[Performance] Game initialization completed in {elapsed:.2f}s")
        return game_state

    async def create_player(self, name: str, user_id: str) -> Player:
        """Create a new player for a specific user"""
        start_time = time.time()
        logger.info(f"[Performance] Creating player: {name} for user: {user_id}")
        
        player_id = f"player_{str(uuid.uuid4())}"
        starting_room = await self.ensure_starting_room()
        
        player = Player(
            id=player_id,
            user_id=user_id,
            name=name,
            current_room=starting_room.id,
            inventory=[],
            quest_progress={},
            memory_log=[],
            last_action=None,
            last_action_text=None
        )
        
        await self.db.set_player(player_id, player.dict())
        
        # Add player to the starting room's player list
        await self.db.add_to_room_players(starting_room.id, player_id)
        
        elapsed = time.time() - start_time
        logger.info(f"[Performance] Player creation completed in {elapsed:.2f}s for {name}")
        return player

    async def generate_room_monsters(self, room_context: Dict[str, Any]) -> List[str]:
        """Generate 0-3 monsters for a room based on biome and environment"""
        import random
        import uuid
        from .templates.monsters import GenericMonsterTemplate
        
        # Use pre-determined number if provided, otherwise random
        monster_count = room_context.get('monster_count')
        if monster_count is None:
            # Higher chance of monsters: 1-3 monsters more likely
            num_monsters = random.choice([0, 1, 1, 2, 2, 3])
        else:
            num_monsters = monster_count
        
        if num_monsters == 0:
            return []
            
        monster_template = GenericMonsterTemplate()
        monster_ids = []
        
        for i in range(num_monsters):
            try:
                # Create a fresh context for each monster to ensure diversity
                # Don't pass room_context directly as it gets modified
                fresh_context = {
                    'room_id': room_context.get('room_id', ''),
                    'room_title': room_context.get('room_title', ''),
                    'room_description': room_context.get('room_description', ''),
                    'biome': room_context.get('biome', '')
                    # Deliberately exclude aggressiveness, intelligence, size to force random generation
                }
                
                # Generate base monster data with random attributes
                base_data = monster_template.generate_monster_data(fresh_context)
                # Enforce: no aggressive monsters in the starting room
                if room_context.get('room_id') == 'room_start' and base_data.get('aggressiveness') == 'aggressive':
                    # Re-roll to a safe aggressiveness
                    base_data['aggressiveness'] = random.choice(['passive', 'neutral', 'territorial'])
                
                # Generate AI content (name, description, special effects)
                # Use the fresh context that now includes the generated attributes
                prompt = monster_template.generate_prompt(fresh_context)
                ai_response = await self.ai_handler.generate_text(prompt)
                
                generated_data = monster_template.parse_response(ai_response)
                
                # Create complete monster data
                monster_id = f"monster_{uuid.uuid4()}"
                monster_data = {
                    'id': monster_id,
                    'name': generated_data['name'],
                    'description': generated_data['description'],
                    'aggressiveness': base_data['aggressiveness'],
                    'intelligence': base_data['intelligence'],
                    'size': base_data['size'],
                    'special_effects': generated_data['special_effects'],
                    'location': room_context.get('room_id', ''),
                    'health': base_data['health'],
                    'is_alive': True,
                    'properties': {}
                }
                
                # Store monster in database
                await self.db.set_monster(monster_id, monster_data)
                monster_ids.append(monster_id)
                
                logger.info(f"[Monsters] Generated monster {generated_data['name']} ({monster_id}) for room {room_context.get('room_id', 'unknown')}")
                
            except Exception as e:
                logger.error(f"[Monsters] Error generating monster {i+1}: {str(e)}")
                continue
        
        return monster_ids

    async def ensure_starting_room(self) -> Room:
        """Ensure the starting room exists"""
        start_time = time.time()
        logger.info(f"[Performance] Ensuring starting room exists")
        
        room_id = "room_start"
        
        # First check if room already exists by ID
        room_data = await self.db.get_room(room_id)
        if room_data:
            # Room exists - just update players and return it
            room = Room(**room_data)
            players_in_room = await self.db.get_room_players(room_id)
            room.players = players_in_room
            await self.db.set_room(room_id, room.dict())

            # Sanitize: ensure no aggressive monsters in starting room
            try:
                if room.monsters:
                    for monster_id in room.monsters:
                        m = await self.db.get_monster(monster_id)
                        if m and m.get('is_alive', True) and m.get('aggressiveness') == 'aggressive':
                            m['aggressiveness'] = 'neutral'
                            await self.db.set_monster(monster_id, m)
                            logger.info(f"[GameManager] Sanitized starting room monster {monster_id}: set aggressiveness to neutral")
            except Exception as e:
                logger.error(f"[GameManager] Failed to sanitize starting room monsters: {str(e)}")
            
            elapsed = time.time() - start_time
            logger.info(f"[Performance] Starting room already exists, loaded in {elapsed:.2f}s")
            return room
        
        # Room doesn't exist - create new starting room at origin
        x, y = 0, 0  # Starting room is at origin
        
        # Check if there's already a room at the origin coordinates
        existing_room_data = await self.db.get_room_by_coordinates(x, y)
        if existing_room_data:
            # Use existing room at origin as starting room
            existing_room = Room(**existing_room_data)
            # Create an alias so both room IDs point to the same room
            await self.db.set_room(room_id, existing_room.dict())
            players_in_room = await self.db.get_room_players(room_id)
            existing_room.players = players_in_room
            
            elapsed = time.time() - start_time
            logger.info(f"[Performance] Using existing room at origin as starting room in {elapsed:.2f}s")
            return existing_room

        # Create new starting room
        logger.info(f"[Performance] Generating new starting room content")
        content_start = time.time()
        
        # Generate biome for starting room using BiomeManager
        try:
            biome_data = await self.biome_manager.get_biome_for_coordinates(x, y)
            starting_biome = biome_data["name"].lower()  # Normalize to lowercase
            starting_biome_desc = biome_data["description"]
            logger.info(f"[GameManager] Generated starting room biome: {starting_biome}")
        except Exception as e:
            logger.error(f"[GameManager] Error generating starting room biome: {str(e)}")
            # Fallback to simple biome generation
            biome_data = await self.ai_handler.generate_biome_chunk("chunk_0_0", set())
            starting_biome = biome_data["name"].lower()  # Normalize to lowercase
            starting_biome_desc = biome_data["description"]
            await self.db.save_biome(biome_data)
            logger.info(f"[GameManager] Generated fallback biome: {starting_biome}")
        
        # Pre-generate monster count for room description
        import random
        monster_count = random.choice([0, 0, 1, 1, 2, 3])  # Same weighting as monster generation
        
        title, description, image_prompt = await self.ai_handler.generate_room_description(
            context={
                "is_starting_room": True,
                "biome": starting_biome,
                "biome_description": starting_biome_desc,
                "monster_count": monster_count
            }
        )
        content_time = time.time() - content_start
        logger.info(f"[Performance] Starting room content generation took {content_time:.2f}s with biome: {starting_biome}")

        # Get current players in the room from Redis set
        players_in_room = await self.db.get_room_players(room_id)

        # Create room with title, description, and biome immediately (progressive loading)
        room = await self.create_room_with_coordinates(
            room_id=room_id,
            x=x,
            y=y,
            title=title,
            description=description,
            biome=starting_biome,
            image_url="",  # No image yet
            players=players_in_room,
            monster_count=monster_count,  # Pass monster count to room creation
            mark_discovered=True  # Starting room is always discovered
        )

        # Set generation status to content_ready (image still pending)
        await self.db.set_room_generation_status(room_id, "content_ready")
        
        logger.info(f"[Performance] Created starting room with title and description in {content_time:.2f}s")

        # Generate image in background
        asyncio.create_task(self._generate_room_image_background(room_id, image_prompt))

        # Trigger preloading of adjacent rooms for the starting room
        # Create a dummy player for context since we don't have the actual player yet
        dummy_player = Player(
            id="dummy",
            user_id="system",  # Dummy user_id for system player
            name="System",
            current_room=room_id,
            inventory=[],
            quest_progress={},
            memory_log=["Starting room created"]
        )
        
        logger.info(f"[Performance] Triggering initial preload for starting room")
        asyncio.create_task(self.preload_adjacent_rooms(
            x, y, room, dummy_player
        ))

        elapsed = time.time() - start_time
        logger.info(f"[Performance] Starting room creation completed in {elapsed:.2f}s (content: {content_time:.2f}s, image generation in background)")
        return room

    async def process_action(
        self,
        player_id: str,
        action: str
    ) -> Tuple[str, Dict[str, any]]:
        """Process a player's action with rate limiting"""
        start_time = time.time()
        self.logger.info(f"[Performance] Processing action for player {player_id}: {action}")
        
        # Check rate limit before processing
        is_allowed, rate_limit_info = await self.rate_limiter.check_rate_limit(
            player_id, 
            self.rate_limit_config['limit'], 
            self.rate_limit_config['interval_minutes']
        )
        
        if not is_allowed:
            # Player has exceeded rate limit
            error_message = f"You have exceeded the rate limit of {rate_limit_info['limit']} actions per {rate_limit_info['interval_minutes']} minutes. Please wait {rate_limit_info['time_until_reset']} seconds before trying again."
            
            self.logger.warning(f"Rate limit exceeded for {player_id}: {rate_limit_info['action_count']}/{rate_limit_info['limit']} actions")
            
            return error_message, {
                'error': 'rate_limit_exceeded',
                'rate_limit_info': rate_limit_info,
                'message': error_message
            }
        
        # Continue with normal action processing
        try:
            # Load current state
            state_start = time.time()
            player_data = await self.db.get_player(player_id)
            if not player_data:
                return "Player not found", {}
            
            player = Player(**player_data)
            current_room_id = player.current_room
            room_data = await self.db.get_room(current_room_id)
            if not room_data:
                return "Room not found", {}
            
            room = Room(**room_data)
            game_state_data = await self.db.get_game_state()
            game_state = GameState(**game_state_data)
            npcs = []
            for npc_id in room.npcs:
                npc_data = await self.db.get_npc(npc_id)
                if npc_data:
                    npcs.append(NPC(**npc_data))
            
            elapsed = time.time() - state_start
            self.logger.info(f"[Performance] State loading took {elapsed:.2f}s")
            
            # Process with AI
            ai_start = time.time()
            response = ""
            updates = {}
            
            # Load monster details for AI context
            monsters = []
            for monster_id in room.monsters:
                monster_data = await self.db.get_monster(monster_id)
                if monster_data:
                    monsters.append(monster_data)
            
            # Fetch last 20 player messages for AI context (newest-first)
            try:
                recent_chat = await self.db.get_player_messages(player_id, limit=20)
                self.logger.info(f"[GameManager] Fetched {len(recent_chat)} recent messages for player {player_id}")
            except Exception as e:
                self.logger.warning(f"[GameManager] Failed to fetch recent player messages for {player_id}: {str(e)}")
                recent_chat = []
            
            async for chunk in self.ai_handler.stream_action(
                player=player,
                room=room,
                game_state=game_state,
                npcs=npcs,
                monsters=monsters,
                action=action,
                chat_history=recent_chat
            ):
                if isinstance(chunk, dict):
                    # This is the final message with updates
                    response = chunk["response"]
                    updates = chunk.get("updates", {})
                    break
                else:
                    # This is a text chunk - collect it
                    response += chunk
            
            elapsed = time.time() - ai_start
            self.logger.info(f"[Performance] AI processing took {elapsed:.2f}s")
            
            # Apply updates
            if updates:
                self.logger.info(f"[GameManager] Action processed - Updates received: {list(updates.keys())}")
                
                # Handle player updates
                if 'player' in updates:
                    player_updates = updates['player']
                    self.logger.info(f"[GameManager] Player updates: {player_updates}")
                    
                    # Update player data (excluding direction which is handled separately)
                    for key, value in player_updates.items():
                        if key != 'direction' and hasattr(player, key):
                            setattr(player, key, value)
                    
                # Handle movement
                if 'direction' in player_updates:
                    self.logger.info(f"[GameManager] Player attempting to move {player_updates['direction']}")
                    
                    # Clear rejoin immunity when player moves to a different room
                    if player.rejoin_immunity:
                        player.rejoin_immunity = False
                        self.logger.info(f"[GameManager] Cleared rejoin immunity for player {player_id} due to movement")
                    
                    actual_room_id, new_room = await self.handle_room_movement_by_direction(
                        player, 
                        room, 
                        player_updates['direction']
                    )
                    # Update current room after movement
                    player.current_room = actual_room_id
                    new_room_id = actual_room_id
                
                # Handle room generation updates
                if 'room_generation' in updates:
                    room_updates = updates['room_generation']
                    self.logger.info(f"[GameManager] Room updates will be handled by streaming endpoint")
                
                # Save updated player data
                await self.db.set_player(player_id, player.dict())
                self.logger.info(f"[GameManager] Saved updated player data to database: {player_id} -> {player.current_room}")
                
                # Start background preload for new room if player moved
                if 'direction' in updates.get('player', {}):
                    new_room_id = player.current_room
                    if new_room_id != current_room_id:
                        self.logger.info(f"[GameManager] Starting background preload for room {new_room_id}")
                        preload_start = time.time()
                        preload_task = asyncio.create_task(self.preload_adjacent_rooms(
                            new_room.x, new_room.y, new_room, player
                        ))
                        
                        # Add error handling for the background task
                        def handle_preload_error(task):
                            try:
                                task.result()
                                preload_elapsed = time.time() - preload_start
                                logger.info(f"[Performance] Background preload completed in {preload_elapsed:.2f}s for room {new_room_id}")
                            except Exception as e:
                                logger.error(f"[GameManager] Background preload failed for room {new_room_id}: {str(e)}")
                        
                        preload_task.add_done_callback(handle_preload_error)
            
            # Store the action record
            try:
                from .models import ActionRecord
                
                # Create a simple session ID for now (we can enhance this later)
                session_id = f"session_{player_id}_{datetime.utcnow().strftime('%Y%m%d')}"
                
                action_record = ActionRecord(
                    player_id=player_id,
                    room_id=current_room_id,
                    action=action,
                    ai_response=response,
                    updates=updates,
                    session_id=session_id,
                    metadata={
                        "room_title": room.title,
                        "npcs_present": [npc.name for npc in npcs],
                        "ai_model": "gpt-4o"
                    }
                )
                
                await self.db.store_action_record(player_id, action_record)
                self.logger.info(f"[Storage] Stored action record for player {player_id}")
                
            except Exception as e:
                self.logger.error(f"Error storing action record: {str(e)}")
            
            elapsed = time.time() - start_time
            self.logger.info(f"[Performance] Total action processing took {elapsed:.2f}s")
            return response, updates
            
        except Exception as e:
            self.logger.error(f"Error processing action for {player_id}: {str(e)}")
            return f"Error processing action: {str(e)}", {}

    async def handle_room_movement_by_direction(
        self, 
        player: Player, 
        current_room: Room, 
        direction: str
    ) -> Tuple[str, Room]:
        """
        Handle player movement to a new room using discovery system based on direction.
        Rooms should only be created during world creation and preloading.
        This function only loads existing rooms or waits for preloading to complete.
        Returns (actual_room_id, room_object)
        """
        start_time = time.time()
        
        # Convert string direction to Direction enum
        try:
            direction_enum = Direction(direction.lower())
        except ValueError:
            logger.warning(f"[Discovery] Invalid direction '{direction}', defaulting to north")
            direction_enum = Direction.NORTH

        # Calculate destination coordinates
        current_x, current_y = current_room.x, current_room.y
        new_x, new_y = self._get_coordinates_for_direction(current_x, current_y, direction_enum)
        
        logger.info(f"[Performance] Player moving {direction} from ({current_x}, {current_y}) to ({new_x}, {new_y})")
        
        # Check if destination coordinates have been discovered
        discovery_check_start = time.time()
        is_discovered = await self.db.is_coordinate_discovered(new_x, new_y)
        discovery_check_time = time.time() - discovery_check_start
        logger.info(f"[Discovery] Coordinate ({new_x}, {new_y}) discovery status: {is_discovered} (check took {discovery_check_time:.2f}s)")
        
        if is_discovered:
            # DISCOVERED COORDINATE: Load existing room data
            room_load_start = time.time()
            existing_room_data = await self.db.get_room_by_coordinates(new_x, new_y)
            if existing_room_data:
                existing_room_id = existing_room_data["id"]
                logger.info(f"[Performance] Loading discovered room {existing_room_id} at ({new_x}, {new_y})")
                # Update room data with current players
                players_in_room = await self.db.get_room_players(existing_room_id)
                existing_room_data["players"] = players_in_room
                room = Room(**existing_room_data)
                
                room_load_time = time.time() - room_load_start
                total_time = time.time() - start_time
                logger.info(f"[Performance] Discovered room loaded in {room_load_time:.2f}s (total: {total_time:.2f}s)")
                
                # Trigger preloading of adjacent rooms for this discovered room
                logger.info(f"[Discovery] Triggering preload for discovered room {existing_room_id} at ({new_x}, {new_y})")
                asyncio.create_task(self.preload_adjacent_rooms(
                    new_x, new_y, room, player
                ))
                
                return existing_room_id, room
            else:
                logger.error(f"[Discovery] Coordinate ({new_x}, {new_y}) marked as discovered but no room found!")
                # Fallback: treat as undiscovered
                is_discovered = False
        
        if not is_discovered:
            # UNDISCOVERED COORDINATE: Wait for preloading to complete or create placeholder
            logger.info(f"[Discovery] Coordinate ({new_x}, {new_y}) not discovered - waiting for preloading")
            room_id = f"room_{new_x}_{new_y}"
            
            # Wait for room to be generated by preloading (with longer timeout)
            timeout = 60  # 60 seconds timeout (increased from 30)
            start_wait = time.time()
            while time.time() - start_wait < timeout:
                # Check if room exists and has content ready
                room_data = await self.db.get_room(room_id)
                if room_data and room_data.get('image_status') in ['content_ready', 'ready']:
                    logger.info(f"[Discovery] Room {room_id} is ready after waiting for preloading")
                    players_in_room = await self.db.get_room_players(room_id)
                    room_data["players"] = players_in_room
                    room = Room(**room_data)
                    return room_id, room
                
                # Check if room is still being generated
                if room_data and room_data.get('image_status') == 'generating':
                    logger.info(f"[Discovery] Room {room_id} is still generating, waiting...")
                    await asyncio.sleep(1.0)  # Increased wait time
                    continue
                
                # Room doesn't exist yet, wait a bit more
                await asyncio.sleep(0.5)  # Increased wait time
            
            # Timeout reached, create fallback room
            logger.warning(f"[Discovery] Timeout waiting for preloading at ({new_x}, {new_y}), creating fallback")
            placeholder_title = f"Unexplored Area ({direction.title()})"
            placeholder_description = f"You venture {direction} into an unexplored area. The details of this place are still forming in your mind..."
            
            new_room = await self.create_room_with_coordinates(
                room_id=room_id,
                x=new_x,
                y=new_y,
                title=placeholder_title,
                description=placeholder_description,
                image_url="",
                players=[player.id],
                mark_discovered=True
            )
            
            # Trigger preloading of adjacent rooms for this newly created room
            logger.info(f"[Discovery] Triggering preload for newly created room {room_id} at ({new_x}, {new_y})")
            asyncio.create_task(self.preload_adjacent_rooms(
                new_x, new_y, new_room, player
            ))
            
            return room_id, new_room

    
    def _get_coordinates_for_direction(self, current_x: int, current_y: int, direction: Direction) -> Tuple[int, int]:
        """Get coordinates for moving in a direction"""
        if direction == Direction.NORTH:
            return current_x, current_y + 1
        elif direction == Direction.SOUTH:
            return current_x, current_y - 1
        elif direction == Direction.EAST:
            return current_x + 1, current_y
        elif direction == Direction.WEST:
            return current_x - 1, current_y
        else:
            # For UP/DOWN, we'll use the same x,y coordinates for now
            return current_x, current_y

    def _get_opposite_direction(self, direction: Direction) -> Direction:
        """Get the opposite direction"""
        opposites = {
            Direction.NORTH: Direction.SOUTH,
            Direction.SOUTH: Direction.NORTH,
            Direction.EAST: Direction.WEST,
            Direction.WEST: Direction.EAST,
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP
        }
        return opposites[direction]
    
    async def _assign_room_item_distribution(self, biome: str, x: int, y: int) -> Dict[str, Any]:
        """Assign item distribution settings for a room"""
        import random
        
        logger.info(f"[Item Distribution] Checking item distribution for room at ({x}, {y}) in biome '{biome}'")
        
        # Assign 2-star item count (0-4 items per room)
        two_star_count = random.randint(0, 4)
        
        # Check if this room should have a 3-star item
        has_three_star = False
        
        if biome and biome != 'unknown':
            # Check if this biome has a preallocated 3-star room
            # Try different case variations due to case mismatch in storage
            biome_three_star_room = await self.db.get_biome_three_star_room(biome)
            logger.info(f"[Item Distribution] First attempt with '{biome}': {biome_three_star_room}")
            if not biome_three_star_room:
                # Try title case version (this is how they're stored)
                biome_three_star_room = await self.db.get_biome_three_star_room(biome.title())
                logger.info(f"[Item Distribution] Second attempt with '{biome.title()}': {biome_three_star_room}")
            if not biome_three_star_room:
                # Try uppercase version as fallback
                biome_three_star_room = await self.db.get_biome_three_star_room(biome.upper())
                logger.info(f"[Item Distribution] Third attempt with '{biome.upper()}': {biome_three_star_room}")
            logger.info(f"[Item Distribution] Final result for biome '{biome}': {biome_three_star_room}")
            
            if biome_three_star_room:
                # Check if this is the designated 3-star room for this biome
                current_room_id = f"room_{x}_{y}"
                # Special case: starting room at (0, 0) uses "room_start" instead of "room_0_0"
                if x == 0 and y == 0:
                    current_room_id = "room_start"
                
                logger.info(f"[Item Distribution] Current room ID: {current_room_id}, 3-star room ID: {biome_three_star_room}")
                
                # Check for match with current room ID or handle the (0,0) special case
                is_three_star_room = False
                if biome_three_star_room == current_room_id:
                    is_three_star_room = True
                elif x == 0 and y == 0 and biome_three_star_room == "room_0_0":
                    # Handle case where biome manager stored "room_0_0" but we're checking "room_start"
                    is_three_star_room = True
                    logger.info(f"[Item Distribution] Matched room_0_0 with room_start for coordinates (0,0)")
                
                if is_three_star_room:
                    has_three_star = True
                    logger.info(f"[Item Distribution] Room at ({x}, {y}) is the preallocated 3-star room for biome '{biome}'")
            else:
                # Fallback: if no preallocated room exists, use the old hash-based system
                # This handles edge cases where biomes were created before preallocation
                import hashlib
                coord_hash = hashlib.md5(f"{biome}_{x}_{y}".encode()).hexdigest()
                hash_value = int(coord_hash[:8], 16)
                
                if hash_value % 100 == 42:  # Fixed value, not random chance
                    has_three_star = True
                    # Store this room as the 3-star room for this biome
                    await self.db.set_biome_three_star_room(biome, f"room_{x}_{y}")
                    logger.info(f"[Item Distribution] Fallback: Room at ({x}, {y}) designated as 3-star room for biome '{biome}'")
        else:
            logger.info(f"[Item Distribution] Biome is unknown or empty, no 3-star item possible")
        
        result = {
            'two_star_count': two_star_count,
            'has_three_star': has_three_star
        }
        logger.info(f"[Item Distribution] Final distribution for room at ({x}, {y}): {result}")
        return result

    async def _generate_room_items(self, room_id: str, item_distribution: Dict[str, Any], biome: str, room_title: str, room_description: str) -> List[str]:
        """Generate actual items for a room based on its distribution settings"""
        import uuid
        from .templates.items import AIItemGenerator
        
        logger.info(f"[Item Generation] Generating items for room {room_id}: {item_distribution}")
        
        item_ids = []
        item_generator = AIItemGenerator()
        
        # Generate 3-star item if this room has one
        if item_distribution['has_three_star']:
            try:
                item_context = {
                    'world_seed': 'room_generation',  # We'll get the actual world seed later
                    'world_theme': 'fantasy',
                    'room_description': room_description,
                    'room_biome': biome,
                    'room_title': room_title,
                    'situation_context': 'room_generation_3star',
                    'desired_rarity': 3,
                    'database': self.db  # Pass database for recent items context
                }
                
                item_data = await item_generator.generate_item(self.ai_handler, item_context)
                item_id = f"item_{str(uuid.uuid4())}"
                item_data['id'] = item_id  # Add the ID to the item data
                await self.db.set_item(item_id, item_data)
                item_ids.append(item_id)
                
                logger.info(f"[Item Generation] Generated 3-star item '{item_data['name']}' for room {room_id}")
            except Exception as e:
                logger.error(f"[Item Generation] Failed to generate 3-star item for room {room_id}: {str(e)}")
        
        # Generate 2-star items
        for i in range(item_distribution['two_star_count']):
            try:
                item_context = {
                    'world_seed': 'room_generation',
                    'world_theme': 'fantasy',
                    'room_description': room_description,
                    'room_biome': biome,
                    'room_title': room_title,
                    'situation_context': 'room_generation_2star',
                    'desired_rarity': 2,
                    'database': self.db  # Pass database for recent items context
                }
                
                item_data = await item_generator.generate_item(self.ai_handler, item_context)
                item_id = f"item_{str(uuid.uuid4())}"
                item_data['id'] = item_id  # Add the ID to the item data
                await self.db.set_item(item_id, item_data)
                item_ids.append(item_id)
                
                logger.info(f"[Item Generation] Generated 2-star item '{item_data['name']}' for room {room_id}")
            except Exception as e:
                logger.error(f"[Item Generation] Failed to generate 2-star item {i+1} for room {room_id}: {str(e)}")
        
        logger.info(f"[Item Generation] Generated {len(item_ids)} items for room {room_id}")
        return item_ids

    async def create_room_with_coordinates(
        self,
        room_id: str,
        x: int,
        y: int,
        title: str,
        description: str,
        image_url: str = "",
        mark_discovered: bool = True,
        **kwargs
    ) -> Room:
        """Create a room with specific coordinates and auto-connect to adjacent rooms"""
        logger.info(f"[GameManager] Creating room {room_id} at coordinates ({x}, {y})")

        # Extract players from kwargs if provided, otherwise use empty list
        players = kwargs.pop('players', [])

        # Debug logging for biome
        biome = kwargs.get('biome', None)
        logger.info(f"[GameManager] Creating room {room_id} with biome: {biome}")
        logger.info(f"[GameManager] kwargs: {kwargs}")

        # Generate monsters for the room  
        monster_context = {
            'room_id': room_id,
            'room_title': title,
            'room_description': description,
            'biome': kwargs.get('biome', 'unknown'),
            'x': x,
            'y': y,
            'monster_count': kwargs.get('monster_count')  # Use pre-determined count if available
        }
        monsters = await self.generate_room_monsters(monster_context)
        
        # Assign item distribution for this room
        item_distribution = await self._assign_room_item_distribution(kwargs.get('biome', 'unknown'), x, y)
        logger.info(f"[Room Creation] Item distribution for room {room_id}: {item_distribution}")
        
        # Generate actual items for this room based on distribution
        room_items = await self._generate_room_items(room_id, item_distribution, kwargs.get('biome', 'unknown'), title, description)
        logger.info(f"[Room Creation] Generated {len(room_items)} items for room {room_id}: {room_items}")
        
        # Create the room object
        room = Room(
            id=room_id,
            title=title,
            description=description,
            x=x,
            y=y,
            image_url=image_url,
            connections={},
            npcs=[],
            items=room_items,  # Use the generated items
            monsters=monsters,
            players=players,
            visited=True,
            properties={},
            **kwargs
        )

        # Use atomic creation to prevent race conditions
        if mark_discovered:
            success = await self.db.atomic_create_room_at_coordinates(room_id, x, y, room.dict())
            if not success:
                # Another process created a room at these coordinates
                logger.warning(f"[GameManager] Room already exists at ({x}, {y}), loading existing room")
                existing_room_data = await self.db.get_room_by_coordinates(x, y)
                if existing_room_data:
                    existing_room = Room(**existing_room_data)
                    logger.info(f"[GameManager] Loaded existing room {existing_room.id} at ({x}, {y})")
                    return existing_room
                else:
                    raise ValueError(f"Coordinate ({x}, {y}) marked as discovered but no room found")
        else:
            # For non-discovered rooms (like placeholders), use regular save
            await self.db.set_room(room_id, room.dict())
            await self.db.set_room_coordinates(room_id, x, y)

        # Auto-connect to adjacent rooms
        await self.auto_connect_adjacent_rooms(room_id, x, y)

        logger.info(f"[GameManager] Created room {room_id} at ({x}, {y}) with auto-connections")
        return room

    async def auto_connect_adjacent_rooms(self, room_id: str, x: int, y: int):
        """Automatically connect a room to its adjacent rooms"""
        logger.info(f"[GameManager] Auto-connecting room {room_id} at ({x}, {y})")

        # Get adjacent rooms
        adjacent_rooms = await self.db.get_adjacent_rooms(x, y)
        logger.debug(f"[GameManager] Adjacent rooms for ({x}, {y}): {adjacent_rooms}")

        # Get the current room
        room_data = await self.db.get_room(room_id)
        if not room_data:
            logger.error(f"[GameManager] Room {room_id} not found for auto-connection")
            return

        room = Room(**room_data)

        # Connect to each adjacent room
        for direction_str, adjacent_room_id in adjacent_rooms.items():
            if adjacent_room_id:
                try:
                    direction = Direction(direction_str)
                    opposite_direction = self._get_opposite_direction(direction)

                    # Add connection from current room to adjacent room
                    room.connections[direction] = adjacent_room_id
                    logger.debug(f"[GameManager] Added connection {direction} -> {adjacent_room_id}")

                    # Add reverse connection from adjacent room to current room
                    adjacent_room_data = await self.db.get_room(adjacent_room_id)
                    if adjacent_room_data:
                        adjacent_room = Room(**adjacent_room_data)
                        adjacent_room.connections[opposite_direction] = room_id
                        await self.db.set_room(adjacent_room_id, adjacent_room.dict())
                        logger.debug(f"[GameManager] Added reverse connection {opposite_direction} -> {room_id}")

                except ValueError as e:
                    logger.warning(f"[GameManager] Invalid direction {direction_str}: {e}")

        # Save the updated room
        await self.db.set_room(room_id, room.dict())
        logger.info(f"[GameManager] Auto-connection completed for room {room_id}")

    async def preload_adjacent_rooms(self, x: int, y: int, current_room: Room, player: Player):
        """Preload the 4 adjacent rooms (north, south, east, west) in parallel"""
        start_time = time.time()
        logger.info(f"[Performance] Starting preload of adjacent rooms for ({x}, {y})")
        
        # Calculate adjacent coordinates
        adjacent_coords = [
            ("north", x, y + 1),
            ("south", x, y - 1), 
            ("east", x + 1, y),
            ("west", x - 1, y)
        ]
        
        # Create tasks for each adjacent room
        preload_tasks = []
        for direction, adj_x, adj_y in adjacent_coords:
            task = self._preload_single_room(adj_x, adj_y, direction, current_room, player)
            preload_tasks.append(task)
        
        # Execute all preload tasks in parallel
        try:
            results = await asyncio.gather(*preload_tasks, return_exceptions=True)
            
            # Count successful and failed preloads
            successful = sum(1 for r in results if not isinstance(r, Exception))
            failed = len(results) - successful
            
            elapsed = time.time() - start_time
            logger.info(f"[Performance] Preload completed in {elapsed:.2f}s - {successful} successful, {failed} failed")
            
            # Log any errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    direction = adjacent_coords[i][0]
                    logger.error(f"[Preload] Error preloading {direction} room: {str(result)}")
                    
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[Performance] Preload failed after {elapsed:.2f}s: {str(e)}")

    async def _preload_single_room(self, x: int, y: int, direction: str, current_room: Room, player: Player):
        """Preload a single room at the given coordinates"""
        start_time = time.time()
        room_id = f"room_{x}_{y}"
        
        try:
            # Check if room already exists at these coordinates
            existing_room_data = await self.db.get_room_by_coordinates(x, y)
            if existing_room_data:
                elapsed = time.time() - start_time
                logger.info(f"[Preload] Room already exists at ({x}, {y}) - skipped in {elapsed:.2f}s")
                return existing_room_data["id"]
            
            # Check if coordinate is already discovered
            is_discovered = await self.db.is_coordinate_discovered(x, y)
            if is_discovered:
                elapsed = time.time() - start_time
                logger.warning(f"[Preload] Coordinate ({x}, {y}) marked as discovered but no room found! This shouldn't happen. Skipped in {elapsed:.2f}s")
                return None
            
            # Check if coordinate is locked (being operated on by another process)
            if await self.db.is_coordinate_locked(x, y):
                elapsed = time.time() - start_time
                logger.debug(f"[Performance] Coordinate ({x}, {y}) is locked - skipped in {elapsed:.2f}s")
                return None
            
            # Try to acquire coordinate lock
            coordinate_lock_acquired = await self.db.set_coordinate_lock(x, y)
            if not coordinate_lock_acquired:
                elapsed = time.time() - start_time
                logger.debug(f"[Performance] Could not acquire coordinate lock for ({x}, {y}) - skipped in {elapsed:.2f}s")
                return None
            
            try:
                # Double-check that coordinate is still undiscovered after acquiring lock
                is_discovered = await self.db.is_coordinate_discovered(x, y)
                if is_discovered:
                    elapsed = time.time() - start_time
                    logger.debug(f"[Performance] Coordinate ({x}, {y}) was discovered by another process - skipped in {elapsed:.2f}s")
                    return None
                
                # Check if room is already being generated
                if await self.db.is_room_generation_locked(room_id):
                    elapsed = time.time() - start_time
                    logger.debug(f"[Performance] Room {room_id} already being generated - skipped in {elapsed:.2f}s")
                    return room_id
                
                # Try to acquire generation lock
                lock_acquired = await self.db.set_room_generation_lock(room_id)
                if not lock_acquired:
                    elapsed = time.time() - start_time
                    logger.debug(f"[Performance] Could not acquire lock for {room_id} - skipped in {elapsed:.2f}s")
                    return room_id
                
                try:
                    logger.info(f"[Performance] Generating room {room_id} at ({x}, {y}) in direction {direction}")
                    
                    # Set generation status
                    await self.db.set_room_generation_status(room_id, "generating")
                    
                    # Generate biome first using BiomeManager
                    biome_start = time.time()
                    biome_data = await self.biome_manager.get_biome_for_coordinates(x, y)
                    biome = biome_data["name"].lower()  # Normalize to lowercase
                    biome_desc = biome_data["description"]
                    biome_time = time.time() - biome_start
                    logger.info(f"[Performance] Biome generation took {biome_time:.2f}s for {room_id}: {biome}")
                    
                    # Pre-generate monster count for room description
                    import random
                    monster_count = random.choice([0, 0, 1, 1, 2, 3])  # Same weighting as monster generation
                    
                    # Generate room description with biome context
                    content_start = time.time()
                    title, description, image_prompt = await self.ai_handler.generate_room_description(
                        context={
                            "previous_room": current_room.dict(),
                            "direction": direction,
                            "player": player.dict(),
                            "biome": biome,
                            "biome_description": biome_desc,
                            "discovering_new_area": True,
                            "is_preload": True,
                            "monster_count": monster_count
                        }
                    )
                    content_time = time.time() - content_start
                    logger.info(f"[Performance] Room content generation took {content_time:.2f}s for {room_id}")
                    
                    # Create the room with title, description, and biome
                    room = await self.create_room_with_coordinates(
                        room_id=room_id,
                        x=x,
                        y=y,
                        title=title,
                        description=description,
                        biome=biome,  # Include biome in room creation
                        image_url="",  # No image yet
                        players=[],  # No players in preloaded room
                        monster_count=monster_count,  # Pass monster count to room creation
                        mark_discovered=True
                    )
                    
                    # Set generation status to content_ready (image still pending)
                    await self.db.set_room_generation_status(room_id, "content_ready")
                    
                    logger.info(f"[Performance] Created room {room_id} with title and description in {content_time:.2f}s")
                    
                    # Generate image in background
                    asyncio.create_task(self._generate_room_image_background(room_id, image_prompt))
                    
                    elapsed = time.time() - start_time
                    logger.info(f"[Performance] Successfully generated room {room_id} content in {elapsed:.2f}s (image generation in background)")
                    return room_id
                    
                except Exception as e:
                    logger.error(f"[Performance] Error generating room {room_id}: {str(e)}")
                    await self.db.set_room_generation_status(room_id, "error")
                    raise
                    
                finally:
                    # Always release the generation lock
                    await self.db.release_room_generation_lock(room_id)
                    
            finally:
                # Always release the coordinate lock
                await self.db.release_coordinate_lock(x, y)
                
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[Performance] Failed to preload room {room_id} after {elapsed:.2f}s: {str(e)}")
            raise

    async def get_adjacent_biomes(self, x: int, y: int) -> List[str]:
        """Get biomes of adjacent rooms that already exist"""
        adjacent_biomes = []
        
        # Check all 4 adjacent coordinates
        adjacent_coords = [(x, y+1), (x, y-1), (x+1, y), (x-1, y)]
        
        for adj_x, adj_y in adjacent_coords:
            try:
                room_data = await self.db.get_room_by_coordinates(adj_x, adj_y)
                if room_data and "biome" in room_data and room_data["biome"]:
                    adjacent_biomes.append(room_data["biome"])
            except Exception as e:
                logger.debug(f"[Biome] Could not get room at ({adj_x}, {adj_y}): {str(e)}")
                continue
        
        logger.debug(f"[Biome] Found adjacent biomes for ({x}, {y}): {adjacent_biomes}")
        return adjacent_biomes

    async def _generate_room_details_async(self, room_id: str, current_room: Room, direction: str, player: Player):
        """Generate detailed room description and image in the background"""
        try:
            logger.info(f"[Room Generation] Starting background room generation for {room_id}")
            
            # Generate the detailed room description
            title, description, image_prompt = await self.ai_handler.generate_room_description(
                context={
                    "previous_room": current_room.dict(),
                    "direction": direction,
                    "player": player.dict(),
                    "discovering_new_area": True  # Hint to AI that this is exploration
                }
            )
            
            # Update the room with the new details
            room_data = await self.db.get_room(room_id)
            if room_data:
                room_data['title'] = title
                room_data['description'] = description
                room_data['image_prompt'] = image_prompt
                room_data['image_status'] = 'generating'
                await self.db.set_room(room_id, room_data)
                
                logger.info(f"[Room Generation] Updated room {room_id} with detailed description")
                
                # Broadcast the updated room to all players
                await self.broadcast_room_update(room_id, {
                    "type": "room_update",
                    "room": room_data
                })
                
                # Generate image in background
                asyncio.create_task(self._generate_room_image(room_id, image_prompt))
            else:
                logger.warning(f"[Room Generation] Room {room_id} not found when updating details")
                
        except Exception as e:
            logger.error(f"[Room Generation] Error generating room details for {room_id}: {str(e)}")

    async def _generate_room_details_async_from_action(self, room_id: str, current_room: Room, action: str, player: Player):
        """Generate detailed room description and image in the background (from action)"""
        try:
            logger.info(f"[Room Generation] Starting background room generation for {room_id} (from action)")
            
            # Generate the detailed room description
            title, description, image_prompt = await self.ai_handler.generate_room_description(
                context={
                    "previous_room": current_room.dict(),
                    "action": action,
                    "player": player.dict(),
                    "discovering_new_area": True  # Hint to AI that this is exploration
                }
            )
            
            # Update the room with the new details
            room_data = await self.db.get_room(room_id)
            if room_data:
                room_data['title'] = title
                room_data['description'] = description
                room_data['image_prompt'] = image_prompt
                room_data['image_status'] = 'generating'
                await self.db.set_room(room_id, room_data)
                
                logger.info(f"[Room Generation] Updated room {room_id} with detailed description")
                
                # Broadcast the updated room to all players
                await self.broadcast_room_update(room_id, {
                    "type": "room_update",
                    "room": room_data
                })
                
                # Generate image in background
                asyncio.create_task(self._generate_room_image(room_id, image_prompt))
            else:
                logger.warning(f"[Room Generation] Room {room_id} not found when updating details")
                
        except Exception as e:
            logger.error(f"[Room Generation] Error generating room details for {room_id}: {str(e)}")

    async def _generate_room_image(self, room_id: str, image_prompt: str):
        """Generate an image for a room and update the room data"""
        try:
            logger.info(f"[Image Generation] Starting image generation for room {room_id}")
            
            # Set image status to generating
            room_data = await self.db.get_room(room_id)
            if room_data:
                room_data['image_status'] = 'generating'
                await self.db.set_room(room_id, room_data)
                
                # Broadcast room update
                await self.broadcast_room_update(room_id, {
                    "type": "room_update",
                    "room": room_data
                })
            
            # Generate the image (remote URL)
            image_url = await self.ai_handler.generate_room_image(image_prompt)
            
            # Save image locally for stability
            local_url = image_url
            try:
                import aiohttp
                from pathlib import Path
                from .main import _static_dir
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status == 200:
                            data = await resp.read()
                            Path(_static_dir).mkdir(parents=True, exist_ok=True)
                            file_name = f"room_{room_id}.webp"
                            file_path = os.path.join(_static_dir, file_name)
                            with open(file_path, 'wb') as f:
                                f.write(data)
                            local_url = f"/static/{file_name}"
                        else:
                            logger.warning(f"[Image Generation] Failed to fetch remote image ({resp.status}), keeping remote URL")
            except Exception as e:
                logger.error(f"[Image Generation] Error saving local image: {str(e)}")
            
            # Update room with final image URL
            room_data = await self.db.get_room(room_id)
            if room_data:
                room_data['image_url'] = local_url
                room_data['image_status'] = 'ready'
                await self.db.set_room(room_id, room_data)
                
                logger.info(f"[Image Generation] Successfully generated image for room {room_id}")
                
                # Broadcast room update
                await self.broadcast_room_update(room_id, {
                    "type": "room_update",
                    "room": room_data
                })
            else:
                logger.error(f"[Image Generation] Room {room_id} not found when updating image")
                
        except Exception as e:
            logger.error(f"[Image Generation] Error generating image for room {room_id}: {str(e)}")
            
            # Set error status
            room_data = await self.db.get_room(room_id)
            if room_data:
                room_data['image_status'] = 'error'
                await self.db.set_room(room_id, room_data)
                
                # Broadcast room update
                await self.broadcast_room_update(room_id, {
                    "type": "room_update",
                    "room": room_data
                })

    async def _generate_room_image_background(self, room_id: str, image_prompt: str):
        """Generate an image for a room in the background (for rooms that already have content)"""
        try:
            logger.info(f"[Background Image] Starting background image generation for room {room_id}")
            
            # Generate the image
            image_url = await self.ai_handler.generate_room_image(image_prompt)
            
            # Update room with image URL
            room_data = await self.db.get_room(room_id)
            if room_data:
                room_data['image_url'] = image_url
                room_data['image_status'] = 'ready'
                await self.db.set_room(room_id, room_data)
                
                logger.info(f"[Background Image] Successfully generated image for room {room_id}")
                
                # Broadcast room update
                await self.broadcast_room_update(room_id, {
                    "type": "room_update",
                    "room": room_data
                })
            else:
                logger.error(f"[Background Image] Room {room_id} not found when updating image")
                
        except Exception as e:
            logger.error(f"[Background Image] Error generating image for room {room_id}: {str(e)}")
            
            # Set error status
            room_data = await self.db.get_room(room_id)
            if room_data:
                room_data['image_status'] = 'error'
                await self.db.set_room(room_id, room_data)
                
                # Broadcast room update
                await self.broadcast_room_update(room_id, {
                    "type": "room_update",
                    "room": room_data
                })

    async def broadcast_room_update(self, room_id: str, update: dict):
        """Broadcast a room update to all clients in the room"""
        try:
            logger.info(f"[GameManager] Broadcasting room update - room: {room_id}, update type: {update.get('type')}")
            logger.debug(f"[GameManager] Full update data: {update}")

            if not self.connection_manager:
                logger.error("[GameManager] Connection manager not set - cannot broadcast update")
                return

            # Get current room data to ensure we're sending complete state
            room_data = await self.db.get_room(room_id)
            if not room_data:
                logger.error(f"[GameManager] Room {room_id} not found when broadcasting update")
                return

            # If this is a room_update, ensure we're sending complete room state
            if update.get('type') == 'room_update':
                room = Room(**room_data)
                # Update with current players
                room.players = await self.db.get_room_players(room_id)
                # Merge any updates
                if 'room' in update:
                    room_updates = update['room']
                    # Ensure image_url is a string if it exists
                    if 'image_url' in room_updates:
                        image_url = room_updates['image_url']
                        if hasattr(image_url, 'url'):
                            room_updates['image_url'] = image_url.url
                        elif hasattr(image_url, '__str__'):
                            room_updates['image_url'] = str(image_url)
                    room = Room(**{**room.dict(), **room_updates})
                # Send complete room state
                update['room'] = room.dict()
                logger.info(f"[GameManager] Broadcasting complete room state for {room_id}")
                logger.debug(f"[GameManager] Room state: {room.dict()}")

            await self.connection_manager.broadcast_to_room(room_id, update)
            logger.info(f"[GameManager] Successfully broadcast update to room {room_id}")
        except Exception as e:
            logger.error(f"[GameManager] Error broadcasting room update: {str(e)}")
            logger.exception(e)  # Log full traceback

    async def handle_npc_interaction(
        self,
        player_id: str,
        npc_id: str,
        message: str
    ) -> str:
        """Handle player interaction with an NPC"""
        # Get current state
        player_data = await self.db.get_player(player_id)
        if not player_data:
            raise ValueError("Player not found")

        player = Player(**player_data)
        npc_data = await self.db.get_npc(npc_id)
        if not npc_data:
            raise ValueError("NPC not found")

        npc = NPC(**npc_data)
        room_data = await self.db.get_room(player.current_room)
        if not room_data:
            raise ValueError("Room not found")

        room = Room(**room_data)

        # Get relevant memories
        relevant_memories = await self.db.get_npc_memories(
            npc_id=npc_id,
            query=message
        )

        # Process the interaction
        response, new_memory = await self.ai_handler.process_npc_interaction(
            message=message,
            npc=npc,
            player=player,
            room=room,
            relevant_memories=relevant_memories
        )

        # Store the new memory
        await self.db.add_npc_memory(
            npc_id=npc_id,
            memory=new_memory,
            metadata={
                "timestamp": datetime.utcnow().isoformat(),
                "player_id": player_id,
                "room_id": room.id,
                "npc_id": npc_id
            }
        )

        return response

    async def get_room_info(self, room_id: str) -> Dict[str, any]:
        """Get complete information about a room"""
        logger.info(f"[BIOME DEBUG] get_room_info called for room {room_id}")
        # Get room data
        room_data = await self.db.get_room(room_id)
        if not room_data:
            raise ValueError("Room not found")

        # Update room data with current players from Redis set
        players_in_room = await self.db.get_room_players(room_id)
        room_data["players"] = players_in_room
        
        # Debug: Log the biome data before and after Room creation
        logger.info(f"[DEBUG] Room data from DB has biome: {room_data.get('biome')}")
        room = Room(**room_data)
        room_dict = room.dict()
        logger.info(f"[DEBUG] Room.dict() has biome: {room_dict.get('biome')}")
        logger.info(f"[DEBUG] Room object biome attribute: {getattr(room, 'biome', 'MISSING')}")

        # Get player objects
        players = []
        for player_id in players_in_room:
            player_data = await self.db.get_player(player_id)
            if player_data:
                players.append(Player(**player_data))

        # Get NPC objects
        npcs = []
        for npc_id in room.npcs:
            npc_data = await self.db.get_npc(npc_id)
            if npc_data:
                npcs.append(NPC(**npc_data))

        # Ensure biome field is explicitly included in the response
        room_dict = room.dict()
        # Force include biome field from original database data
        room_dict['biome'] = room_data.get('biome')
        
        # Include biome color if available
        if room_data.get('biome'):
            chunk_id = get_chunk_id(room.x, room.y)
            biome_data = await self.db.get_chunk_biome(chunk_id)
            if biome_data and 'color' in biome_data:
                room_dict['biome_color'] = biome_data['color']
        
        return {
            "room": room_dict,
            "players": [p.dict() for p in players],
            "npcs": [n.dict() for n in npcs]
        }

    async def get_world_structure(self) -> Dict[str, any]:
        """Get a summary of the world structure including all rooms and their discovery status"""
        try:
            # Get all room keys from Redis
            from .database import redis_client
            room_keys = [key.decode() if isinstance(key, bytes) else key 
                        for key in redis_client.keys("room:*")]
            
            # Get discovered coordinates
            discovered_coords = await self.db.get_discovered_coordinates()
            
            world_map = {}
            rooms_summary = []
            discovered_count = 0
            undiscovered_count = 0
            
            for room_key in room_keys:
                room_id = room_key.replace("room:", "")
                room_data = await self.db.get_room(room_id)
                
                if room_data:
                    room = Room(**room_data)
                    coord_key = f"({room.x}, {room.y})"
                    coord_lookup = f"{room.x}:{room.y}"
                    
                    # Check discovery status
                    is_discovered = coord_lookup in discovered_coords
                    if is_discovered:
                        discovered_count += 1
                    else:
                        undiscovered_count += 1
                    
                    # Check if there's already a room at these coordinates
                    if coord_key in world_map:
                        logger.warning(f"[World Structure] DUPLICATE COORDINATES: {coord_key} has both {world_map[coord_key]} and {room.id}")
                        world_map[coord_key] += f" AND {room.id}"
                    else:
                        status = "🗺️" if is_discovered else "❓"
                        world_map[coord_key] = f"{status} {room.id}"
                    
                    rooms_summary.append({
                        "id": room.id,
                        "title": room.title,
                        "coordinates": coord_key,
                        "discovered": is_discovered,
                        "connections": {str(direction): dest_id for direction, dest_id in room.connections.items()},
                        "players": room.players
                    })
            
            return {
                "world_map": world_map,
                "rooms": rooms_summary,
                "total_rooms": len(rooms_summary),
                "discovered_rooms": discovered_count,
                "undiscovered_rooms": undiscovered_count,
                "discovery_rate": f"{discovered_count}/{discovered_count + undiscovered_count}"
            }
        except Exception as e:
            logger.error(f"[World Structure] Error getting world structure: {str(e)}")
            return {"error": str(e)}

    # Add a helper function to get the 7x7 local map with room info
    async def get_local_map_with_room_info(self, center_x, center_y, size=7):
        half = size // 2
        local_map = []
        for dx in range(-half, half + 1):
            for dy in range(-half, half + 1):
                x, y = center_x + dx, center_y + dy
                room_data = await self.db.get_room_by_coordinates(x, y)
                if room_data:
                    local_map.append({
                        "x": x,
                        "y": y,
                        "biome": room_data.get("biome"),
                        "name": room_data.get("title"),
                        "description": room_data.get("description", "")
                    })
                # Don't add anything for undiscovered rooms - just skip them
        return local_map