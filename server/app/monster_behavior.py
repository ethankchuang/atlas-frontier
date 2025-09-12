import logging
import random
from typing import Dict, List, Any, Optional, Tuple
from .models import Player, Room, Monster

logger = logging.getLogger(__name__)

class MonsterBehaviorManager:
    """Manages monster behaviors based on their aggressiveness levels"""
    
    def __init__(self):
        # Track which directions territorial monsters are blocking
        # Format: {room_id: {monster_id: direction}}
        self.territorial_blocks = {}
        
        # Track aggressive monsters for movement checking
        # Format: {room_id: {monster_id: monster_name}}
        self.aggressive_monsters = {}
        
        # Track player's last room for aggressive monster logic
        # Format: {player_id: room_id}
        self.player_last_room = {}
    
    async def handle_player_room_entry(
        self, 
        player_id: str, 
        new_room_id: str, 
        old_room_id: str,
        entry_direction: str,
        room_data: Dict[str, Any],
        game_manager
    ) -> List[str]:
        """
        Handle player entering a room - trigger monster behaviors
        Returns list of messages to send to player
        """
        messages = []
        
        # Update player's last room
        self.player_last_room[player_id] = old_room_id
        logger.info(f"[MonsterBehavior] Updated player_last_room: {player_id} -> {old_room_id}")
        logger.info(f"[MonsterBehavior] All player_last_room entries: {self.player_last_room}")
        
        # Get monsters in the room
        monster_ids = room_data.get('monsters', [])
        if not monster_ids:
            return messages
        
        logger.info(f"[MonsterBehavior] Player {player_id} entered {new_room_id} from {entry_direction}, checking {len(monster_ids)} monsters")
        
        # Sync territorial blocks from persisted room properties (do not clear on entry)
        try:
            room_db = await game_manager.db.get_room(new_room_id)
            if room_db:
                props = room_db.get('properties', {}) or {}
                persisted_blocks = props.get('territorial_blocks', {}) or {}
                if persisted_blocks:
                    self.territorial_blocks[new_room_id] = dict(persisted_blocks)
                    logger.info(f"[MonsterBehavior] Synced persisted territorial blocks for {new_room_id}: {persisted_blocks}")
        except Exception as e:
            logger.error(f"[MonsterBehavior] Failed to sync persisted territorial blocks: {str(e)}")
        
        # Process each monster's behavior
        # PRIORITY: Territorial monsters take precedence over aggressive ones
        territorial_monsters = []
        aggressive_monsters = []
        
        for monster_id in monster_ids:
            monster_data = await game_manager.db.get_monster(monster_id)
            if not monster_data or not monster_data.get('is_alive', True):
                continue
                
            aggressiveness = monster_data.get('aggressiveness', 'neutral')
            monster_name = monster_data.get('name', 'Unknown Monster')
            
            # Categorize monsters by behavior
            if aggressiveness == 'territorial':
                territorial_monsters.append((monster_id, monster_name))
            elif aggressiveness == 'aggressive':
                aggressive_monsters.append((monster_id, monster_name))
        
        # Handle territorial monsters first (they take priority for blocking)
        for monster_id, monster_name in territorial_monsters:
            blocked_direction = await self._handle_territorial_monster(
                monster_id, monster_name, new_room_id, entry_direction, room_data
            )
            if blocked_direction:
                messages.append(f"🛡️ {monster_name} moves to block the {blocked_direction} exit, watching you warily.")
                # Persist territorial blocking info to room properties for admin tools/clients
                try:
                    room_db = await game_manager.db.get_room(new_room_id)
                    if room_db:
                        props = room_db.get('properties', {}) or {}
                        terr = props.get('territorial_blocks', {}) or {}
                        terr[monster_id] = blocked_direction
                        props['territorial_blocks'] = terr
                        room_db['properties'] = props
                        await game_manager.db.set_room(new_room_id, room_db)
                        logger.info(f"[MonsterBehavior] Persisted territorial block: {monster_name} blocks {blocked_direction} in {new_room_id}")
                except Exception as e:
                    logger.error(f"[MonsterBehavior] Failed to persist territorial block: {str(e)}")
        
        # Handle aggressive monsters (they can coexist with territorial ones)
        for monster_id, monster_name in aggressive_monsters:
            messages.append(await self._handle_aggressive_monster(
                player_id, monster_id, monster_name, new_room_id, game_manager
            ))
        
        return [msg for msg in messages if msg]  # Filter out None messages
    
    async def generate_monster_dialogue(self, monster_id: str, message: str, room_id: str, game_manager) -> Optional[str]:
        """Generate a monster's dialogue response using the AI with full context.
        Aggressive monsters won't talk and will attack instead (handled by caller)."""
        try:
            monster_data = await game_manager.db.get_monster(monster_id)
            if not monster_data:
                return None
            if not monster_data.get('is_alive', True):
                return None

            aggressiveness = monster_data.get('aggressiveness', 'neutral')
            if aggressiveness == 'aggressive':
                # Aggressive handled elsewhere
                return None

            # Gather context
            room_data = await game_manager.db.get_room(room_id) or {}
            player_message = (message or '').strip()

            # Build prompt for AI
            prompt = (
                "You are a creature in a medieval fantasy MUD game. Stay in character and reply briefly.\n"
                "CONSTRAINTS:\n"
                "- 1 sentence max (concise).\n"
                "- Natural, varied wording (avoid repeating the exact same phrase across turns).\n"
                "- No game mechanics or stats.\n"
                "CONTEXT:\n"
                f"Monster: {monster_data.get('name','Unknown')}\n"
                f"Description: {monster_data.get('description','')}\n"
                f"Size: {monster_data.get('size','unknown')} | Intelligence: {monster_data.get('intelligence','unknown')} | Aggressiveness: {aggressiveness}\n"
                f"Room: {room_data.get('title','Unknown Room')} - {room_data.get('description','')}\n"
                f"Player said: '{player_message}'\n"
                "TASK:\n"
                "- Respond in-character to the player line above.\n"
                "- If the player line is unclear, ask a short clarifying question.\n"
            )

            # Use AI to generate the response
            reply = await game_manager.ai_handler.generate_text(prompt)
            return (reply or '').strip()

        except Exception as e:
            logger.error(f"[MonsterBehavior] Error generating monster dialogue: {str(e)}")
            return None

    async def _handle_aggressive_monster(
        self, 
        player_id: str, 
        monster_id: str, 
        monster_name: str, 
        room_id: str,
        game_manager
    ) -> Optional[str]:
        """Handle aggressive monster behavior - they attack immediately"""
        try:
            logger.info(f"[MonsterBehavior] Aggressive monster {monster_name} in room {room_id}")
            
            # Store aggressive monster info for movement checking
            if room_id not in self.aggressive_monsters:
                self.aggressive_monsters[room_id] = {}
            self.aggressive_monsters[room_id][monster_id] = monster_name
            
            return f"⚔️ {monster_name} charges at you aggressively! The monster will attack if you try to move to a new room!"
            
        except Exception as e:
            logger.error(f"[MonsterBehavior] Error handling aggressive monster: {str(e)}")
            return None
    
    async def _handle_territorial_monster(
        self, 
        monster_id: str, 
        monster_name: str, 
        room_id: str, 
        entry_direction: str,
        room_data: Dict[str, Any]
    ) -> Optional[str]:
        """Handle territorial monster behavior - they block exits"""
        try:
            # Get available exits (excluding the one player came from)
            connections = room_data.get('connections', {})
            # CRITICAL: Exclude the opposite of the entry direction, not the entry direction itself
            # If player entered from east, we should NOT block west (the way they came)
            opposite_direction = self._get_opposite_direction(entry_direction)
            available_exits = [direction for direction in connections.keys() 
                             if direction != opposite_direction]
            
            logger.info(f"[MonsterBehavior] Territorial monster setup: entry={entry_direction}, opposite={opposite_direction}, excluded={opposite_direction}, available={available_exits}")
            
            if not available_exits:
                return None
            
            # Choose a random exit to block
            blocked_direction = random.choice(available_exits)
            
            # Store the blocking information
            if room_id not in self.territorial_blocks:
                self.territorial_blocks[room_id] = {}
            self.territorial_blocks[room_id][monster_id] = blocked_direction
            
            logger.info(f"[MonsterBehavior] Territorial monster {monster_name} blocking {blocked_direction} in {room_id}")
            
            return blocked_direction
            
        except Exception as e:
            logger.error(f"[MonsterBehavior] Error handling territorial monster: {str(e)}")
            return None
    
    def _get_opposite_direction(self, direction: str) -> str:
        """Get the opposite direction"""
        opposites = {
            'north': 'south',
            'south': 'north',
            'east': 'west',
            'west': 'east',
            'up': 'down',
            'down': 'up'
        }
        return opposites.get(direction.lower(), direction)
    
    async def check_territorial_blocking(
        self, 
        player_id: str, 
        room_id: str, 
        attempted_direction: str,
        game_manager
    ) -> Optional[Tuple[str, str]]:
        """
        Check if a territorial monster is blocking the player's movement
        Returns (monster_id, monster_name) if blocked, None if allowed
        """
        logger.info(f"[MonsterBehavior] Checking territorial blocking: player={player_id}, room={room_id}, direction={attempted_direction}")
        
        # Ensure in-memory blocks are synced from persisted data if missing
        if room_id not in self.territorial_blocks or not self.territorial_blocks.get(room_id):
            try:
                room_db = await game_manager.db.get_room(room_id)
                if room_db:
                    props = room_db.get('properties', {}) or {}
                    persisted = props.get('territorial_blocks', {}) or {}
                    if persisted:
                        self.territorial_blocks[room_id] = dict(persisted)
                        logger.info(f"[MonsterBehavior] Loaded persisted territorial blocks for {room_id}: {persisted}")
            except Exception as e:
                logger.error(f"[MonsterBehavior] Failed to load persisted territorial blocks: {str(e)}")
        
        if room_id not in self.territorial_blocks or not self.territorial_blocks.get(room_id):
            logger.info(f"[MonsterBehavior] No territorial blocks in room {room_id}")
            return None
        
        logger.info(f"[MonsterBehavior] Territorial blocks in {room_id}: {self.territorial_blocks[room_id]}")
        
        for monster_id, blocked_direction in self.territorial_blocks[room_id].items():
            logger.info(f"[MonsterBehavior] Checking monster {monster_id}: blocks {blocked_direction} vs attempted {attempted_direction.lower()}")
            if blocked_direction == attempted_direction.lower():
                # This monster is blocking this direction
                monster_data = await game_manager.db.get_monster(monster_id)
                if monster_data and monster_data.get('is_alive', True):
                    monster_name = monster_data.get('name', 'Unknown Monster')
                    logger.info(f"[MonsterBehavior] ⚔️ BLOCKING: Territorial monster {monster_name} blocking {attempted_direction}")
                    return monster_id, monster_name
                else:
                    logger.info(f"[MonsterBehavior] Monster {monster_id} is dead or missing, not blocking")
        
        return None
    
    async def handle_territorial_combat_initiation(
        self, 
        player_id: str, 
        monster_id: str, 
        room_id: str,
        direction: str,
        game_manager
    ) -> str:
        """Initiate combat with territorial monster when player tries to pass"""
        try:
            monster_data = await game_manager.db.get_monster(monster_id)
            monster_name = monster_data.get('name', 'Unknown Monster') if monster_data else 'Unknown Monster'
            
            # Import here to avoid circular import
            from .main import initiate_monster_duel
            
            logger.info(f"[MonsterBehavior] Initiating territorial combat: {monster_name} vs player {player_id}")
            
            # Initiate combat with proper action description
            await initiate_monster_duel(player_id, monster_id, f"attempt to move {direction}", room_id, game_manager)
            
            # Return message that will be sent to player
            return f"⚔️ {monster_name} blocks your path {direction} and engages you in combat!"
            
        except Exception as e:
            logger.error(f"[MonsterBehavior] Error initiating territorial combat: {str(e)}")
            return f"⚔️ The territorial monster blocks your path and attacks!"
    
    def clear_territorial_blocks_for_room(self, room_id: str):
        """Clear territorial blocks when monsters are defeated or leave"""
        if room_id in self.territorial_blocks:
            del self.territorial_blocks[room_id]
    
    def clear_territorial_block_for_monster(self, room_id: str, monster_id: str):
        """Clear territorial block for specific monster"""
        if room_id in self.territorial_blocks and monster_id in self.territorial_blocks[room_id]:
            del self.territorial_blocks[room_id][monster_id]
            
            # Clean up empty room entries
            if not self.territorial_blocks[room_id]:
                del self.territorial_blocks[room_id]
    
    async def check_aggressive_monster_blocking(
        self, 
        player_id: str, 
        room_id: str, 
        attempted_direction: str,
        game_manager
    ) -> Optional[Tuple[str, str]]:
        """
        Check if an aggressive monster should block the player's action
        Returns (monster_id, monster_name) if blocked, None if allowed
        """
        logger.info(f"[MonsterBehavior] Checking aggressive blocking: player={player_id}, room={room_id}, direction={attempted_direction}")
        
        if room_id not in self.aggressive_monsters:
            logger.info(f"[MonsterBehavior] No aggressive monsters in room {room_id}")
            return None
        
        # Get the player's last room
        last_room = self.player_last_room.get(player_id)
        logger.info(f"[MonsterBehavior] Player {player_id} last room: {last_room}")
        logger.info(f"[MonsterBehavior] All player_last_room entries: {self.player_last_room}")
        
        if not last_room:
            logger.info(f"[MonsterBehavior] No last room recorded for player {player_id}")
            return None
        
        # Special case: if direction is "any_action", this is a general action check
        if attempted_direction == "any_action":
            # For any action, aggressive monsters should block unless it's a retreat
            # We need to check if this is a movement action that would be a retreat
            # Since we don't have the action text here, we'll block all non-movement actions
            # Movement actions will be checked separately in the main action processing
            logger.info(f"[MonsterBehavior] ⚔️ BLOCKING: Aggressive monster blocking any action")
            # Return the first aggressive monster (they all behave the same)
            for monster_id, monster_name in self.aggressive_monsters[room_id].items():
                return monster_id, monster_name
        
        # Check if the attempted direction leads back to the last room (retreat)
        room_data = await game_manager.db.get_room(room_id)
        if not room_data:
            return None
        
        connections_raw = room_data.get('connections', {})
        # Normalize connection keys to lowercase strings (handle Enum keys in storage)
        connections = {}
        try:
            for k, v in connections_raw.items():
                key = getattr(k, 'value', k)
                if isinstance(key, str):
                    connections[key.lower()] = v
        except Exception:
            connections = {str(k).lower(): v for k, v in connections_raw.items()}
        target_room = connections.get(attempted_direction.lower())
        logger.info(f"[MonsterBehavior] Attempted direction {attempted_direction} leads to {target_room}")
        logger.info(f"[MonsterBehavior] Last room is {last_room}")
        
        if target_room == last_room:
            logger.info(f"[MonsterBehavior] Player {player_id} attempting to retreat to {last_room} - ALLOWED")
            return None  # Allow retreat
        
        # Player is trying to move to a new room - aggressive monster attacks
        logger.info(f"[MonsterBehavior] Player {player_id} attempting to move to new room {target_room} - BLOCKED")
        
        # Return the first aggressive monster (they all behave the same)
        for monster_id, monster_name in self.aggressive_monsters[room_id].items():
            logger.info(f"[MonsterBehavior] ⚔️ BLOCKING: Aggressive monster {monster_name} blocking movement to {target_room}")
            return monster_id, monster_name
        
        return None
    
    async def handle_aggressive_combat_initiation(
        self, 
        player_id: str, 
        monster_id: str, 
        room_id: str,
        direction: str,
        game_manager
    ) -> str:
        """Initiate combat with aggressive monster when player tries to perform any action"""
        try:
            monster_data = await game_manager.db.get_monster(monster_id)
            monster_name = monster_data.get('name', 'Unknown Monster') if monster_data else 'Unknown Monster'
            monster_size = (monster_data or {}).get('size', 'creature')
            monster_desc = (monster_data or {}).get('description', '').strip()
            brief_desc = ''
            if monster_desc:
                brief_desc = monster_desc.split('.')[0][:120]
            
            # Import here to avoid circular import
            from .main import initiate_monster_duel
            
            logger.info(f"[MonsterBehavior] Initiating aggressive combat: {monster_name} vs player {player_id}")
            
            # Initiate combat with proper action description
            if direction == "any_action":
                await initiate_monster_duel(player_id, monster_id, "attempt any action", room_id, game_manager)
                if brief_desc:
                    return f"⚔️ {monster_name} surges forward! The {monster_size} closes in as {brief_desc.lower()}"
                return f"⚔️ {monster_name} surges forward and attacks!"
            else:
                await initiate_monster_duel(player_id, monster_id, f"attempt to move {direction}", room_id, game_manager)
                if brief_desc:
                    return f"⚔️ {monster_name} cuts off your {direction} move! The {monster_size} advances as {brief_desc.lower()}"
                return f"⚔️ {monster_name} blocks your {direction} move and attacks!"
            
        except Exception as e:
            logger.error(f"[MonsterBehavior] Error initiating aggressive combat: {str(e)}")
            return f"⚔️ The aggressive monster blocks your path and attacks!"

# Global instance
monster_behavior_manager = MonsterBehaviorManager() 