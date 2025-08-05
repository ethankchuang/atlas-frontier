from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional, Any
import json
import asyncio
import random
from datetime import datetime
from sse_starlette.sse import EventSourceResponse
import logging

from .models import (
    ActionRequest,
    ActionResponse,
    ChatMessage,
    NPCInteraction,
    Player,
    Room,
    GameState,
    CreatePlayerRequest,
    PresenceRequest,
    Direction,
    ActionRecord,
    Monster
)
from .game_manager import GameManager
from .config import settings
from .logger import setup_logging
from .templates.items import GenericItemTemplate
import uuid
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta
import asyncio
from .game_manager import GameManager
from .database import Database
from .move_validator import MoveValidator
from .logger import setup_logging

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)


app = FastAPI(title="AI MUD Game Server")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}  # room_id -> {player_id: websocket}

    async def connect(self, websocket: WebSocket, room_id: str, player_id: str):
        logger.info(f"[WebSocket] New connection request - room: {room_id}, player: {player_id}")
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = {}
        self.active_connections[room_id][player_id] = websocket
        logger.info(f"[WebSocket] Connection accepted - room: {room_id}, player: {player_id}")
        logger.info(f"[WebSocket] Active connections: {self.get_connection_summary()}")

    def disconnect(self, room_id: str, player_id: str):
        logger.info(f"[WebSocket] Disconnecting - room: {room_id}, player: {player_id}")
        if room_id in self.active_connections:
            self.active_connections[room_id].pop(player_id, None)
            if not self.active_connections[room_id]:
                self.active_connections.pop(room_id)
        logger.info(f"[WebSocket] Active connections after disconnect: {self.get_connection_summary()}")

    def get_connection_summary(self) -> str:
        summary = {}
        for room_id, connections in self.active_connections.items():
            summary[room_id] = len(connections)
        return str(summary)

    async def broadcast_to_room(self, room_id: str, message: dict, exclude_player: Optional[str] = None):
        logger.info(f"[WebSocket] Broadcasting to room {room_id} - message type: {message.get('type')}")
        if room_id in self.active_connections:
            for player_id, connection in self.active_connections[room_id].items():
                if player_id != exclude_player:
                    try:
                        await connection.send_json(message)
                        logger.debug(f"[WebSocket] Sent message to player {player_id} in room {room_id}")
                    except Exception as e:
                        logger.error(f"[WebSocket] Failed to send message to player {player_id}: {str(e)}")
        else:
            logger.warning(f"[WebSocket] No active connections in room {room_id}")

    async def send_to_player(self, room_id: str, player_id: str, message: dict):
        """Send a message to a specific player in a room"""
        logger.info(f"[WebSocket] Sending to player {player_id} in room {room_id} - message type: {message.get('type')}")
        if room_id in self.active_connections and player_id in self.active_connections[room_id]:
            try:
                await self.active_connections[room_id][player_id].send_json(message)
                logger.debug(f"[WebSocket] Sent message to player {player_id} in room {room_id}")
            except Exception as e:
                logger.error(f"[WebSocket] Failed to send message to player {player_id}: {str(e)}")
        else:
            logger.warning(f"[WebSocket] Player {player_id} not found in room {room_id}")

def rarity_to_stars(rarity: int) -> str:
    """Convert rarity number to star representation"""
    return "★" * rarity + "☆" * (4 - rarity)

# Initialize managers
manager = ConnectionManager()
game_manager = GameManager()
game_manager.set_connection_manager(manager)

# Item types will be loaded when game manager is first accessed
@app.on_event("startup")
async def startup_event():
    """Load item types for existing worlds on startup"""
    try:
        # Load item types from database for existing worlds
        await game_manager.load_item_types()
        
        logger.info("Server startup completed - types loaded successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        # Continue starting up even if type loading fails

def get_game_manager():
    return game_manager

# Global duel state tracking
duel_moves = {}  # {duel_id: {player_id: move}}
duel_pending = {}  # {duel_id: {player1_id, player2_id, room_id, round, player1_condition, player2_condition, player1_tags, player2_tags}}

# Monster combat globals
monster_combat_pending = {}  # {combat_id: {player_id, monster_id, room_id, round, player_condition, monster_condition, player_tags, monster_tags}}
monster_combat_moves = {}   # {combat_id: {player_id: move, monster_id: move}}

async def handle_duel_message(message: dict, room_id: str, player_id: str, game_manager: GameManager):
    """Handle duel-related messages and coordinate AI analysis"""
    global duel_moves, duel_pending
    
    message_type = message.get("type")
    
    if message_type == "duel_move":
        # Store the move
        duel_id = message.get("duel_id")
        
        # If no duel_id provided, find it based on player and opponent (for monster duels)
        if not duel_id:
            opponent_id = message.get("opponent_id")
            if opponent_id:
                # Find active duel involving this player and opponent
                for potential_duel_id, duel_info in duel_pending.items():
                    if ((duel_info["player1_id"] == player_id and duel_info["player2_id"] == opponent_id) or
                        (duel_info["player1_id"] == opponent_id and duel_info["player2_id"] == player_id)):
                        duel_id = potential_duel_id
                        logger.info(f"[handle_duel_message] Found duel_id {duel_id} for player {player_id} vs {opponent_id}")
                        break
        
        if not duel_id:
            logger.error(f"[handle_duel_message] Could not find duel_id for player {player_id}")
            return
            
        move = message["move"]
        
        if duel_id not in duel_moves:
            duel_moves[duel_id] = {}
        
        duel_moves[duel_id][player_id] = move
        
        # Check if both players have submitted moves
        if duel_id in duel_pending:
            pending_duel = duel_pending[duel_id]
            player_ids = {pending_duel["player1_id"], pending_duel["player2_id"]}
            
            # For monster duels, auto-submit monster move when player submits
            if pending_duel.get('is_monster_duel') and player_id == pending_duel["player1_id"]:
                # Player submitted move, now auto-submit monster move
                monster_id = pending_duel["player2_id"]
                player_data = await game_manager.db.get_player(player_id)
                monster_data = pending_duel.get('monster_data', {})
                room_id = pending_duel["room_id"]
                current_round = pending_duel["round"]
                
                await auto_submit_monster_move(duel_id, monster_id, player_data, monster_data, room_id, current_round, game_manager)
            elif player_ids.issubset(set(duel_moves[duel_id].keys())):
                # Both moves received, process the round
                await analyze_duel_moves(duel_id, game_manager)

async def get_room_monsters_description(room_id: str, game_manager: GameManager) -> str:
    """Get a description of monsters in the room for display to players"""
    try:
        room_data = await game_manager.db.get_room(room_id)
        if not room_data or not room_data.get('monsters'):
            return ""
        
        monster_descriptions = []
        for monster_id in room_data['monsters']:
            monster_data = await game_manager.db.get_monster(monster_id)
            if monster_data and monster_data.get('is_alive', True):
                name = monster_data['name']
                aggressiveness = monster_data['aggressiveness']
                size = monster_data['size']
                
                # Create descriptive text based on attributes
                size_desc = {
                    'insect': 'tiny',
                    'chicken': 'small', 
                    'human': 'medium-sized',
                    'horse': 'large',
                    'dinosaur': 'enormous',
                    'colossal': 'massive'
                }.get(size, 'strange')
                
                aggr_desc = {
                    'passive': 'peaceful',
                    'neutral': 'watchful',
                    'territorial': 'defensive',
                    'aggressive': 'menacing'
                }.get(aggressiveness, 'mysterious')
                
                monster_descriptions.append(f"A {size_desc}, {aggr_desc} {name}")
        
        if monster_descriptions:
            if len(monster_descriptions) == 1:
                return f"🐲 {monster_descriptions[0]} is here."
            else:
                monsters_text = ", ".join(monster_descriptions[:-1]) + f", and {monster_descriptions[-1]}"
                return f"🐲 You see {monsters_text} in this area."
        
        return ""
        
    except Exception as e:
        logger.error(f"Error getting room monsters description: {str(e)}")
        return ""

async def generate_monster_combat_move(monster_data: Dict[str, Any], player_data: Dict[str, Any], room_data: Dict[str, Any], round_number: int, game_manager: GameManager) -> str:
    """Generate a contextual combat move for a monster using AI"""
    try:
        # Build context for AI
        monster_name = monster_data.get('name', 'Unknown Monster')
        monster_size = monster_data.get('size', 'human')
        monster_aggressiveness = monster_data.get('aggressiveness', 'neutral')
        monster_intelligence = monster_data.get('intelligence', 'animal')
        monster_description = monster_data.get('description', '')
        monster_special_effects = monster_data.get('special_effects', '')
        monster_health = monster_data.get('health', 100)
        
        player_name = player_data.get('name', 'Unknown Player')
        
        room_title = room_data.get('title', 'Unknown Room')
        room_biome = room_data.get('biome', 'unknown')
        
        # Create AI prompt for monster move generation
        prompt = f"""You are controlling a monster in combat. Generate a single combat move for this creature.

MONSTER DETAILS:
- Name: {monster_name}
- Size: {monster_size}
- Aggressiveness: {monster_aggressiveness}
- Intelligence: {monster_intelligence}
- Description: {monster_description}
- Special Effects: {monster_special_effects}
- Current Health: {monster_health}

COMBAT CONTEXT:
- Round: {round_number}
- Fighting: {player_name}
- Location: {room_title} ({room_biome})

MOVE GENERATION RULES:
1. Generate ONE specific combat action (2-5 words)
2. Match the monster's aggressiveness level:
   - passive: defensive moves, retreating, minimal attacks
   - neutral: balanced offense and defense
   - aggressive: fierce attacks, advancing moves
   - territorial: protective attacks, warning strikes
3. Match the monster's intelligence:
   - animal: instinctive moves (bite, claw, pounce)
   - subhuman: simple tactics (charge, strike, dodge)
   - human: tactical moves (feint, combo attacks, positioning)
   - omnipotent: complex strategies (multi-stage attacks)
4. Use size appropriately:
   - insect/chicken: quick, darting moves
   - human/horse: standard combat moves
   - dinosaur/colossal: powerful, crushing moves
5. Incorporate special effects when relevant
6. Use basic combat actions (no equipment needed)

EXAMPLES:
- "lunges with claws extended"
- "breathes a cone of fire"
- "charges with lowered horns"
- "strikes with venomous fangs"
- "dodges and counterattacks"

Generate ONLY the move, nothing else:"""

        # Get AI response
        ai_response = await game_manager.ai_handler.generate_text(prompt)
        move = ai_response.strip()
        
        # Ensure reasonable length
        if len(move) > 100:
            move = move[:100]
        
        logger.info(f"[generate_monster_combat_move] Generated move for {monster_name}: '{move}'")
        return move
        
    except Exception as e:
        logger.error(f"Error generating monster combat move: {str(e)}")
        # Fallback based on aggressiveness
        aggressiveness = monster_data.get('aggressiveness', 'neutral')
        fallback_moves = {
            'aggressive': 'lunges forward aggressively',
            'territorial': 'strikes defensively',
            'passive': 'moves cautiously away',
            'neutral': 'attacks with claws'
        }
        return fallback_moves.get(aggressiveness, 'attacks')

async def detect_monster_attack(action_text: str, player_id: str, room_data: Dict[str, Any], game_manager: GameManager) -> str:
    """Detect if a player action is attacking a monster and return monster_id if so"""
    try:
        if not room_data or not room_data.get('monsters'):
            return None
            
        # Get monster data
        monsters_in_room = []
        for monster_id in room_data['monsters']:
            monster_data = await game_manager.db.get_monster(monster_id)
            if monster_data and monster_data.get('is_alive', True):
                monsters_in_room.append((monster_id, monster_data))
        
        if not monsters_in_room:
            return None
        
        # Check for attack keywords
        attack_keywords = [
            'attack', 'fight', 'strike', 'hit', 'punch', 'kick', 'slash', 'stab',
            'shoot', 'fire', 'cast', 'throw', 'charge', 'tackle', 'grapple',
            'kill', 'slay', 'destroy', 'harm', 'hurt', 'wound', 'damage'
        ]
        
        action_lower = action_text.lower()
        
        # Check if action contains attack keywords
        is_attack = any(keyword in action_lower for keyword in attack_keywords)
        if not is_attack:
            return None
        
        # For now, attack the first monster in the room
        # TODO: Later we can add logic to target specific monsters by name
        target_monster_id, target_monster_data = monsters_in_room[0]
        
        logger.info(f"[detect_monster_attack] Player {player_id} attacking monster {target_monster_data.get('name', 'Unknown')} with action: '{action_text}'")
        return target_monster_id
        
    except Exception as e:
        logger.error(f"Error detecting monster attack: {str(e)}")
        return None

async def initiate_monster_duel(player_id: str, monster_id: str, player_action: str, room_id: str, game_manager: GameManager):
    """Start a duel between a player and a monster using the existing duel system"""
    try:
        import uuid
        duel_id = f"monster_duel_{uuid.uuid4()}"
        
        logger.info(f"[initiate_monster_duel] Starting duel {duel_id}: {player_id} vs {monster_id}")
        
        # Get player and monster data
        player_data = await game_manager.db.get_player(player_id)
        monster_data = await game_manager.db.get_monster(monster_id)
        
        if not player_data or not monster_data:
            logger.error(f"[initiate_monster_duel] Missing data - player: {bool(player_data)}, monster: {bool(monster_data)}")
            return
        
        # Send duel challenge from player to monster
        duel_challenge = {
            "type": "duel_challenge",
            "challenger_id": player_id,
            "target_id": monster_id,  # Monster ID as target
            "room_id": room_id,
            "timestamp": datetime.now().isoformat()
        }
        await manager.broadcast_to_room(room_id, duel_challenge)
        
        # Immediately auto-accept the duel as the monster
        await asyncio.sleep(0.1)  # Small delay for realism
        
        duel_response = {
            "type": "duel_response", 
            "challenger_id": player_id,
            "responder_id": monster_id,  # Monster ID as responder
            "response": "accept",
            "room_id": room_id,
            "timestamp": datetime.now().isoformat(),
            "monster_name": monster_data.get('name', 'Unknown Monster'),  # Add monster name for frontend
            "is_monster_duel": True  # Flag to indicate this is a monster duel
        }
        await manager.broadcast_to_room(room_id, duel_response)
        
        # Initialize the duel in the pending duels system
        duel_pending[duel_id] = {
            "player1_id": player_id,
            "player2_id": monster_id,  # Use monster_id as player2
            "room_id": room_id,
            "round": 1,
            "player1_condition": "healthy",
            "player2_condition": "healthy", 
            "player1_tags": [],
            "player2_tags": [],
            "player1_total_severity": 0,
            "player2_total_severity": 0,
            "is_monster_duel": True,  # Flag for special handling
            "monster_data": monster_data  # Store monster data for AI move generation
        }
        
        # Don't store the initial attack - let player choose their combat move
        # The initial action was just to initiate the duel
        
        # Since player hasn't submitted a move yet, wait for them to do so
        # The auto_submit_monster_move will be called when player submits their move
        logger.info(f"[initiate_monster_duel] Duel setup complete. Player must now choose their combat move.")
        
    except Exception as e:
        logger.error(f"Error initiating monster duel: {str(e)}")

async def auto_submit_monster_move(duel_id: str, monster_id: str, player_data: dict, monster_data: dict, room_id: str, round_number: int, game_manager: GameManager):
    """Automatically generate and submit a move for a monster in a duel"""
    try:
        # Get room data
        room_data = await game_manager.db.get_room(room_id)
        
        # Generate monster move
        monster_move = await generate_monster_combat_move(
            monster_data, player_data, room_data, round_number, game_manager
        )
        
        # Submit the monster's move
        if duel_id not in duel_moves:
            duel_moves[duel_id] = {}
        duel_moves[duel_id][monster_id] = monster_move
        
        logger.info(f"[auto_submit_monster_move] Monster {monster_data.get('name')} submitted move: '{monster_move}'")
        
        # Send duel move message for the monster (so frontend knows monster submitted)
        duel_move_message = {
            "type": "duel_move",
            "player_id": monster_id,
            "move": "preparing combat action...",  # Don't reveal the actual move
            "room_id": room_id,
            "timestamp": datetime.now().isoformat(),
            "is_monster_move": True,
            "monster_name": monster_data.get('name', 'Unknown Monster')
        }
        await manager.broadcast_to_room(room_id, duel_move_message)
        
        # Check if both moves are now ready for processing
        if duel_id in duel_pending:
            pending_duel = duel_pending[duel_id]
            player_ids = {pending_duel["player1_id"], pending_duel["player2_id"]}
            
            if player_ids.issubset(set(duel_moves[duel_id].keys())):
                # Both moves received, process the round
                logger.info(f"[auto_submit_monster_move] Both moves ready, processing duel round for {duel_id}")
                await analyze_duel_moves(duel_id, game_manager)
                
    except Exception as e:
        logger.error(f"Error auto-submitting monster move: {str(e)}")

async def prepare_next_monster_duel_round(duel_id: str, game_manager: GameManager):
    """Prepare the next round for a monster duel by auto-generating monster moves"""
    try:
        if duel_id not in duel_pending:
            return
            
        duel_info = duel_pending[duel_id]
        if not duel_info.get('is_monster_duel'):
            return
            
        player_id = duel_info['player1_id']
        monster_id = duel_info['player2_id']
        room_id = duel_info['room_id']
        next_round = duel_info['round'] + 1
        
        # Update round number (don't clear moves here, they'll be cleared when new moves arrive)
        duel_info['round'] = next_round
        
        # Send "next round" message to prepare UI
        next_round_message = {
            "type": "duel_next_round",
            "round": next_round,
            "player1_condition": duel_info['player1_condition'],
            "player2_condition": duel_info['player2_condition'],
            "player1_total_severity": duel_info['player1_total_severity'],
            "player2_total_severity": duel_info['player2_total_severity'],
            "room_id": room_id,
            "timestamp": datetime.now().isoformat()
        }
        await manager.broadcast_to_room(room_id, next_round_message)
        
        logger.info(f"[prepare_next_monster_duel_round] Prepared round {next_round} for monster duel {duel_id}")
        
    except Exception as e:
        logger.error(f"Error preparing next monster duel round: {str(e)}")

async def analyze_monster_combat(combat_id: str, game_manager: GameManager):
    """Analyze combat between a player and monster (similar to analyze_duel_moves)"""
    try:
        logger.info(f"[analyze_monster_combat] Starting analysis for combat {combat_id}")
        
        combat_info = monster_combat_pending[combat_id]
        player_id = combat_info['player_id']
        monster_id = combat_info['monster_id']
        room_id = combat_info['room_id']
        current_round = combat_info['round']
        
        # Get moves
        moves = monster_combat_moves[combat_id]
        player_move = moves.get(player_id, 'do nothing')
        monster_move = moves.get(monster_id, 'do nothing')
        
        logger.info(f"[analyze_monster_combat] Round {current_round}: {player_id} vs {monster_id}")
        logger.info(f"[analyze_monster_combat] Moves: '{player_move}' vs '{monster_move}'")
        
        # Get player and monster data
        player_data = await game_manager.db.get_player(player_id)
        monster_data = await game_manager.db.get_monster(monster_id)
        player_name = player_data.get('name', 'Unknown') if player_data else "Unknown"
        monster_name = monster_data.get('name', 'Unknown Monster') if monster_data else "Unknown Monster"
        player_inventory = player_data.get('inventory', []) if player_data else []
        
        # Get room information
        room_data = await game_manager.db.get_room(room_id)
        room_name = room_data.get('title', 'Unknown Room') if room_data else "Unknown Room"
        room_description = room_data.get('description', 'An unknown location') if room_data else "An unknown location"
        
        # Get current conditions and tags
        player_condition = combat_info.get('player_condition', 'healthy')
        monster_condition = combat_info.get('monster_condition', 'healthy')
        player_current_tags = combat_info.get('player_tags', [])
        monster_current_tags = combat_info.get('monster_tags', [])
        
        # Validate equipment (monsters don't have inventory, so only validate player)
        equipment_result = await validate_equipment(
            player_name, player_move, player_inventory,
            monster_name, monster_move, [],  # Monster has no inventory
            game_manager
        )
        
        # Determine invalid moves
        player_invalid = None if equipment_result['player1_valid'] else {
            'move': player_move,
            'reason': equipment_result['player1_reason']
        }
        monster_invalid = None  # Monsters always use valid basic attacks
        
        logger.info(f"[analyze_monster_combat] Equipment validation complete:")
        logger.info(f"[analyze_monster_combat] {player_name}: {'VALID' if equipment_result['player1_valid'] else 'INVALID'} - {equipment_result['player1_reason']}")
        logger.info(f"[analyze_monster_combat] {monster_name}: VALID (monster attacks)")
        
        # Analyze combat outcome
        logger.info(f"[analyze_monster_combat] Analyzing combat outcome...")
        combat_outcome = await analyze_combat_outcome(
            player_name, player_move, player_condition, equipment_result['player1_valid'],
            monster_name, monster_move, monster_condition, True,  # Monster moves always valid
            player_invalid, monster_invalid, player_inventory, [],
            room_name, room_description, game_manager
        )
        
        logger.info(f"[analyze_monster_combat] Combat outcome:")
        logger.info(f"[analyze_monster_combat] {player_name}: {combat_outcome['player1_result']['condition']} (can_continue: {combat_outcome['player1_result']['can_continue']})")
        logger.info(f"[analyze_monster_combat] {monster_name}: {combat_outcome['player2_result']['condition']} (can_continue: {combat_outcome['player2_result']['can_continue']})")
        
        # Generate narrative
        logger.info(f"[analyze_monster_combat] Generating combat narrative...")
        narrative = await generate_combat_narrative(
            player_name, player_move, combat_outcome['player1_result'],
            monster_name, monster_move, combat_outcome['player2_result'],
            player_invalid, monster_invalid, current_round,
            room_name, room_description, game_manager
        )
        
        logger.info(f"[analyze_monster_combat] Narrative generated: {narrative[:100]}...")
        
        # Generate tags based on narrative
        logger.info(f"[analyze_monster_combat] Generating tags from narrative...")
        tags_result = await generate_combat_tags_from_narrative(
            player_name, monster_name, narrative, player_current_tags, monster_current_tags,
            game_manager
        )
        
        logger.info(f"[analyze_monster_combat] Tags generated:")
        logger.info(f"[analyze_monster_combat] {player_name} new tags: {[tag['name'] for tag in tags_result['player1_new_tags']]}")
        logger.info(f"[analyze_monster_combat] {monster_name} new tags: {[tag['name'] for tag in tags_result['player2_new_tags']]}")
        
        # Calculate total severity
        player_current_total = combat_info.get('player_total_severity', 0)
        monster_current_total = combat_info.get('monster_total_severity', 0)
        
        player_new_severity = sum(tag['severity'] for tag in tags_result['player1_new_tags'] if tag['type'] == 'negative')
        monster_new_severity = sum(tag['severity'] for tag in tags_result['player2_new_tags'] if tag['type'] == 'negative')
        
        player_total_severity = player_current_total + player_new_severity
        monster_total_severity = monster_current_total + monster_new_severity
        
        # Check if combat should end
        combat_ends = (
            combat_outcome['player1_result']['can_continue'] == False or
            combat_outcome['player2_result']['can_continue'] == False or
            player_total_severity >= 50 or
            monster_total_severity >= 50
        )
        
        logger.info(f"[analyze_monster_combat] Severity totals: {player_name}={player_total_severity}, {monster_name}={monster_total_severity}")
        logger.info(f"[analyze_monster_combat] Combat ends: {combat_ends}")
        
        # Update combat state
        combat_info['player_condition'] = combat_outcome['player1_result']['condition']
        combat_info['monster_condition'] = combat_outcome['player2_result']['condition']
        combat_info['player_tags'].extend(tags_result['player1_new_tags'])
        combat_info['monster_tags'].extend(tags_result['player2_new_tags'])
        combat_info['player_total_severity'] = player_total_severity
        combat_info['monster_total_severity'] = monster_total_severity
        
        # Update monster health if severely damaged
        if monster_total_severity >= 50:
            monster_data['is_alive'] = False
            await game_manager.db.set_monster(monster_id, monster_data)
            logger.info(f"[analyze_monster_combat] {monster_name} has been defeated!")
        
        # Send results to player
        await send_monster_combat_results(
            room_id, player_id, monster_id, current_round,
            player_move, monster_move,
            combat_outcome['player1_result']['condition'],
            combat_outcome['player2_result']['condition'],
            tags_result['player1_new_tags'], tags_result['player2_new_tags'],
            player_total_severity, monster_total_severity,
            narrative, combat_ends, game_manager
        )
        
        # Clean up if combat ends
        if combat_ends:
            if combat_id in monster_combat_pending:
                del monster_combat_pending[combat_id]
            if combat_id in monster_combat_moves:
                del monster_combat_moves[combat_id]
        else:
            # Prepare for next round
            combat_info['round'] = current_round + 1
        
    except Exception as e:
        logger.error(f"Error analyzing monster combat: {str(e)}")

async def send_monster_combat_results(room_id: str, player_id: str, monster_id: str, round_number: int,
                                    player_move: str, monster_move: str, player_condition: str, monster_condition: str,
                                    player_new_tags: List[Dict], monster_new_tags: List[Dict],
                                    player_total_severity: int, monster_total_severity: int,
                                    narrative: str, combat_ends: bool, game_manager: GameManager):
    """Send monster combat results to the player via WebSocket"""
    try:
        # Get monster name
        monster_data = await game_manager.db.get_monster(monster_id)
        monster_name = monster_data.get('name', 'Unknown Monster') if monster_data else "Unknown Monster"
        
        # Format combat message
        combat_message = {
            "type": "monster_combat_outcome",
            "round": round_number,
            "monster_name": monster_name,
            "player_move": player_move,
            "monster_move": monster_move,
            "player_condition": player_condition,
            "monster_condition": monster_condition,
            "player_new_tags": player_new_tags,
            "monster_new_tags": monster_new_tags,
            "player_severity": player_total_severity,
            "monster_severity": monster_total_severity,
            "narrative": narrative,
            "combat_ends": combat_ends,
            "monster_defeated": monster_total_severity >= 50
        }
        
        # Send to room
        await manager.broadcast_to_room(room_id, combat_message)
        
        logger.info(f"[send_monster_combat_results] Sent combat results to room {room_id}")
        
    except Exception as e:
        logger.error(f"Error sending monster combat results: {str(e)}")

async def analyze_duel_moves(duel_id: str, game_manager: GameManager):
    """Analyze the moves for a duel and determine the outcome"""
    try:
        logger.info(f"[analyze_duel_moves] Starting analysis for duel {duel_id}")
        
        duel_info = duel_pending[duel_id]
        player1_id = duel_info['player1_id']
        player2_id = duel_info['player2_id']
        room_id = duel_info['room_id']
        current_round = duel_info['round']
        
        # Get player moves
        moves = duel_moves[duel_id]
        player1_move = moves.get(player1_id, 'do nothing')
        player2_move = moves.get(player2_id, 'do nothing')
        
        logger.info(f"[analyze_duel_moves] Round {current_round}: {player1_id} vs {player2_id}")
        logger.info(f"[analyze_duel_moves] Moves: '{player1_move}' vs '{player2_move}'")
        
        # Get player names and inventory
        player1_data = await game_manager.db.get_player(player1_id)
        player1_name = player1_data.get('name', 'Unknown') if player1_data else "Unknown"
        player1_inventory = player1_data.get('inventory', []) if player1_data else []
        
        # Handle monster duels
        is_monster_duel = duel_info.get('is_monster_duel', False)
        if is_monster_duel:
            # Player2 is a monster
            monster_data = duel_info.get('monster_data', {})
            player2_name = monster_data.get('name', 'Unknown Monster')
            player2_inventory = []  # Monsters don't have inventories
        else:
            # Player2 is a regular player
            player2_data = await game_manager.db.get_player(player2_id)
            player2_name = player2_data.get('name', 'Unknown') if player2_data else "Unknown"
            player2_inventory = player2_data.get('inventory', []) if player2_data else []
        
        # Get room information for environment context
        room_data = await game_manager.db.get_room(room_id)
        room_name = room_data.get('title', 'Unknown Room') if room_data else "Unknown Room"
        room_description = room_data.get('description', 'An unknown location') if room_data else "An unknown location"
        
        # Get current conditions and tags
        player1_condition = duel_info.get('player1_condition', 'healthy')
        player2_condition = duel_info.get('player2_condition', 'healthy')
        player1_current_tags = duel_info.get('player1_tags', [])
        player2_current_tags = duel_info.get('player2_tags', [])
        
        # Validate equipment (skip validation for monsters)
        is_monster_duel = duel_info.get('is_monster_duel', False)
        equipment_result = await validate_equipment(
            player1_name, player1_move, player1_inventory,
            player2_name, player2_move, player2_inventory,
            game_manager, is_monster_duel
        )
        
        # Determine invalid moves
        player1_invalid = None if equipment_result['player1_valid'] else {
            'move': player1_move,
            'reason': equipment_result['player1_reason']
        }
        player2_invalid = None if equipment_result['player2_valid'] else {
            'move': player2_move,
            'reason': equipment_result['player2_reason']
        }
        
        logger.info(f"[analyze_duel_moves] Equipment validation complete:")
        logger.info(f"[analyze_duel_moves] {player1_name}: {'VALID' if equipment_result['player1_valid'] else 'INVALID'} - {equipment_result['player1_reason']}")
        logger.info(f"[analyze_duel_moves] {player2_name}: {'VALID' if equipment_result['player2_valid'] else 'INVALID'} - {equipment_result['player2_reason']}")
        
        # Analyze combat outcome
        logger.info(f"[analyze_duel_moves] Analyzing combat outcome...")
        combat_outcome = await analyze_combat_outcome(
            player1_name, player1_move, player1_condition, equipment_result['player1_valid'],
            player2_name, player2_move, player2_condition, equipment_result['player2_valid'],
            player1_invalid, player2_invalid, player1_inventory, player2_inventory,
            room_name, room_description, game_manager
        )
        
        logger.info(f"[analyze_duel_moves] Combat outcome:")
        logger.info(f"[analyze_duel_moves] {player1_name}: {combat_outcome['player1_result']['condition']} (can_continue: {combat_outcome['player1_result']['can_continue']})")
        logger.info(f"[analyze_duel_moves] {player2_name}: {combat_outcome['player2_result']['condition']} (can_continue: {combat_outcome['player2_result']['can_continue']})")
        
        # Generate narrative FIRST
        logger.info(f"[analyze_duel_moves] Generating combat narrative...")
        narrative = await generate_combat_narrative(
            player1_name, player1_move, combat_outcome['player1_result'],
            player2_name, player2_move, combat_outcome['player2_result'],
            player1_invalid, player2_invalid, current_round,
            room_name, room_description, game_manager
        )
        
        logger.info(f"[analyze_duel_moves] Narrative generated: {narrative[:100]}...")
        
        # Generate tags BASED ON the narrative
        logger.info(f"[analyze_duel_moves] Generating tags from narrative...")
        tags_result = await generate_combat_tags_from_narrative(
            player1_name, player2_name, narrative, player1_current_tags, player2_current_tags,
            game_manager
        )
        
        logger.info(f"[analyze_duel_moves] Tags generated:")
        logger.info(f"[analyze_duel_moves] {player1_name} new tags: {[tag['name'] for tag in tags_result['player1_new_tags']]}")
        logger.info(f"[analyze_duel_moves] {player2_name} new tags: {[tag['name'] for tag in tags_result['player2_new_tags']]}")
        
        # Calculate total severity
        player1_current_total = duel_info.get('player1_total_severity', 0)
        player2_current_total = duel_info.get('player2_total_severity', 0)
        
        player1_new_severity = sum(tag['severity'] for tag in tags_result['player1_new_tags'] if tag['type'] == 'negative')
        player2_new_severity = sum(tag['severity'] for tag in tags_result['player2_new_tags'] if tag['type'] == 'negative')
        
        player1_total_severity = player1_current_total + player1_new_severity
        player2_total_severity = player2_current_total + player2_new_severity
    
        # Check if combat should end
        combat_ends = (
            combat_outcome['player1_result']['can_continue'] == False or
            combat_outcome['player2_result']['can_continue'] == False or
            player1_total_severity >= 50 or
            player2_total_severity >= 50
        )
        
        logger.info(f"[analyze_duel_moves] Severity totals: {player1_name}={player1_total_severity}, {player2_name}={player2_total_severity}")
        logger.info(f"[analyze_duel_moves] Combat ends: {combat_ends} (reason: {'player1_can_continue=False' if not combat_outcome['player1_result']['can_continue'] else ''} {'player2_can_continue=False' if not combat_outcome['player2_result']['can_continue'] else ''} {'player1_severity>=50' if player1_total_severity >= 50 else ''} {'player2_severity>=50' if player2_total_severity >= 50 else ''})")
    
        # Update duel state
        duel_info['player1_condition'] = combat_outcome['player1_result']['condition']
        duel_info['player2_condition'] = combat_outcome['player2_result']['condition']
        duel_info['player1_tags'].extend(tags_result['player1_new_tags'])
        duel_info['player2_tags'].extend(tags_result['player2_new_tags'])
        duel_info['player1_total_severity'] = player1_total_severity
        duel_info['player2_total_severity'] = player2_total_severity
    
        # Send results to players
        await send_duel_results(
            duel_id, room_id, player1_id, player2_id, current_round,
            player1_move, player2_move,
            combat_outcome['player1_result']['condition'],
            combat_outcome['player2_result']['condition'],
            tags_result['player1_new_tags'], tags_result['player2_new_tags'],
            player1_total_severity, player2_total_severity,
            narrative, combat_ends, game_manager
        )
        
        # Handle monster duel continuation
        if not combat_ends and duel_info.get('is_monster_duel'):
            # For monster duels, don't call prepare_next_monster_duel_round here
            # The next round will be handled when the player submits their next move
            logger.info(f"[analyze_duel_moves] Monster duel continues to round {current_round + 1}")
    
    except Exception as e:
        logger.error(f"Error analyzing duel round: {str(e)}")
        # Send error message to players
        error_message = {
            "type": "duel_outcome",
            "winner_id": None,
            "loser_id": None,
            "analysis": "The duel ended in confusion due to an error.",
            "room_id": room_id,
            "timestamp": datetime.now().isoformat()
        }
        await manager.send_to_player(room_id, player1_id, error_message)
        await manager.send_to_player(room_id, player2_id, error_message)
        
        # Clean up duel state
        if duel_id in duel_moves:
            del duel_moves[duel_id]
        if duel_id in duel_pending:
            del duel_pending[duel_id]

async def validate_equipment(player1_name: str, player1_move: str, player1_inventory: List[str], 
                           player2_name: str, player2_move: str, player2_inventory: List[str], 
                           game_manager: GameManager, is_monster_duel: bool = False) -> Dict[str, Any]:
    """Validate if moves are possible with current equipment using enhanced move validator"""
    
    logger.info(f"[validate_equipment] Starting enhanced validation for duel moves")
    logger.info(f"[validate_equipment] {player1_name}: '{player1_move}' (inventory: {player1_inventory})")
    logger.info(f"[validate_equipment] {player2_name}: '{player2_move}' (inventory: {player2_inventory})")
    
    try:
        # Get player IDs from names (we need to find them in the game manager)
        player1_id = None
        player2_id = None
        
        # Find players by name in the current room - improved lookup
        logger.info(f"[validate_equipment] Looking for players by name: {player1_name}, {player2_name}")
        logger.info(f"[validate_equipment] Active connections: {game_manager.connection_manager.active_connections}")
        
        for room_id in game_manager.connection_manager.active_connections:
            for pid in game_manager.connection_manager.active_connections[room_id]:
                try:
                    player = await game_manager.get_player(pid)
                    if player:
                        logger.info(f"[validate_equipment] Found player: {player.name} (ID: {pid})")
                        if player.name == player1_name:
                            player1_id = pid
                            logger.info(f"[validate_equipment] Matched {player1_name} to ID: {pid}")
                        elif player.name == player2_name:
                            player2_id = pid
                            logger.info(f"[validate_equipment] Matched {player2_name} to ID: {pid}")
                except Exception as e:
                    logger.error(f"[validate_equipment] Error getting player {pid}: {str(e)}")
                    continue
        
        # Handle monster duels - skip validation for monsters
        if is_monster_duel:
            # In monster duels, player2 is the monster - always valid
            if not player1_id:
                logger.warning(f"[validate_equipment] Could not find player ID for {player1_name}")
                return {
                    "player1_valid": False,
                    "player1_reason": f"Could not find player {player1_name}",
                    "player2_valid": True,
                    "player2_reason": "Monster moves are always valid"
                }
            else:
                # Validate only the player, monster is always valid
                logger.info(f"[validate_equipment] Monster duel detected - skipping validation for {player2_name}")
                
                # Use enhanced move validator for player only
                logger.info(f"[validate_equipment] Calling MoveValidator for {player1_name} (ID: {player1_id})")
                player1_valid, player1_reason, player1_suggestion = await MoveValidator.validate_move(player1_id, player1_move, game_manager)
                
                logger.info(f"[validate_equipment] Monster {player2_name} moves are always valid")
                player2_valid = True
                player2_reason = "Monster moves are always valid"
                player2_suggestion = None
        else:
            # Regular player vs player duel
            if not player1_id or not player2_id:
                logger.warning(f"[validate_equipment] Could not find player IDs for {player1_name} or {player2_name}")
                logger.warning(f"[validate_equipment] player1_id: {player1_id}, player2_id: {player2_id}")
                
                # Try alternative approach - search all players in database
                logger.info(f"[validate_equipment] Trying alternative player lookup...")
                
                # For now, use a simple approach - create mock player IDs based on names
                # This is a temporary fix until we can properly resolve player IDs
                player1_id = f"player_{player1_name.lower().replace(' ', '_')}"
                player2_id = f"player_{player2_name.lower().replace(' ', '_')}"
                
                logger.info(f"[validate_equipment] Using generated IDs: {player1_id}, {player2_id}")
            
            # Use enhanced move validator for both players
            logger.info(f"[validate_equipment] Calling MoveValidator for {player1_name} (ID: {player1_id})")
            player1_valid, player1_reason, player1_suggestion = await MoveValidator.validate_move(player1_id, player1_move, game_manager)
            
            logger.info(f"[validate_equipment] Calling MoveValidator for {player2_name} (ID: {player2_id})")
            player2_valid, player2_reason, player2_suggestion = await MoveValidator.validate_move(player2_id, player2_move, game_manager)
        
        # Log enhanced validation results
        logger.info(f"[validate_equipment] Enhanced Validation Results:")
        logger.info(f"[validate_equipment] {player1_name}: {player1_valid} - {player1_reason}")
        if player1_suggestion:
            logger.info(f"[validate_equipment] {player1_name} suggestion: {player1_suggestion}")
        logger.info(f"[validate_equipment] {player2_name}: {player2_valid} - {player2_reason}")
        if player2_suggestion:
            logger.info(f"[validate_equipment] {player2_name} suggestion: {player2_suggestion}")
        
        return {
            'player1_valid': player1_valid,
            'player2_valid': player2_valid,
            'player1_reason': player1_reason,
            'player2_reason': player2_reason
        }
        
    except Exception as e:
        logger.error(f"[validate_equipment] Error in enhanced validation: {str(e)}")
        logger.info(f"[validate_equipment] Falling back to basic validation...")
        
        # Fallback: basic keyword-based validation that recognizes basic combat actions
        basic_combat_actions = ['punch', 'kick', 'tackle', 'dodge', 'block', 'parry', 'grapple', 'wrestle', 
                               'headbutt', 'elbow', 'knee', 'shoulder', 'charge', 'sidestep', 'duck', 
                               'jump', 'roll', 'crawl', 'climb', 'run', 'walk', 'sneak', 'hide']
        
        weapon_terms = ['shoot', 'gun', 'fire', 'blast', 'stab', 'slash', 'sword', 'knife', 'dagger', 'blade']
        magic_terms = ['cast', 'spell', 'magic', 'fireball', 'lightning', 'teleport', 'summon', 'fly', 'levitate', 'invisibility']
        
        # Check if moves are basic combat actions (always valid)
        player1_is_basic = any(action in player1_move.lower() for action in basic_combat_actions)
        player2_is_basic = any(action in player2_move.lower() for action in basic_combat_actions)
        
        # Check if moves require equipment
        player1_has_equipment_terms = any(term in player1_move.lower() for term in weapon_terms + magic_terms)
        player2_has_equipment_terms = any(term in player2_move.lower() for term in weapon_terms + magic_terms)
        
        player1_valid = player1_is_basic or not player1_has_equipment_terms
        player2_valid = player2_is_basic or not player2_has_equipment_terms
        
        # Log fallback validation results
        logger.info(f"[validate_equipment] Fallback Validation Results:")
        logger.info(f"[validate_equipment] {player1_name}: {player1_valid} - {'Basic combat action' if player1_is_basic else 'Contains equipment terms' if player1_has_equipment_terms else 'No equipment terms detected'}")
        logger.info(f"[validate_equipment] {player2_name}: {player2_valid} - {'Basic combat action' if player2_is_basic else 'Contains equipment terms' if player2_has_equipment_terms else 'No equipment terms detected'}")
        
        return {
            'player1_valid': player1_valid,
            'player2_valid': player2_valid,
            'player1_reason': 'Fallback validation - basic combat allowed' if player1_is_basic else 'Fallback validation - no equipment required',
            'player2_reason': 'Fallback validation - basic combat allowed' if player2_is_basic else 'Fallback validation - no equipment required'
        }

async def analyze_combat_outcome(player1_name: str, player1_move: str, player1_condition: str, player1_equipment_valid: bool,
                                player2_name: str, player2_move: str, player2_condition: str, player2_equipment_valid: bool,
                                player1_invalid_move: Optional[Dict[str, Any]], player2_invalid_move: Optional[Dict[str, Any]],
                                player1_inventory: List[str], player2_inventory: List[str], room_name: str, room_description: str, game_manager: GameManager) -> Dict[str, Any]:
    """Analyze the outcome of combat moves"""
    
    prompt = f"""
COMBAT OUTCOME ANALYSIS:

Location: {room_name} - {room_description}

{player1_name} vs {player2_name} in combat:

{player1_name} (attacking {player2_name}):
- Move: "{player1_move}"
- Condition: {player1_condition}
- Equipment Valid: {player1_equipment_valid}
- Inventory: {player1_inventory}
- Invalid Move Info: {player1_invalid_move if player1_invalid_move else 'None'}

{player2_name} (attacking {player1_name}):
- Move: "{player2_move}"
- Condition: {player2_condition}
- Equipment Valid: {player2_equipment_valid}
- Inventory: {player2_inventory}
- Invalid Move Info: {player2_invalid_move if player2_invalid_move else 'None'}

CRITICAL RULES:
1. VALIDATION RULES:
   - If player1_equipment_valid = True, {player1_name}'s move is VALID and can have full effect
   - If player2_equipment_valid = True, {player2_name}'s move is VALID and can have full effect
   - Basic combat actions (punch, kick, tackle, dodge, block, etc.) are ALWAYS VALID
   - Equipment-based actions (slash with sword, shoot with bow, etc.) require the specific equipment
   - Invalid moves (missing equipment) have NO EFFECT and cannot harm anyone
   - Valid moves can cause damage and affect the target

2. ATTACKS TARGET THE OPPONENT:
   - {player1_name}'s move targets {player2_name}
   - {player2_name}'s move targets {player1_name}
   - Successful attacks harm the TARGET, not the attacker
   - VALID ATTACKS ALWAYS HAVE IMPACT unless countered by defensive actions
   - Monster attacks are ALWAYS VALID and should ALWAYS have some effect
   - Only invalid moves (missing equipment) have no effect
   - If {player2_name} is a monster, their attacks should ALWAYS affect {player1_name} unless {player1_name} uses defensive moves

3. MOVE IMPACT RULES:
   - VALID ATTACKS MUST CAUSE DAMAGE unless the target is actively defending
   - Monster moves should ALWAYS have some effect (physical, mental, or status effect)
   - Mind control, fear, confusion, and other mental attacks should affect the target
   - If a player is NOT using defensive moves (block, dodge, parry), they take full damage
   - If {player1_name} attacks with a valid move, {player2_name} takes damage UNLESS {player2_name} is blocking/dodging
   - If {player2_name} attacks with a valid move, {player1_name} takes damage UNLESS {player1_name} is blocking/dodging
   - Defensive moves (block, dodge, parry) can reduce or prevent damage
   - Invalid moves (missing equipment) cause NO DAMAGE and have NO EFFECT

4. EXPLAIN MISSED ATTACKS:
   - If an attack misses, EXPLAIN WHY it missed
   - "Missing equipment" - player tried to use equipment they don't have
   - "Target blocked" - target used a defensive move
   - "Target dodged" - target used a dodge move
   - "Attack missed" - attack was inaccurate or target moved
   - "No effect" - invalid move due to missing equipment

3. DODGING/BLOCKING RULES:
   - Players can ONLY dodge/block if their move explicitly includes dodging/blocking
   - If a player's move is "punch", they cannot dodge - they are punching
   - If a player's move is "dodge" or "block", then they can avoid attacks
   - If a player's move is "kick", they cannot dodge - they are kicking
   - Only allow dodging/blocking when it's part of the player's actual move

4. ATTACKS MISS ONLY WITH SOLID DEFENSIVE REASONS:
   - Target is actively blocking/defending against the attack (only if their move includes blocking)
   - Target is dodging/moving away from the attack (only if their move includes dodging)
   - Target is invisible/hidden from the attacker
   - Attacker is incapacitated/unconscious
   - Attacker's move is invalid (no equipment)
   - Target used a defensive maneuver (only if their move includes defensive actions)
   - Attacker was off-balance or injured, affecting accuracy
   - Environmental factors (slippery ground, poor footing, etc.)

5. VALID ATTACKS = MUST HAVE IMPACT:
   - Successful attacks should injure/harm target
   - Attacks should change the combat situation
   - Even if target defends, attacks should have some effect

6. DEFENSIVE MOVES:
   - Blocking/dodging can prevent full damage (only if move includes blocking/dodging)
   - But should still take some effect from attacks
   - Defensive moves should be rewarded with positive tags

7. PEACEFUL ACTIONS:
   - Meditation, calming, etc. should not cause injury
   - Only aggressive actions should risk harm

8. USE ACTUAL NAMES:
   - Always refer to players by their actual names: {player1_name} and {player2_name}
   - Do not use "Player 1" or "Player 2"

9. PROVIDE CLEAR REASONS:
   - If an attack misses, explain WHY it missed
   - If an attack lands, describe HOW it affected the target
   - Be specific about defensive actions and their effectiveness

10. ENVIRONMENT AWARENESS:
    - Consider the location: {room_name}
    - Reference the environment only when relevant to the action
    - Don't mention environments that don't match the current location

Return JSON:
{{
    "player1_result": {{
        "condition": "healthy/injured/maimed/unconscious/dead/surrendered",
        "can_continue": true/false,
        "reason": "description of what happened to {player1_name}"
    }},
    "player2_result": {{
        "condition": "healthy/injured/maimed/unconscious/dead/surrendered",
        "can_continue": true/false,
        "reason": "description of what happened to {player2_name}"
    }}
}}
"""

    try:
        # Call AI to analyze combat outcome
        response = await game_manager.ai_handler.generate_text(prompt)
        
        # Parse AI response
        result = json.loads(response)
        return {
            'player1_result': result.get('player1_result', {
                'condition': 'healthy',
                'can_continue': True,
                'reason': f'{player1_name} continues fighting'
            }),
            'player2_result': result.get('player2_result', {
                'condition': 'healthy',
                'can_continue': True,
                'reason': f'{player2_name} continues fighting'
            })
        }
    except Exception as e:
        logger.error(f"[analyze_combat_outcome] Error analyzing combat outcome with AI: {str(e)}")
        # Fallback: assume basic outcomes
        return {
            'player1_result': {
                'condition': 'injured' if not player1_equipment_valid else 'healthy',
                'can_continue': True,
                'reason': f'{player1_name} {"attempted invalid move" if not player1_equipment_valid else "landed a basic attack"}'
            },
            'player2_result': {
                'condition': 'injured' if not player2_equipment_valid else 'healthy',
                'can_continue': True,
                'reason': f'{player2_name} {"attempted invalid move" if not player2_equipment_valid else "landed a basic attack"}'
            }
        }

async def generate_combat_tags(
    player1_name: str, player1_result: Dict[str, Any], player1_current_tags: List[Dict[str, Any]],
    player2_name: str, player2_result: Dict[str, Any], player2_current_tags: List[Dict[str, Any]],
    game_manager: GameManager
) -> Dict[str, Any]:
    """Generate new tags based on combat outcomes"""
    
    prompt = f"""
        Analyze this combat round and generate appropriate tags for both players.

        {player1_name}:
        - Move: {player1_result.get('reason', 'Unknown')}
        - Result: {player1_result.get('condition', 'Unknown')}
        - Current condition: {player1_result.get('condition', 'Unknown')}
        - Current tags: {player1_current_tags}

        {player2_name}:
        - Move: {player2_result.get('reason', 'Unknown')}
        - Result: {player2_result.get('condition', 'Unknown')}
        - Current condition: {player2_result.get('condition', 'Unknown')}
        - Current tags: {player2_current_tags}

        Generate NEW tags based on THIS ROUND's outcomes. Do not duplicate existing tags.
        
        CRITICAL RULES:
        1. ATTACKS HARM THE TARGET, NOT THE ATTACKER:
           - If {player1_name} attacks {player2_name}, {player2_name} gets negative tags
           - If {player2_name} attacks {player1_name}, {player1_name} gets negative tags
           - Attackers should NOT get negative tags for successful attacks
        
        2. ONLY MAJOR INJURIES GET HIGH SEVERITY:
           - Basic injuries (bruises, minor cuts): 1-3 severity
           - Moderate injuries (bleeding, sprains): 4-8 severity  
           - Serious injuries (broken bones, major wounds): 9-20 severity
           - Critical injuries (life-threatening, unconscious): 21-50 severity
        
        3. POSITIVE TAGS ARE RARE AND SPECIFIC:
           - Only for genuine advantages: "invisible", "high ground", "focused", "energized"
           - NOT for successful attacks (those harm the opponent)
           - NOT for basic defensive moves
        
        4. CONCISE TAG NAMES:
           - Use specific injury types: "black eye", "bruised ribs", "concussion", "broken arm"
           - Use specific advantages: "high ground", "invisible", "focused", "energized"
           - DO NOT describe how the tag was obtained in the name
           - Keep names short and descriptive

        5. NO UNJUSTIFIED NEGATIVE TAGS:
           - Players should not get injured from peaceful actions (meditation, etc.)
           - Failed attacks should not harm the attacker unless there's a good reason
           - Only generate negative tags when someone actually gets hurt

        Return a JSON object with this structure:
        {{
            "player1_new_tags": [
                {{"name": "specific injury/advantage", "severity": number, "type": "positive/negative"}}
            ],
            "player2_new_tags": [
                {{"name": "specific injury/advantage", "severity": number, "type": "positive/negative"}}
            ]
        }}
        """

    try:
        # Call AI to generate tags
        response = await game_manager.ai_handler.generate_text(prompt)
        
        # Parse AI response
        result = json.loads(response)
        
        player1_new_tags = result.get('player1_new_tags', [])
        player2_new_tags = result.get('player2_new_tags', [])
        
        logger.info(f"[generate_combat_tags] AI generated tags for {player1_name}: {player1_new_tags}")
        logger.info(f"[generate_combat_tags] AI generated tags for {player2_name}: {player2_new_tags}")
        
        return {
            'player1_new_tags': player1_new_tags,
            'player2_new_tags': player2_new_tags
        }
    except Exception as e:
        logger.error(f"[generate_combat_tags] Error generating combat tags with AI: {str(e)}")
        # Fallback: no new tags
        return {
            'player1_new_tags': [],
            'player2_new_tags': []
        }

async def generate_combat_narrative(
    player1_name: str, player1_move: str, player1_result: Dict[str, Any],
    player2_name: str, player2_move: str, player2_result: Dict[str, Any],
    player1_invalid_move: Optional[Dict[str, Any]], player2_invalid_move: Optional[Dict[str, Any]],
    current_round: int, room_name: str, room_description: str, game_manager: GameManager
) -> str:
    """Create narrative description of combat round"""
    
    prompt = f"""
        Create an engaging, descriptive narrative for this combat round.

        Location: {room_name} - {room_description}

        Combat Context:
        - {player1_name} attacks {player2_name} with: {player1_move}
        - {player2_name} attacks {player1_name} with: {player2_move}
        
        {player1_name} Results:
        - Condition: {player1_result.get('condition', 'Unknown')}
        - Outcome: {player1_result.get('reason', 'Unknown')}
        
        {player2_name} Results:
        - Condition: {player2_result.get('condition', 'Unknown')}
        - Outcome: {player2_result.get('reason', 'Unknown')}
        
        Invalid Move Context:
        - {player1_name} Invalid: {player1_invalid_move if player1_invalid_move else 'None'}
        - {player2_name} Invalid: {player2_invalid_move if player2_invalid_move else 'None'}

        Instructions:
        - Create a vivid, engaging narrative that describes what happened
        - If there are invalid moves (missing equipment), EXPLAIN WHY they failed (e.g., "tried to shoot without a gun")
        - If moves are valid (including basic actions like punch/kick), describe them as effective attacks
        - Describe the actual outcomes and their impact on both players
        - Make it feel like a real combat scene, not just a game log
        - Keep it concise but descriptive (2-4 sentences)
        - Use active voice and dynamic language
        - Use actual player names: {player1_name} and {player2_name}
        - Basic actions like punch, kick, tackle are valid and can cause damage
        - Only equipment-based actions without the required equipment are invalid
        - ALWAYS explain why attacks miss or fail - be specific about the reason
        
        CRITICAL RULES:
        1. DO NOT directly reference tags, severity levels, or game mechanics
           - Don't say "with a severity level of 3" or "gets a negative tag"
           - Instead, describe the actual injury/advantage naturally
           - Example: "leaving him bruised and shaken" not "gets bruised ribs tag"
        
        2. MOVE IMPACT RULES:
           - VALID ATTACKS MUST CAUSE DAMAGE unless the target is actively defending
           - If a valid attack lands, describe the damage and its effect
           - If an attack misses, EXPLAIN WHY (missing equipment, target blocked, target dodged, etc.)
           - Invalid moves (missing equipment) have NO EFFECT and should be explained as such
        
        3. DODGING/BLOCKING RULES:
           - Players can ONLY dodge/block if their move explicitly includes dodging/blocking
           - If a player's move is "punch", they cannot dodge - they are punching
           - If a player's move is "dodge" or "block", then they can avoid attacks
           - If a player's move is "kick", they cannot dodge - they are kicking
           - Only describe dodging/blocking when it's part of the player's actual move

        3. ENVIRONMENT AWARENESS:
           - The combat is taking place in: {room_name}
           - Environment description: {room_description}
           - DO NOT start sentences with room descriptions like "In the fiery glow of..." or "Under the blood-red canopy of..."
           - DO NOT mention the room unless it directly affects the player's move
           - Only reference the environment when a player's move specifically uses it (climbing rocks, using terrain, etc.)
           - Focus on the combat action, not the setting

        4. CLEAR ATTACK TARGETS:
           - Make it clear that {player1_name} is attacking {player2_name}
           - Make it clear that {player2_name} is attacking {player1_name}
           - Successful attacks harm the target, not the attacker
           - Use phrases like "{player1_name} strikes at {player2_name}" or "{player2_name} defends against {player1_name}'s attack"

        5. CONSISTENT OUTCOMES:
           - The narrative must match the combat results
           - If {player1_name} is "injured", show them getting hurt in the narrative
           - If {player2_name} is "healthy", show them avoiding damage or successfully defending
           - Make sure the narrative outcomes align with the combat analysis

        Return only the narrative text, no JSON formatting.
        """

    try:
        # Call AI to generate narrative
        narrative = await game_manager.ai_handler.generate_text(prompt)
        
        # Clean up the response
        narrative = narrative.strip()
        if narrative.startswith('"') and narrative.endswith('"'):
            narrative = narrative[1:-1]
        
        logger.info(f"[generate_combat_narrative] AI generated narrative: {narrative}")
        return narrative
    except Exception as e:
        logger.error(f"[generate_combat_narrative] Error generating combat narrative with AI: {str(e)}")
        # Fallback narrative
        return f"Round {current_round}: {player1_name} and {player2_name} engaged in combat in {room_name}."

async def generate_combat_tags_from_narrative(
    player1_name: str, player2_name: str, narrative: str,
    player1_current_tags: List[Dict[str, Any]], player2_current_tags: List[Dict[str, Any]],
    game_manager: GameManager
) -> Dict[str, Any]:
    """Generate new tags based on combat outcomes, derived from the narrative."""
    
    prompt = f"""
        Analyze the combat narrative and generate appropriate tags for both players.

        Narrative: {narrative}

        {player1_name} Current Tags: {player1_current_tags}
        {player2_name} Current Tags: {player2_current_tags}

        Generate NEW tags based on THIS ROUND's narrative. Do not duplicate existing tags.
        
        CRITICAL RULES:
        1. ATTACKS HARM THE TARGET, NOT THE ATTACKER:
           - If {player1_name} attacks {player2_name}, {player2_name} gets negative tags
           - If {player2_name} attacks {player1_name}, {player1_name} gets negative tags
           - Attackers should NOT get negative tags for successful attacks
           - READ THE NARRATIVE CAREFULLY: If it says "{player1_name} punched {player2_name} and left him bruised", then {player2_name} gets the "bruised" tag, NOT {player1_name}
           - COMMON MISTAKE: Do NOT give the attacker injury tags for their own successful attacks
        
        2. SUCCESSFUL ATTACKS ALWAYS CAUSE DAMAGE:
           - If the narrative says an attack "connected", "landed", "hit", "struck", etc., the target MUST get a negative tag
           - If the narrative says someone is "injured", "hurt", "shaken", "wounded", etc., they MUST get a negative tag
           - Even minor hits should result in injury tags (1-3 severity)
           - MENTAL ATTACKS (mind control, fear, confusion, etc.) should also cause negative tags
           - ANY attack that affects the target should result in appropriate tags
        
        3. SEVERITY GUIDELINES:
           - Basic injuries (bruises, minor cuts, shaken): 1-3 severity
           - Moderate injuries (bleeding, sprains, dazed): 4-8 severity  
           - Serious injuries (broken bones, major wounds): 9-20 severity
           - Critical injuries (life-threatening, unconscious): 21-50 severity
        
        4. POSITIVE TAGS ARE RARE AND SPECIFIC:
           - Only for genuine advantages: "invisible", "high ground", "focused", "energized"
           - NOT for successful attacks (those harm the opponent)
           - NOT for basic defensive moves
           - NOT for avoiding damage (that's just normal combat)
        
        5. CONCISE TAG NAMES:
           - Use specific injury types: "black eye", "bruised ribs", "concussion", "broken arm"
           - Use specific advantages: "high ground", "invisible", "focused", "energized"
           - DO NOT describe how the tag was obtained in the name
           - Keep names short and descriptive

        6. NARRATIVE INTERPRETATION:
           - Look for words like: "connected", "landed", "hit", "struck", "injured", "hurt", "shaken", "wounded", "damaged"
           - If these words appear, someone should get a negative tag
           - "none" is NOT a valid tag name - use actual injury descriptions
           - EXAMPLE: "Player A punched Player B, leaving Player B bruised" → Player B gets "bruised" tag
           - EXAMPLE: "Player B attacked Player A, causing Player A to be wounded" → Player A gets "wounded" tag

        Return a JSON object with this structure:
        {{
            "player1_new_tags": [
                {{"name": "specific injury/advantage", "severity": number, "type": "positive/negative"}}
            ],
            "player2_new_tags": [
                {{"name": "specific injury/advantage", "severity": number, "type": "positive/negative"}}
            ]
        }}
        """

    try:
        # Call AI to generate tags
        response = await game_manager.ai_handler.generate_text(prompt)
        
        # Parse AI response
        result = json.loads(response)
        
        player1_new_tags = result.get('player1_new_tags', [])
        player2_new_tags = result.get('player2_new_tags', [])
        
        logger.info(f"[generate_combat_tags_from_narrative] AI generated tags for {player1_name}: {player1_new_tags}")
        logger.info(f"[generate_combat_tags_from_narrative] AI generated tags for {player2_name}: {player2_new_tags}")
        
        return {
            'player1_new_tags': player1_new_tags,
            'player2_new_tags': player2_new_tags
        }
    except Exception as e:
        logger.error(f"[generate_combat_tags_from_narrative] Error generating combat tags with AI: {str(e)}")
        # Fallback: no new tags
        return {
            'player1_new_tags': [],
            'player2_new_tags': []
        }

async def send_duel_results(
    duel_id: str, room_id: str, player1_id: str, player2_id: str, current_round: int,
    player1_move: str, player2_move: str,
    player1_condition: str, player2_condition: str,
    player1_tags: List[Dict[str, Any]], player2_tags: List[Dict[str, Any]],
    player1_total_severity: int, player2_total_severity: int,
    narrative: str, combat_ends: bool, game_manager: GameManager
):
    """
    Sends the round result, combat end message, and updates player conditions/tags.
    Uses AI to determine victory conditions and outcome messages.
    """
    # Get player names for display
    player1_data = await game_manager.db.get_player(player1_id)
    player2_data = await game_manager.db.get_player(player2_id)
    player1_name = player1_data.get('name', 'Unknown') if player1_data else 'Unknown'
    player2_name = player2_data.get('name', 'Unknown') if player2_data else 'Unknown'
    
    # duel_id is now passed as parameter - no need to reconstruct it
    
    round_message = {
        "type": "duel_round_result",
        "round": current_round,
        "player1_id": player1_id,
        "player2_id": player2_id,
        "player1_move": player1_move,
        "player2_move": player2_move,
        "player1_condition": player1_condition,
        "player2_condition": player2_condition,
        "player1_tags": player1_tags,
        "player2_tags": player2_tags,
        "player1_total_severity": player1_total_severity,
        "player2_total_severity": player2_total_severity,
        "description": narrative,
        "combat_ends": combat_ends,
        "room_id": room_id,
        "timestamp": datetime.now().isoformat()
    }
    
    await manager.send_to_player(room_id, player1_id, round_message)
    await manager.send_to_player(room_id, player2_id, round_message)
    
    # Add round description to room chat
    chat_message = {
        "player_id": "system",
        "room_id": room_id,
        "message": f"⚔️ Round {current_round + 1}: {narrative}",
        "message_type": "system",
        "timestamp": datetime.now().isoformat()
    }
    await manager.broadcast_to_room(room_id, chat_message)

    if combat_ends:
        # Hardcoded victory condition: severity >= 50
        winner_id = None
        loser_id = None
        
        if player1_total_severity >= 50:
            winner_id = player2_id
            loser_id = player1_id
        elif player2_total_severity >= 50:
            winner_id = player1_id
            loser_id = player2_id
        elif player1_condition.lower() in ['dead', 'unconscious', 'surrendered', 'maimed', 'incapacitated']:
            winner_id = player2_id
            loser_id = player1_id
        elif player2_condition.lower() in ['dead', 'unconscious', 'surrendered', 'maimed', 'incapacitated']:
            winner_id = player1_id
            loser_id = player2_id

        if winner_id:
            # Use AI to generate the victory message
            try:
                winner_name = player1_name if winner_id == player1_id else player2_name
                loser_name = player2_name if winner_id == player1_id else player1_name
                
                victory_prompt = f"""
                Create a dramatic victory message for this combat ending.

                Combat Summary:
                - Winner: {winner_name} (ID: {winner_id})
                - Loser: {loser_name} (ID: {loser_id})
                - Winner Condition: {player1_condition if winner_id == player1_id else player2_condition}
                - Loser Condition: {player2_condition if winner_id == player1_id else player1_condition}
                - Winner Total Severity: {player1_total_severity if winner_id == player1_id else player2_total_severity}
                - Loser Total Severity: {player2_total_severity if winner_id == player1_id else player1_total_severity}
                - Final Round: {current_round + 1}

                Instructions:
                - Create an engaging, dramatic victory message
                - Consider the nature of the defeat (severity threshold, death, unconsciousness, etc.)
                - Make it feel like a real combat conclusion
                - Keep it concise but impactful

                Return only the victory message text, no JSON formatting.
                """

                victory_message = await game_manager.ai_handler.generate_text(victory_prompt)
                victory_message = victory_message.strip()
                if victory_message.startswith('"') and victory_message.endswith('"'):
                    victory_message = victory_message[1:-1]
                
                logger.info(f"AI generated victory message: {victory_message}")
                
            except Exception as e:
                logger.error(f"Error generating victory message with AI: {e}")
                victory_message = f"{winner_name} has defeated {loser_name}!"
            
            outcome_message = {
                "type": "duel_outcome",
                "winner_id": winner_id,
                "loser_id": loser_id,
                "analysis": victory_message,
                "room_id": room_id,
                "timestamp": datetime.now().isoformat()
            }
            
            await manager.send_to_player(room_id, player1_id, outcome_message)
            await manager.send_to_player(room_id, player2_id, outcome_message)
            
            # Clean up duel state
            if duel_id in duel_moves:
                del duel_moves[duel_id]
            if duel_id in duel_pending:
                del duel_pending[duel_id]
        else:
            # No clear winner, combat ends in draw or confusion
            outcome_message = {
                "type": "duel_outcome",
                "winner_id": None,
                "loser_id": None,
                "analysis": f"{player1_name} and {player2_name} ended their combat.",
                "room_id": room_id,
                "timestamp": datetime.now().isoformat()
            }
            
            await manager.send_to_player(room_id, player1_id, outcome_message)
            await manager.send_to_player(room_id, player2_id, outcome_message)
            
            # Clean up duel state
            if duel_id in duel_moves:
                del duel_moves[duel_id]
            if duel_id in duel_pending:
                del duel_pending[duel_id]
    else:
        # Combat continues - prepare for next round
        duel_pending[duel_id]['round'] = current_round + 1
        duel_pending[duel_id]['player1_condition'] = player1_condition
        duel_pending[duel_id]['player2_condition'] = player2_condition
        duel_pending[duel_id]['player1_tags'] = player1_tags
        duel_pending[duel_id]['player2_tags'] = player2_tags
        if duel_id in duel_moves:
            del duel_moves[duel_id]  # Clear moves for next round
        
        # Send next round message
        next_round_message = {
            "type": "duel_next_round",
            "round": current_round + 1,
            "player1_condition": player1_condition,
            "player2_condition": player2_condition,
            "player1_tags": player1_tags,
            "player2_tags": player2_tags,
            "player1_total_severity": player1_total_severity,
            "player2_total_severity": player2_total_severity,
            "room_id": room_id,
            "timestamp": datetime.now().isoformat()
        }
        
        await manager.send_to_player(room_id, player1_id, next_round_message)
        await manager.send_to_player(room_id, player2_id, next_round_message)

# WebSocket endpoint for real-time updates
@app.websocket("/ws/{room_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    logger.info(f"[WebSocket] New connection request from player {player_id} for room {room_id}")
    await manager.connect(websocket, room_id, player_id)
    try:
        # Send current room state immediately after connection
        room_data = await game_manager.db.get_room(room_id)
        if room_data:
            try:
                logger.info(f"[WebSocket] Sending initial room state for {room_id}")
                room = Room(**room_data)
                # Get current players in room
                room.players = await game_manager.db.get_room_players(room_id)
                # Convert to dict and ensure all values are JSON serializable
                room_dict = room.dict()
                # Convert any bytes to strings
                for key, value in room_dict.items():
                    if isinstance(value, bytes):
                        room_dict[key] = value.decode('utf-8')

                await websocket.send_json({
                    "type": "room_update",
                    "room": room_dict
                })
                logger.info(f"[WebSocket] Successfully sent initial room state for {room_id}")
            except Exception as e:
                logger.error(f"[WebSocket] Error preparing room state: {str(e)}")
                logger.error(f"[WebSocket] Room data: {room_data}")
        else:
            logger.warning(f"[WebSocket] Room {room_id} not found when sending initial state")

        while True:
            data = await websocket.receive_text()
            logger.debug(f"[WebSocket] Received message from player {player_id}: {data[:100]}...")
            message = json.loads(data)

            if message.get('type') == 'action':
                logger.info(f"[WebSocket] Received action from player {player_id}: {message['action']}")
                # Actions are now processed only through the streaming endpoint
                # WebSocket just acknowledges receipt but doesn't process
                logger.info(f"[WebSocket] Action will be processed via streaming endpoint")
            elif message.get('type') in ['duel_challenge', 'duel_response', 'duel_move', 'duel_cancel', 'duel_outcome']:
                logger.info(f"[WebSocket] Received duel message type {message.get('type')} from player {player_id}")
                # Handle duel messages
                await handle_duel_message(message, room_id, player_id, game_manager)
            else:
                logger.info(f"[WebSocket] Broadcasting message type {message.get('type')} from player {player_id}")
                # For other message types (chat, etc.), just broadcast
                await manager.broadcast_to_room(
                    room_id=room_id,
                    message=message,
                    exclude_player=player_id
                )
    except WebSocketDisconnect:
        logger.info(f"[WebSocket] Client disconnected - room: {room_id}, player: {player_id}")
        manager.disconnect(room_id, player_id)
        await manager.broadcast_to_room(
            room_id=room_id,
            message={"type": "presence", "player_id": player_id, "status": "disconnected"}
        )
    except Exception as e:
        logger.error(f"[WebSocket] Error in connection: {str(e)}")
        manager.disconnect(room_id, player_id)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Game initialization endpoint
@app.post("/start")
async def start_game(game_manager: GameManager = Depends(get_game_manager)):
    game_state = await game_manager.initialize_game()
    return game_state

# Player creation endpoint
@app.post("/player")
async def create_player(
    request: CreatePlayerRequest,
    game_manager: GameManager = Depends(get_game_manager)
):
    player = await game_manager.create_player(request.name)
    return player

# Action endpoint with streaming support
@app.post("/action/stream")
async def process_action_stream(
    action_request: ActionRequest,
    game_manager: GameManager = Depends(get_game_manager)
):
    async def event_generator():
        try:
            # Check if player is in a duel
            for duel_id, duel_info in duel_pending.items():
                if (action_request.player_id == duel_info['player1_id'] or 
                    action_request.player_id == duel_info['player2_id']):
                    # Player is in a duel - don't process normal actions
                    yield json.dumps({
                        "type": "final",
                        "content": "⚔️ You are in a duel! Use the chat input to submit your combat move.",
                        "updates": {}
                    })
                    return

            # Get initial state
            player_data = await game_manager.db.get_player(action_request.player_id)
            if not player_data:
                yield json.dumps({"error": "Player not found"})
                return

            player = Player(**player_data)
            room_data = await game_manager.db.get_room(player.current_room)
            if not room_data:
                yield json.dumps({"error": "Room not found"})
                return

            room = Room(**room_data)
            game_state_data = await game_manager.db.get_game_state()
            game_state = GameState(**game_state_data)

            # Get NPCs in the room
            npcs = []
            for npc_id in room.npcs:
                npc_data = await game_manager.db.get_npc(npc_id)
                if npc_data:
                    npcs.append(NPC(**npc_data))
            
            # Get monster details for AI context
            monsters = []
            for monster_id in room.monsters:
                monster_data = await game_manager.db.get_monster(monster_id)
                if monster_data:
                    monsters.append(monster_data)

            # Check rate limit before processing action
            is_allowed, rate_limit_info = await game_manager.rate_limiter.check_rate_limit(
                action_request.player_id,
                game_manager.rate_limit_config['limit'],
                game_manager.rate_limit_config['interval_minutes']
            )
            
            if not is_allowed:
                # Player has exceeded rate limit - display as chat message instead of error
                wait_minutes = rate_limit_info['interval_minutes']
                wait_seconds = rate_limit_info['time_until_reset']
                
                if wait_minutes >= 1:
                    time_message = f"{wait_minutes:.1f} minutes"
                else:
                    time_message = f"{wait_seconds} seconds"
                
                rate_limit_message = f"⏰ Rate limit reached! You can only send {rate_limit_info['limit']} message every {wait_minutes} minutes. Please wait {time_message} before sending another message."
                
                logger.warning(f"Rate limit exceeded for {action_request.player_id}: {rate_limit_info['action_count']}/{rate_limit_info['limit']} actions")
                
                # Return as a normal chat message instead of an error
                yield json.dumps({
                    "type": "final",
                    "content": rate_limit_message,
                    "updates": {}
                })
                return
            
            # Check for monster attacks first
            monster_target_id = await detect_monster_attack(action_request.action, action_request.player_id, room_data, game_manager)
            if monster_target_id:
                logger.info(f"[Stream] Monster attack detected - initiating duel with {monster_target_id}")
                
                # Get monster name for the message
                monster_data = await game_manager.db.get_monster(monster_target_id)
                monster_name = monster_data.get('name', 'Unknown Monster') if monster_data else "Unknown Monster"
                
                # Initiate monster duel using the existing duel system
                await initiate_monster_duel(action_request.player_id, monster_target_id, action_request.action, player.current_room, game_manager)
                
                # Return a simple acknowledgment - the duel system will handle the rest
                yield json.dumps({
                    "type": "final", 
                    "content": f"⚔️ You challenge the {monster_name} to combat!",
                    "updates": {}
                })
                return
            
            # All actions go through AI processing for rich narrative responses
            logger.info(f"[Stream] Processing action with AI: {action_request.action}")
            
            # Let the AI determine item discovery and rewards based on context
            # No hardcoded keywords - trust the AI's judgment
            pending_item_type = None
            if hasattr(player, 'pending_item_type') and player.pending_item_type:
                # Reconstruct ItemType object from stored data
                from .templates.item_types import ItemType
                pending_item_type = ItemType(
                    name=player.pending_item_type['name'],
                    description=player.pending_item_type['description'],
                    capabilities=player.pending_item_type['capabilities']
                )
                logger.info(f"[Item Discovery] Using pending item type: {pending_item_type.name}")
            
            # Use the pending type if available
            item_type_for_ai = pending_item_type
            
            # Use AI processing for all actions (including movement) 
            logger.info(f"[Stream] AI context includes {len(monsters)} monsters: {[m.get('name', 'Unknown') for m in monsters]}")
            async for chunk in game_manager.ai_handler.stream_action(
                action=action_request.action,
                player=player,
                room=room,
                game_state=game_state,
                npcs=npcs,
                monsters=monsters,
                potential_item_type=item_type_for_ai
            ):
                if isinstance(chunk, dict):
                    # Apply updates BEFORE yielding the final response
                    if "player" in chunk["updates"]:
                        player_updates = chunk["updates"]["player"]
                        if "direction" in player_updates:
                            direction = player_updates["direction"]
                            
                            logger.info(f"[Stream] Player attempting to move {direction} from {player.current_room}")
                            
                            # CRITICAL: Use GameManager's coordinate-based room movement logic to prevent duplicate coordinates
                            actual_room_id, new_room = await game_manager.handle_room_movement_by_direction(
                                player, room, direction
                            )
                            
                            # Update player's destination to the actual room ID
                            player_updates["current_room"] = actual_room_id
                            new_room_id = actual_room_id
                            
                            logger.info(f"[Stream] Player moving to room: {new_room_id}")
                            
                            # Room movement is now handled entirely by GameManager
                            # Remove the direction from updates since it's been processed
                            del player_updates["direction"]
                            
                            # CRITICAL: Update player data in database BEFORE broadcasting
                            updated_player = Player(**{**player.dict(), **player_updates})
                            await game_manager.db.set_player(action_request.player_id, updated_player.dict())
                            
                            # CRITICAL: Update room player lists in database
                            old_room_id = player.current_room
                            await game_manager.db.remove_from_room_players(old_room_id, action_request.player_id)
                            await game_manager.db.add_to_room_players(new_room_id, action_request.player_id)
                            logger.info(f"[Stream] Updated room player lists: removed from {old_room_id}, added to {new_room_id}")
                            
                            # CRITICAL: Handle presence updates for room movement
                            # Notify old room that player is leaving BEFORE they disconnect
                            if manager.active_connections.get(old_room_id):
                                await manager.broadcast_to_room(
                                    room_id=old_room_id,
                                    message={
                                        "type": "presence", 
                                        "player_id": action_request.player_id, 
                                        "status": "left"
                                    },
                                    exclude_player=action_request.player_id
                                )
                                logger.info(f"[Stream] Sent 'left' presence to room {old_room_id} for player {action_request.player_id}")
                            
                            # The client will handle disconnecting from old room and connecting to new room
                            # We don't need to manually move WebSocket connections since they're tied to room endpoints

                    # Check if this is a rate limit error
                    if chunk.get("updates", {}).get("error") == "rate_limit_exceeded":
                        # Yield rate limit error
                        yield json.dumps({
                            "type": "error",
                            "error": "rate_limit_exceeded",
                            "message": chunk["updates"]["message"],
                            "rate_limit_info": chunk["updates"]["rate_limit_info"]
                        })
                    else:
                        # NOW yield the final response with updated player data
                        yield json.dumps({
                            "type": "final",
                            "content": chunk["response"],
                            "updates": chunk["updates"]
                        })

                    # Store the action record with player input and AI response
                    try:
                        from .models import ActionRecord
                        
                        # Create a simple session ID for now (we can enhance this later)
                        session_id = f"session_{action_request.player_id}_{datetime.utcnow().strftime('%Y%m%d')}"
                        
                        action_record = ActionRecord(
                            player_id=action_request.player_id,
                            room_id=action_request.room_id,
                            action=action_request.action,
                            ai_response=chunk["response"],
                            updates=chunk.get("updates", {}),
                            session_id=session_id,
                            metadata={
                                "room_title": room.title,
                                "npcs_present": [npc.name for npc in npcs],
                                "ai_model": "gpt-4o"
                            }
                        )
                        await game_manager.db.store_action_record(action_request.player_id, action_record)
                        logger.info(f"[Storage] Stored action record for player {action_request.player_id}")
                    except Exception as e:
                        logger.error(f"[Storage] Failed to store action record: {str(e)}")

                    # Continue with remaining updates
                    if "player" in chunk["updates"]:
                        player_updates = chunk["updates"]["player"]
                        
                        # Update last_action timestamp and text
                        current_time = datetime.utcnow()
                        player_updates["last_action"] = current_time.isoformat()
                        player_updates["last_action_text"] = action_request.action

                        player = Player(**{**player.dict(), **player_updates})
                        await game_manager.db.set_player(player.id, player.dict())
                        
                        # Check if AI decided player deserves an item reward
                        if "reward_item" in chunk:
                            reward_item = chunk["reward_item"]
                            logger.info(f"[Item Generation] Reward item data: {reward_item}")
                            
                            # Handle both boolean and string values for deserves_item
                            deserves_item = reward_item.get("deserves_item")
                            if isinstance(deserves_item, str):
                                deserves_item = deserves_item.lower() == "true"
                            
                            # Trust the AI's decision completely - no keyword restrictions
                            if deserves_item:
                                try:
                                    logger.info(f"[Item Generation] Player {player.id} is grabbing an item they previously discovered")
                                    
                                    # Use the AI's chosen item type if available, otherwise use pending or random
                                    ai_chosen_item_type = reward_item.get("item_type")
                                    
                                    if ai_chosen_item_type:
                                        # Use the AI's chosen item type
                                        try:
                                            item_type = game_manager.item_type_manager.get_item_type_by_name(ai_chosen_item_type)
                                            logger.info(f"[Item Generation] Using AI-chosen item type: {item_type.name}")
                                        except ValueError:
                                            logger.warning(f"[Item Generation] AI chose invalid item type '{ai_chosen_item_type}', falling back to random")
                                            item_type = game_manager.item_type_manager.get_random_item_type()
                                    elif hasattr(player, 'pending_item_type') and player.pending_item_type:
                                        # Use pending item type if AI didn't specify one
                                        from .templates.item_types import ItemType
                                        item_type = ItemType(
                                            name=player.pending_item_type['name'],
                                            description=player.pending_item_type['description'],
                                            capabilities=player.pending_item_type['capabilities']
                                        )
                                        logger.info(f"[Item Generation] Using pending item type: {item_type.name}")
                                        
                                        # Clear the pending item type since we're using it now
                                        player.pending_item_type = None
                                        await game_manager.db.set_player(player.id, player.dict())
                                    else:
                                        # Fallback: randomly select item type
                                        try:
                                            item_type = game_manager.item_type_manager.get_random_item_type()
                                            logger.info(f"[Item Generation] No AI choice or pending type, randomly selected: {item_type.name}")
                                        except ValueError:
                                            # No item types available, try to generate default ones
                                            logger.warning(f"[Item Generation] No item types available, attempting to generate defaults")
                                            try:
                                                await game_manager.item_type_manager.generate_default_item_types()
                                                await game_manager.db.set_item_types(game_manager.item_type_manager.to_dict_list())
                                                item_type = game_manager.item_type_manager.get_random_item_type()
                                                logger.info(f"[Item Generation] Generated default types, selected: {item_type.name}")
                                            except Exception as e:
                                                logger.error(f"[Item Generation] Failed to generate default types: {str(e)}")
                                                # Ultimate fallback: create a basic item type
                                                from .templates.item_types import ItemType
                                                item_type = ItemType(
                                                    name="Mysterious Artifact",
                                                    description="A mysterious artifact of unknown origin",
                                                    capabilities=["examine", "hold", "carry"]
                                                )
                                    
                                    # Generate rarity
                                    rarity = random.randint(1, 4)
                                    
                                    # Use GenericItemTemplate to generate a proper item name
                                    item_template = GenericItemTemplate(game_manager.item_type_manager)
                                    context = {
                                        'room_title': room.title,
                                        'room_description': room.description,
                                        'biome': room.biome,
                                        'item_type': item_type.name,
                                        'item_type_description': item_type.description,
                                        'item_type_capabilities': item_type.capabilities
                                    }
                                    
                                    # Generate item name using AI
                                    prompt = item_template.generate_prompt(context)
                                    ai_response = await game_manager.ai_handler.generate_text(prompt)
                                    item_data_response = item_template.parse_response(ai_response, context)
                                    item_name = item_data_response.get('name', f"{room.title.split()[0]} {item_type.name}")
                                    
                                    # Create item data
                                    item_data = {
                                        'name': item_name,
                                        'type': item_type.name,
                                        'type_description': item_type.description,
                                        'type_capabilities': item_type.capabilities,
                                        'rarity': rarity,
                                        'special_effects': "No special effects" if rarity < 3 else "Special effects"
                                    }
                                    
                                    # Create item ID and add to player's inventory
                                    item_id = f"item_{str(uuid.uuid4())}"
                                    item_data["id"] = item_id
                                    
                                    # Add item to player's inventory
                                    player.inventory.append(item_id)
                                    await game_manager.db.set_player(player.id, player.dict())
                                    
                                    # Save item to database
                                    await game_manager.db.set_item(item_id, item_data)
                                    
                                    logger.info(f"[Item Generation] Added item '{item_data['name']}' (Type: {item_data.get('type', 'Unknown')}) to player {player.id}")
                                    
                                    # Send server message to player about the obtained item
                                    rarity_stars = rarity_to_stars(item_data['rarity'])
                                    item_type_name = item_data.get('type', 'Unknown Type')
                                    item_message = f"🎁 You obtained: {item_data['name']} [{item_type_name}] {rarity_stars}"
                                    
                                    await manager.send_to_player(
                                        room_id=player.current_room,
                                        player_id=action_request.player_id,
                                        message={
                                            "type": "item_obtained",
                                            "player_id": action_request.player_id,
                                            "item_name": item_data['name'],
                                            "item_rarity": item_data['rarity'],
                                            "item_type": item_data.get('type', 'Unknown'),
                                            "rarity_stars": rarity_stars,
                                            "message": item_message,
                                            "timestamp": datetime.utcnow().isoformat()
                                        }
                                    )
                                    
                                    # Add item acquisition to player's memory log with type info
                                    item_type_name = item_data.get('type', 'Unknown Type')
                                    player.memory_log.append(f"Found {item_data['name']} [{item_type_name}] - {item_data['special_effects']}")
                                    await game_manager.db.set_player(player.id, player.dict())
                                    
                                except Exception as e:
                                    logger.error(f"[Item Generation] Failed to generate item for player {player.id}: {str(e)}")
                            else:
                                logger.debug(f"[Item Generation] AI decided player {player.id} does not deserve an item for this action")
                        else:
                            logger.info(f"[Item Generation] No reward_item field in AI response. Chunk keys: {list(chunk.keys())}")

                    if "room" in chunk["updates"]:
                        # Only update the current room, not the new room we just created
                        if not chunk["updates"].get("new_room"):
                            logger.info(f"[WebSocket] Updating room {room.id}")
                            room_updates = chunk["updates"]["room"]
                            if "players" not in room_updates:
                                room_updates["players"] = await game_manager.db.get_room_players(room.id)
                            # Ensure image_url is a string if it exists
                            if "image_url" in room_updates:
                                image_url = room_updates["image_url"]
                                if hasattr(image_url, 'url'):
                                    room_updates["image_url"] = image_url.url
                                elif hasattr(image_url, '__str__'):
                                    room_updates["image_url"] = str(image_url)
                            room = Room(**{**room.dict(), **room_updates})
                            await game_manager.db.set_room(room.id, room.dict())

                            # Broadcast room update via WebSocket
                            logger.info(f"[WebSocket] Broadcasting room update for {room.id}")
                            await manager.broadcast_to_room(
                                room_id=room.id,
                                message={
                                    "type": "room_update",
                                    "room": room.dict()
                                }
                            )

                            # Remove room data from chunk to prevent double updates
                            chunk["updates"]["room"] = {}

                    if "npcs" in chunk["updates"]:
                        for npc_update in chunk["updates"]["npcs"]:
                            npc_id = npc_update["id"]
                            npc_data = await game_manager.db.get_npc(npc_id)
                            if npc_data:
                                npc = NPC(**{**npc_data, **npc_update})
                                await game_manager.db.set_npc(npc_id, npc.dict())

                    # Notify other players in the room about the action
                    # CRITICAL: Only broadcast to OTHER players, not the player who performed the action
                    await manager.broadcast_to_room(
                        room_id=action_request.room_id,
                        message={
                            "type": "action",
                            "player_id": action_request.player_id,
                            "action": action_request.action,
                            "message": chunk["response"],
                            "updates": {
                                "player": chunk.get("updates", {}).get("player"),
                                "npcs": chunk.get("updates", {}).get("npcs")
                            }
                        },
                        exclude_player=action_request.player_id
                    )
                else:
                    # This is a text chunk
                    yield json.dumps({
                        "type": "chunk",
                        "content": chunk
                    })

        except Exception as e:
            yield json.dumps({"error": str(e)})

    return EventSourceResponse(event_generator())

# Room information endpoint
@app.get("/room/{room_id}")
async def get_room_info(room_id: str, game_manager: GameManager = Depends(get_game_manager)):
    """Get room information including players, NPCs, and items"""
    try:
        # Get room data
        room_data = await game_manager.db.get_room(room_id)
        if not room_data:
            raise HTTPException(status_code=404, detail="Room not found")
        
        room = Room(**room_data)
        
        # Get players in room
        players = []
        for player_id in room.players:
            player_data = await game_manager.db.get_player(player_id)
            if player_data:
                players.append(Player(**player_data))
        
        # Get NPCs in room
        npcs = []
        for npc_id in room.npcs:
            npc_data = await game_manager.db.get_npc(npc_id)
            if npc_data:
                npcs.append(NPC(**npc_data))
        
        # Get items in room
        items = []
        for item_id in room.items:
            item_data = await game_manager.db.get_item(item_id)
            if item_data:
                items.append(Item(**item_data))
        
        # Get monsters in room
        monsters = []
        for monster_id in room.monsters:
            monster_data = await game_manager.db.get_monster(monster_id)
            if monster_data:
                monsters.append(Monster(**monster_data))
        
        # Generate atmospheric monster presence description
        atmospheric_presence = ""
        if room.monsters:
            logger.info(f"[get_room_info] Generating atmospheric presence for {len(room.monsters)} monsters in room {room.id}")
            atmospheric_presence = await get_atmospheric_monster_presence(room_data, game_manager)
            logger.info(f"[get_room_info] Generated atmospheric presence: '{atmospheric_presence[:100]}...' (length: {len(atmospheric_presence)})")
        else:
            logger.info(f"[get_room_info] No monsters in room {room.id}, skipping atmospheric presence")
        
        return {
            "room": room,
            "players": players,
            "npcs": npcs,
            "items": items,
            "monsters": monsters,
            "atmospheric_presence": atmospheric_presence
        }
    except Exception as e:
        logger.error(f"Error getting room info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_atmospheric_monster_presence(room_data: Dict[str, Any], game_manager: GameManager = None) -> str:
    """Generate AI-powered atmospheric descriptions of monsters in a room"""
    try:
        if not room_data or not room_data.get('monsters'):
            return ""
        
        # Get monster data
        monsters_info = []
        for monster_id in room_data['monsters']:
            if game_manager:
                monster_data = await game_manager.db.get_monster(monster_id)
                if monster_data and monster_data.get('is_alive', True):
                    monsters_info.append(monster_data)
        
        if not monsters_info:
            return ""
            
        # Create AI prompt for atmospheric description
        biome = room_data.get('biome', 'unknown area')
        room_title = room_data.get('title', 'this location')
        
        # Build monster context for AI
        monster_context = []
        for monster in monsters_info:
            monster_context.append({
                'name': monster['name'],
                'size': monster['size'],
                'description': monster['description'],
                'aggressiveness': monster['aggressiveness']
            })
        
        # Generate AI description
        if game_manager and hasattr(game_manager, 'ai_handler'):
            prompt = f"""You are describing what a player sees when entering a room with monsters. Write an atmospheric description from the player's perspective, as if observing these creatures from a distance.

IMPORTANT GUIDELINES:
- Write from the player's perspective ("You see...", "You notice...")
- Describe what the creatures LOOK like, not their stats or abilities
- Make it feel like distant observation - mysterious but visual
- Keep it atmospheric and immersive
- Don't mention creature names directly
- Focus on visual appearance and behavior
- 2-3 sentences maximum
- Make it fit the {biome} environment

LOCATION: {room_title}
BIOME: {biome}
MONSTERS: {len(monsters_info)} creature(s)

CREATURE DETAILS:
""" + "\n".join([f"- A {m['size']}-sized creature: {m['description']} (appears {m['aggressiveness']})" for m in monster_context])

            prompt += f"\n\nWrite an atmospheric description of what the player observes from a distance:"
            
            try:
                ai_response = await game_manager.ai_handler.generate_text(prompt)
                return ai_response.strip()
            except Exception as e:
                logger.error(f"Error generating AI monster description: {str(e)}")
                # Fallback to basic description
                pass
        
        # Fallback: Simple description if AI fails
        if len(monsters_info) == 1:
            monster = monsters_info[0]
            return f"You notice a {monster['size']} creature moving through the {biome}..."
        else:
            return f"You observe {len(monsters_info)} creatures inhabiting this {biome}..."
        
    except Exception as e:
        logger.error(f"Error generating atmospheric monster presence: {str(e)}")
        return ""

# World structure endpoint for debugging
@app.get("/world/structure")
async def get_world_structure(
    game_manager: GameManager = Depends(get_game_manager)
):
    try:
        world_structure = await game_manager.get_world_structure()
        return world_structure
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get player data endpoint
@app.get("/players/{player_id}")
async def get_player(
    player_id: str,
    game_manager: GameManager = Depends(get_game_manager)
):
    try:
        player_data = await game_manager.db.get_player(player_id)
        if not player_data:
            raise HTTPException(status_code=404, detail="Player not found")
        return player_data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Player presence update endpoint
@app.post("/presence")
async def update_presence(
    request: PresenceRequest,
    game_manager: GameManager = Depends(get_game_manager)
):
    try:
        # Get player info
        player_data = await game_manager.db.get_player(request.player_id)
        if not player_data:
            raise ValueError("Player not found")

        player = Player(**player_data)

        # Update room presence
        await game_manager.db.remove_from_room_players(player.current_room, request.player_id)
        await game_manager.db.add_to_room_players(request.room_id, request.player_id)

        # Update player's current room
        player.current_room = request.room_id
        await game_manager.db.set_player(request.player_id, player.dict())

        # Notify other players
        await manager.broadcast_to_room(
            room_id=request.room_id,
            message={
                "type": "presence", 
                "player_id": request.player_id, 
                "player_data": player.dict(),
                "status": "joined"
            },
            exclude_player=request.player_id
        )

        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Chat endpoint
@app.post("/chat")
async def send_chat(
    message: ChatMessage,
    game_manager: GameManager = Depends(get_game_manager)
):
    try:
        # Store the chat message
        await game_manager.db.store_chat_message(message.room_id, message)
        
        # Broadcast the message to all players in the room
        await manager.broadcast_to_room(
            room_id=message.room_id,
            message=message.dict(),
            exclude_player=message.player_id if message.message_type != "system" else None
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# NPC interaction endpoint
@app.post("/npc")
async def interact_with_npc(
    interaction: NPCInteraction,
    game_manager: GameManager = Depends(get_game_manager)
):
    try:
        response = await game_manager.handle_npc_interaction(
            player_id=interaction.player_id,
            npc_id=interaction.npc_id,
            message=interaction.message
        )

        # Broadcast the interaction to other players in the room
        await manager.broadcast_to_room(
            room_id=interaction.room_id,
            message={
                "type": "npc_interaction",
                "player_id": interaction.player_id,
                "npc_id": interaction.npc_id,
                "message": interaction.message,
                "response": response
            },
            exclude_player=interaction.player_id
        )

        return {
            "success": True,
            "response": response
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Chat history endpoint
@app.get("/chat/history/{room_id}")
async def get_room_chat_history(
    room_id: str,
    limit: int = 50,
    game_manager: GameManager = Depends(get_game_manager)
):
    """Get chat history for a room"""
    try:
        messages = await game_manager.db.get_chat_history(room_id, limit)
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Action history endpoint
@app.get("/actions/history/{player_id}")
async def get_player_action_history(
    player_id: str,
    limit: int = 50,
    game_manager: GameManager = Depends(get_game_manager)
):
    """Get action history for a player"""
    try:
        actions = await game_manager.db.get_action_history(player_id, limit)
        return {"actions": actions}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Analytics endpoint
@app.get("/analytics/player/{player_id}")
async def get_player_analytics(
    player_id: str,
    days: int = 7,
    game_manager: GameManager = Depends(get_game_manager)
):
    """Get player action analytics"""
    try:
        from datetime import timedelta
        from collections import Counter
        
        actions = await game_manager.db.get_action_history(player_id, limit=1000)
        
        # Filter by date range
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        recent_actions = []
        
        for action in actions:
            action_time = datetime.fromisoformat(action['timestamp'])
            if action_time > cutoff_date:
                recent_actions.append(action)
        
        return {
            "total_actions": len(recent_actions),
            "actions_per_day": len(recent_actions) / days if days > 0 else 0,
            "most_common_actions": Counter([a['action'] for a in recent_actions]).most_common(10),
            "rooms_visited": list(set([a['room_id'] for a in recent_actions])),
            "total_ai_responses": len(recent_actions),
            "average_response_length": sum(len(a['ai_response']) for a in recent_actions) / len(recent_actions) if recent_actions else 0
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Rate limit status endpoint
@app.get("/rate-limit/status/{player_id}")
async def get_rate_limit_status(
    player_id: str,
    game_manager: GameManager = Depends(get_game_manager)
):
    """Get current rate limit status for a player"""
    try:
        status = await game_manager.rate_limiter.get_rate_limit_status(
            player_id,
            game_manager.rate_limit_config['limit'],
            game_manager.rate_limit_config['interval_minutes']
        )
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Update rate limit configuration endpoint
@app.post("/rate-limit/config")
async def update_rate_limit_config(
    config: dict,
    game_manager: GameManager = Depends(get_game_manager)
):
    """Update rate limit configuration"""
    try:
        if 'limit' in config:
            game_manager.rate_limit_config['limit'] = config['limit']
        if 'interval_minutes' in config:
            game_manager.rate_limit_config['interval_minutes'] = config['interval_minutes']
        
        return {
            "success": True,
            "config": game_manager.rate_limit_config
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)