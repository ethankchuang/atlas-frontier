import redis
import chromadb
from chromadb.config import Settings as ChromaSettings
import json
from typing import Any, Dict, List, Optional
from .config import settings
import logging
from .logger import setup_logging
from datetime import datetime
import uuid

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Redis connection
redis_client = redis.from_url(settings.REDIS_URL)

# ChromaDB connection
chroma_client = chromadb.Client(ChromaSettings(
    persist_directory=settings.CHROMA_PERSIST_DIRECTORY,
    is_persistent=True,
    anonymized_telemetry=settings.CHROMA_TELEMETRY_ENABLED,
    allow_reset=settings.CHROMA_ALLOW_RESET
))

# Create collections for different types of data
npc_memory_collection = chroma_client.get_or_create_collection("npc_memories")
room_collection = chroma_client.get_or_create_collection("room_descriptions")

class Database:
    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """Helper method to serialize values for Redis storage"""
        if isinstance(value, bytes):
            return value.decode('utf-8')
        elif isinstance(value, (dict, list)):
            # Handle nested structures
            return json.loads(json.dumps(value, default=str))
        else:
            return str(value) if not isinstance(value, (int, float, bool, type(None))) else value

    @staticmethod
    def _serialize_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Helper method to serialize dictionary data for Redis storage"""
        serializable_data = {}
        for key, value in data.items():
            try:
                serializable_data[key] = Database._serialize_value(value)
            except Exception as e:
                logger.error(f"Error serializing key {key}: {str(e)}")
                raise ValueError(f"Failed to serialize key {key}: {str(e)}")
        return serializable_data

    @staticmethod
    async def get_room(room_id: str) -> Optional[Dict[str, Any]]:
        """Get room data from Redis"""
        try:
            room_data = redis_client.get(f"room:{room_id}")
            if room_data:
                if isinstance(room_data, bytes):
                    room_data = room_data.decode('utf-8')
                return json.loads(room_data)
            return None
        except Exception as e:
            logger.error(f"Error getting room {room_id}: {str(e)}")
            raise

    @staticmethod
    async def set_room(room_id: str, room_data: Dict[str, Any]) -> bool:
        """Save room data to Redis"""
        try:
            logger.debug(f"Setting room {room_id} with data: {room_data}")
            serializable_data = Database._serialize_data(room_data)
            logger.debug(f"Serialized room data: {serializable_data}")
            return redis_client.set(f"room:{room_id}", json.dumps(serializable_data))
        except Exception as e:
            logger.error(f"Error setting room {room_id}: {str(e)}")
            raise

    @staticmethod
    async def get_player(player_id: str) -> Optional[Dict[str, Any]]:
        """Get player data from Redis"""
        try:
            logger.debug(f"[Redis] Getting player {player_id}")
            player_data = redis_client.get(f"player:{player_id}")
            if player_data:
                if isinstance(player_data, bytes):
                    player_data = player_data.decode('utf-8')
                logger.debug(f"[Redis] Found player {player_id} in Redis")
                return json.loads(player_data)
            logger.debug(f"[Redis] Player {player_id} not found in Redis")
            return None
        except Exception as e:
            logger.error(f"Error getting player {player_id}: {str(e)}")
            raise

    @staticmethod
    async def set_player(player_id: str, player_data: Dict[str, Any]) -> bool:
        """Save player data to Redis"""
        try:
            logger.debug(f"[Redis] Setting player {player_id} with data: {player_data}")
            serializable_data = Database._serialize_data(player_data)
            logger.debug(f"[Redis] Serialized player data: {serializable_data}")
            result = redis_client.set(f"player:{player_id}", json.dumps(serializable_data))
            logger.debug(f"[Redis] Set player {player_id} result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error setting player {player_id}: {str(e)}")
            raise

    @staticmethod
    async def get_npc(npc_id: str) -> Optional[Dict[str, Any]]:
        """Get NPC data from Redis"""
        try:
            npc_data = redis_client.get(f"npc:{npc_id}")
            if npc_data:
                if isinstance(npc_data, bytes):
                    npc_data = npc_data.decode('utf-8')
                return json.loads(npc_data)
            return None
        except Exception as e:
            logger.error(f"Error getting NPC {npc_id}: {str(e)}")
            raise

    @staticmethod
    async def set_npc(npc_id: str, npc_data: Dict[str, Any]) -> bool:
        """Save NPC data to Redis"""
        try:
            logger.debug(f"Setting NPC {npc_id} with data: {npc_data}")
            serializable_data = Database._serialize_data(npc_data)
            logger.debug(f"Serialized NPC data: {serializable_data}")
            return redis_client.set(f"npc:{npc_id}", json.dumps(serializable_data))
        except Exception as e:
            logger.error(f"Error setting NPC {npc_id}: {str(e)}")
            raise

    @staticmethod
    async def get_item(item_id: str) -> Optional[Dict[str, Any]]:
        """Get item data from Redis"""
        try:
            item_data = redis_client.get(f"item:{item_id}")
            if item_data:
                if isinstance(item_data, bytes):
                    item_data = item_data.decode('utf-8')
                return json.loads(item_data)
            return None
        except Exception as e:
            logger.error(f"Error getting item {item_id}: {str(e)}")
            raise

    @staticmethod
    async def set_item(item_id: str, item_data: Dict[str, Any]) -> bool:
        """Save item data to Redis"""
        try:
            logger.debug(f"Setting item {item_id} with data: {item_data}")
            serializable_data = Database._serialize_data(item_data)
            logger.debug(f"Serialized item data: {serializable_data}")
            return redis_client.set(f"item:{item_id}", json.dumps(serializable_data))
        except Exception as e:
            logger.error(f"Error setting item {item_id}: {str(e)}")
            raise

    @staticmethod
    async def get_recent_high_rarity_items(min_rarity: int = 2, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recently generated items with specified minimum rarity for AI context"""
        try:
            # Get all item keys
            item_keys = redis_client.keys("item:*")
            
            if not item_keys:
                return []
            
            # Get all items and filter by rarity
            filtered_items = []
            for key in item_keys:
                try:
                    item_data = redis_client.get(key)
                    if item_data:
                        if isinstance(item_data, bytes):
                            item_data = item_data.decode('utf-8')
                        item = json.loads(item_data)
                        if item.get('rarity', 1) >= min_rarity:
                            filtered_items.append(item)
                except Exception as e:
                    logger.warning(f"Error loading item from key {key}: {str(e)}")
                    continue
            
            # Sort by ID (newer items have later UUIDs) and limit
            filtered_items.sort(key=lambda x: x.get('id', ''), reverse=True)
            return filtered_items[:limit]
            
        except Exception as e:
            logger.error(f"Error getting recent high rarity items: {str(e)}")
            return []


    @staticmethod
    async def get_monster_types() -> Optional[List[Dict[str, Any]]]:
        """Get monster types for the current world"""
        try:
            monster_types_data = redis_client.get("monster_types")
            if monster_types_data:
                if isinstance(monster_types_data, bytes):
                    monster_types_data = monster_types_data.decode('utf-8')
                return json.loads(monster_types_data)
            return None
        except Exception as e:
            logger.error(f"Error getting monster types: {str(e)}")
            raise

    @staticmethod
    async def set_monster_types(monster_types_data: List[Dict[str, Any]]) -> bool:
        """Save monster types for the current world"""
        try:
            logger.debug(f"Setting monster types with data: {monster_types_data}")
            # For lists, we need to serialize each item individually
            serializable_data = []
            for monster_data in monster_types_data:
                serializable_monster = {}
                for key, value in monster_data.items():
                    serializable_monster[key] = Database._serialize_value(value)
                serializable_data.append(serializable_monster)
            logger.debug(f"Serialized monster types data: {serializable_data}")
            return redis_client.set("monster_types", json.dumps(serializable_data))
        except Exception as e:
            logger.error(f"Error setting monster types: {str(e)}")
            raise

    @staticmethod
    async def get_monster(monster_id: str) -> Optional[Dict[str, Any]]:
        """Get monster data from Redis"""
        try:
            monster_data = redis_client.get(f"monster:{monster_id}")
            if monster_data:
                if isinstance(monster_data, bytes):
                    monster_data = monster_data.decode('utf-8')
                return json.loads(monster_data)
            return None
        except Exception as e:
            logger.error(f"Error getting monster {monster_id}: {str(e)}")
            raise

    @staticmethod
    async def set_monster(monster_id: str, monster_data: Dict[str, Any]) -> bool:
        """Save monster data to Redis"""
        try:
            logger.debug(f"Setting monster {monster_id} with data: {monster_data}")
            serializable_data = Database._serialize_data(monster_data)
            logger.debug(f"Serialized monster data: {serializable_data}")
            return redis_client.set(f"monster:{monster_id}", json.dumps(serializable_data))
        except Exception as e:
            logger.error(f"Error setting monster {monster_id}: {str(e)}")
            raise

    @staticmethod
    async def add_npc_memory(npc_id: str, memory: str, metadata: Dict[str, Any]) -> None:
        """Add a memory to NPC's vector store"""
        npc_memory_collection.add(
            documents=[memory],
            metadatas=[metadata],
            ids=[f"{npc_id}_{metadata.get('timestamp', '')}"]
        )

    @staticmethod
    async def get_npc_memories(npc_id: str, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Query NPC's relevant memories"""
        results = npc_memory_collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"npc_id": npc_id}
        )
        return results.get("metadatas", [[]])[0]

    @staticmethod
    async def get_game_state() -> Dict[str, Any]:
        """Get global game state"""
        try:
            state_data = redis_client.get("game_state")
            if state_data:
                if isinstance(state_data, bytes):
                    state_data = state_data.decode('utf-8')
                return json.loads(state_data)
            return {}
        except Exception as e:
            logger.error(f"Error getting game state: {str(e)}")
            raise

    @staticmethod
    async def set_game_state(state_data: Dict[str, Any]) -> bool:
        """Save global game state"""
        try:
            logger.debug(f"Setting game state with data: {state_data}")
            serializable_data = Database._serialize_data(state_data)
            logger.debug(f"Serialized game state data: {serializable_data}")
            return redis_client.set("game_state", json.dumps(serializable_data))
        except Exception as e:
            logger.error(f"Error setting game state: {str(e)}")
            raise

    @staticmethod
    async def add_to_room_players(room_id: str, player_id: str) -> bool:
        """Add player to room's player list"""
        try:
            logger.debug(f"Adding player {player_id} to room {room_id}")
            return redis_client.sadd(f"room:{room_id}:players", player_id)
        except Exception as e:
            logger.error(f"Error adding player {player_id} to room {room_id}: {str(e)}")
            raise

    @staticmethod
    async def remove_from_room_players(room_id: str, player_id: str) -> bool:
        """Remove player from room's player list"""
        try:
            logger.debug(f"Removing player {player_id} from room {room_id}")
            return redis_client.srem(f"room:{room_id}:players", player_id)
        except Exception as e:
            logger.error(f"Error removing player {player_id} from room {room_id}: {str(e)}")
            raise

    @staticmethod
    async def get_room_players(room_id: str) -> List[str]:
        """Get list of players in a room"""
        try:
            players = redis_client.smembers(f"room:{room_id}:players")
            # Convert any bytes to strings
            return [p.decode('utf-8') if isinstance(p, bytes) else p for p in players]
        except Exception as e:
            logger.error(f"Error getting players for room {room_id}: {str(e)}")
            raise

    @staticmethod
    async def get_room_by_coordinates(x: int, y: int) -> Optional[Dict[str, Any]]:
        """Get room at specific coordinates"""
        try:
            room_id = redis_client.get(f"coord:{x}:{y}")
            if room_id:
                if isinstance(room_id, bytes):
                    room_id = room_id.decode('utf-8')
                return await Database.get_room(room_id)
            return None
        except Exception as e:
            logger.error(f"Error getting room at coordinates ({x}, {y}): {str(e)}")
            raise

    @staticmethod
    async def set_room_coordinates(room_id: str, x: int, y: int) -> bool:
        """Set coordinate mapping for a room"""
        try:
            logger.debug(f"Setting coordinates ({x}, {y}) for room {room_id}")
            return redis_client.set(f"coord:{x}:{y}", room_id)
        except Exception as e:
            logger.error(f"Error setting coordinates ({x}, {y}) for room {room_id}: {str(e)}")
            raise

    @staticmethod
    async def get_adjacent_rooms(x: int, y: int) -> Dict[str, Optional[str]]:
        """Get adjacent room IDs at coordinates around (x, y)"""
        try:
            adjacent = {}
            directions = [
                ("north", x, y + 1),
                ("south", x, y - 1),
                ("east", x + 1, y),
                ("west", x - 1, y)
            ]
            
            for direction, adj_x, adj_y in directions:
                room_id = redis_client.get(f"coord:{adj_x}:{adj_y}")
                if room_id:
                    if isinstance(room_id, bytes):
                        room_id = room_id.decode('utf-8')
                    adjacent[direction] = room_id
                else:
                    adjacent[direction] = None
            
            return adjacent
        except Exception as e:
            logger.error(f"Error getting adjacent rooms for coordinates ({x}, {y}): {str(e)}")
            raise

    @staticmethod
    async def remove_room_coordinates(x: int, y: int) -> bool:
        """Remove coordinate mapping"""
        try:
            return redis_client.delete(f"coord:{x}:{y}")
        except Exception as e:
            logger.error(f"Error removing coordinates ({x}, {y}): {str(e)}")
            raise

    @staticmethod
    async def is_coordinate_discovered(x: int, y: int) -> bool:
        """Check if a coordinate has been discovered/explored"""
        try:
            discovered = redis_client.get(f"discovered:{x}:{y}")
            return discovered is not None
        except Exception as e:
            logger.error(f"Error checking if coordinate ({x}, {y}) is discovered: {str(e)}")
            return False

    @staticmethod
    async def mark_coordinate_discovered(x: int, y: int, room_id: str) -> bool:
        """Mark a coordinate as discovered and associate it with a room"""
        try:
            logger.debug(f"Marking coordinate ({x}, {y}) as discovered with room {room_id}")
            # Set both the discovery flag and the room mapping
            redis_client.set(f"discovered:{x}:{y}", room_id)
            redis_client.set(f"coord:{x}:{y}", room_id)
            return True
        except Exception as e:
            logger.error(f"Error marking coordinate ({x}, {y}) as discovered: {str(e)}")
            return False

    @staticmethod
    async def get_discovered_coordinates() -> Dict[str, str]:
        """Get all discovered coordinates and their associated room IDs"""
        try:
            discovered_coords = {}
            discovered_keys = redis_client.keys("discovered:*")
            
            for key in discovered_keys:
                key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                coord_part = key_str.replace("discovered:", "")
                room_id = redis_client.get(key)
                if room_id:
                    room_id = room_id.decode('utf-8') if isinstance(room_id, bytes) else room_id
                    discovered_coords[coord_part] = room_id
            
            return discovered_coords
        except Exception as e:
            logger.error(f"Error getting discovered coordinates: {str(e)}")
            return {}

    @staticmethod
    async def remove_coordinate_discovery(x: int, y: int) -> bool:
        """Remove discovery status for a coordinate"""
        try:
            redis_client.delete(f"discovered:{x}:{y}")
            redis_client.delete(f"coord:{x}:{y}")
            return True
        except Exception as e:
            logger.error(f"Error removing discovery for coordinate ({x}, {y}): {str(e)}")
            return False

    @staticmethod
    async def create_active_duel(duel_data: Dict[str, Any]) -> bool:
        """Create an active duel record"""
        try:
            duel_id = duel_data.get('duel_id')
            if not duel_id:
                return False
            logger.debug(f"Creating active duel {duel_id}")
            return redis_client.set(f"active_duel:{duel_id}", json.dumps(duel_data))
        except Exception as e:
            logger.error(f"Error creating active duel: {str(e)}")
            return False

    @staticmethod
    async def get_active_duel(duel_id: str) -> Optional[Dict[str, Any]]:
        """Get an active duel by ID"""
        try:
            duel_data = redis_client.get(f"active_duel:{duel_id}")
            if duel_data:
                if isinstance(duel_data, bytes):
                    duel_data = duel_data.decode('utf-8')
                return json.loads(duel_data)
            return None
        except Exception as e:
            logger.error(f"Error getting active duel {duel_id}: {str(e)}")
            return None

    @staticmethod
    async def get_active_duels_for_player(player_id: str) -> List[Dict[str, Any]]:
        """Get all active duels for a specific player"""
        try:
            active_duels = []
            duel_keys = redis_client.keys("active_duel:*")
            
            for key in duel_keys:
                duel_data = redis_client.get(key)
                if duel_data:
                    if isinstance(duel_data, bytes):
                        duel_data = duel_data.decode('utf-8')
                    duel = json.loads(duel_data)
                    if duel.get('is_active', False) and (duel.get('player1_id') == player_id or duel.get('player2_id') == player_id):
                        active_duels.append(duel)
            
            return active_duels
        except Exception as e:
            logger.error(f"Error getting active duels for player {player_id}: {str(e)}")
            return []

    @staticmethod
    async def end_active_duel(duel_id: str) -> bool:
        """End an active duel"""
        try:
            logger.debug(f"Ending active duel {duel_id}")
            return redis_client.delete(f"active_duel:{duel_id}")
        except Exception as e:
            logger.error(f"Error ending active duel {duel_id}: {str(e)}")
            return False

    @staticmethod
    async def set_room_generation_status(room_id: str, status: str) -> bool:
        """Set room generation status: 'pending', 'generating', 'ready', 'error'"""
        try:
            logger.debug(f"Setting room {room_id} generation status to {status}")
            return redis_client.set(f"room:{room_id}:generation_status", status)
        except Exception as e:
            logger.error(f"Error setting room {room_id} generation status: {str(e)}")
            return False

    @staticmethod
    async def get_room_generation_status(room_id: str) -> Optional[str]:
        """Get room generation status"""
        try:
            status = redis_client.get(f"room:{room_id}:generation_status")
            if status:
                return status.decode('utf-8') if isinstance(status, bytes) else status
            return None
        except Exception as e:
            logger.error(f"Error getting room {room_id} generation status: {str(e)}")
            return None

    @staticmethod
    async def is_room_generating(room_id: str) -> bool:
        """Check if a room is currently being generated"""
        try:
            status = await Database.get_room_generation_status(room_id)
            return status == "generating"
        except Exception as e:
            logger.error(f"Error checking if room {room_id} is generating: {str(e)}")
            return False

    @staticmethod
    async def set_room_generation_lock(room_id: str, lock_duration: int = 300) -> bool:
        """Set a lock to prevent concurrent generation of the same room"""
        try:
            # Use Redis SET with NX (only if not exists) and EX (expiration)
            result = redis_client.set(f"room:{room_id}:generation_lock", "1", ex=lock_duration, nx=True)
            return result is True
        except Exception as e:
            logger.error(f"Error setting generation lock for room {room_id}: {str(e)}")
            return False

    @staticmethod
    async def release_room_generation_lock(room_id: str) -> bool:
        """Release the generation lock for a room"""
        try:
            return redis_client.delete(f"room:{room_id}:generation_lock") > 0
        except Exception as e:
            logger.error(f"Error releasing generation lock for room {room_id}: {str(e)}")
            return False

    @staticmethod
    async def is_room_generation_locked(room_id: str) -> bool:
        """Check if a room generation is locked (being generated by another process)"""
        try:
            lock_exists = redis_client.exists(f"room:{room_id}:generation_lock")
            return lock_exists > 0
        except Exception as e:
            logger.error(f"Error checking generation lock for room {room_id}: {str(e)}")
            return False

    @staticmethod
    async def reset_world() -> None:
        """Reset the entire game world by clearing all data"""
        try:
            # Clear all Redis data (includes coordinate mappings, saved biomes, chunk biome assignments, item types, and monster types)
            redis_client.flushall()
            logger.info("Redis data cleared (including coordinate mappings, saved biomes, chunk biome assignments, item types, and monster types)")

            # Clear ChromaDB collections
            try:
                npc_results = npc_memory_collection.get()
                if npc_results and npc_results.get("ids"):
                    npc_memory_collection.delete(ids=npc_results["ids"])
                logger.info("NPC memories cleared")
            except Exception as e:
                logger.error(f"Error clearing NPC memories: {str(e)}")

            try:
                room_results = room_collection.get()
                if room_results and room_results.get("ids"):
                    room_collection.delete(ids=room_results["ids"])
                logger.info("Room descriptions cleared")
            except Exception as e:
                logger.error(f"Error clearing room descriptions: {str(e)}")
        except Exception as e:
            logger.error(f"Error resetting world: {str(e)}")
            raise

    @staticmethod
    async def set_coordinate_lock(x: int, y: int, lock_duration: int = 300) -> bool:
        """Set a lock to prevent concurrent operations on a specific coordinate"""
        try:
            # Use Redis SET with NX (only if not exists) and EX (expiration)
            result = redis_client.set(f"coord_lock:{x}:{y}", "1", ex=lock_duration, nx=True)
            return result is True
        except Exception as e:
            logger.error(f"Error setting coordinate lock for ({x}, {y}): {str(e)}")
            return False

    @staticmethod
    async def release_coordinate_lock(x: int, y: int) -> bool:
        """Release the coordinate lock"""
        try:
            return redis_client.delete(f"coord_lock:{x}:{y}") > 0
        except Exception as e:
            logger.error(f"Error releasing coordinate lock for ({x}, {y}): {str(e)}")
            return False

    @staticmethod
    async def is_coordinate_locked(x: int, y: int) -> bool:
        """Check if a coordinate is locked (being operated on by another process)"""
        try:
            lock_exists = redis_client.exists(f"coord_lock:{x}:{y}")
            return lock_exists > 0
        except Exception as e:
            logger.error(f"Error checking coordinate lock for ({x}, {y}): {str(e)}")
            return False

    @staticmethod
    async def atomic_create_room_at_coordinates(room_id: str, x: int, y: int, room_data: Dict[str, Any]) -> bool:
        """Atomically create a room at specific coordinates, ensuring no race conditions"""
        try:
            # Use Redis transaction to ensure atomicity
            pipe = redis_client.pipeline()
            
            # Check if coordinate is already discovered
            pipe.get(f"discovered:{x}:{y}")
            pipe.get(f"coord:{x}:{y}")
            
            # Execute the check
            results = pipe.execute()
            discovered_flag = results[0]
            existing_room_id = results[1]
            
            if discovered_flag is not None:
                logger.warning(f"Coordinate ({x}, {y}) already discovered with room {existing_room_id}")
                return False
            
            if existing_room_id is not None:
                logger.warning(f"Coordinate ({x}, {y}) already has room {existing_room_id}")
                return False
            
            # Atomically set the room and coordinate mapping
            pipe.set(f"room:{room_id}", json.dumps(Database._serialize_data(room_data)))
            pipe.set(f"discovered:{x}:{y}", room_id)
            pipe.set(f"coord:{x}:{y}", room_id)
            
            # Execute the transaction
            pipe.execute()
            
            logger.info(f"Atomically created room {room_id} at coordinates ({x}, {y})")
            return True
            
        except Exception as e:
            logger.error(f"Error atomically creating room {room_id} at ({x}, {y}): {str(e)}")
            return False


    @staticmethod
    async def store_player_message(player_id: str, message: 'ChatMessage') -> bool:
        """Store a chat message in the player's message history"""
        try:
            key = f"messages:player:{player_id}"
            message_data = message.dict()
            message_data['timestamp'] = message_data['timestamp'].isoformat()
            
            logger.info(f"[Database] Storing message for player {player_id}: {message_data.get('message', 'No message')[:50]}... (type: {message_data.get('message_type', 'unknown')})")
            logger.info(f"[Database] Message data: {message_data}")
            
            # Add to Redis list (left push for newest first)
            redis_client.lpush(key, json.dumps(message_data))
            
            # Trim to keep only last 1000 messages per player
            redis_client.ltrim(key, 0, 999)
            
            # Set TTL for automatic cleanup
            redis_client.expire(key, 60 * 60 * 24 * 30)  # 30 days
            
            # Verify the message was stored
            stored_count = redis_client.llen(key)
            logger.info(f"[Database] Message stored successfully. Total messages for player {player_id}: {stored_count}")
            return True
        except Exception as e:
            logger.error(f"Error storing player message: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    @staticmethod
    async def get_player_messages(player_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages for a specific player"""
        try:
            key = f"messages:player:{player_id}"
            
            logger.info(f"[Database] Retrieving messages for player {player_id} with limit {limit}")
            logger.info(f"[Database] Redis key: {key}")
            
            # Check if key exists
            key_exists = redis_client.exists(key)
            logger.info(f"[Database] Key exists: {key_exists}")
            
            if not key_exists:
                logger.info(f"[Database] No messages found for player {player_id}")
                return []
            
            # Get total count
            total_count = redis_client.llen(key)
            logger.info(f"[Database] Total messages in Redis for player {player_id}: {total_count}")
            
            # Get messages from Redis list
            messages_data = redis_client.lrange(key, 0, limit - 1)
            logger.info(f"[Database] Retrieved {len(messages_data)} raw message data from Redis")
            
            messages = []
            for i, msg_data in enumerate(messages_data):
                try:
                    message = json.loads(msg_data.decode('utf-8') if isinstance(msg_data, bytes) else msg_data)
                    messages.append(message)
                    logger.info(f"[Database] Parsed message {i+1}: {message.get('message', 'No message')[:50]}... (type: {message.get('message_type', 'unknown')})")
                except json.JSONDecodeError as e:
                    logger.warning(f"[Database] Failed to parse message {i+1}: {str(e)}")
                    continue
            
            logger.info(f"[Database] Successfully retrieved {len(messages)} messages for player {player_id}")
            return messages
            
        except Exception as e:
            logger.error(f"Error getting player messages: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    @staticmethod
    async def store_action_record(player_id: str, action_record: 'ActionRecord') -> bool:
        """Store a player action and AI response"""
        try:
            key = f"actions:player:{player_id}"
            record_data = action_record.dict()
            record_data['timestamp'] = record_data['timestamp'].isoformat()
            
            # Add to Redis list
            redis_client.lpush(key, json.dumps(record_data))
            
            # Trim to keep only last 500 actions per player
            redis_client.ltrim(key, 0, 499)
            
            # Set TTL for automatic cleanup
            redis_client.expire(key, 60 * 60 * 24 * 90)  # 90 days
            
            logger.debug(f"Stored action record for player {player_id}: {action_record.id}")
            return True
        except Exception as e:
            logger.error(f"Error storing action record: {str(e)}")
            raise

    @staticmethod
    async def get_action_history(player_id: Optional[str] = None, room_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get action history with optional filtering"""
        try:
            # Get all action record keys (stored as lists)
            if player_id:
                # Get actions for specific player
                pattern = f"actions:player:{player_id}"
                keys = redis_client.keys(pattern)
            else:
                # Get all player action keys
                pattern = "actions:player:*"
                keys = redis_client.keys(pattern)
            
            if not keys:
                return []
            
            # Get all records
            records = []
            for key in keys:
                try:
                    # Get all actions from the list
                    action_list = redis_client.lrange(key, 0, -1)
                    
                    for action_data in action_list:
                        try:
                            # Parse the JSON action record
                            action = json.loads(action_data.decode('utf-8'))
                            
                            # Apply room filter if specified
                            if room_id and action.get('room_id') != room_id:
                                continue
                            
                            records.append(action)
                        except json.JSONDecodeError as e:
                            logger.warning(f"Error parsing action record: {str(e)}")
                            continue
                            
                except Exception as e:
                    logger.warning(f"Error reading action list {key}: {str(e)}")
                    continue
            
            # Sort by timestamp (newest first) and limit
            records.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return records[:limit]
            
        except Exception as e:
            logger.error(f"Error getting action history: {str(e)}")
            return []

    @staticmethod
    async def get_actions_in_time_window(player_id: str, cutoff_timestamp: str) -> List[Dict[str, Any]]:
        """Get all actions for a player within a specific time window"""
        try:
            # Get actions for specific player
            pattern = f"actions:player:{player_id}"
            keys = redis_client.keys(pattern)
            
            if not keys:
                return []
            
            # Get all records within time window
            records = []
            for key in keys:
                try:
                    # Get all actions from the list
                    action_list = redis_client.lrange(key, 0, -1)
                    
                    for action_data in action_list:
                        try:
                            # Parse the JSON action record
                            action = json.loads(action_data.decode('utf-8'))
                            
                            # Only include actions within the time window
                            action_timestamp = action.get('timestamp', '')
                            if action_timestamp >= cutoff_timestamp:
                                records.append(action)
                            
                        except json.JSONDecodeError as e:
                            logger.warning(f"Error parsing action record: {str(e)}")
                            continue
                            
                except Exception as e:
                    logger.warning(f"Error reading action list {key}: {str(e)}")
                    continue
            
            # Sort by timestamp (newest first)
            records.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            return records
            
        except Exception as e:
            logger.error(f"Error getting actions in time window: {str(e)}")
            return []
    
    
    @staticmethod
    async def get_game_sessions(player_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get game sessions with optional filtering"""
        try:
            # Get all session keys
            pattern = "session:*"
            keys = redis_client.keys(pattern)
            
            if not keys:
                return []
            
            # Get all sessions
            sessions = []
            for key in keys[:limit * 2]:  # Get more than limit to account for filtering
                try:
                    session_data = redis_client.hgetall(key)
                    if session_data:
                        # Convert bytes to strings
                        session = {k.decode('utf-8') if isinstance(k, bytes) else k: 
                                 v.decode('utf-8') if isinstance(v, bytes) else v 
                                 for k, v in session_data.items()}
                        
                        # Apply filters
                        if player_id and session.get('player_id') != player_id:
                            continue
                        
                        sessions.append(session)
                except Exception as e:
                    logger.warning(f"Error reading session {key}: {str(e)}")
                    continue
            
            # Sort by start time (newest first) and limit
            sessions.sort(key=lambda x: x.get('start_time', ''), reverse=True)
            return sessions[:limit]
            
        except Exception as e:
            logger.error(f"Error getting game sessions: {str(e)}")
            return []

    @staticmethod
    async def create_game_session(player_id: str) -> str:
        """Create a new game session"""
        try:
            session_id = str(uuid.uuid4())
            session_data = {
                "session_id": session_id,
                "player_id": player_id,
                "start_time": datetime.utcnow().isoformat(),
                "total_actions": "0",
                "rooms_visited": "[]",
                "items_obtained": "[]"
            }
            
            key = f"session:{session_id}"
            redis_client.hset(key, mapping=session_data)
            redis_client.expire(key, 60 * 60 * 24 * 7)  # 7 days
            
            return session_id
        except Exception as e:
            logger.error(f"Error creating game session: {str(e)}")
            raise

    @staticmethod
    async def update_session(session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data"""
        try:
            key = f"session:{session_id}"
            redis_client.hset(key, mapping=updates)
            return True
        except Exception as e:
            logger.error(f"Error updating session: {str(e)}")
            return False

    @staticmethod
    async def get_chunk_biome(chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get biome data for a chunk from Redis"""
        try:
            biome_data = redis_client.get(f"chunk_biome:{chunk_id}")
            if biome_data:
                if isinstance(biome_data, bytes):
                    biome_data = biome_data.decode('utf-8')
                return json.loads(biome_data)
            return None
        except Exception as e:
            logger.error(f"Error getting chunk biome {chunk_id}: {str(e)}")
            return None

    @staticmethod
    async def set_chunk_biome(chunk_id: str, biome_data: Dict[str, Any]) -> bool:
        """Set biome data for a chunk in Redis"""
        try:
            serializable_data = Database._serialize_data(biome_data)
            return redis_client.set(f"chunk_biome:{chunk_id}", json.dumps(serializable_data))
        except Exception as e:
            logger.error(f"Error setting chunk biome {chunk_id}: {str(e)}")
            return False

    @staticmethod
    async def get_all_biomes() -> List[Dict[str, Any]]:
        """Return a list of all biome dicts ever created"""
        try:
            biome_keys = redis_client.keys("biome:*")
            biomes = []
            for key in biome_keys:
                biome_data = redis_client.get(key)
                if biome_data:
                    if isinstance(biome_data, bytes):
                        biome_data = biome_data.decode('utf-8')
                    try:
                        biomes.append(json.loads(biome_data))
                    except Exception as e:
                        logger.error(f"Error decoding biome {key}: {str(e)}")
                        continue
            return biomes
        except Exception as e:
            logger.error(f"Error getting all biomes: {str(e)}")
            return []

    @staticmethod
    async def get_all_saved_biomes() -> List[Dict[str, Any]]:
        """Return a list of all biome dicts ever created (alias for get_all_biomes)"""
        return await Database.get_all_biomes()

    @staticmethod
    async def save_biome(biome_data: Dict[str, Any]) -> bool:
        """Save a new biome to Redis (use a hash of the name as the key)"""
        try:
            import hashlib
            name = biome_data.get("name", "")
            name_hash = hashlib.sha256(name.encode('utf-8')).hexdigest()[:16]
            key = f"biome:{name_hash}"
            serializable_data = Database._serialize_data(biome_data)
            return redis_client.set(key, json.dumps(serializable_data))
        except Exception as e:
            logger.error(f"Error saving biome {biome_data}: {str(e)}")
            return False

    # Dynamic validation system methods
    @staticmethod
    async def get_world_validation_rules(world_seed: str) -> Optional[Dict[str, Any]]:
        """Get validation rules for a specific world"""
        try:
            rules_data = redis_client.get(f"validation_rules:{world_seed}")
            if rules_data:
                if isinstance(rules_data, bytes):
                    rules_data = rules_data.decode('utf-8')
                return json.loads(rules_data)
            return None
        except Exception as e:
            logger.error(f"Error getting validation rules for world {world_seed}: {str(e)}")
            return None

    @staticmethod
    async def set_world_validation_rules(world_seed: str, rules_data: Dict[str, Any]) -> bool:
        """Set validation rules for a specific world"""
        try:
            serializable_data = Database._serialize_data(rules_data)
            return redis_client.set(f"validation_rules:{world_seed}", json.dumps(serializable_data))
        except Exception as e:
            logger.error(f"Error setting validation rules for world {world_seed}: {str(e)}")
            return False

    @staticmethod
    async def update_validation_rules(world_seed: str, updates: Dict[str, Any]) -> bool:
        """Update validation rules for a world (merge with existing rules)"""
        try:
            existing_rules = await Database.get_world_validation_rules(world_seed)
            if existing_rules:
                existing_rules.update(updates)
            else:
                existing_rules = updates
            
            return await Database.set_world_validation_rules(world_seed, existing_rules)
        except Exception as e:
            logger.error(f"Error updating validation rules for world {world_seed}: {str(e)}")
            return False

    @staticmethod
    async def get_validation_learning_data(world_seed: str) -> List[Dict[str, Any]]:
        """Get learning data for validation rule improvements"""
        try:
            learning_data = redis_client.get(f"validation_learning:{world_seed}")
            if learning_data:
                if isinstance(learning_data, bytes):
                    learning_data = learning_data.decode('utf-8')
                return json.loads(learning_data)
            return []
        except Exception as e:
            logger.error(f"Error getting validation learning data for world {world_seed}: {str(e)}")
            return []

    @staticmethod
    async def add_validation_learning_data(world_seed: str, learning_entry: Dict[str, Any]) -> bool:
        """Add learning data for validation rule improvements"""
        try:
            learning_data = await Database.get_validation_learning_data(world_seed)
            learning_data.append(learning_entry)
            
            # Keep only the last 1000 entries to prevent memory issues
            if len(learning_data) > 1000:
                learning_data = learning_data[-1000:]
            
            serializable_data = Database._serialize_data(learning_data)
            return redis_client.set(f"validation_learning:{world_seed}", json.dumps(serializable_data))
        except Exception as e:
            logger.error(f"Error adding validation learning data for world {world_seed}: {str(e)}")
            return False

    @staticmethod
    async def get_world_validation_stats(world_seed: str) -> Dict[str, Any]:
        """Get validation statistics for a world"""
        try:
            stats_data = redis_client.get(f"validation_stats:{world_seed}")
            if stats_data:
                if isinstance(stats_data, bytes):
                    stats_data = stats_data.decode('utf-8')
                return json.loads(stats_data)
            return {
                "total_validations": 0,
                "valid_actions": 0,
                "invalid_actions": 0,
                "ai_validations": 0,
                "common_invalid_actions": {},
                "validation_mode_changes": []
            }
        except Exception as e:
            logger.error(f"Error getting validation stats for world {world_seed}: {str(e)}")
            return {}

    @staticmethod
    async def update_validation_stats(world_seed: str, validation_result: Dict[str, Any]) -> bool:
        """Update validation statistics for a world"""
        try:
            stats = await Database.get_world_validation_stats(world_seed)
            
            # Update basic stats
            stats["total_validations"] = stats.get("total_validations", 0) + 1
            
            if validation_result.get("valid", False):
                stats["valid_actions"] = stats.get("valid_actions", 0) + 1
            else:
                stats["invalid_actions"] = stats.get("invalid_actions", 0) + 1
                
                # Track common invalid actions
                action = validation_result.get("action", "unknown")
                if action in stats.get("common_invalid_actions", {}):
                    stats["common_invalid_actions"][action] += 1
                else:
                    stats["common_invalid_actions"][action] = 1
            
            if validation_result.get("ai_validated", False):
                stats["ai_validations"] = stats.get("ai_validations", 0) + 1
            
            serializable_data = Database._serialize_data(stats)
            return redis_client.set(f"validation_stats:{world_seed}", json.dumps(serializable_data))
        except Exception as e:
            logger.error(f"Error updating validation stats for world {world_seed}: {str(e)}")
            return False