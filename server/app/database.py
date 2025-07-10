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
    async def reset_world() -> None:
        """Reset the entire game world by clearing all data"""
        try:
            # Clear all Redis data
            redis_client.flushall()
            logger.info("Redis data cleared")

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