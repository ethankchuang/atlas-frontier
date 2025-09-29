from typing import Any, Dict, List, Optional, Tuple
from .supabase_client import get_supabase_client
from .logger import setup_logging
import logging
import json
import hashlib

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

class SupabaseDatabase:
    """
    Supabase database operations for persistent game data.
    This class handles the persistent data that was previously stored in Redis.
    """
    
    @staticmethod
    def _serialize_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Helper method to serialize dictionary data for Supabase storage"""
        try:
            # Ensure all data is JSON serializable
            return json.loads(json.dumps(data, default=str))
        except Exception as e:
            logger.error(f"Error serializing data: {str(e)}")
            raise ValueError(f"Failed to serialize data: {str(e)}")

    @staticmethod
    async def get_room(room_id: str) -> Optional[Dict[str, Any]]:
        """Get room data from Supabase"""
        try:
            client = get_supabase_client()
            result = client.table('rooms').select('data').eq('id', room_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['data']
            return None
        except Exception as e:
            logger.error(f"Error getting room {room_id}: {str(e)}")
            raise

    @staticmethod
    async def set_room(room_id: str, room_data: Dict[str, Any]) -> bool:
        """Save room data to Supabase"""
        try:
            logger.debug(f"Setting room {room_id} with data: {room_data}")
            client = get_supabase_client()
            serializable_data = SupabaseDatabase._serialize_data(room_data)
            
            # Use upsert to insert or update
            result = client.table('rooms').upsert({
                'id': room_id,
                'data': serializable_data
            }).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error setting room {room_id}: {str(e)}")
            raise

    @staticmethod
    async def get_player(player_id: str) -> Optional[Dict[str, Any]]:
        """Get player data from Supabase"""
        try:
            # Skip guest players - they should be stored in Redis
            if player_id.startswith('guest_'):
                logger.debug(f"Skipping Supabase lookup for guest player: {player_id}")
                return None
                
            client = get_supabase_client()
            result = client.table('players').select('data').eq('id', player_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['data']
            return None
        except Exception as e:
            logger.error(f"Error getting player {player_id}: {str(e)}")
            raise

    @staticmethod
    async def set_player(player_id: str, player_data: Dict[str, Any]) -> bool:
        """Save player data to Supabase"""
        try:
            logger.debug(f"Setting player {player_id} with data: {player_data}")
            client = get_supabase_client()
            serializable_data = SupabaseDatabase._serialize_data(player_data)
            
            # Extract user_id from player_data for the foreign key
            user_id = player_data.get('user_id')
            if not user_id:
                logger.error(f"Player data missing user_id: {player_data}")
                return False
            
            # Skip saving system/dummy/guest players to avoid foreign key constraint issues
            if user_id == "system" or player_id == "dummy" or user_id == "guest":
                logger.debug(f"Skipping save for system/dummy/guest player: {player_id}")
                return True  # Return success without actually saving
            
            result = client.table('players').upsert({
                'id': player_id,
                'user_id': user_id,
                'data': serializable_data
            }).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error setting player {player_id}: {str(e)}")
            raise

    @staticmethod
    async def get_players_for_user(user_id: str) -> List[Dict[str, Any]]:
        """Get all players for a specific user"""
        try:
            client = get_supabase_client()
            result = client.table('players').select('*').eq('user_id', user_id).execute()
            
            players = []
            for row in result.data:
                player_data = row['data']
                players.append(player_data)
            
            return players
        except Exception as e:
            logger.error(f"Error getting players for user {user_id}: {str(e)}")
            return []

    @staticmethod
    async def get_npc(npc_id: str) -> Optional[Dict[str, Any]]:
        """Get NPC data from Supabase"""
        try:
            client = get_supabase_client()
            result = client.table('npcs').select('data').eq('id', npc_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['data']
            return None
        except Exception as e:
            logger.error(f"Error getting NPC {npc_id}: {str(e)}")
            raise

    @staticmethod
    async def set_npc(npc_id: str, npc_data: Dict[str, Any]) -> bool:
        """Save NPC data to Supabase"""
        try:
            logger.debug(f"Setting NPC {npc_id} with data: {npc_data}")
            client = get_supabase_client()
            serializable_data = SupabaseDatabase._serialize_data(npc_data)
            
            result = client.table('npcs').upsert({
                'id': npc_id,
                'data': serializable_data
            }).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error setting NPC {npc_id}: {str(e)}")
            raise

    @staticmethod
    async def get_item(item_id: str) -> Optional[Dict[str, Any]]:
        """Get item data from Supabase"""
        try:
            client = get_supabase_client()
            result = client.table('items').select('data').eq('id', item_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['data']
            return None
        except Exception as e:
            logger.error(f"Error getting item {item_id}: {str(e)}")
            raise

    @staticmethod
    async def set_item(item_id: str, item_data: Dict[str, Any]) -> bool:
        """Save item data to Supabase"""
        try:
            logger.debug(f"Setting item {item_id} with data: {item_data}")
            client = get_supabase_client()
            serializable_data = SupabaseDatabase._serialize_data(item_data)
            
            result = client.table('items').upsert({
                'id': item_id,
                'data': serializable_data
            }).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error setting item {item_id}: {str(e)}")
            raise

    @staticmethod
    async def get_monster(monster_id: str) -> Optional[Dict[str, Any]]:
        """Get monster data from Supabase"""
        try:
            client = get_supabase_client()
            result = client.table('monsters').select('data').eq('id', monster_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['data']
            return None
        except Exception as e:
            logger.error(f"Error getting monster {monster_id}: {str(e)}")
            raise

    @staticmethod
    async def set_monster(monster_id: str, monster_data: Dict[str, Any]) -> bool:
        """Save monster data to Supabase"""
        try:
            logger.debug(f"Setting monster {monster_id} with data: {monster_data}")
            client = get_supabase_client()
            serializable_data = SupabaseDatabase._serialize_data(monster_data)
            
            result = client.table('monsters').upsert({
                'id': monster_id,
                'data': serializable_data
            }).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error setting monster {monster_id}: {str(e)}")
            raise


    @staticmethod
    async def get_recent_high_rarity_items(min_rarity: int = 2, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recently generated items with specified minimum rarity for AI context"""
        try:
            client = get_supabase_client()
            
            # Query items with minimum rarity, ordered by creation time (most recent first)
            # We'll use the id field as a proxy for creation time since newer items have more recent UUIDs
            result = client.table('items').select('data').execute()
            
            if not result.data:
                return []
            
            # Filter items by rarity and sort by ID (newer UUIDs come later alphabetically)
            filtered_items = []
            for item_row in result.data:
                item_data = item_row.get('data', {})
                if item_data.get('rarity', 1) >= min_rarity:
                    filtered_items.append(item_data)
            
            # Sort by ID (newer items have later UUIDs) and limit
            filtered_items.sort(key=lambda x: x.get('id', ''), reverse=True)
            return filtered_items[:limit]
            
        except Exception as e:
            logger.error(f"Error getting recent high rarity items: {str(e)}")
            return []

    @staticmethod
    async def get_monster_types() -> Optional[List[Dict[str, Any]]]:
        """Get monster types from Supabase"""
        try:
            client = get_supabase_client()
            result = client.table('global_data').select('data').eq('key', 'monster_types').execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['data']
            return None
        except Exception as e:
            logger.error(f"Error getting monster types: {str(e)}")
            raise

    @staticmethod
    async def set_monster_types(monster_types_data: List[Dict[str, Any]]) -> bool:
        """Save monster types to Supabase"""
        try:
            logger.debug(f"Setting monster types with data: {monster_types_data}")
            client = get_supabase_client()
            serializable_data = [SupabaseDatabase._serialize_data(monster) for monster in monster_types_data]
            
            result = client.table('global_data').upsert({
                'key': 'monster_types',
                'data': serializable_data
            }).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error setting monster types: {str(e)}")
            raise

    @staticmethod
    async def get_game_state() -> Dict[str, Any]:
        """Get global game state from Supabase"""
        try:
            client = get_supabase_client()
            result = client.table('global_data').select('data').eq('key', 'game_state').execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['data']
            return {}
        except Exception as e:
            logger.error(f"Error getting game state: {str(e)}")
            raise

    @staticmethod
    async def set_game_state(state_data: Dict[str, Any]) -> bool:
        """Save global game state to Supabase"""
        try:
            logger.debug(f"Setting game state with data: {state_data}")
            client = get_supabase_client()
            serializable_data = SupabaseDatabase._serialize_data(state_data)
            
            result = client.table('global_data').upsert({
                'key': 'game_state',
                'data': serializable_data
            }).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error setting game state: {str(e)}")
            raise

    @staticmethod
    async def get_room_by_coordinates(x: int, y: int) -> Optional[Dict[str, Any]]:
        """Get room at specific coordinates from Supabase"""
        try:
            client = get_supabase_client()
            result = client.table('coordinates').select('room_id').eq('x', x).eq('y', y).execute()
            
            if result.data and len(result.data) > 0:
                room_id = result.data[0]['room_id']
                return await SupabaseDatabase.get_room(room_id)
            return None
        except Exception as e:
            logger.error(f"Error getting room at coordinates ({x}, {y}): {str(e)}")
            raise

    @staticmethod
    async def set_room_coordinates(room_id: str, x: int, y: int) -> bool:
        """Set coordinate mapping for a room in Supabase"""
        try:
            logger.debug(f"Setting coordinates ({x}, {y}) for room {room_id}")
            client = get_supabase_client()
            
            result = client.table('coordinates').upsert({
                'x': x,
                'y': y,
                'room_id': room_id,
                'is_discovered': True
            }).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error setting coordinates ({x}, {y}) for room {room_id}: {str(e)}")
            raise

    @staticmethod
    async def get_adjacent_rooms(x: int, y: int) -> Dict[str, Optional[str]]:
        """Get adjacent room IDs at coordinates around (x, y) from Supabase"""
        try:
            client = get_supabase_client()
            directions = [
                ("north", x, y + 1),
                ("south", x, y - 1),
                ("east", x + 1, y),
                ("west", x - 1, y)
            ]
            
            adjacent = {}
            for direction, adj_x, adj_y in directions:
                result = client.table('coordinates').select('room_id').eq('x', adj_x).eq('y', adj_y).execute()
                
                if result.data and len(result.data) > 0:
                    adjacent[direction] = result.data[0]['room_id']
                else:
                    adjacent[direction] = None
            
            return adjacent
        except Exception as e:
            logger.error(f"Error getting adjacent rooms for coordinates ({x}, {y}): {str(e)}")
            raise

    @staticmethod
    async def is_coordinate_discovered(x: int, y: int) -> bool:
        """Check if a coordinate has been discovered/explored in Supabase"""
        try:
            client = get_supabase_client()
            result = client.table('coordinates').select('is_discovered').eq('x', x).eq('y', y).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['is_discovered']
            return False
        except Exception as e:
            logger.error(f"Error checking if coordinate ({x}, {y}) is discovered: {str(e)}")
            return False

    @staticmethod
    async def mark_coordinate_discovered(x: int, y: int, room_id: str) -> bool:
        """Mark a coordinate as discovered and associate it with a room in Supabase"""
        try:
            logger.debug(f"Marking coordinate ({x}, {y}) as discovered with room {room_id}")
            client = get_supabase_client()
            
            result = client.table('coordinates').upsert({
                'x': x,
                'y': y,
                'room_id': room_id,
                'is_discovered': True
            }).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error marking coordinate ({x}, {y}) as discovered: {str(e)}")
            return False

    @staticmethod
    async def get_discovered_coordinates() -> Dict[str, str]:
        """Get all discovered coordinates and their associated room IDs from Supabase"""
        try:
            client = get_supabase_client()
            result = client.table('coordinates').select('x, y, room_id').eq('is_discovered', True).execute()
            
            discovered_coords = {}
            for row in result.data:
                coord_key = f"{row['x']}:{row['y']}"
                discovered_coords[coord_key] = row['room_id']
            
            return discovered_coords
        except Exception as e:
            logger.error(f"Error getting discovered coordinates: {str(e)}")
            return {}

    @staticmethod
    async def remove_coordinate_discovery(x: int, y: int) -> bool:
        """Remove discovery status for a coordinate in Supabase"""
        try:
            client = get_supabase_client()
            result = client.table('coordinates').delete().eq('x', x).eq('y', y).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error removing discovery for coordinate ({x}, {y}): {str(e)}")
            return False

    @staticmethod
    async def atomic_create_room_at_coordinates(room_id: str, x: int, y: int, room_data: Dict[str, Any]) -> bool:
        """Atomically create a room at specific coordinates in Supabase"""
        try:
            client = get_supabase_client()
            
            # Check if coordinate is already discovered
            existing = client.table('coordinates').select('room_id').eq('x', x).eq('y', y).execute()
            if existing.data and len(existing.data) > 0:
                logger.warning(f"Coordinate ({x}, {y}) already has room {existing.data[0]['room_id']}")
                return False
            
            # Create room and coordinate mapping in a transaction-like manner
            serializable_data = SupabaseDatabase._serialize_data(room_data)
            
            # Insert room
            room_result = client.table('rooms').insert({
                'id': room_id,
                'data': serializable_data
            }).execute()
            
            if not room_result.data:
                return False
            
            # Insert coordinate mapping
            coord_result = client.table('coordinates').insert({
                'x': x,
                'y': y,
                'room_id': room_id,
                'is_discovered': True
            }).execute()
            
            if not coord_result.data:
                # Rollback room creation
                client.table('rooms').delete().eq('id', room_id).execute()
                return False
            
            logger.info(f"Atomically created room {room_id} at coordinates ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Error atomically creating room {room_id} at ({x}, {y}): {str(e)}")
            return False

    @staticmethod
    async def get_chunk_biome(chunk_id: str) -> Optional[Dict[str, Any]]:
        """Get biome data for a chunk from Supabase"""
        try:
            client = get_supabase_client()
            result = client.table('chunk_biomes').select('data').eq('chunk_id', chunk_id).execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['data']
            return None
        except Exception as e:
            logger.error(f"Error getting chunk biome {chunk_id}: {str(e)}")
            return None

    @staticmethod
    async def set_chunk_biome(chunk_id: str, biome_data: Dict[str, Any]) -> bool:
        """Set biome data for a chunk in Supabase"""
        try:
            client = get_supabase_client()
            serializable_data = SupabaseDatabase._serialize_data(biome_data)
            
            result = client.table('chunk_biomes').upsert({
                'chunk_id': chunk_id,
                'data': serializable_data
            }).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error setting chunk biome {chunk_id}: {str(e)}")
            return False

    @staticmethod
    async def get_all_biomes() -> List[Dict[str, Any]]:
        """Return a list of all biome dicts from Supabase"""
        try:
            client = get_supabase_client()
            result = client.table('biomes').select('data').execute()
            
            return [row['data'] for row in result.data]
        except Exception as e:
            logger.error(f"Error getting all biomes: {str(e)}")
            return []

    @staticmethod
    async def save_biome(biome_data: Dict[str, Any]) -> bool:
        """Save a new biome to Supabase"""
        try:
            name = biome_data.get("name", "")
            name_hash = hashlib.sha256(name.encode('utf-8')).hexdigest()[:16]
            biome_id = f"biome_{name_hash}"
            
            client = get_supabase_client()
            serializable_data = SupabaseDatabase._serialize_data(biome_data)
            
            result = client.table('biomes').upsert({
                'id': biome_id,
                'data': serializable_data
            }).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error saving biome {biome_data}: {str(e)}")
            return False

    @staticmethod
    async def get_biome_three_star_room(biome: str) -> Optional[str]:
        """Get the room ID that has the 3-star item for a biome"""
        try:
            client = get_supabase_client()
            result = client.table('global_data').select('data').eq('key', f'biome_three_star_{biome}').execute()
            
            if result.data and len(result.data) > 0:
                return result.data[0]['data'].get('room_id')
            return None
        except Exception as e:
            logger.error(f"Error getting biome 3-star room for {biome}: {str(e)}")
            return None

    @staticmethod
    async def set_biome_three_star_room(biome: str, room_id: str) -> bool:
        """Set the room ID that has the 3-star item for a biome"""
        try:
            client = get_supabase_client()
            serializable_data = SupabaseDatabase._serialize_data({'room_id': room_id})
            
            result = client.table('global_data').upsert({
                'key': f'biome_three_star_{biome}',
                'data': serializable_data
            }).execute()
            
            return len(result.data) > 0
        except Exception as e:
            logger.error(f"Error setting biome 3-star room for {biome}: {str(e)}")
            return False

    @staticmethod
    async def reset_world() -> None:
        """Reset the entire game world by clearing all Supabase data (preserves user_profiles)"""
        try:
            client = get_supabase_client()
            
            # Clear all game-related tables (but preserve user_profiles)
            # Order matters due to foreign key constraints - clear dependent tables first
            tables = [
                'coordinates',  # References rooms
                'chunk_biomes',
                'biomes', 
                'global_data',
                'monsters',
                'items',
                'npcs',
                'players',  # References user_profiles (will be cleared but users preserved)
                'rooms'
            ]
            
            for table in tables:
                try:
                    # Delete all records in the table
                    # Note: Supabase requires a filter for delete operations, so we'll use a range that covers all data
                    result = client.table(table).delete().neq('created_at', '1970-01-01T00:00:00Z').execute()
                    logger.info(f"Cleared {len(result.data) if result.data else 0} records from {table}")
                except Exception as e:
                    logger.error(f"Error clearing table {table}: {str(e)}")
            
            logger.info("Supabase game data cleared (user_profiles preserved)")
        except Exception as e:
            logger.error(f"Error resetting world: {str(e)}")
            raise