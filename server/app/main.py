from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request, status
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
from .auth_models import (
    RegisterRequest,
    LoginRequest,
    UpdateUsernameRequest,
    AuthResponse,
    UserProfile,
    RegisterResponse
)
from .auth_service import AuthService
from .auth_utils import get_current_user, get_optional_current_user
from .game_manager import GameManager
from .config import settings
from .logger import setup_logging
from .templates.items import GenericItemTemplate
from .monster_behavior import monster_behavior_manager
import uuid
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta
import asyncio
from .game_manager import GameManager
from .hybrid_database import HybridDatabase as Database
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
    
    if message_type == "duel_challenge":
        try:
            challenger_id = message.get("challenger_id") or player_id
            target_id = message.get("target_id")
            if not target_id:
                logger.error("[handle_duel_message] duel_challenge missing target_id")
                return
            import uuid as _uuid
            duel_id = f"pvp_duel_{_uuid.uuid4()}"
            duel_pending[duel_id] = {
                "player1_id": challenger_id,
                "player2_id": target_id,
                "room_id": room_id,
                "round": 1,
                "player1_condition": "healthy",
                "player2_condition": "healthy",
                "player1_tags": [],
                "player2_tags": [],
                "player1_total_severity": 0,
                "player2_total_severity": 0,
                "is_monster_duel": False,
                "history": [],
                "player1_vital": 0,
                "player2_vital": 0,
                "player1_control": 0,
                "player2_control": 0,
                "finishing_window_owner": None
            }
            await manager.broadcast_to_room(room_id, {
                "type": "duel_challenge",
                "challenger_id": challenger_id,
                "target_id": target_id,
                "room_id": room_id,
                "timestamp": datetime.now().isoformat()
            })
            return
        except Exception as e:
            logger.error(f"[handle_duel_message] Error handling duel_challenge: {str(e)}")
            return
    
    if message_type == "duel_response":
        try:
            challenger_id = message.get("challenger_id")
            responder_id = message.get("responder_id") or player_id
            response = message.get("response")
            duel_id = None
            for potential_duel_id, duel_info in duel_pending.items():
                if (duel_info.get("room_id") == room_id and
                    {duel_info.get("player1_id"), duel_info.get("player2_id")} == {challenger_id, responder_id} and
                    not duel_info.get("is_monster_duel")):
                    duel_id = potential_duel_id
                    break
            if not duel_id and response == "accept" and challenger_id and responder_id:
                import uuid as _uuid
                duel_id = f"pvp_duel_{_uuid.uuid4()}"
                duel_pending[duel_id] = {
                    "player1_id": challenger_id,
                    "player2_id": responder_id,
                    "room_id": room_id,
                    "round": 1,
                    "player1_condition": "healthy",
                    "player2_condition": "healthy",
                    "player1_tags": [],
                    "player2_tags": [],
                    "player1_total_severity": 0,
                    "player2_total_severity": 0,
                    "is_monster_duel": False,
                    "history": [],
                    "player1_vital": 0,
                    "player2_vital": 0,
                    "player1_control": 0,
                    "player2_control": 0,
                    "finishing_window_owner": None
                }
            await manager.broadcast_to_room(room_id, {
                "type": "duel_response",
                "challenger_id": challenger_id,
                "responder_id": responder_id,
                "response": response,
                "room_id": room_id,
                "timestamp": datetime.now().isoformat()
            })
            if response == "decline" and duel_id and duel_id in duel_pending:
                del duel_pending[duel_id]
            return
        except Exception as e:
            logger.error(f"[handle_duel_message] Error handling duel_response: {str(e)}")
            return
    
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
        
        # Ensure duel has history container
        try:
            duel_pending.get(duel_id, {}).setdefault('history', [])
        except Exception as e:
            logger.error(f"[handle_duel_message] Error ensuring duel history exists: {str(e)}")
        
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

async def generate_monster_combat_move(monster_data: Dict[str, Any], player_data: Dict[str, Any], room_data: Dict[str, Any], round_number: int, game_manager: GameManager, recent_rounds: Optional[List[Dict[str, Any]]] = None) -> str:
    """Generate a contextual combat move for a monster using AI"""
    try:
        recent_rounds = recent_rounds or []
        # Build concise recent monster move history
        monster_history_lines: List[str] = []
        try:
            for r in recent_rounds[-5:]:
                m = r.get('player2_move') or r.get('monster_move') or ''
                if m:
                    monster_history_lines.append(f"R{r.get('round')}: {m}")
        except Exception:
            monster_history_lines = []
        history_block = "\n".join(monster_history_lines) if monster_history_lines else "None"
        recent_moves = [
            (r.get('player2_move') or r.get('monster_move') or '').strip().lower()
            for r in recent_rounds[-5:]
            if (r.get('player2_move') or r.get('monster_move'))
        ]
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
        prompt = f"""You are controlling a monster in combat. Generate FIVE distinct candidate combat moves for this creature.
 
 RECENT MONSTER MOVES (avoid repeating, vary tactics):
 {history_block}
 
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
 1. Generate FIVE specific combat actions (2-5 words each)
 2. Match the monster's aggressiveness level:
    - passive: NEVER directly attack the player - only defensive moves, retreating, evasion, or intimidation
    - neutral: balanced offense and defense, only attacks when provoked
    - aggressive: fierce attacks, advancing moves, relentless offense
    - territorial: protective attacks, warning strikes, defending their space
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
 7. Avoid repeating recent moves; vary verbs and approach.
 
 EXAMPLES:
 - "lunges with claws extended"
 - "breathes a cone of fire"
 - "charges with lowered horns"
 - "strikes with venomous fangs"
 - "dodges and counterattacks"
 
 Return STRICT JSON array of 5 strings, no prose, e.g.: ["option 1", "option 2", "option 3", "option 4", "option 5"]"""
 
        # Get AI response
        ai_response = await game_manager.ai_handler.generate_text(prompt)
        text = ai_response.strip()
        # Parse JSON array of options
        options: List[str] = []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                options = [str(x).strip() for x in parsed if isinstance(x, (str, int, float))]
        except Exception:
            # Fallback: try to extract between [ ]
            try:
                start = text.find('[')
                end = text.rfind(']')
                if start != -1 and end != -1 and end > start:
                    parsed = json.loads(text[start:end+1])
                    if isinstance(parsed, list):
                        options = [str(x).strip() for x in parsed if isinstance(x, (str, int, float))]
            except Exception:
                options = []
        if not options:
            # Last fallback: split by newlines and take up to 5
            options = [line.strip('- ').strip() for line in text.splitlines() if line.strip()][:5]

        # Choose option least similar to recent moves (avoid repetition) using difflib ratio
        try:
            from difflib import SequenceMatcher
            def max_similarity(candidate: str) -> float:
                cand = (candidate or '').strip().lower()
                if not recent_moves:
                    return 0.0
                return max(SequenceMatcher(None, cand, prev).ratio() for prev in recent_moves)
            # Rank by smallest maximum similarity; tie-break by length diversity
            ranked = sorted(options, key=lambda o: (round(max_similarity(o), 4), len(o)))
            chosen = ranked[0] if ranked else (options[0] if options else "attacks")
        except Exception:
            chosen = options[0] if options else "attacks"

        # Trim overly long
        if len(chosen) > 100:
            chosen = chosen[:100]

        logger.info(f"[generate_monster_combat_move] Generated move for {monster_name} (chosen): '{chosen}' from options: {options}")
        return chosen
        
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
        
        # Compute max vitals upfront and include immediately
        player1_max_vital = 6
        player2_max_vital = await get_monster_max_vital(monster_data)

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
            "is_monster_duel": True,  # Flag to indicate this is a monster duel
            "player1_max_vital": player1_max_vital,
            "player2_max_vital": player2_max_vital
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
            "monster_data": monster_data,  # Store monster data for AI move generation
            "history": [],  # Keep last 10 rounds of combat history
            "player1_vital": 0,
            "player2_vital": 0,
            "player1_control": 0,
            "player2_control": 0,
            "finishing_window_owner": None
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
        
        # Fetch recent history to promote varied moves
        recent_rounds = []
        try:
            recent_rounds = (duel_pending.get(duel_id, {}) or {}).get('history', [])[-5:]
        except Exception:
            recent_rounds = []

        # Generate monster move
        monster_move = await generate_monster_combat_move(
            monster_data, player_data, room_data, round_number, game_manager, recent_rounds=recent_rounds
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
        # Ensure history list exists
        combat_history = combat_info.setdefault('history', [])
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
        
        # Current conditions
        player_condition = combat_info.get('player_condition', 'healthy')
        monster_condition = combat_info.get('monster_condition', 'healthy')
        
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
            room_name, room_description, game_manager,
            recent_rounds=combat_history[-10:]
        )
        
        logger.info(f"[analyze_monster_combat] Narrative generated: {narrative[:100]}...")
        
        # Update combat state
        combat_info['player_condition'] = combat_outcome['player1_result']['condition']
        combat_info['monster_condition'] = combat_outcome['player2_result']['condition']
        
        # Append round to history and cap at last 10
        try:
            combat_history.append({
                'round': current_round,
                'player_move': player_move,
                'monster_move': monster_move,
                'narrative': narrative,
                'player_result': combat_outcome.get('player1_result', {}),
                'monster_result': combat_outcome.get('player2_result', {})
            })
            if len(combat_history) > 10:
                del combat_history[:-10]
        except Exception as e:
            logger.error(f"[analyze_monster_combat] Error updating combat history: {str(e)}")
        
        # End combat when someone cannot continue
        combat_ends = (
            combat_outcome['player1_result']['can_continue'] == False or
            combat_outcome['player2_result']['can_continue'] == False
        )
        
        # Send results to player
        await send_monster_combat_results(
            room_id, player_id, monster_id, current_round,
            player_move, monster_move,
            combat_outcome['player1_result']['condition'],
            combat_outcome['player2_result']['condition'],
            0, 0,
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

async def get_monster_max_severity(monster_data: dict) -> int:
    """Compute max severity threshold based on monster size using base 20."""
    size = (monster_data or {}).get('size', 'human')
    size_multipliers = {
        'insect': 0.25,
        'chicken': 0.5,
        'human': 1.0,
        'horse': 1.5,
        'dinosaur': 2.0,
        'colossal': 3.0,
    }
    return int(20 * size_multipliers.get(size, 1.0))

async def get_monster_max_vital(monster_data: dict) -> int:
    """Compute max vital (HP clock) based on monster size using base 6 with exact multipliers.
    Mapping:
      - colossal: 300% -> 18
      - dinosaur: 200% -> 12
      - horse: 150% -> 9
      - human: 100% -> 6
      - chicken: 50% -> 3
      - insect: 25% -> 2 (rounded from 1.5)
    """
    size = (monster_data or {}).get('size', 'human')
    size_multipliers = {
        'insect': 0.25,
        'chicken': 0.5,
        'human': 1.0,
        'horse': 1.5,
        'dinosaur': 2.0,
        'colossal': 3.0,
    }
    mult = size_multipliers.get(size, 1.0)
    # Round to nearest, minimum 1
    return max(1, int(round(6 * mult)))

async def send_monster_combat_results(room_id: str, player_id: str, monster_id: str, round_number: int,
                                    player_move: str, monster_move: str, player_condition: str, monster_condition: str,
                                    _player_total_severity: int, _monster_total_severity: int,
                                    narrative: str, combat_ends: bool, game_manager: GameManager):
    """Send monster combat results to the player via WebSocket"""
    try:
        # Get monster name
        monster_data = await game_manager.db.get_monster(monster_id)
        monster_name = monster_data.get('name', 'Unknown Monster') if monster_data else "Unknown Monster"
        
        # Format combat message (tags and severity removed)
        combat_message = {
            "type": "monster_combat_outcome",
            "round": round_number,
            "monster_name": monster_name,
            "player_move": player_move,
            "monster_move": monster_move,
            "player_condition": player_condition,
            "monster_condition": monster_condition,
            "narrative": narrative,
            "combat_ends": combat_ends,
            "monster_defeated": False,
            "player_vital": 0,
            "monster_vital": 0,
            "player_control": 0,
            "monster_control": 0,
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
        
        duel_info = duel_pending.get(duel_id)
        if not duel_info:
            raise ValueError(f"Duel info not found for {duel_id}")
        # Ensure history list exists
        duel_history = duel_info.setdefault('history', [])
        player1_id = duel_info['player1_id']
        player2_id = duel_info['player2_id']
        room_id = duel_info['room_id']
        current_round = duel_info['round']
        
        # Get player moves
        moves = duel_moves.get(duel_id, {})
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
            player2_data = None  # Monsters don't have player data
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
        player1_condition_prev = duel_info.get('player1_condition', 'healthy')
        player2_condition_prev = duel_info.get('player2_condition', 'healthy')
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
            player1_name, player1_move, player1_condition_prev, equipment_result['player1_valid'],
            player2_name, player2_move, player2_condition_prev, equipment_result['player2_valid'],
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
            room_name, room_description, game_manager,
            recent_rounds=duel_history[-10:]
        )
 
        logger.info(f"[analyze_duel_moves] Narrative generated: {narrative[:100]}...")
 
        # NEW: Derive Vital/Control strictly from outcome (and lightly from narrative), not from separate AI ticks
        def condition_to_severity(cond: str) -> int:
            c = (cond or '').strip().lower()
            if c in ('dead', 'unconscious', 'surrendered', 'maimed', 'incapacitated'):
                return 3
            if c in ('injured', 'hurt', 'wounded', 'dazed', 'shaken'):
                return 1
            return 0
 
        p1_sev_prev = condition_to_severity(player1_condition_prev)
        p2_sev_prev = condition_to_severity(player2_condition_prev)
        p1_sev_new = condition_to_severity(combat_outcome['player1_result'].get('condition'))
        p2_sev_new = condition_to_severity(combat_outcome['player2_result'].get('condition'))
 
        # Vital deltas are the positive change in condition severity, clamped 0..3
        p1_vital_delta = max(0, min(3, p1_sev_new - p1_sev_prev))
        p2_vital_delta = max(0, min(3, p2_sev_new - p2_sev_prev))
 
        # Control deltas: reward the side that caused damage this round; small defensive gain if clean evade indicated
        p1_control_delta = 0
        p2_control_delta = 0
        if p2_vital_delta > 0 and p1_vital_delta == 0:
            p1_control_delta += 1
        if p1_vital_delta > 0 and p2_vital_delta == 0:
            p2_control_delta += 1
        # Defensive cues from narrative
        narrative_l = (narrative or '').lower()
        defend_terms = ('dodge', 'dodges', 'dodged', 'block', 'blocks', 'blocked', 'parry', 'parries', 'parried', 'evade', 'evades', 'evaded', 'retreat', 'retreats', 'hide', 'hides', 'hiding')
        if any(t in narrative_l for t in defend_terms):
            # Heuristically award +1 control to the side that did not take damage if any defense cue present
            if p1_vital_delta == 0 and p2_vital_delta > 0:
                p1_control_delta = max(p1_control_delta, 1)
            if p2_vital_delta == 0 and p1_vital_delta > 0:
                p2_control_delta = max(p2_control_delta, 1)
 
        # Clamp deltas to allowed ranges
        p1_control_delta = max(-2, min(2, p1_control_delta))
        p2_control_delta = max(-2, min(2, p2_control_delta))
 
        # Update Vital/Control clocks
        p1_vital = max(0, duel_info.get('player1_vital', 0) + p1_vital_delta)
        p2_vital = max(0, duel_info.get('player2_vital', 0) + p2_vital_delta)
        p1_control = max(0, min(5, duel_info.get('player1_control', 0) + p1_control_delta))
        p2_control = max(0, min(5, duel_info.get('player2_control', 0) + p2_control_delta))
 
        duel_info['player1_vital'] = p1_vital
        duel_info['player2_vital'] = p2_vital
        duel_info['player1_control'] = p1_control
        duel_info['player2_control'] = p2_control
 
        # Compute win conditions for 2-track system
        player1_max_vital = 6
        player2_max_vital = 6
        if is_monster_duel:
            player2_max_vital = await get_monster_max_vital(monster_data)
 
        finishing_owner = duel_info.get('finishing_window_owner')
        finishing_now = None
        if p1_control >= 5 and not finishing_owner:
            duel_info['finishing_window_owner'] = 'player1'
        elif p2_control >= 5 and not finishing_owner:
            duel_info['finishing_window_owner'] = 'player2'
 
        # End if Vital maxed, or Control full with successful follow-up
        p1_broken = p1_vital >= player1_max_vital
        p2_broken = p2_vital >= player2_max_vital
 
        # Check if combat should end
        combat_ends = (
            combat_outcome['player1_result']['can_continue'] == False or
            combat_outcome['player2_result']['can_continue'] == False or
            p1_broken or p2_broken
        )
  
        logger.info(f"[analyze_duel_moves] Combat ends: {combat_ends} (reason: {'player1_can_continue=False' if not combat_outcome['player1_result']['can_continue'] else ''} {'player2_can_continue=False' if not combat_outcome['player2_result']['can_continue'] else ''} {'player1_vital_full' if p1_broken else ''} {'player2_vital_full' if p2_broken else ''})")
  
        # Update duel state
        duel_info['player1_condition'] = combat_outcome['player1_result']['condition']
        duel_info['player2_condition'] = combat_outcome['player2_result']['condition']
        # Legacy fields kept for compatibility but set to zero
        duel_info['player1_total_severity'] = 0
        duel_info['player2_total_severity'] = 0
        # Append round to history and cap at last 10
        try:
            duel_history.append({
                'round': current_round,
                'player1_move': player1_move,
                'player2_move': player2_move,
                'narrative': narrative,
                'player1_result': combat_outcome.get('player1_result', {}),
                'player2_result': combat_outcome.get('player2_result', {}),
                'player1_vital_delta': p1_vital_delta,
                'player2_vital_delta': p2_vital_delta,
                'player1_control_delta': p1_control_delta,
                'player2_control_delta': p2_control_delta,
                'player1_vital': p1_vital,
                'player2_vital': p2_vital,
                'player1_control': p1_control,
                'player2_control': p2_control
            })
            if len(duel_history) > 10:
                del duel_history[:-10]
        except Exception as e:
            logger.error(f"[analyze_duel_moves] Error updating duel history: {str(e)}")
  
        # Send results to players
        await send_duel_results(
            duel_id, room_id, player1_id, player2_id, current_round,
            player1_move, player2_move,
            combat_outcome['player1_result']['condition'],
            combat_outcome['player2_result']['condition'],
            [], [],
            0, 0,
            narrative, combat_ends, game_manager,
            p1_vital, p2_vital, p1_control, p2_control,
            player1_max_vital, player2_max_vital
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

                return {
                    'player1_valid': player1_valid,
                    'player2_valid': player2_valid,
                    'player1_reason': player1_reason,
                    'player2_reason': player2_reason
                }
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

{player1_name} action toward {player2_name}:
- Move: "{player1_move}"
- Condition: {player1_condition}
- Equipment Valid: {player1_equipment_valid}
- Inventory: {player1_inventory}
- Invalid Move Info: {player1_invalid_move if player1_invalid_move else 'None'}

{player2_name} action toward {player1_name}:
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

2. DO NOT INVENT ACTIONS:
   - ONLY use the exact moves provided above for each side
   - If a player's move is defensive (defend, block, parry, dodge, retreat), treat it as DEFENSIVE. Do not describe them attacking
   - Attacks must come from explicit attack-like moves (punch, stab, shoot, slash, strike, etc.)

3. TARGETING:
   - {player1_name}'s attack-like moves target {player2_name}
   - {player2_name}'s attack-like moves target {player1_name}
   - Successful attacks harm the TARGET, not the attacker
   - VALID ATTACKS should have impact unless countered by defensive actions
   - Monster attacks are ALWAYS VALID and should have some effect

4. DEFENSE:
   - Defensive moves (block, dodge, parry) can reduce or prevent damage only when the player actually chose them
   - Invalid moves (missing equipment) cause NO DAMAGE and have NO EFFECT

5. EXPLAIN MISSED/FAILED ATTACKS:
   - If an attack fails or misses, explain WHY (invalid equipment, target blocked, target dodged, poor footing, etc.)

6. ENVIRONMENT AWARENESS:
    - Consider the location: {room_name}
    - Reference environment only when relevant to the move

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
    current_round: int, room_name: str, room_description: str, game_manager: GameManager,
    recent_rounds: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Create narrative description of combat round"""
    
    # Build a compact recent history summary (up to last 10 rounds)
    recent_rounds = recent_rounds or []
    history_lines: List[str] = []
    try:
        for r in recent_rounds[-10:]:
            rnum = r.get('round')
            p1m = r.get('player1_move') or r.get('player_move')
            p2m = r.get('player2_move') or r.get('monster_move')
            p1res = (r.get('player1_result') or r.get('player_result') or {}).get('reason', '')
            p2res = (r.get('player2_result') or r.get('monster_result') or {}).get('reason', '')
            history_lines.append(f"R{rnum}: {player1_name} -> '{p1m}' ({p1res}); {player2_name} -> '{p2m}' ({p2res})")
    except Exception as e:
        logger.error(f"[generate_combat_narrative] Error summarizing recent rounds: {str(e)}")
        history_lines = []
    history_block = "\n".join(history_lines) if history_lines else "None"

    prompt = f"""
        Create an engaging, descriptive narrative for this combat round.
 
        Location: {room_name} - {room_description}
 
        Recent Rounds (most recent first, up to 10):
        {history_block}
 
        Combat Context:
-        - {player1_name} attacks {player2_name} with: {player1_move}
-        - {player2_name} attacks {player1_name} with: {player2_move}
+        - {player1_name} acts with: {player1_move}
+        - {player2_name} acts with: {player2_move}
         
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
-        - If moves are valid (including basic actions like punch/kick), describe them as effective attacks
+        - If moves are valid (including basic actions like punch/kick), describe them accordingly
         - Describe the actual outcomes and their impact on both players
         - Make it feel like a real combat scene, not just a game log
         - Keep it concise but descriptive (2-4 sentences)
         - Use active voice and dynamic language
         - Use actual player names: {player1_name} and {player2_name}
-        - Basic actions like punch, kick, tackle are valid and can cause damage
+        - Basic actions like punch, kick, tackle are valid and can cause damage when chosen
         - Only equipment-based actions without the required equipment are invalid
         - ALWAYS explain why attacks miss or fail - be specific about the reason
          
         CRITICAL RULES:
         1. DO NOT directly reference tags, severity levels, or game mechanics
            - Don't say "with a severity level of 3" or "gets a negative tag"
            - Instead, describe the actual injury/advantage naturally
            - Example: "leaving him bruised and shaken" not "gets bruised ribs tag"
           
         2. MOVE IMPACT RULES:
-            - VALID ATTACKS MUST CAUSE DAMAGE unless the target is actively defending
-            - If a valid attack lands, describe the damage and its effect
+            - Do NOT invent actions. ONLY describe what each side actually attempted.
+            - If a player's move is defensive (e.g., defend, block, parry, dodge, retreat), DO NOT describe them attacking. Focus on mitigation, positioning, or advantage shifts.
+            - VALID ATTACKS MUST CAUSE DAMAGE unless the target is explicitly defending in their own move
+            - If a valid attack lands, describe the damage and its effect; if it fails, explain why
             - If an attack misses, EXPLAIN WHY (missing equipment, target blocked, target dodged, etc.)
             - Invalid moves (missing equipment) have NO EFFECT and should be explained as such
          
         3. DODGING/BLOCKING RULES:
             - Players can ONLY dodge/block if their move explicitly includes dodging/blocking
             - If a player's move is "punch", they cannot dodge - they are punching
             - If a player's move is "dodge" or "block", then they can avoid attacks
             - If a player's move is "kick", they cannot dodge - they are kicking
             - Only describe dodging/blocking when it's part of the player's actual move
 
         3. ENVIRONMENT AWARENESS:
             - The combat is taking place in: 
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
    game_manager: GameManager,
    recent_rounds: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Generate new tags based on combat outcomes, derived from the narrative."""
    
    # Build a compact recent history summary (up to last 10 rounds)
    recent_rounds = recent_rounds or []
    history_lines: List[str] = []
    try:
        for r in recent_rounds[-10:]:
            rnum = r.get('round')
            p1m = r.get('player1_move') or r.get('player_move')
            p2m = r.get('player2_move') or r.get('monster_move')
            p1tags = r.get('player1_new_tags') or r.get('player_new_tags') or []
            p2tags = r.get('player2_new_tags') or r.get('monster_new_tags') or []
            p1sev = sum(t.get('severity', 0) for t in p1tags if t.get('type') == 'negative')
            p2sev = sum(t.get('severity', 0) for t in p2tags if t.get('type') == 'negative')
            history_lines.append(f"R{rnum}: {player1_name} '{p1m}' (-{p1sev}); {player2_name} '{p2m}' (-{p2sev})")
    except Exception as e:
        logger.error(f"[generate_combat_tags_from_narrative] Error summarizing recent rounds: {str(e)}")
        history_lines = []
    history_block = "\n".join(history_lines) if history_lines else "None"

    prompt = f"""
        Analyze the combat narrative and generate appropriate tags for both players.
 
        Narrative: {narrative}
 
        Recent Rounds (most recent first, up to 10):
        {history_block}
 
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
           - Use the recent rounds to calibrate: avoid monotonously repeating 1-2 severity every round. If a clear, smart, or well-timed attack lands, vary with justified moderate severity.
           - Do NOT inflate severity just for variation. Escalate only when the narrative clearly supports it (clean hit, counter, exposed target, environmental advantage, or equipment properly used).
         
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
 
        7. IMPACTFUL SMART PLAY:
           - Reward smart tactics: counters, using terrain, exploiting openings, valid equipment synergy, set-ups from prior rounds.
           - If a player clearly outplays the opponent this round, increase severity appropriately.
           - Only give negative impact when a player does something obviously poor or is countered.
 
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
    narrative: str, combat_ends: bool, game_manager: GameManager,
    player1_vital: int, player2_vital: int, player1_control: int, player2_control: int,
    player1_max_vital: int = 6, player2_max_vital: int = 6
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
        "player1_vital": player1_vital,
        "player2_vital": player2_vital,
        "player1_control": player1_control,
        "player2_control": player2_control,
        "player1_max_vital": player1_max_vital,
        "player2_max_vital": player2_max_vital,
        "description": narrative,
        "combat_ends": combat_ends,
        "room_id": room_id,
        "timestamp": datetime.now().isoformat()
    }
    
    await manager.send_to_player(room_id, player1_id, round_message)
    await manager.send_to_player(room_id, player2_id, round_message)
    
    # Add round description to room chat

    if combat_ends:
        # Determine winner based on clocks/conditions
        incapacitated = {'dead', 'unconscious', 'surrendered', 'maimed', 'incapacitated'}
        # Assume base 6 for now (monsters may scale upstream)
        p1_broken = player1_vital >= player1_max_vital or (player1_condition or '').lower() in incapacitated
        p2_broken = player2_vital >= player2_max_vital or (player2_condition or '').lower() in incapacitated
        winner_id = None
        loser_id = None
        if p1_broken and not p2_broken:
            winner_id = player2_id
            loser_id = player1_id
        elif p2_broken and not p1_broken:
            winner_id = player1_id
            loser_id = player2_id
        elif (player1_condition or '').lower() in incapacitated and (player2_condition or '').lower() not in incapacitated:
            winner_id = player2_id
            loser_id = player1_id
        elif (player2_condition or '').lower() in incapacitated and (player1_condition or '').lower() not in incapacitated:
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
                - Final Round: {current_round + 1}

                Instructions:
                - Create an engaging, dramatic victory message
                - Consider the nature of the defeat (body overwhelmed or finishing window converted)
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

# ===============================
# Authentication Endpoints
# ===============================

@app.post("/auth/register", response_model=RegisterResponse)
async def register_user(request: RegisterRequest):
    """Register a new user with email, password, and username"""
    result = await AuthService.register_user(
        email=request.email,
        password=request.password,
        username=request.username
    )
    return result

@app.post("/auth/login", response_model=AuthResponse)
async def login_user(request: LoginRequest):
    """Login user with email and password"""
    result = await AuthService.login_user(
        email=request.email,
        password=request.password
    )
    return result

@app.get("/auth/profile", response_model=UserProfile)
async def get_user_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user's profile"""
    return {
        'id': current_user['id'],
        'username': current_user['username'],
        'email': current_user['email'],
        'current_player_id': current_user['current_player_id']
    }

@app.put("/auth/username")
async def update_username(
    request: UpdateUsernameRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Update user's username"""
    result = await AuthService.update_username(
        user_id=current_user['id'],
        new_username=request.username
    )
    return result

@app.get("/auth/check-username/{username}")
async def check_username_availability(username: str):
    """Check if a username is available"""
    from .auth_utils import validate_username, is_username_available
    
    # Validate format
    if not validate_username(username):
        return {
            'available': False,
            'reason': 'Username must be 3-20 characters, start with a letter, and contain only letters and numbers'
        }
    
    # Check availability
    is_available = await is_username_available(username)
    return {
        'available': is_available,
        'reason': None if is_available else 'Username is already taken'
    }

# ===============================
# Game Endpoints
# ===============================

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Game initialization endpoint (admin only - creates world)
@app.post("/start")
async def start_game(game_manager: GameManager = Depends(get_game_manager)):
    game_state = await game_manager.initialize_game()
    return game_state

# Join game endpoint (requires auth - places player in starting room)
@app.post("/join")
async def join_game(
    current_user: Dict[str, Any] = Depends(get_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Place the authenticated user's player in the game world"""
    if not current_user['current_player_id']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No player found for this user"
        )
    
    player = await game_manager.get_player(current_user['current_player_id'])
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )
    
    # If player doesn't have a current room, place them in starting room
    if not player.current_room:
        # Get or create starting room
        starting_room = await game_manager.ensure_starting_room()
        
        # Update player's location
        player.current_room = starting_room.id
        await game_manager.db.set_player(player.id, player.dict())
        
        # Add player to room's player list
        await game_manager.db.add_to_room_players(starting_room.id, player.id)
        
        logger.info(f"Placed player {player.name} in starting room {starting_room.id}")
        
        return {
            'message': f'Welcome to the game, {player.name}!',
            'player': player,
            'room': starting_room
        }
    else:
        # Player already in game, return current state
        room_data = await game_manager.db.get_room(player.current_room)
        room = Room(**room_data) if room_data else None
        
        return {
            'message': f'Welcome back, {player.name}!',
            'player': player,
            'room': room
        }

# Get current player endpoint (requires auth)
@app.get("/player")
async def get_current_player(
    current_user: Dict[str, Any] = Depends(get_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Get the current authenticated user's player"""
    if not current_user['current_player_id']:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No player found for this user"
        )
    
    player = await game_manager.get_player(current_user['current_player_id'])
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )
    
    return player

# Action endpoint with streaming support (requires auth)
@app.post("/action/stream")
async def process_action_stream(
    action_request: ActionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    # Validate that the user owns this player
    if action_request.player_id != current_user['current_player_id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only perform actions for your own player"
        )
    
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
                            
                            # Structured movement blocking: compute retreat and check monsters
                            room_data_current = await game_manager.db.get_room(player.current_room)
                            connections = room_data_current.get('connections', {}) if room_data_current else {}
                            last_room = monster_behavior_manager.player_last_room.get(action_request.player_id)
                            target_room = connections.get(direction.lower())
                            is_retreat = (last_room is not None and target_room == last_room)

                            # Aggressive blocking (allows retreat internally)
                            aggressive_block = None
                            if not is_retreat:
                                aggressive_block = await monster_behavior_manager.check_aggressive_monster_blocking(
                                    action_request.player_id, player.current_room, direction, game_manager
                                )
                            if aggressive_block:
                                monster_id, _ = aggressive_block
                                combat_message = await monster_behavior_manager.handle_aggressive_combat_initiation(
                                    action_request.player_id, monster_id, player.current_room, direction, game_manager
                                )
                                yield json.dumps({
                                    "type": "final",
                                    "content": combat_message,
                                    "updates": {}
                                })
                                return

                            # Territorial blocking (skip on retreat)
                            if not is_retreat:
                                territorial_block = await monster_behavior_manager.check_territorial_blocking(
                                    action_request.player_id, player.current_room, direction, game_manager
                                )
                                if territorial_block:
                                    monster_id, _ = territorial_block
                                    combat_message = await monster_behavior_manager.handle_territorial_combat_initiation(
                                        action_request.player_id, monster_id, player.current_room, direction, game_manager
                                    )
                                    yield json.dumps({
                                        "type": "final",
                                        "content": combat_message,
                                        "updates": {}
                                    })
                                    return

                            # Proceed with movement
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
                            
                            # Handle monster behaviors when entering new room
                            try:
                                new_room_data = await game_manager.db.get_room(new_room_id)
                                if new_room_data:
                                    # Get the direction the player came FROM (opposite of where they're going)
                                    # If player moves WEST, they entered from EAST
                                    opposite_directions = {
                                        'north': 'south',
                                        'south': 'north',
                                        'east': 'west',
                                        'west': 'east',
                                        'up': 'down',
                                        'down': 'up'
                                    }
                                    # The entry direction is the opposite of the movement direction
                                    entry_direction = opposite_directions.get(direction.lower(), direction)
                                    
                                    logger.info(f"[MonsterBehavior] Player moved {direction}, entered from {entry_direction}")
                                    
                                    behavior_messages = await monster_behavior_manager.handle_player_room_entry(
                                        action_request.player_id, new_room_id, old_room_id, entry_direction, new_room_data, game_manager
                                    )
                                    
                                    # Send behavior messages to player if any
                                    for behavior_message in behavior_messages:
                                        await manager.send_to_player(new_room_id, action_request.player_id, {
                                            "type": "system_message",
                                            "message": behavior_message,
                                            "timestamp": datetime.now().isoformat()
                                        })
                            except Exception as e:
                                logger.error(f"[Stream] Error handling monster behaviors: {str(e)}")
                            
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
                        # Non-movement actions: aggressive monsters attack on any action (retreat handled in movement logic)
                        is_movement = ("player" in chunk.get("updates", {}) and "direction" in chunk["updates"]["player"])
                        if not is_movement:
                            additional_content = ""

                            # NEW: If AI flags combat intent, initiate monster duel
                            combat_intent = chunk.get("updates", {}).get("combat")
                            if combat_intent is not None:
                                try:
                                    # Resolve target monster
                                    player_room_data = await game_manager.db.get_room(player.current_room)
                                    room_monsters = player_room_data.get("monsters", []) if player_room_data else []
                                    target_monster_id = None
                                    if isinstance(combat_intent, dict):
                                        target_monster_id = combat_intent.get("monster_id")
                                    if not target_monster_id and len(room_monsters) == 1:
                                        target_monster_id = room_monsters[0]
                                    if target_monster_id:
                                        combat_message = await monster_behavior_manager.handle_aggressive_combat_initiation(
                                            action_request.player_id, target_monster_id, player.current_room, "any_action", game_manager
                                        )
                                        yield json.dumps({
                                            "type": "final",
                                            "content": combat_message,
                                            "updates": {}
                                        })
                                        return
                                except Exception as e:
                                    logger.error(f"[Stream] Error initiating combat from AI intent: {str(e)}")

                            # If the AI indicates a monster interaction (talking), handle it before generic aggressive check
                            interaction = chunk.get("updates", {}).get("monster_interaction")
                            if interaction:
                                # Resolve monster target
                                target_monster_id = interaction.get("monster_id") if isinstance(interaction, dict) else None
                                player_room_data = await game_manager.db.get_room(player.current_room)
                                room_monsters = player_room_data.get("monsters", []) if player_room_data else []
                                if not target_monster_id and len(room_monsters) == 1:
                                    target_monster_id = room_monsters[0]

                                # If a target is found, check aggressiveness
                                if target_monster_id:
                                    monster_data = await game_manager.db.get_monster(target_monster_id)
                                    if monster_data and monster_data.get("is_alive", True):
                                        if monster_data.get("aggressiveness") == "aggressive":
                                            # Aggressive: initiate combat immediately on any action
                                            aggressive_block = await monster_behavior_manager.check_aggressive_monster_blocking(
                                                action_request.player_id, player.current_room, "any_action", game_manager
                                            )
                                            if aggressive_block:
                                                monster_id, _ = aggressive_block
                                                combat_message = await monster_behavior_manager.handle_aggressive_combat_initiation(
                                                    action_request.player_id, monster_id, player.current_room, "any_action", game_manager
                                                )
                                                yield json.dumps({
                                                    "type": "final",
                                                    "content": combat_message,
                                                    "updates": {}
                                                })
                                                return
                                        else:
                                            # Non-aggressive: produce dialogue based on intelligence via AI
                                            player_message = interaction.get("message", "") if isinstance(interaction, dict) else ""
                                            reply = await monster_behavior_manager.generate_monster_dialogue(
                                                target_monster_id, player_message, player.current_room, game_manager
                                            )
                                            if reply:
                                                additional_content = reply
                            # If no resolvable target, fall through to aggressive any_action check
                            aggressive_block = await monster_behavior_manager.check_aggressive_monster_blocking(
                                action_request.player_id, player.current_room, "any_action", game_manager
                            )
                            if aggressive_block:
                                monster_id, _ = aggressive_block
                                combat_message = await monster_behavior_manager.handle_aggressive_combat_initiation(
                                    action_request.player_id, monster_id, player.current_room, "any_action", game_manager
                                )
                                yield json.dumps({
                                    "type": "final",
                                    "content": combat_message,
                                    "updates": {}
                                })
                                return

                            # Fallback: ensure monsters always respond to general player messages
                            try:
                                player_room_data = await game_manager.db.get_room(player.current_room)
                                room_monsters = player_room_data.get("monsters", []) if player_room_data else []
                                if room_monsters:
                                    # Prefer a non-aggressive monster; otherwise use the first alive one
                                    chosen_monster_id = None
                                    for m_id in room_monsters:
                                        m = await game_manager.db.get_monster(m_id)
                                        if m and m.get("is_alive", True) and m.get("aggressiveness") != "aggressive":
                                            chosen_monster_id = m_id
                                            break
                                    if not chosen_monster_id:
                                        # Fallback to any alive monster
                                        for m_id in room_monsters:
                                            m = await game_manager.db.get_monster(m_id)
                                            if m and m.get("is_alive", True):
                                                chosen_monster_id = m_id
                                                break
                                    if chosen_monster_id:
                                        reply = await monster_behavior_manager.generate_monster_dialogue(
                                            chosen_monster_id, chunk.get("original_input", chunk.get("input", "")) or action_request.action, player.current_room, game_manager
                                        )
                                        if reply and not additional_content:
                                            additional_content = reply
                            except Exception as e:
                                logger.error(f"[Stream] Fallback monster reply error: {str(e)}")

                        # Handle item hinting/awarding from AI before yielding final response
                        try:
                            reward_info = chunk.get("reward_item")
                            if reward_info is not None:
                                deserves_item = reward_info.get("deserves_item")
                                item_type_name = reward_info.get("item_type")

                                # Ensure updates scaffolding exists
                                if "updates" not in chunk or not isinstance(chunk["updates"], dict):
                                    chunk["updates"] = {}
                                if "player" not in chunk["updates"] or not isinstance(chunk["updates"].get("player"), dict):
                                    chunk["updates"]["player"] = {}

                                # If AI hinted an item type but not awarding yet → remember it for next action
                                if not deserves_item and item_type_name:
                                    try:
                                        from .templates.item_types import ItemType
                                        item_type_obj = game_manager.item_type_manager.get_item_type_by_name(item_type_name)
                                        player.pending_item_type = item_type_obj.to_dict()
                                        await game_manager.db.set_player(action_request.player_id, player.dict())
                                        logger.info(f"[Item Discovery] Pending item set for player {action_request.player_id}: {item_type_name}")
                                    except Exception as e:
                                        logger.error(f"[Item Discovery] Failed setting pending item type '{item_type_name}': {str(e)}")

                                # If AI says player deserves item → generate and award it
                                if deserves_item:
                                    try:
                                        from .templates.items import GenericItemTemplate
                                        from .templates.item_types import ItemType
                                        import uuid as _uuid

                                        # Resolve item type from reward or pending
                                        item_type_obj = None
                                        if item_type_name:
                                            try:
                                                item_type_obj = game_manager.item_type_manager.get_item_type_by_name(item_type_name)
                                            except Exception:
                                                item_type_obj = None
                                        if not item_type_obj and player.pending_item_type:
                                            try:
                                                item_type_obj = ItemType(
                                                    name=player.pending_item_type['name'],
                                                    description=player.pending_item_type['description'],
                                                    capabilities=player.pending_item_type['capabilities']
                                                )
                                            except Exception:
                                                item_type_obj = None

                                        # Generate item details with AI (fallback to template if needed)
                                        template = GenericItemTemplate(game_manager.item_type_manager)
                                        context = {
                                            'item_type': item_type_obj.name if item_type_obj else item_type_name,
                                            'location': room.title,
                                            'theme': room.biome or 'fantasy'
                                        }
                                        try:
                                            prompt = template.generate_prompt(context)
                                            ai_text = await game_manager.ai_handler.generate_text(prompt)
                                            parsed = template.parse_response(ai_text, context)
                                        except Exception as e:
                                            logger.error(f"[Item Award] AI generation failed: {str(e)}. Using fallback.")
                                            parsed = template.generate_item(context)

                                        rarity = int(parsed.get('rarity', 1))
                                        special_effects = parsed.get('special_effects', 'No special effects')
                                        item_name = parsed.get('name', item_type_name or 'Mysterious Item')

                                        # Build DB item
                                        new_item_id = f"item_{str(_uuid.uuid4())}"
                                        db_item = {
                                            'id': new_item_id,
                                            'name': item_name,
                                            'description': (item_type_obj.description if item_type_obj else (room.description or 'An item')),
                                            'is_takeable': True,
                                            # Top-level fields used by validators
                                            'item_type': (item_type_obj.name if item_type_obj else (item_type_name or 'Unknown')),
                                            'type_capabilities': (item_type_obj.capabilities if item_type_obj else []),
                                            'special_effects': special_effects,
                                            'rarity': rarity,
                                            # Also include properties for client UI
                                            'properties': {
                                                'rarity': str(rarity),
                                                'special_effects': special_effects,
                                                'item_type': (item_type_obj.name if item_type_obj else (item_type_name or 'Unknown')),
                                                'capabilities': ', '.join(item_type_obj.capabilities) if item_type_obj else ''
                                            }
                                        }

                                        await game_manager.db.set_item(new_item_id, db_item)

                                        # Update player inventory and clear pending
                                        updated_inventory = list(player.inventory)
                                        if new_item_id not in updated_inventory:
                                            updated_inventory.append(new_item_id)
                                        player.inventory = updated_inventory
                                        player.pending_item_type = None
                                        await game_manager.db.set_player(action_request.player_id, player.dict())

                                        # Provide updates to client via SSE
                                        chunk["updates"]["player"]["inventory"] = updated_inventory
                                        chunk["updates"]["new_item"] = {
                                            'id': new_item_id,
                                            'name': db_item['name'],
                                            'description': db_item['description'],
                                            'is_takeable': True,
                                            'properties': db_item['properties']
                                        }

                                        # Also notify via WebSocket with a system message
                                        try:
                                            stars = rarity_to_stars(rarity)
                                            await manager.send_to_player(player.current_room, action_request.player_id, {
                                                'type': 'item_obtained',
                                                'player_id': action_request.player_id,
                                                'item_name': db_item['name'],
                                                'item_rarity': rarity,
                                                'rarity_stars': stars,
                                                'message': f"You obtained {db_item['name']} ({stars})",
                                                'timestamp': datetime.now().isoformat()
                                            })
                                        except Exception as e:
                                            logger.error(f"[Item Award] Failed to send WebSocket item_obtained: {str(e)}")

                                        logger.info(f"[Item Award] Player {action_request.player_id} received item {db_item['name']} (rarity {rarity})")
                                    except Exception as e:
                                        logger.error(f"[Item Award] Error awarding item: {str(e)}")
                        except Exception as e:
                            logger.error(f"[Item Handling] Unexpected error: {str(e)}")

                        # NOW yield the final response with updated player data (default path)
                        final_content = chunk["response"] + (f"\n\n{additional_content}" if 'additional_content' in locals() and additional_content else "")
                        yield json.dumps({
                            "type": "final",
                            "content": final_content,
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
                            ai_response=final_content if 'final_content' in locals() else chunk["response"],
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
        
        # Get territorial blocking information
        territorial_info = {}
        if game_manager and hasattr(game_manager, 'monster_behavior_manager'):
            room_id = room_data.get('id', '')
            # Ensure territorial blocks exist; if missing, assign one deterministically
            for monster in monsters_info:
                if monster.get('aggressiveness') == 'territorial':
                    if room_id not in game_manager.monster_behavior_manager.territorial_blocks:
                        game_manager.monster_behavior_manager.territorial_blocks[room_id] = {}
                    current = game_manager.monster_behavior_manager.territorial_blocks[room_id].get(monster['id'])
                    if not current:
                        # Choose a direction to block based on available connections (fallback to first key)
                        connections = room_data.get('connections', {}) or {}
                        blocked_direction = None
                        if connections:
                            # Pick first direction key deterministically
                            blocked_direction = list(connections.keys())[0]
                        else:
                            blocked_direction = 'north'
                        game_manager.monster_behavior_manager.territorial_blocks[room_id][monster['id']] = blocked_direction
                        current = blocked_direction
                    territorial_info[monster['id']] = current
        
        # Build monster context for AI
        monster_context = []
        for monster in monsters_info:
            monster_context_item = {
                'id': monster['id'],
                'name': monster['name'],
                'size': monster['size'],
                'description': monster['description'],
                'aggressiveness': monster['aggressiveness']
            }
            # Add territorial blocking information if available
            if monster['id'] in territorial_info:
                monster_context_item['blocking_direction'] = territorial_info[monster['id']]
            monster_context.append(monster_context_item)
        
        # Generate AI description
        if game_manager and hasattr(game_manager, 'ai_handler'):
            # Build creature details with territorial blocking info
            creature_details = []
            for m in monster_context:
                detail = f"- A {m['size']}-sized creature: {m['description']} (appears {m['aggressiveness']})"
                if 'blocking_direction' in m:
                    detail += f" - BLOCKING {m['blocking_direction'].upper()} EXIT"
                creature_details.append(detail)
            
            prompt = f"""You are describing what a player sees when entering a room with monsters. Write an atmospheric description from the player's perspective, as if observing these creatures from a distance.
 
 IMPORTANT GUIDELINES:
 - Write from the player's perspective ("You see...", "You notice...")
 - Describe what the creatures LOOK like, not their stats or abilities
 - Make it feel like distant observation - mysterious but visual
 - Keep it atmospheric and immersive
 - Don't mention creature names directly
 - Focus on visual appearance and behavior
 - 2-3 sentences maximum
 - CRITICAL: Show their aggressiveness through behavior:
   * AGGRESSIVE monsters: "charging toward you", "rushing in your direction", "advancing menacingly"
   * TERRITORIAL monsters: "guarding the [direction] path", "blocking the [direction] exit", "watching the [direction] passage"
   * PASSIVE monsters: "minding their own business", "peacefully grazing", "ignoring your presence"
   * NEUTRAL monsters: "observing you cautiously", "keeping their distance", "watching you warily"
 - CRITICAL: If a monster is blocking a direction, mention it clearly: "guarding the [direction] exit", "blocking the [direction] path"
 
 Room: {room_title} ({biome})
 Creatures:\n{chr(10).join(creature_details)}
 
 Return only the atmospheric description, no JSON.
 """
 
            description = await game_manager.ai_handler.generate_text(prompt)
            return description.strip()
        
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