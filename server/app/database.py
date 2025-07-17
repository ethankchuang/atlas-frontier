import redis
import chromadb
from chromadb.config import Settings as ChromaSettings
import json
from typing import Any, Dict, List, Optional
from .config import settings
import logging
from .logger import setup_logging

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
            player_data = redis_client.get(f"player:{player_id}")
            if player_data:
                if isinstance(player_data, bytes):
                    player_data = player_data.decode('utf-8')
                return json.loads(player_data)
            return None
        except Exception as e:
            logger.error(f"Error getting player {player_id}: {str(e)}")
            raise

    @staticmethod
    async def set_player(player_id: str, player_data: Dict[str, Any]) -> bool:
        """Save player data to Redis"""
        try:
            logger.debug(f"Setting player {player_id} with data: {player_data}")
            serializable_data = Database._serialize_data(player_data)
            logger.debug(f"Serialized player data: {serializable_data}")
            return redis_client.set(f"player:{player_id}", json.dumps(serializable_data))
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
            # Clear all Redis data (includes coordinate mappings)
            redis_client.flushall()
            logger.info("Redis data cleared (including coordinate mappings)")

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