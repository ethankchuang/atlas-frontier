from typing import Dict, List, Optional, Tuple
from datetime import datetime
from .models import Room, Player, NPC, GameState, Direction
from .database import Database
from .ai_handler import AIHandler
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)

class GameManager:
    def __init__(self):
        self.db = Database()
        self.ai = AIHandler()
        self.connection_manager = None  # Will be set by FastAPI app

    def set_connection_manager(self, manager):
        """Set the connection manager instance"""
        self.connection_manager = manager

    async def initialize_game(self) -> GameState:
        """Initialize a new game world"""
        game_state = await self.ai.generate_world_seed()
        await self.db.set_game_state(game_state.dict())
        return game_state

    async def create_player(self, name: str) -> Player:
        """Create a new player"""
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

        return player

    async def ensure_starting_room(self) -> Room:
        """Ensure the starting room exists"""
        room_id = "room_start"
        
        # First check if room already exists by ID
        room_data = await self.db.get_room(room_id)
        if room_data:
            # Room exists - just update players and return it
            room = Room(**room_data)
            players_in_room = await self.db.get_room_players(room_id)
            room.players = players_in_room
            await self.db.set_room(room_id, room.dict())
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
            return existing_room

        # Create new starting room
        title, description, image_prompt = await self.ai.generate_room_description(
            context={"is_starting_room": True}
        )

        image_url = await self.ai.generate_room_image(image_prompt)

        # Get current players in the room from Redis set
        players_in_room = await self.db.get_room_players(room_id)

        # Create room using coordinate system and mark as discovered
        room = await self.create_room_with_coordinates(
            room_id=room_id,
            x=x,
            y=y,
            title=title,
            description=description,
            image_url=image_url,
            players=players_in_room,
            mark_discovered=True  # Starting room is always discovered
        )

        return room

    async def process_action(
        self,
        player_id: str,
        action: str
    ) -> Tuple[str, Dict[str, any]]:
        """Process a player's action"""
        logger.info(f"[GameManager] Processing action for player {player_id}: {action}")

        # Get initial state
        player_data = await self.db.get_player(player_id)
        if not player_data:
            raise ValueError("Player not found")

        player = Player(**player_data)
        current_room_id = player.current_room
        room_data = await self.db.get_room(current_room_id)
        if not room_data:
            raise ValueError("Room not found")

        room = Room(**room_data)
        logger.info(f"[GameManager] Current room: {current_room_id}, Action: {action}")

        # Get game state
        game_state_data = await self.db.get_game_state()
        game_state = GameState(**game_state_data)

        # Get NPCs in the room
        npcs = []
        for npc_id in room.npcs:
            npc_data = await self.db.get_npc(npc_id)
            if npc_data:
                npcs.append(NPC(**npc_data))

        # Process the action through AI (collect streaming chunks)
        response = ""
        updates = {}
        
        async for chunk in self.ai.stream_action(action, player, room, game_state, npcs):
            if isinstance(chunk, dict):
                # This is the final message with updates
                response = chunk["response"]
                updates = chunk.get("updates", {})
                break
            else:
                # This is a text chunk - collect it
                response += chunk
        
        logger.info(f"[GameManager] Action processed - Updates received: {list(updates.keys())}")

        # If player moved to a new room
        if "direction" in updates.get("player", {}):
            direction = updates["player"]["direction"]
            logger.info(f"[GameManager] Player attempting to move {direction}")

            # Use coordinate-based room movement
            actual_room_id, new_room = await self.handle_room_movement_by_direction(
                player, room, direction
            )
            
            # Update the player's destination to the actual room ID
            updates["player"]["current_room"] = actual_room_id
            new_room_id = actual_room_id
            
            logger.info(f"[GameManager] Player moving to room: {new_room_id}")

            # First broadcast exit from current room
            await self.broadcast_room_update(current_room_id, {
                "type": "room_update",
                "room": {"id": current_room_id}
            })

            # Then broadcast entry to new room
            logger.info(f"[GameManager] Broadcasting new room state: {new_room_id}")
            await self.broadcast_room_update(new_room_id, {
                "type": "room_update",
                "room": new_room.dict()
            })

            # Update room players in database
            await self.db.remove_from_room_players(current_room_id, player_id)
            await self.db.add_to_room_players(new_room_id, player_id)
            
            # Remove the direction from updates since it's been processed
            del updates["player"]["direction"]

        # Update player state
        player_updates = updates.get("player", {})
        player_updates["last_action"] = datetime.utcnow().isoformat()
        player_updates["last_action_text"] = action
        player = Player(**{**player.dict(), **player_updates})
        await self.db.set_player(player_id, player.dict())
        logger.info(f"[GameManager] Updated player state: {player_id}")

        # Update current room state if needed (but preserve coordinates)
        if "room" in updates and not updates.get("new_room"):
            room_updates = updates["room"]
            if "players" not in room_updates:
                room_updates["players"] = await self.db.get_room_players(room.id)
            
            # CRITICAL: Never allow AI to change room coordinates - preserve discovery system coordinates
            if "x" in room_updates:
                logger.warning(f"[GameManager] AI tried to change room coordinates - ignoring x={room_updates['x']}")
                del room_updates["x"]
            if "y" in room_updates:
                logger.warning(f"[GameManager] AI tried to change room coordinates - ignoring y={room_updates['y']}")
                del room_updates["y"]
            
            room = Room(**{**room.dict(), **room_updates})
            await self.db.set_room(room.id, room.dict())
            logger.info(f"[GameManager] Broadcasting room update after state change: {room.id}")
            await self.broadcast_room_update(room.id, {
                "type": "room_update",
                "room": room.dict()
            })

        # Update NPCs if needed
        if "npcs" in updates:
            for npc_update in updates["npcs"]:
                npc_id = npc_update["id"]
                npc_data = await self.db.get_npc(npc_id)
                if npc_data:
                    npc = NPC(**{**npc_data, **npc_update})
                    await self.db.set_npc(npc_id, npc.dict())

        return response, updates

    async def handle_room_movement_by_direction(
        self, 
        player: Player, 
        current_room: Room, 
        direction: str
    ) -> Tuple[str, Room]:
        """
        Handle player movement to a new room using discovery system based on direction.
        Each coordinate has two states: discovered and undiscovered.
        Returns (actual_room_id, room_object)
        """
        # Convert string direction to Direction enum
        try:
            direction_enum = Direction(direction.lower())
        except ValueError:
            logger.warning(f"[Discovery] Invalid direction '{direction}', defaulting to north")
            direction_enum = Direction.NORTH

        # Calculate destination coordinates
        current_x, current_y = current_room.x, current_room.y
        new_x, new_y = self._get_coordinates_for_direction(current_x, current_y, direction_enum)
        
        logger.info(f"[Discovery] Player moving {direction} from ({current_x}, {current_y}) to ({new_x}, {new_y})")
        
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
            # UNDISCOVERED COORDINATE: Generate new room and mark as discovered
            logger.info(f"[Discovery] Discovering new coordinate ({new_x}, {new_y})")
            
            # Generate a unique room ID based on coordinates and direction
            import time
            timestamp = str(int(time.time()))
            unique_room_id = f"room_{new_x}_{new_y}_{timestamp}"
            
            # Create a simple placeholder room first to avoid blocking the stream
            # We'll generate the detailed description in the background
            placeholder_title = f"Unexplored Area ({direction.title()})"
            placeholder_description = f"You venture {direction} into an unexplored area. The details of this place are still forming in your mind..."
            
            # Create new room with placeholder content and mark coordinate as discovered
            new_room = await self.create_room_with_coordinates(
                room_id=unique_room_id,
                x=new_x,
                y=new_y,
                title=placeholder_title,
                description=placeholder_description,
                image_url="",
                players=[player.id],
                mark_discovered=True  # Mark as discovered during creation
            )
            
            # Schedule room generation for after streaming response completes
            # We'll trigger this from the main.py after the streaming response finishes
            # asyncio.create_task(self._generate_room_details_async(
            #     unique_room_id, current_room, direction, player
            # ))
            
            logger.info(f"[Discovery] Created and discovered new room {unique_room_id} at ({new_x}, {new_y})")
            return unique_room_id, new_room

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
            # UNDISCOVERED COORDINATE: Generate new room and mark as discovered
            logger.info(f"[Discovery] Discovering new coordinate ({new_x}, {new_y})")
            
            # Ensure unique room ID - if AI suggested room already exists, make it unique
            unique_room_id = ai_suggested_room_id
            existing_room_data = await self.db.get_room(unique_room_id)
            if existing_room_data:
                # Room ID already exists - make it unique
                import time
                timestamp = str(int(time.time()))
                unique_room_id = f"{ai_suggested_room_id}_{timestamp}"
                logger.info(f"[Discovery] Room {ai_suggested_room_id} exists, using unique ID: {unique_room_id}")
            
            # Create a simple placeholder room first to avoid blocking the stream
            # We'll generate the detailed description in the background
            placeholder_title = f"Unexplored Area"
            placeholder_description = f"You venture into an unexplored area. The details of this place are still forming in your mind..."
            
            # Create new room with placeholder content and mark coordinate as discovered
            new_room = await self.create_room_with_coordinates(
                room_id=unique_room_id,
                x=new_x,
                y=new_y,
                title=placeholder_title,
                description=placeholder_description,
                image_url="",
                players=[player.id],
                mark_discovered=True  # Mark as discovered during creation
            )
            
            # Generate the detailed room description in the background
            # NOTE: This is deprecated - background generation should be handled in main.py
            # asyncio.create_task(self._generate_room_details_async_from_action(
            #     unique_room_id, current_room, action, player
            # ))
            
            logger.info(f"[Discovery] Created and discovered new room {unique_room_id} at ({new_x}, {new_y})")
            return unique_room_id, new_room

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

        # Create the room
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

        # Save the room to database
        await self.db.set_room(room_id, room.dict())
        
        # Mark coordinate as discovered if requested
        if mark_discovered:
            await self.db.mark_coordinate_discovered(x, y, room_id)
            logger.info(f"[Discovery] Marked coordinate ({x}, {y}) as discovered")
        else:
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

    async def _generate_room_details_async(self, room_id: str, current_room: Room, direction: str, player: Player):
        """Generate detailed room description and image in the background"""
        try:
            logger.info(f"[Room Generation] Starting background room generation for {room_id}")
            
            # Generate the detailed room description
            title, description, image_prompt = await self.ai.generate_room_description(
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
            title, description, image_prompt = await self.ai.generate_room_description(
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
        """Background task to generate room image and update room data"""
        try:
            # Get current room data
            room_data = await self.db.get_room(room_id)
            if not room_data:
                logger.error(f"Room {room_id} not found when generating image")
                return

            room = Room(**room_data)

            # Set status to generating
            room.image_status = "generating"
            await self.db.set_room(room_id, room.dict())

            # Broadcast status update
            await self.broadcast_room_update(room_id, {
                "type": "room_update",
                "room": {
                    "id": room_id,
                    "image_status": "generating"
                }
            })

            # Generate image
            image_url = await self.ai.generate_room_image(image_prompt)

            if image_url:
                # Update room with image URL
                room.image_url = image_url
                room.image_status = "ready"
                await self.db.set_room(room_id, room.dict())

                # Broadcast update to all clients
                logger.info(f"Broadcasting image update for room {room_id}")
                await self.broadcast_room_update(room_id, {
                    "type": "room_update",
                    "room": {
                        "id": room_id,
                        "image_url": image_url,
                        "image_status": "ready"
                    }
                })
            else:
                # Handle image generation failure
                room.image_status = "error"
                await self.db.set_room(room_id, room.dict())
                await self.broadcast_room_update(room_id, {
                    "type": "room_update",
                    "room": {
                        "id": room_id,
                        "image_status": "error"
                    }
                })

        except Exception as e:
            logger.error(f"Error generating room image: {str(e)}")
            # Update room status to error
            try:
                room_data = await self.db.get_room(room_id)
                if room_data:
                    room = Room(**room_data)
                    room.image_status = "error"
                    await self.db.set_room(room_id, room.dict())
                    await self.broadcast_room_update(room_id, {
                        "type": "room_update",
                        "room": {
                            "id": room_id,
                            "image_status": "error"
                        }
                    })
            except Exception as inner_e:
                logger.error(f"Error updating room status after image generation failure: {str(inner_e)}")

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
        response, new_memory = await self.ai.process_npc_interaction(
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