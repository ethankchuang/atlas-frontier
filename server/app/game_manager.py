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
        room_data = await self.db.get_room(room_id)

        if not room_data:
            title, description, image_prompt = await self.ai.generate_room_description(
                context={"is_starting_room": True}
            )

            image_url = await self.ai.generate_room_image(image_prompt)

            # Get current players in the room from Redis set
            players_in_room = await self.db.get_room_players(room_id)

            room = Room(
                id=room_id,
                title=title,
                description=description,
                image_url=image_url,
                connections={},
                npcs=[],
                items=[],
                players=players_in_room,  # Initialize with current players
                visited=True,
                properties={}
            )

            await self.db.set_room(room_id, room.dict())
            return room

        # Get current players in the room from Redis set
        players_in_room = await self.db.get_room_players(room_id)

        # Update room data with current players
        room_data["players"] = players_in_room
        room = Room(**room_data)

        # Save the updated room data
        await self.db.set_room(room_id, room.dict())
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

        # Process the action through AI
        response, updates = await self.ai.process_action(action, player, room, game_state, npcs)
        logger.info(f"[GameManager] Action processed - Updates received: {list(updates.keys())}")

        # If player moved to a new room
        if "current_room" in updates.get("player", {}) and updates["player"]["current_room"] != player.current_room:
            new_room_id = updates["player"]["current_room"]
            logger.info(f"[GameManager] Player moving to new room: {new_room_id}")

            # Ensure the new room exists before proceeding
            new_room_data = await self.db.get_room(new_room_id)
            if not new_room_data:
                logger.error(f"[GameManager] New room {new_room_id} not found - canceling room transition")
                raise ValueError(f"Destination room {new_room_id} not found")

            # First broadcast exit from current room
            await self.broadcast_room_update(current_room_id, {
                "type": "room_update",
                "room": {"id": current_room_id}
            })

            # Then broadcast entry to new room
            new_room = Room(**new_room_data)
            logger.info(f"[GameManager] Broadcasting new room state: {new_room_id}")
            await self.broadcast_room_update(new_room_id, {
                "type": "room_update",
                "room": new_room.dict()
            })

            # Update room players in database
            await self.db.remove_from_room_players(current_room_id, player_id)
            await self.db.add_to_room_players(new_room_id, player_id)

        # Update player state
        player_updates = updates.get("player", {})
        player_updates["last_action"] = datetime.utcnow().isoformat()
        player_updates["last_action_text"] = action
        player = Player(**{**player.dict(), **player_updates})
        await self.db.set_player(player_id, player.dict())
        logger.info(f"[GameManager] Updated player state: {player_id}")

        # Update current room state if needed
        if "room" in updates and not updates.get("new_room"):
            room_updates = updates["room"]
            if "players" not in room_updates:
                room_updates["players"] = await self.db.get_room_players(room.id)
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