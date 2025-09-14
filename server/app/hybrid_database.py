from typing import Any, Dict, List, Optional
from .database import Database as RedisDatabase
from .supabase_database import SupabaseDatabase
from .logger import setup_logging
import logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

class HybridDatabase:
    """
    Hybrid database that routes operations to appropriate backends:
    - Redis for transient, high-frequency, and performance-critical data
    - Supabase for persistent game data
    """

    # === PERSISTENT DATA (Supabase) ===
    
    @staticmethod
    async def get_room(room_id: str) -> Optional[Dict[str, Any]]:
        """Get room data from Supabase"""
        return await SupabaseDatabase.get_room(room_id)

    @staticmethod
    async def set_room(room_id: str, room_data: Dict[str, Any]) -> bool:
        """Save room data to Supabase"""
        return await SupabaseDatabase.set_room(room_id, room_data)

    @staticmethod
    async def get_player(player_id: str) -> Optional[Dict[str, Any]]:
        """Get player data from Supabase"""
        return await SupabaseDatabase.get_player(player_id)

    @staticmethod
    async def set_player(player_id: str, player_data: Dict[str, Any]) -> bool:
        """Save player data to Supabase"""
        return await SupabaseDatabase.set_player(player_id, player_data)

    @staticmethod
    async def get_players_for_user(user_id: str) -> List[Dict[str, Any]]:
        """Get all players for a specific user from Supabase"""
        return await SupabaseDatabase.get_players_for_user(user_id)

    @staticmethod
    async def get_npc(npc_id: str) -> Optional[Dict[str, Any]]:
        """Get NPC data from Supabase"""
        return await SupabaseDatabase.get_npc(npc_id)

    @staticmethod
    async def set_npc(npc_id: str, npc_data: Dict[str, Any]) -> bool:
        """Save NPC data to Supabase"""
        return await SupabaseDatabase.set_npc(npc_id, npc_data)

    @staticmethod
    async def get_item(item_id: str) -> Optional[Dict[str, Any]]:
        """Get item data from Supabase"""
        return await SupabaseDatabase.get_item(item_id)

    @staticmethod
    async def set_item(item_id: str, item_data: Dict[str, Any]) -> bool:
        """Save item data to Supabase"""
        return await SupabaseDatabase.set_item(item_id, item_data)

    @staticmethod
    async def get_monster(monster_id: str) -> Optional[Dict[str, Any]]:
        """Get monster data from Supabase"""
        return await SupabaseDatabase.get_monster(monster_id)

    @staticmethod
    async def set_monster(monster_id: str, monster_data: Dict[str, Any]) -> bool:
        """Save monster data to Supabase"""
        return await SupabaseDatabase.set_monster(monster_id, monster_data)

    @staticmethod
    async def get_item_types() -> Optional[List[Dict[str, Any]]]:
        """Get item types from Supabase"""
        return await SupabaseDatabase.get_item_types()

    @staticmethod
    async def set_item_types(item_types_data: List[Dict[str, Any]]) -> bool:
        """Save item types to Supabase"""
        return await SupabaseDatabase.set_item_types(item_types_data)

    @staticmethod
    async def get_monster_types() -> Optional[List[Dict[str, Any]]]:
        """Get monster types from Supabase"""
        return await SupabaseDatabase.get_monster_types()

    @staticmethod
    async def set_monster_types(monster_types_data: List[Dict[str, Any]]) -> bool:
        """Save monster types to Supabase"""
        return await SupabaseDatabase.set_monster_types(monster_types_data)

    @staticmethod
    async def get_game_state() -> Dict[str, Any]:
        """Get global game state from Supabase"""
        return await SupabaseDatabase.get_game_state()

    @staticmethod
    async def set_game_state(state_data: Dict[str, Any]) -> bool:
        """Save global game state to Supabase"""
        return await SupabaseDatabase.set_game_state(state_data)

    @staticmethod
    async def get_room_by_coordinates(x: int, y: int) -> Optional[Dict[str, Any]]:
        """Get room at specific coordinates from Supabase"""
        return await SupabaseDatabase.get_room_by_coordinates(x, y)

    @staticmethod
    async def set_room_coordinates(room_id: str, x: int, y: int) -> bool:
        """Set coordinate mapping for a room in Supabase"""
        return await SupabaseDatabase.set_room_coordinates(room_id, x, y)

    @staticmethod
    async def get_adjacent_rooms(x: int, y: int) -> Dict[str, Optional[str]]:
        """Get adjacent room IDs at coordinates around (x, y) from Supabase"""
        return await SupabaseDatabase.get_adjacent_rooms(x, y)

    @staticmethod
    async def is_coordinate_discovered(x: int, y: int) -> bool:
        """Check if a coordinate has been discovered/explored in Supabase"""
        return await SupabaseDatabase.is_coordinate_discovered(x, y)

    @staticmethod
    async def mark_coordinate_discovered(x: int, y: int, room_id: str) -> bool:
        """Mark a coordinate as discovered and associate it with a room in Supabase"""
        return await SupabaseDatabase.mark_coordinate_discovered(x, y, room_id)

    @staticmethod
    async def get_discovered_coordinates() -> Dict[str, str]:
        """Get all discovered coordinates and their associated room IDs from Supabase"""
        return await SupabaseDatabase.get_discovered_coordinates()

    @staticmethod
    async def remove_coordinate_discovery(x: int, y: int) -> bool:
        """Remove discovery status for a coordinate in Supabase"""
        return await SupabaseDatabase.remove_coordinate_discovery(x, y)

    @staticmethod
    async def atomic_create_room_at_coordinates(room_id: str, x: int, y: int, room_data: Dict[str, Any]) -> bool:
        """Atomically create a room at specific coordinates in Supabase"""
        return await SupabaseDatabase.atomic_create_room_at_coordinates(room_id, x, y, room_data)

    @staticmethod
    async def get_chunk_biome(chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get biome data for a chunk from Supabase"""
        return await SupabaseDatabase.get_chunk_biome(chunk_id)

    @staticmethod
    async def set_chunk_biome(chunk_id: str, biome_data: Dict[str, Any]) -> bool:
        """Set biome data for a chunk in Supabase"""
        return await SupabaseDatabase.set_chunk_biome(chunk_id, biome_data)

    @staticmethod
    async def get_all_biomes() -> List[Dict[str, Any]]:
        """Return a list of all biome dicts from Supabase"""
        return await SupabaseDatabase.get_all_biomes()

    @staticmethod
    async def get_all_saved_biomes() -> List[Dict[str, Any]]:
        """Return a list of all biome dicts from Supabase (alias for get_all_biomes)"""
        return await SupabaseDatabase.get_all_biomes()

    @staticmethod
    async def save_biome(biome_data: Dict[str, Any]) -> bool:
        """Save a new biome to Supabase"""
        return await SupabaseDatabase.save_biome(biome_data)

    # === TRANSIENT DATA (Redis) ===
    
    @staticmethod
    async def add_to_room_players(room_id: str, player_id: str) -> bool:
        """Add player to room's player list (Redis)"""
        return await RedisDatabase.add_to_room_players(room_id, player_id)

    @staticmethod
    async def remove_from_room_players(room_id: str, player_id: str) -> bool:
        """Remove player from room's player list (Redis)"""
        return await RedisDatabase.remove_from_room_players(room_id, player_id)

    @staticmethod
    async def get_room_players(room_id: str) -> List[str]:
        """Get list of players in a room (Redis)"""
        return await RedisDatabase.get_room_players(room_id)

    @staticmethod
    async def store_chat_message(room_id: str, message: 'ChatMessage') -> bool:
        """Store a chat message in the room's chat history (Redis)"""
        return await RedisDatabase.store_chat_message(room_id, message)

    @staticmethod
    async def store_action_record(player_id: str, action_record: 'ActionRecord') -> bool:
        """Store a player action and AI response (Redis)"""
        return await RedisDatabase.store_action_record(player_id, action_record)

    @staticmethod
    async def get_action_history(player_id: Optional[str] = None, room_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get action history with optional filtering (Redis)"""
        return await RedisDatabase.get_action_history(player_id, room_id, limit)

    @staticmethod
    async def get_actions_in_time_window(player_id: str, cutoff_timestamp: str) -> List[Dict[str, Any]]:
        """Get all actions for a player within a specific time window (Redis)"""
        return await RedisDatabase.get_actions_in_time_window(player_id, cutoff_timestamp)

    @staticmethod
    async def get_chat_history(player_id: Optional[str] = None, room_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get chat history with optional filtering (Redis)"""
        return await RedisDatabase.get_chat_history(player_id, room_id, limit)

    @staticmethod
    async def get_game_sessions(player_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get game sessions with optional filtering (Redis)"""
        return await RedisDatabase.get_game_sessions(player_id, limit)

    @staticmethod
    async def create_game_session(player_id: str) -> str:
        """Create a new game session (Redis)"""
        return await RedisDatabase.create_game_session(player_id)

    @staticmethod
    async def update_session(session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data (Redis)"""
        return await RedisDatabase.update_session(session_id, updates)

    @staticmethod
    async def set_room_generation_status(room_id: str, status: str) -> bool:
        """Set room generation status (Redis)"""
        return await RedisDatabase.set_room_generation_status(room_id, status)

    @staticmethod
    async def get_room_generation_status(room_id: str) -> Optional[str]:
        """Get room generation status (Redis)"""
        return await RedisDatabase.get_room_generation_status(room_id)

    @staticmethod
    async def is_room_generating(room_id: str) -> bool:
        """Check if a room is currently being generated (Redis)"""
        return await RedisDatabase.is_room_generating(room_id)

    @staticmethod
    async def set_room_generation_lock(room_id: str, lock_duration: int = 300) -> bool:
        """Set a lock to prevent concurrent generation of the same room (Redis)"""
        return await RedisDatabase.set_room_generation_lock(room_id, lock_duration)

    @staticmethod
    async def release_room_generation_lock(room_id: str) -> bool:
        """Release the generation lock for a room (Redis)"""
        return await RedisDatabase.release_room_generation_lock(room_id)

    @staticmethod
    async def is_room_generation_locked(room_id: str) -> bool:
        """Check if a room generation is locked (Redis)"""
        return await RedisDatabase.is_room_generation_locked(room_id)

    @staticmethod
    async def set_coordinate_lock(x: int, y: int, lock_duration: int = 300) -> bool:
        """Set a lock to prevent concurrent operations on a specific coordinate (Redis)"""
        return await RedisDatabase.set_coordinate_lock(x, y, lock_duration)

    @staticmethod
    async def release_coordinate_lock(x: int, y: int) -> bool:
        """Release the coordinate lock (Redis)"""
        return await RedisDatabase.release_coordinate_lock(x, y)

    @staticmethod
    async def is_coordinate_locked(x: int, y: int) -> bool:
        """Check if a coordinate is locked (Redis)"""
        return await RedisDatabase.is_coordinate_locked(x, y)

    # === VALIDATION SYSTEM (Redis) ===
    
    @staticmethod
    async def get_world_validation_rules(world_seed: str) -> Optional[Dict[str, Any]]:
        """Get validation rules for a specific world (Redis)"""
        return await RedisDatabase.get_world_validation_rules(world_seed)

    @staticmethod
    async def set_world_validation_rules(world_seed: str, rules_data: Dict[str, Any]) -> bool:
        """Set validation rules for a specific world (Redis)"""
        return await RedisDatabase.set_world_validation_rules(world_seed, rules_data)

    @staticmethod
    async def update_validation_rules(world_seed: str, updates: Dict[str, Any]) -> bool:
        """Update validation rules for a world (Redis)"""
        return await RedisDatabase.update_validation_rules(world_seed, updates)

    @staticmethod
    async def get_validation_learning_data(world_seed: str) -> List[Dict[str, Any]]:
        """Get learning data for validation rule improvements (Redis)"""
        return await RedisDatabase.get_validation_learning_data(world_seed)

    @staticmethod
    async def add_validation_learning_data(world_seed: str, learning_entry: Dict[str, Any]) -> bool:
        """Add learning data for validation rule improvements (Redis)"""
        return await RedisDatabase.add_validation_learning_data(world_seed, learning_entry)

    @staticmethod
    async def get_world_validation_stats(world_seed: str) -> Dict[str, Any]:
        """Get validation statistics for a world (Redis)"""
        return await RedisDatabase.get_world_validation_stats(world_seed)

    @staticmethod
    async def update_validation_stats(world_seed: str, validation_result: Dict[str, Any]) -> bool:
        """Update validation statistics for a world (Redis)"""
        return await RedisDatabase.update_validation_stats(world_seed, validation_result)

    # === HYBRID OPERATIONS ===

    @staticmethod
    async def reset_world() -> None:
        """Reset the entire game world by clearing all data from both Redis and Supabase"""
        try:
            logger.info("Resetting world data in both Redis and Supabase...")
            
            # Clear persistent data from Supabase
            await SupabaseDatabase.reset_world()
            
            # Clear transient data from Redis
            await RedisDatabase.reset_world()
            
            logger.info("World reset completed successfully")
        except Exception as e:
            logger.error(f"Error resetting world: {str(e)}")
            raise

    # === VECTOR/CHROMA OPERATIONS (unchanged) ===
    
    @staticmethod
    async def add_npc_memory(npc_id: str, memory: str, metadata: Dict[str, Any]) -> None:
        """Add a memory to NPC's vector store (ChromaDB)"""
        return await RedisDatabase.add_npc_memory(npc_id, memory, metadata)

    @staticmethod
    async def get_npc_memories(npc_id: str, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Query NPC's relevant memories (ChromaDB)"""
        return await RedisDatabase.get_npc_memories(npc_id, query, n_results)