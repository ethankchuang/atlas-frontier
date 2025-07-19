from typing import Dict, List, Optional, Tuple
from datetime import datetime
import time
from .models import Room, Player, NPC, GameState, Direction
from .database import Database
from .ai_handler import AIHandler
import uuid
import asyncio
import time
from .ai_handler import AIHandler
from .database import Database
from .rate_limiter import RateLimiter
import logging
from typing import Dict, Any, List, Optional, Tuple
from .models import Player, Room, GameState, ActionRecord
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class GameManager:
    def __init__(self):
        self.db = Database()
        self.ai_handler = AIHandler()
        self.rate_limiter = RateLimiter(self.db)
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

    async def initialize_game(self) -> GameState:
        """Initialize a new game world"""
        start_time = time.time()
        logger.info(f"[Performance] Starting game initialization")
        
        game_state = await self.ai_handler.generate_world_seed()
        await self.db.set_game_state(game_state.dict())
        
        elapsed = time.time() - start_time
        logger.info(f"[Performance] Game initialization completed in {elapsed:.2f}s")
        return game_state

    async def create_player(self, name: str) -> Player:
        """Create a new player"""
        start_time = time.time()
        logger.info(f"[Performance] Creating player: {name}")
        
        player_id = f"player_{str(uuid.uuid4())}"
        starting_room = "room_start"  # We'll create this if it doesn't exist

        player = Player(
            id=player_id,
            name=name,
            current_room=starting_room,
            inventory=[],
            quest_progress={},
            memory_log=["Entered the world"]
        )

        await self.db.set_player(player_id, player.dict())
        await self.ensure_starting_room()
        await self.db.add_to_room_players(starting_room, player_id)

        # Create a new game session for the player
        session_id = await self.db.create_game_session(player_id)
        logger.info(f"[GameManager] Created session {session_id} for player {player_id}")

        elapsed = time.time() - start_time
        logger.info(f"[Performance] Player creation completed in {elapsed:.2f}s for {name}")
        return player

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
        title, description, image_prompt = await self.ai_handler.generate_room_description(
            context={"is_starting_room": True}
        )
        content_time = time.time() - content_start
        logger.info(f"[Performance] Starting room content generation took {content_time:.2f}s")

        # Get current players in the room from Redis set
        players_in_room = await self.db.get_room_players(room_id)

        # Create room with title and description immediately (progressive loading)
        room = await self.create_room_with_coordinates(
            room_id=room_id,
            x=x,
            y=y,
            title=title,
            description=description,
            image_url="",  # No image yet
            players=players_in_room,
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
            
            async for chunk in self.ai_handler.stream_action(
                player=player,
                room=room,
                game_state=game_state,
                npcs=npcs,
                action=action
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
        logger.info(f"[Performance] Discovery check took {discovery_check_time:.2f}s")
        
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

    async def handle_room_movement(
        self, 
        player: Player, 
        current_room: Room, 
        action: str, 
        ai_suggested_room_id: str
    ) -> Tuple[str, Room]:
        """
        Handle player movement to a new room using discovery system.
        Each coordinate has two states: discovered and undiscovered.
        Returns (actual_room_id, room_object)
        DEPRECATED: Use handle_room_movement_by_direction instead
        """
        # Determine direction based on action
        action_lower = action.lower()
        if "north" in action_lower:
            direction = Direction.NORTH
        elif "south" in action_lower:
            direction = Direction.SOUTH
        elif "east" in action_lower:
            direction = Direction.EAST
        elif "west" in action_lower:
            direction = Direction.WEST
        elif "up" in action_lower or "climb" in action_lower:
            direction = Direction.UP
        elif "down" in action_lower or "descend" in action_lower:
            direction = Direction.DOWN
        else:
            # Default to north if no direction is specified
            direction = Direction.NORTH

        # Calculate destination coordinates
        current_x, current_y = current_room.x, current_room.y
        new_x, new_y = self._get_coordinates_for_direction(current_x, current_y, direction)
        
        logger.info(f"[Discovery] Player moving from ({current_x}, {current_y}) to ({new_x}, {new_y})")
        
        # Check if destination coordinates have been discovered
        is_discovered = await self.db.is_coordinate_discovered(new_x, new_y)
        
        if is_discovered:
            # DISCOVERED COORDINATE: Load existing room data
            existing_room_data = await self.db.get_room_by_coordinates(new_x, new_y)
            if existing_room_data:
                existing_room_id = existing_room_data["id"]
                logger.info(f"[Discovery] Loading discovered room {existing_room_id} at ({new_x}, {new_y})")
                # Update room data with current players
                players_in_room = await self.db.get_room_players(existing_room_id)
                existing_room_data["players"] = players_in_room
                room = Room(**existing_room_data)
                return existing_room_id, room
            else:
                logger.error(f"[Discovery] Coordinate ({new_x}, {new_y}) marked as discovered but no room found!")
                # Fallback: treat as undiscovered
                is_discovered = False
        
        if not is_discovered:
            # UNDISCOVERED COORDINATE: Trigger preloading and wait for completion
            logger.info(f"[Discovery] Coordinate ({new_x}, {new_y}) not discovered - triggering preloading")
            room_id = f"room_{new_x}_{new_y}"
            
            # Check if room is already being generated
            if await self.db.is_room_generation_locked(room_id):
                logger.info(f"[Discovery] Room {room_id} is already being generated - waiting for completion")
            else:
                # Try to acquire generation lock and start generation
                lock_acquired = await self.db.set_room_generation_lock(room_id)
                if lock_acquired:
                    logger.info(f"[Discovery] Starting generation for room {room_id}")
                    # Start generation in background
                    asyncio.create_task(self._generate_room_details_async(
                        room_id, current_room, direction, player
                    ))
                else:
                    logger.info(f"[Discovery] Could not acquire lock for {room_id} - waiting for completion")
            
            # Wait for room to be generated (with timeout)
            timeout = 60  # 60 seconds timeout
            start_wait = time.time()
            while time.time() - start_wait < timeout:
                # Check if room exists and has content ready
                room_data = await self.db.get_room(room_id)
                if room_data and room_data.get('image_status') in ['content_ready', 'ready']:
                    logger.info(f"[Discovery] Room {room_id} is ready after generation")
                    players_in_room = await self.db.get_room_players(room_id)
                    room_data["players"] = players_in_room
                    room = Room(**room_data)
                    return room_id, room
                
                # Check if room is still being generated
                if room_data and room_data.get('image_status') == 'generating':
                    logger.info(f"[Discovery] Room {room_id} is still generating, waiting...")
                    await asyncio.sleep(1.0)
                    continue
                
                # Room doesn't exist yet, wait a bit more
                await asyncio.sleep(0.5)
            
            # Timeout reached, create fallback room
            logger.warning(f"[Discovery] Timeout waiting for generation at ({new_x}, {new_y}), creating fallback")
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
            items=[],
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
                logger.debug(f"[Performance] Room already exists at ({x}, {y}) - skipped in {elapsed:.2f}s")
                return existing_room_data["id"]
            
            # Check if coordinate is already discovered
            is_discovered = await self.db.is_coordinate_discovered(x, y)
            if is_discovered:
                elapsed = time.time() - start_time
                logger.debug(f"[Performance] Coordinate ({x}, {y}) already discovered - skipped in {elapsed:.2f}s")
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
                    
                    # Generate room description
                    content_start = time.time()
                    title, description, image_prompt = await self.ai_handler.generate_room_description(
                        context={
                            "previous_room": current_room.dict(),
                            "direction": direction,
                            "player": player.dict(),
                            "discovering_new_area": True,
                            "is_preload": True  # Hint that this is preloading
                        }
                    )
                    content_time = time.time() - content_start
                    logger.info(f"[Performance] Room content generation took {content_time:.2f}s for {room_id}")
                    
                    # Create the room with title and description immediately
                    room = await self.create_room_with_coordinates(
                        room_id=room_id,
                        x=x,
                        y=y,
                        title=title,
                        description=description,
                        image_url="",  # No image yet
                        players=[],  # No players in preloaded room
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
            
            # Generate the image
            image_url = await self.ai_handler.generate_room_image(image_prompt)
            
            # Update room with image URL
            room_data = await self.db.get_room(room_id)
            if room_data:
                room_data['image_url'] = image_url
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
        # Get room data
        room_data = await self.db.get_room(room_id)
        if not room_data:
            raise ValueError("Room not found")

        # Update room data with current players from Redis set
        players_in_room = await self.db.get_room_players(room_id)
        room_data["players"] = players_in_room
        room = Room(**room_data)

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

        return {
            "room": room.dict(),
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