from typing import Any, Dict, List, Optional
from .database import Database as RedisDatabase
from .supabase_database import SupabaseDatabase
from .logger import setup_logging
from .config import settings
import logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

class HybridDatabase:
    """
    Hybrid database that routes operations to appropriate backends:
    - Redis for transient, high-frequency, and performance-critical data
    - Supabase for persistent game data (with Redis fallback if Supabase not configured)
    """
    
    @staticmethod
    def _is_supabase_configured() -> bool:
        """Check if Supabase is properly configured"""
        return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)

    # === PERSISTENT DATA (Supabase with Redis fallback) ===
    
    @staticmethod
    async def get_room(room_id: str) -> Optional[Dict[str, Any]]:
        """Get room data from Supabase or Redis fallback with retry logic"""
        logger.info(f"[HybridDatabase] Getting room {room_id}")
        
        # Try both databases and return the first result found
        supabase_result = None
        redis_result = None
        
        # Try Supabase first if configured
        if HybridDatabase._is_supabase_configured():
            logger.info(f"[HybridDatabase] Supabase is configured, trying Supabase first")
            try:
                supabase_result = await SupabaseDatabase.get_room(room_id)
                if supabase_result:
                    logger.info(f"[HybridDatabase] Found room {room_id} in Supabase")
                    # Try to sync to Redis if not already there
                    try:
                        await RedisDatabase.set_room(room_id, supabase_result)
                        logger.info(f"[HybridDatabase] Synced room {room_id} from Supabase to Redis")
                    except Exception as e:
                        logger.warning(f"[HybridDatabase] Failed to sync room {room_id} to Redis: {str(e)}")
                    return supabase_result
                else:
                    logger.warning(f"[HybridDatabase] Room {room_id} not found in Supabase")
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase get_room failed: {str(e)}")
        else:
            logger.info(f"[HybridDatabase] Supabase not configured")
        
        # Try Redis
        try:
            redis_result = await RedisDatabase.get_room(room_id)
            if redis_result:
                logger.info(f"[HybridDatabase] Found room {room_id} in Redis")
                # Try to sync to Supabase if configured and not already there
                if HybridDatabase._is_supabase_configured():
                    try:
                        await SupabaseDatabase.set_room(room_id, redis_result)
                        logger.info(f"[HybridDatabase] Synced room {room_id} from Redis to Supabase")
                    except Exception as e:
                        logger.warning(f"[HybridDatabase] Failed to sync room {room_id} to Supabase: {str(e)}")
                return redis_result
            else:
                logger.warning(f"[HybridDatabase] Room {room_id} not found in Redis")
        except Exception as e:
            logger.warning(f"[HybridDatabase] Redis get_room failed: {str(e)}")
        
        # If neither database has the room, try one more time with a small delay
        logger.warning(f"[HybridDatabase] Room {room_id} not found in any database, retrying...")
        import asyncio
        await asyncio.sleep(0.1)  # Small delay to allow for potential race conditions
        
        # Try Redis one more time (most likely to have the data)
        try:
            redis_result = await RedisDatabase.get_room(room_id)
            if redis_result:
                logger.info(f"[HybridDatabase] Found room {room_id} in Redis on retry")
                return redis_result
        except Exception as e:
            logger.warning(f"[HybridDatabase] Redis retry failed: {str(e)}")
        
        # If still not found, log the issue
        logger.error(f"[HybridDatabase] Room {room_id} not found in any database after retry")
        return None

    @staticmethod
    async def set_room(room_id: str, room_data: Dict[str, Any]) -> bool:
        """Save room data to Supabase or Redis fallback"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.set_room(room_id, room_data)
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase set_room failed, falling back to Redis: {str(e)}")
        
        return await RedisDatabase.set_room(room_id, room_data)

    @staticmethod
    async def get_player(player_id: str) -> Optional[Dict[str, Any]]:
        """Get player data from Supabase or Redis fallback"""
        # For guest players, always use Redis directly
        if player_id.startswith('guest_'):
            logger.debug(f"[HybridDatabase] Guest player {player_id}, using Redis directly")
            result = await RedisDatabase.get_player(player_id)
            logger.debug(f"[HybridDatabase] Redis returned for {player_id}: {result is not None}")
            return result
        
        if HybridDatabase._is_supabase_configured():
            try:
                result = await SupabaseDatabase.get_player(player_id)
                # If Supabase returns None (e.g., for guest players), fall back to Redis
                if result is not None:
                    return result
                logger.debug(f"[HybridDatabase] Supabase returned None for {player_id}, falling back to Redis")
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase get_player failed, falling back to Redis: {str(e)}")
        
        logger.debug(f"[HybridDatabase] Falling back to Redis for player {player_id}")
        result = await RedisDatabase.get_player(player_id)
        logger.debug(f"[HybridDatabase] Redis returned for {player_id}: {result is not None}")
        return result

    @staticmethod
    async def set_player(player_id: str, player_data: Dict[str, Any]) -> bool:
        """Save player data to Supabase or Redis fallback"""
        # For guest players, always use Redis directly
        if player_id.startswith('guest_'):
            logger.debug(f"[HybridDatabase] Guest player {player_id}, using Redis directly")
            return await RedisDatabase.set_player(player_id, player_data)
        
        if HybridDatabase._is_supabase_configured():
            try:
                result = await SupabaseDatabase.set_player(player_id, player_data)
                # If Supabase returns False (e.g., for guest players), fall back to Redis
                if result:
                    return result
                logger.debug(f"[HybridDatabase] Supabase returned False for {player_id}, falling back to Redis")
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase set_player failed, falling back to Redis: {str(e)}")
        
        return await RedisDatabase.set_player(player_id, player_data)

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
        """Get item data from Supabase or Redis fallback"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.get_item(item_id)
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase get_item failed, falling back to Redis: {str(e)}")
        
        return await RedisDatabase.get_item(item_id)

    @staticmethod
    async def set_item(item_id: str, item_data: Dict[str, Any]) -> bool:
        """Save item data to Supabase or Redis fallback"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.set_item(item_id, item_data)
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase set_item failed, falling back to Redis: {str(e)}")
        
        return await RedisDatabase.set_item(item_id, item_data)

    @staticmethod
    async def get_monster(monster_id: str) -> Optional[Dict[str, Any]]:
        """Get monster data from Supabase"""
        return await SupabaseDatabase.get_monster(monster_id)

    @staticmethod
    async def set_monster(monster_id: str, monster_data: Dict[str, Any]) -> bool:
        """Save monster data to Supabase"""
        return await SupabaseDatabase.set_monster(monster_id, monster_data)


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
        """Get room at specific coordinates from Supabase or Redis fallback"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.get_room_by_coordinates(x, y)
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase get_room_by_coordinates failed, falling back to Redis: {str(e)}")
        
        return await RedisDatabase.get_room_by_coordinates(x, y)

    @staticmethod
    async def set_room_coordinates(room_id: str, x: int, y: int) -> bool:
        """Set coordinate mapping for a room in Supabase or Redis fallback"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.set_room_coordinates(room_id, x, y)
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase set_room_coordinates failed, falling back to Redis: {str(e)}")
        
        return await RedisDatabase.set_room_coordinates(room_id, x, y)

    @staticmethod
    async def get_adjacent_rooms(x: int, y: int) -> Dict[str, Optional[str]]:
        """Get adjacent room IDs at coordinates around (x, y) from Supabase or Redis fallback"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.get_adjacent_rooms(x, y)
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase get_adjacent_rooms failed, falling back to Redis: {str(e)}")
        
        return await RedisDatabase.get_adjacent_rooms(x, y)

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
        """Atomically create a room at specific coordinates in Supabase or Redis fallback"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.atomic_create_room_at_coordinates(room_id, x, y, room_data)
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase atomic_create_room_at_coordinates failed, falling back to Redis: {str(e)}")
        
        return await RedisDatabase.atomic_create_room_at_coordinates(room_id, x, y, room_data)

    @staticmethod
    async def get_chunk_biome(chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get biome data for a chunk from Supabase or Redis fallback"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.get_chunk_biome(chunk_id)
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase get_chunk_biome failed, falling back to Redis: {str(e)}")
        
        # Redis fallback - return None since Redis doesn't store chunk biomes
        return None

    @staticmethod
    async def set_chunk_biome(chunk_id: str, biome_data: Dict[str, Any]) -> bool:
        """Set biome data for a chunk in Supabase or Redis fallback"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.set_chunk_biome(chunk_id, biome_data)
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase set_chunk_biome failed, falling back to Redis: {str(e)}")
        
        # Redis fallback - return False since Redis doesn't store chunk biomes
        return False

    @staticmethod
    async def get_all_biomes() -> List[Dict[str, Any]]:
        """Return a list of all biome dicts from Supabase or Redis fallback"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.get_all_biomes()
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase get_all_biomes failed, falling back to Redis: {str(e)}")
        
        # Redis fallback - return empty list since Redis doesn't store biomes
        return []

    @staticmethod
    async def get_all_saved_biomes() -> List[Dict[str, Any]]:
        """Return a list of all biome dicts from Supabase or Redis fallback"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.get_all_biomes()
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase get_all_biomes failed, falling back to Redis: {str(e)}")
        
        # Redis fallback - return empty list since Redis doesn't store biomes
        return []

    @staticmethod
    async def save_biome(biome_data: Dict[str, Any]) -> bool:
        """Save a new biome to Supabase or Redis fallback"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.save_biome(biome_data)
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase save_biome failed, falling back to Redis: {str(e)}")
        
        # Redis fallback - return False since Redis doesn't store biomes
        return False
    
    @staticmethod
    async def get_biome_three_star_room(biome: str) -> Optional[str]:
        """Get the room ID that has the 3-star item for a biome"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.get_biome_three_star_room(biome)
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase get_biome_three_star_room failed, falling back to Redis: {str(e)}")
        
        # Redis fallback - return None since Redis doesn't store biome 3-star rooms
        return None
    
    @staticmethod
    async def set_biome_three_star_room(biome: str, room_id: str) -> bool:
        """Set the room ID that has the 3-star item for a biome"""
        if HybridDatabase._is_supabase_configured():
            try:
                return await SupabaseDatabase.set_biome_three_star_room(biome, room_id)
            except Exception as e:
                logger.warning(f"[HybridDatabase] Supabase set_biome_three_star_room failed, falling back to Redis: {str(e)}")
        
        # Redis fallback - return False since Redis doesn't store biome 3-star rooms
        return False

    # === TRANSIENT DATA (Redis) ===
    
    @staticmethod
    async def get_active_duels_for_player(player_id: str) -> List[Dict[str, Any]]:
        """Get all active duels for a specific player (Redis)"""
        return await RedisDatabase.get_active_duels_for_player(player_id)
    
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
    async def store_player_message(player_id: str, message) -> bool:
        """Store a chat message in the player's message history (Redis)"""
        return await RedisDatabase.store_player_message(player_id, message)

    @staticmethod
    async def store_action_record(player_id: str, action_record) -> bool:
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
    async def get_player_messages(player_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent messages for a specific player (Redis)"""
        return await RedisDatabase.get_player_messages(player_id, limit)

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

    @staticmethod
    async def get_recent_high_rarity_items(min_rarity: int = 2, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recently generated items with specified minimum rarity for AI context"""
        try:
            if HybridDatabase._is_supabase_configured():
                return await SupabaseDatabase.get_recent_high_rarity_items(min_rarity, limit)
            else:
                return await RedisDatabase.get_recent_high_rarity_items(min_rarity, limit)
        except Exception as e:
            logger.warning(f"[HybridDatabase] Error getting recent high rarity items: {str(e)}")
            return []