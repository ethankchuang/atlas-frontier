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
    Monster,
    NPC,
    Item
)
from .auth_models import (
    RegisterRequest,
    LoginRequest,
    UpdateUsernameRequest,
    AuthResponse,
    UserProfile,
    RegisterResponse,
    GuestConversionRequest,
    AnonymousGuestRequest
)
from .auth_service import AuthService
from .auth_utils import get_current_user, get_optional_current_user, validate_username, is_username_available
from .supabase_client import get_supabase_client
from .game_manager import GameManager
from .config import settings
from .logger import setup_logging
from .api_key_auth import api_key_auth
import os
from .monster_behavior import monster_behavior_manager
from . import combat
from .ai_handler import WORLD_CONFIG
import uuid
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime, timedelta
import asyncio
from .game_manager import GameManager
from .hybrid_database import HybridDatabase as Database
from .logger import setup_logging

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

ALLOW_ANY_COMBAT_MOVE = os.getenv("ALLOW_ANY_COMBAT_MOVE", "false").lower() == "true"


app = FastAPI(title="AI MUD Game Server")

# Configure CORS
allowed_origins = settings.ALLOWED_ORIGINS.split(",") if settings.ALLOWED_ORIGINS else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Add API key authentication middleware
@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    # Check API key before processing request
    api_key_auth(request)
    response = await call_next(request)
    return response

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

    async def send_personal_message(self, message: dict, player_id: str):
        """Send a personal message to a specific player (finds their room automatically)"""
        logger.info(f"[WebSocket] Sending personal message to player {player_id} - message type: {message.get('type')}")
        
        # Find which room the player is in
        for room_id, connections in self.active_connections.items():
            if player_id in connections:
                try:
                    await connections[player_id].send_json(message)
                    logger.debug(f"[WebSocket] Sent personal message to player {player_id} in room {room_id}")
                    return
                except Exception as e:
                    logger.error(f"[WebSocket] Failed to send personal message to player {player_id}: {str(e)}")
                    return
        
        logger.warning(f"[WebSocket] Player {player_id} not found in any active room")

def rarity_to_stars(rarity: int) -> str:
    """Convert rarity number to star representation"""
    return "★" * rarity + "☆" * (4 - rarity)

# Initialize managers
manager = ConnectionManager()
game_manager = GameManager()
game_manager.set_connection_manager(manager)

@app.on_event("startup")
async def startup_event():
    """Server startup initialization"""
    try:
        logger.info("Server startup completed successfully")
    except Exception as e:
        logger.error(f"Error during startup: {str(e)}")
        # Continue starting up even if initialization fails

def get_game_manager():
    return game_manager

# Global duel state tracking
# Use combat module state
duel_moves = combat.duel_moves
duel_pending = combat.duel_pending

async def handle_duel_message(message: dict, room_id: str, player_id: str, game_manager: GameManager):
    """Handle duel-related messages and coordinate AI analysis"""
    global duel_moves, duel_pending
    
    message_type = message.get("type")
    logger.info(f"[handle_duel_message] Processing {message_type} from player {player_id} in room {room_id}")
    
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
                "is_monster_duel": False,
                "history": [],
                "player1_vital": 0,
                "player2_vital": 0,
                "player1_control": 0,
                "player2_control": 0,
                "finishing_window_owner": None
            }
            
            # Create active duel record for disconnect handling
            active_duel_data = {
                "duel_id": duel_id,
                "player1_id": challenger_id,
                "player2_id": target_id,
                "room_id": room_id,
                "current_round": 1,
                "player1_condition": "Healthy",
                "player2_condition": "Healthy",
                "player1_vital": 6,
                "player2_vital": 6,
                "player1_control": 0,
                "player2_control": 0,
                "player1_max_vital": 6,
                "player2_max_vital": 6,
                "start_time": datetime.utcnow().isoformat(),
                "is_active": True
            }
            await game_manager.db.create_active_duel(active_duel_data)
            
            await manager.broadcast_to_room(room_id, {
                "type": "duel_challenge",
                "challenger_id": challenger_id,
                "target_id": target_id,
                "room_id": room_id,
                "timestamp": datetime.now().isoformat()
            })
            logger.info(f"[handle_duel_message] Duel challenge broadcasted from {challenger_id} to {target_id}")
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
        await combat.handle_duel_move(message, room_id, player_id, game_manager)
        return
    
    if message_type == "duel_cancel":
        try:
            duel_id = message.get("duel_id")
            if duel_id and duel_id in duel_pending:
                del duel_pending[duel_id]
            return
        except Exception as e:
            logger.error(f"[handle_duel_message] Error handling duel_cancel: {str(e)}")
            return
    
    if message_type == "duel_outcome":
        try:
            duel_id = message.get("duel_id")
            if duel_id and duel_id in duel_pending:
                del duel_pending[duel_id]
                # Also clean up active duel record
                await game_manager.db.end_active_duel(duel_id)
            return
        except Exception as e:
            logger.error(f"[handle_duel_message] Error handling duel_outcome: {str(e)}")
            return

async def get_room_monsters_description(room_id: str, game_manager: GameManager) -> str:
    """Get a description of AGGRESSIVE monsters in the room for display to players when entering"""
    try:
        room_data = await game_manager.db.get_room(room_id)
        if not room_data or not room_data.get('monsters'):
            return ""
        
        monster_descriptions = []
        for monster_id in room_data['monsters']:
            monster_data = await game_manager.db.get_monster(monster_id)
            if monster_data and monster_data.get('is_alive', True):
                aggressiveness = monster_data['aggressiveness']
                
                # ONLY show aggressive monsters in this function
                # Skip monsters that have the rejoin_safe flag (made non-engaging for rejoining players)
                if aggressiveness == 'aggressive' and not monster_data.get('rejoin_safe', False):
                    name = monster_data['name']
                    size = monster_data['size']
                    
                    # Create concise description focusing on aggression
                    size_desc = {
                        'insect': 'tiny',
                        'chicken': 'small', 
                        'human': 'medium-sized',
                        'horse': 'large',
                        'dinosaur': 'enormous',
                        'colossal': 'massive'
                    }.get(size, 'strange')
                    
                    # Focus on how the monster is approaching/aggressing
                    monster_descriptions.append(f"A {size_desc} {name} charging toward you menacingly")
        
        if monster_descriptions:
            if len(monster_descriptions) == 1:
                return f"⚔️ {monster_descriptions[0]}!"
            else:
                monsters_text = ", ".join(monster_descriptions[:-1]) + f", and {monster_descriptions[-1]}"
                return f"⚔️ {monsters_text}!"
        
        return ""
        
    except Exception as e:
        logger.error(f"Error getting room monsters description: {str(e)}")
        return ""


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
        
        # Ask AI to classify whether the action intends to attack a monster, and which one
        # Retry mechanism for JSON parsing
        max_retries = 3
        for attempt in range(max_retries):
            try:
                monsters_context = [
                    {"id": mid, "name": mdata.get("name", "Unknown Monster")}
                    for (mid, mdata) in monsters_in_room
                ]
                prompt = (
                    f"You are an impartial combat intent classifier for a {WORLD_CONFIG['setting_primary']} {WORLD_CONFIG['setting_secondary']} {WORLD_CONFIG['game_type']}.\n"
                    f"Player action: {json.dumps(action_text)}\n"
                    f"Monsters present: {json.dumps(monsters_context)}\n"
                    "Task: Determine if the player intends to ATTACK any of the listed monsters right now.\n"
                    "Return ONLY strict JSON with keys: is_attack (boolean) and target_monster_id (string|null). "
                    "If an attack is intended but target is ambiguous, pick the most obvious; otherwise null.\n"
                    "Base your judgment on overall intent and semantics, not fixed keywords."
                )
                response = await game_manager.ai_handler.generate_text(prompt)
                logger.info(f"[detect_monster_attack] AI raw response (attempt {attempt + 1}): {response}")
                
                result = json.loads(response)
                is_attack = bool(result.get('is_attack', False))
                target_monster_id = result.get('target_monster_id')
                if is_attack:
                    valid_ids = {mid for (mid, _) in monsters_in_room}
                    if target_monster_id in valid_ids:
                        logger.info(f"[detect_monster_attack] AI classified action as attack on monster {target_monster_id}")
                        return target_monster_id
                    # Fallback if unspecified/ambiguous: choose first alive monster
                    first_id = monsters_in_room[0][0]
                    logger.info(f"[detect_monster_attack] AI classified attack with ambiguous target; defaulting to {first_id}")
                    return first_id
                return None
                
            except json.JSONDecodeError as e:
                logger.warning(f"[detect_monster_attack] JSON parsing failed on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    # Final attempt failed, return None (no attack detected)
                    logger.error(f"[detect_monster_attack] All {max_retries} attempts failed, assuming no attack intended")
                    return None
                else:
                    # Wait a bit before retrying
                    await asyncio.sleep(0.5)
                    continue
                    
            except Exception as e:
                logger.error(f"[detect_monster_attack] Unexpected error on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    # Final attempt failed, return None (no attack detected)
                    logger.error(f"[detect_monster_attack] All {max_retries} attempts failed due to unexpected error, assuming no attack intended")
                    return None
                else:
                    # Wait a bit before retrying
                    await asyncio.sleep(0.5)
                    continue
        
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
        player1_max_vital = 5
        player2_max_vital = await combat.get_monster_max_vital(monster_data)

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
            "is_monster_duel": True,  # Flag for special handling
            "monster_data": monster_data,  # Store monster data for AI move generation
            "history": [],  # Keep last 10 rounds of combat history
            "player1_health": player1_max_vital,  # Start with max health
            "player2_health": player2_max_vital,  # Start with max health
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




async def get_monster_max_vital(monster_data: dict) -> int:
    # Backward compatibility shim; use combat module
    return await combat.get_monster_max_vital(monster_data)


async def analyze_duel_moves(duel_id: str, game_manager: GameManager):
    return await combat.analyze_duel_moves(duel_id, game_manager)


async def analyze_combat_outcome(*args, **kwargs):
    return await combat.analyze_combat_outcome(*args, **kwargs)

async def generate_combat_tags(*args, **kwargs):
    # Deprecated; keep a shim for any stray calls
    return {'player1_new_tags': [], 'player2_new_tags': []}

async def generate_combat_narrative(*args, **kwargs):
    return await combat.generate_combat_narrative(*args, **kwargs)

async def generate_combat_tags_from_narrative(*args, **kwargs):
    # Deprecated; keep a shim for any stray calls
    return {'player1_new_tags': [], 'player2_new_tags': []}


# WebSocket endpoint for real-time updates
@app.websocket("/ws/{room_id}/{player_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, player_id: str):
    logger.info(f"[WebSocket] New connection request from player {player_id} for room {room_id}")
    await manager.connect(websocket, room_id, player_id)
    
    # Ensure player is in the room's player list
    try:
        room_players = await game_manager.db.get_room_players(room_id)
        if player_id not in room_players:
            await game_manager.db.add_to_room_players(room_id, player_id)
            logger.info(f"[WebSocket] Added player {player_id} to room {room_id} player list")
            
            # Get player data and broadcast presence update
            try:
                player_data = await game_manager.db.get_player(player_id)
                if player_data:
                    await manager.broadcast_to_room(
                        room_id=room_id,
                        message={
                            "type": "presence", 
                            "player_id": player_id, 
                            "status": "joined",
                            "player_data": player_data
                        },
                        exclude_player=player_id
                    )
                    logger.info(f"[WebSocket] Broadcasted player join for {player_id}")
            except Exception as e:
                logger.error(f"[WebSocket] Error broadcasting player join: {str(e)}")
    except Exception as e:
        logger.error(f"[WebSocket] Error managing room player list: {str(e)}")
    
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

                # Check for active quest and send storyline if not shown
                try:
                    player_data = await game_manager.db.get_player(player_id)
                    if player_data and player_data.get('active_quest_id'):
                        from .quest_manager import QuestManager
                        quest_manager = QuestManager(game_manager.db)

                        player_quest = await quest_manager._get_player_quest(
                            player_id,
                            player_data['active_quest_id']
                        )

                        if player_quest and not player_quest.get('storyline_shown', False):
                            # Send storyline in chunks for typewriter effect
                            chunks = await quest_manager.get_storyline_chunks(
                                player_data['active_quest_id'],
                                chunk_size=80
                            )

                            for chunk in chunks:
                                await websocket.send_json({
                                    'type': 'quest_storyline',
                                    'message': chunk
                                })
                                await asyncio.sleep(0.3)  # Delay between chunks for typewriter effect

                            # Mark storyline as shown
                            player_quest['storyline_shown'] = True
                            await quest_manager._save_player_quest(player_quest)
                            logger.info(f"[Quest] Sent storyline for quest {player_data['active_quest_id']} to player {player_id}")
                except Exception as e:
                    logger.error(f"[Quest] Error sending quest storyline: {str(e)}")

                # Aggressive monster descriptions are now included in atmospheric_presence via room info
            except Exception as e:
                logger.error(f"[WebSocket] Error preparing room state: {str(e)}")
                logger.error(f"[WebSocket] Room data: {room_data}")
        else:
            logger.warning(f"[WebSocket] Room {room_id} not found when sending initial state")

        while True:
            data = await websocket.receive_text()
            logger.debug(f"[WebSocket] Received message from player {player_id}: {data[:100]}...")
            
            # Retry mechanism for JSON parsing
            max_retries = 3
            message = None
            for attempt in range(max_retries):
                try:
                    message = json.loads(data)
                    break  # Success, exit retry loop
                except json.JSONDecodeError as e:
                    logger.warning(f"[WebSocket] JSON parsing failed on attempt {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:
                        # Final attempt failed, send error message to client
                        logger.error(f"[WebSocket] All {max_retries} attempts failed, sending error to client")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Invalid message format. Please try again.",
                            "timestamp": datetime.now().isoformat()
                        })
                        continue  # Continue to next message
                    else:
                        # Wait a bit before retrying
                        await asyncio.sleep(0.1)
                        continue
                except Exception as e:
                    logger.error(f"[WebSocket] Unexpected error parsing message on attempt {attempt + 1}: {str(e)}")
                    if attempt == max_retries - 1:
                        # Final attempt failed, send error message to client
                        logger.error(f"[WebSocket] All {max_retries} attempts failed due to unexpected error, sending error to client")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Message processing error. Please try again.",
                            "timestamp": datetime.now().isoformat()
                        })
                        continue  # Continue to next message
                    else:
                        # Wait a bit before retrying
                        await asyncio.sleep(0.1)
                        continue
            
            # Skip processing if message parsing failed
            if message is None:
                continue

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
        
        # Handle duel forfeit on disconnect
        await handle_player_disconnect(player_id, room_id)
        
        # Remove player from room's player list in database
        try:
            await game_manager.db.remove_from_room_players(room_id, player_id)
            logger.info(f"[WebSocket] Removed player {player_id} from room {room_id} player list")
        except Exception as e:
            logger.error(f"[WebSocket] Error removing player from room list: {str(e)}")
        
        manager.disconnect(room_id, player_id)
        await manager.broadcast_to_room(
            room_id=room_id,
            message={"type": "presence", "player_id": player_id, "status": "disconnected"}
        )
    except Exception as e:
        logger.error(f"[WebSocket] Error in connection: {str(e)}")
        manager.disconnect(room_id, player_id)

# ===============================
# Duel Forfeit Handler
# ===============================

async def handle_player_disconnect(player_id: str, room_id: str):
    """Handle player disconnect, including duel forfeit logic"""
    try:
        # Check if player is in any active duels
        active_duels = await game_manager.db.get_active_duels_for_player(player_id)
        
        for duel in active_duels:
            if duel.get('is_active', False):
                logger.info(f"[Duel Forfeit] Player {player_id} disconnected during active duel {duel.get('duel_id')}")
                
                # Determine the opponent
                opponent_id = duel.get('player2_id') if duel.get('player1_id') == player_id else duel.get('player1_id')
                opponent_name = "Unknown"
                
                # Get opponent name
                try:
                    opponent_data = await game_manager.db.get_player(opponent_id)
                    if opponent_data:
                        opponent_name = opponent_data.get('name', 'Unknown')
                except Exception as e:
                    logger.warning(f"[Duel Forfeit] Could not get opponent name: {str(e)}")
                
                # End the duel
                await game_manager.db.end_active_duel(duel.get('duel_id'))
                
                # Send forfeit message to opponent
                try:
                    await manager.send_personal_message(
                        player_id=opponent_id,
                        room_id=duel.get('room_id', room_id),
                        message={
                            "type": "duel_forfeit",
                            "message": f"{player_id} has forfeited the duel by disconnecting. You win!",
                            "opponent_name": player_id,
                            "result": "forfeit_win"
                        }
                    )
                    logger.info(f"[Duel Forfeit] Sent forfeit notification to opponent {opponent_id}")
                except Exception as e:
                    logger.error(f"[Duel Forfeit] Failed to notify opponent: {str(e)}")
                
                # Broadcast to room that duel ended
                try:
                    await manager.broadcast_to_room(
                        room_id=duel.get('room_id', room_id),
                        message={
                            "type": "duel_ended",
                            "message": f"Duel ended - {player_id} forfeited by disconnecting",
                            "result": "forfeit",
                            "winner": opponent_id,
                            "loser": player_id
                        }
                    )
                    logger.info(f"[Duel Forfeit] Broadcasted duel end to room {duel.get('room_id', room_id)}")
                except Exception as e:
                    logger.error(f"[Duel Forfeit] Failed to broadcast duel end: {str(e)}")
                
                logger.info(f"[Duel Forfeit] Successfully processed forfeit for duel {duel.get('duel_id')}")
        
        if not active_duels:
            logger.info(f"[Duel Forfeit] Player {player_id} had no active duels")
            
    except Exception as e:
        logger.error(f"[Duel Forfeit] Error handling player disconnect: {str(e)}")

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

@app.post("/auth/guest")
async def create_guest_player(
    request: AnonymousGuestRequest,
    game_manager: GameManager = Depends(get_game_manager)
):
    """Create or retrieve a guest player for anonymous Supabase user (idempotent)"""
    try:
        # Use the anonymous user ID from Supabase
        anonymous_user_id = request.anonymous_user_id
        guest_player_id = f"guest_{anonymous_user_id}"

        # Check if guest player already exists
        existing_player = await game_manager.db.get_player(guest_player_id)
        if existing_player:
            logger.info(f"Guest player {guest_player_id} already exists, returning existing player")
            return {
                'player': Player(**existing_player),
                'message': 'Existing guest player retrieved successfully'
            }
        
        # Get starting room
        starting_room = await game_manager.ensure_starting_room()

        # Create user profile in Supabase for guest user (if it doesn't exist)
        try:
            from .supabase_client import get_supabase_client
            client = get_supabase_client()

            # Check if profile exists
            profile_check = client.table('user_profiles').select('id').eq('id', anonymous_user_id).execute()

            if not profile_check.data or len(profile_check.data) == 0:
                # Create the user profile (guests have username starting with "Anon_")
                # Use a placeholder email for guest users
                client.table('user_profiles').insert({
                    'id': anonymous_user_id,
                    'username': f"Anon_{anonymous_user_id[:6]}",
                    'email': f"guest_{anonymous_user_id[:6]}@anonymous.local"
                }).execute()
                logger.info(f"[create_guest_player] Created user profile for guest user {anonymous_user_id}")
        except Exception as profile_err:
            logger.error(f"[create_guest_player] Failed to create user profile: {profile_err}")
            # Continue anyway - will fall back to Redis

        # Create new guest player with anonymous user ID
        player = Player(
            id=guest_player_id,
            user_id=anonymous_user_id,  # Use the Supabase anonymous user ID
            name=f"Anon_{anonymous_user_id[:6]}",
            current_room=starting_room.id,
            inventory=[],
            quest_progress={},
            memory_log=[],
            last_action=None,
            last_action_text=None
        )

        # Save the guest player
        await game_manager.db.set_player(guest_player_id, player.dict())

        # Add player to the starting room's player list
        await game_manager.db.add_to_room_players(starting_room.id, guest_player_id)

        # Assign tutorial quest to new guest player
        try:
            from app.quest_manager import QuestManager
            quest_manager = QuestManager(game_manager.db)
            quest_result = await quest_manager.assign_tutorial_quest(guest_player_id)

            if quest_result:
                logger.info(f"[Quest] Assigned tutorial quest to new guest player {guest_player_id}")

                # Spawn quest items if quest has spawn config
                quest_data = quest_result.get('quest')
                if quest_data and quest_data.get('spawn_config'):
                    await game_manager.spawn_quest_items(guest_player_id, starting_room.id, quest_data['spawn_config'])
            else:
                logger.warning(f"[Quest] Failed to assign tutorial quest to guest player {guest_player_id}")
        except Exception as e:
            logger.error(f"[Quest] Error assigning tutorial quest to guest player: {str(e)}")
            # Don't fail player creation if quest assignment fails

        logger.info(f"Created new guest player {guest_player_id}")
        return {
            'player': player,
            'message': 'Anonymous guest player created successfully'
        }
    except Exception as e:
        logger.error(f"Error creating guest player: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create guest player"
        )

@app.post("/join/guest/{player_id}")
async def join_game_as_guest(
    player_id: str,
    game_manager: GameManager = Depends(get_game_manager)
):
    """Join game as a guest player (no authentication required)"""
    try:
        # Verify this is a guest player
        if not player_id.startswith('guest_'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This endpoint is only for guest players"
            )
        
        # Get the player
        player = await game_manager.get_player(player_id)
        if not player:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guest player not found"
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
            
            logger.info(f"Placed guest player {player.name} in starting room {starting_room.id}")
            
            return {
                'message': f'Welcome to the game, {player.name}!',
                'player': player,
                'room': starting_room
            }
        else:
            # Player already in game - return their current state without moving them
            # Give player temporary immunity to ALL aggressive monsters when rejoining
            player.rejoin_immunity = True
            await game_manager.db.set_player(player_id, player.dict())
            logger.info(f"[Join Game] Guest player {player_id} granted rejoin immunity to aggressive monsters")
            
            room_data = await game_manager.db.get_room(player.current_room)
            if room_data:
                room = Room(**room_data)
                
                # If there are aggressive monsters in the room, make them non-engaging
                if room.monsters:
                    for monster_id in room.monsters:
                        try:
                            monster_data = await game_manager.db.get_monster(monster_id)
                            if monster_data and monster_data.get('aggressiveness') == 'aggressive':
                                # Temporarily make the monster non-aggressive for this player's session
                                monster_data['aggressiveness'] = 'neutral'
                                monster_data['rejoin_safe'] = True
                                await game_manager.db.set_monster(monster_id, monster_data)
                                logger.info(f"[Join Game] Made aggressive monster {monster_id} non-engaging for rejoining guest player {player_id}")
                        except Exception as e:
                            logger.warning(f"[Join Game] Error updating monster {monster_id}: {str(e)}")
            
            # Return current state without moving player
            room = Room(**room_data) if room_data else None
            
            return {
                'message': f'Welcome back, {player.name}!',
                'player': player,
                'room': room
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error joining game as guest {player_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to join game as guest"
        )

@app.post("/auth/guest-to-user")
async def convert_guest_to_user(
    request: GuestConversionRequest,
    game_manager: GameManager = Depends(get_game_manager)
):
    """Convert an anonymous guest player to a registered user, preserving player data"""
    try:
        # Validate username format
        if not validate_username(request.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username must be 3-20 characters, start with a letter, and contain only letters and numbers"
            )
        
        # Check if username is available (case insensitive)
        if not await is_username_available(request.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username is already taken"
            )
        
        # Get the guest player data
        guest_player_data = await game_manager.db.get_player(request.guest_player_id)
        
        if not guest_player_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Guest player not found"
            )
        
        # Update the existing guest user profile in Supabase with real username and email
        # The guest already has a profile created when they first connected
        supabase = get_supabase_client()
        guest_user_id = guest_player_data['user_id']

        # Update the existing guest profile with real credentials
        profile_result = supabase.table('user_profiles').update({
            'username': request.username.lower(),  # Store as lowercase for consistency
            'email': request.email
        }).eq('id', guest_user_id).execute()

        if not profile_result.data:
            logger.error(f"Failed to update user profile for guest {guest_user_id}: {profile_result}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user profile"
            )

        # Note: We keep the same user_id - no need to update it since we're updating the existing profile
        guest_player_data['name'] = request.username  # Update player name to match username
        
        # Save the updated player
        await game_manager.db.set_player(request.guest_player_id, guest_player_data)
        
        logger.info(f"Successfully converted guest player {request.guest_player_id} to user {request.username}")

        return {
            'user_id': guest_user_id,
            'username': request.username,
            'email': request.email,
            'guest_converted': True,
            'message': 'Anonymous guest account converted to registered user successfully'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error converting guest to user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to convert guest to user"
        )

@app.get("/players")
async def get_user_players(
    current_user: Dict[str, Any] = Depends(get_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Get all players for the current user"""
    try:
        # Use the hybrid database to get players for this user
        players_data = await game_manager.db.get_players_for_user(current_user['id'])
        return {'players': players_data}
    except Exception as e:
        logger.error(f"Error getting players for user {current_user['id']}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get players"
        )

@app.post("/players")
async def create_new_player(
    request: CreatePlayerRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Create a new player for the current user"""
    try:
        player = await game_manager.create_player(request.name, current_user['id'])
        return {'player': player}
    except Exception as e:
        logger.error(f"Error creating player for user {current_user['id']}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create player"
        )

@app.get("/auth/profile", response_model=UserProfile)
async def get_user_profile(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get current user's profile"""
    return {
        'id': current_user['id'],
        'username': current_user['username'],
        'email': current_user['email'],
        'is_anonymous': current_user.get('is_anonymous', False)
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

@app.get("/test-cors")
async def test_cors():
    return {"status": "cors_working", "message": "CORS is working"}

@app.get("/debug/duel-state")
async def debug_duel_state():
    """Debug endpoint to check duel state"""
    global duel_pending
    return {
        "duel_pending": duel_pending,
        "duel_pending_count": len(duel_pending)
    }

# Game initialization endpoint (admin only - creates world)
@app.post("/start")
async def start_game(game_manager: GameManager = Depends(get_game_manager)):
    game_state = await game_manager.initialize_game()
    return game_state

# Join game endpoint (requires auth - places specified player in starting room)
@app.post("/join/{player_id}")
async def join_game(
    player_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Place the authenticated user's specified player in the game world"""
    # Get the player and verify ownership
    player = await game_manager.get_player(player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )
    
    # Verify the player belongs to the current user
    if player.user_id != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only join the game with your own players"
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
        # Player already in game - return their current state without moving them
        # No teleportation for any reason - players always stay where they are
        
        # Give player temporary immunity to ALL aggressive monsters when rejoining
        player.rejoin_immunity = True
        await game_manager.db.set_player(player_id, player.dict())
        logger.info(f"[Join Game] Player {player_id} granted rejoin immunity to aggressive monsters")
        
        room_data = await game_manager.db.get_room(player.current_room)
        if room_data:
            room = Room(**room_data)
            
            # If there are aggressive monsters in the room, make them non-engaging
            if room.monsters:
                for monster_id in room.monsters:
                    try:
                        monster_data = await game_manager.db.get_monster(monster_id)
                        if monster_data and monster_data.get('aggressiveness') == 'aggressive':
                            # Temporarily make the monster non-aggressive for this player's session
                            # This prevents engagement without moving the player
                            monster_data['aggressiveness'] = 'neutral'
                            monster_data['rejoin_safe'] = True  # Flag to indicate this is a rejoin safety measure
                            await game_manager.db.set_monster(monster_id, monster_data)
                            logger.info(f"[Join Game] Made aggressive monster {monster_id} non-engaging for rejoining player {player_id}")
                    except Exception as e:
                        logger.warning(f"[Join Game] Error updating monster {monster_id}: {str(e)}")
        
        # Return current state without moving player
        room = Room(**room_data) if room_data else None
        
        return {
            'message': f'Welcome back, {player.name}!',
            'player': player,
            'room': room
        }

# Get player inventory items endpoint (requires auth)
@app.get("/player/{player_id}/inventory")
async def get_player_inventory(
    player_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Get player's inventory items with full item data"""
    # Get the player and verify ownership
    player = await game_manager.get_player(player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )
    
    # Verify the player belongs to the current user (skip for anonymous users)
    if not current_user or player.user_id != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own player's inventory"
        )
    
    # Load inventory items
    inventory_items = []
    for item_id in player.inventory:
        try:
            item_data = await game_manager.db.get_item(item_id)
            if item_data:
                inventory_items.append(item_data)
            else:
                logger.warning(f"[Player Inventory] Item {item_id} not found for player {player_id}")
        except Exception as e:
            logger.error(f"[Player Inventory] Error loading item {item_id}: {str(e)}")
    
    logger.info(f"[Player Inventory] Loaded {len(inventory_items)} items for player {player_id}")
    return {"items": inventory_items}

# Drop item from player inventory endpoint (requires auth)
@app.post("/player/{player_id}/drop-item")
async def drop_player_item(
    player_id: str,
    request: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Drop an item from player's inventory"""
    # Extract parameters from request body
    item_id = request.get('item_id')
    drop_to_room = request.get('drop_to_room', True)
    
    if not item_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="item_id is required"
        )
    
    # Get the player and verify ownership
    player = await game_manager.get_player(player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )
    
    # Verify the player belongs to the current user
    if player.user_id != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only drop items from your own player's inventory"
        )
    
    # Call the drop_item function
    result = await game_manager.drop_item(player_id, item_id, drop_to_room)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    logger.info(f"[Drop Item] Player {player_id} dropped item {item_id} (drop_to_room: {drop_to_room})")
    return result

# Combine items from player inventory endpoint (requires auth)
@app.post("/player/{player_id}/combine-items")
async def combine_player_items(
    player_id: str,
    request: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Combine multiple items from player's inventory to create a new item"""
    # Extract parameters from request body
    item_ids = request.get('item_ids', [])
    combination_description = request.get('combination_description', '')
    
    if not item_ids or len(item_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 items are required for combination"
        )
    
    # Get the player and verify ownership
    player = await game_manager.get_player(player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )
    
    # Verify the player belongs to the current user
    if player.user_id != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only combine items from your own player's inventory"
        )
    
    # Call the combine_items function
    result = await game_manager.combine_items(player_id, item_ids, combination_description)
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    logger.info(f"[Combine Items] Player {player_id} combined {len(item_ids)} items")
    return result

# ============================================
# QUEST SYSTEM ENDPOINTS
# ============================================

@app.get("/player/{player_id}/quest-status")
async def get_player_quest_status(
    player_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Get player's current active quest status"""
    from .quest_manager import QuestManager

    # Get the player and verify ownership
    player = await game_manager.get_player(player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )

    # Verify ownership (skip for anonymous users)
    if not current_user or player.user_id != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own player's quest data"
        )

    quest_manager = QuestManager(game_manager.db)
    quest_status = await quest_manager.get_player_quest_status(player_id)

    return quest_status if quest_status else {"quest": None}

@app.get("/player/{player_id}/quest-log")
async def get_player_quest_log(
    player_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Get player's quest log (current and completed quests)"""
    from .quest_manager import QuestManager

    # Get the player and verify ownership
    player = await game_manager.get_player(player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )

    # Verify ownership (skip for anonymous users)
    if not current_user or player.user_id != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own player's quest log"
        )

    quest_manager = QuestManager(game_manager.db)
    quest_log = await quest_manager.get_player_quest_log(player_id)

    return quest_log

@app.get("/player/{player_id}/badges")
async def get_player_badges(
    player_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Get player's earned badges"""
    from .quest_manager import QuestManager

    # Get the player and verify ownership
    player = await game_manager.get_player(player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )

    # Verify ownership (skip for anonymous users)
    if not current_user or player.user_id != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own player's badges"
        )

    quest_manager = QuestManager(game_manager.db)
    badges = await quest_manager.get_player_badges(player_id)

    return {"badges": badges}

# Get player visited coordinates endpoint (requires auth)
@app.get("/player/{player_id}/visited-coordinates")
async def get_player_visited_coordinates(
    player_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Get player's visited coordinates and minimap state"""
    # Get the player and verify ownership
    player = await game_manager.get_player(player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )
    
    # Verify the player belongs to the current user (skip for anonymous users)
    if not current_user or player.user_id != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own player's data"
        )
    
    logger.info(f"[Player Coordinates] Retrieved {len(player.visited_coordinates)} visited coordinates for player {player_id}")
    logger.info(f"[Player Coordinates] Visited biomes: {player.visited_biomes}")
    logger.info(f"[Player Coordinates] Biome colors: {player.biome_colors}")
    return {
        "visited_coordinates": player.visited_coordinates,
        "visited_biomes": player.visited_biomes,
        "biome_colors": player.biome_colors
    }

# Update player visited coordinates endpoint (requires auth)
@app.post("/player/{player_id}/visit-coordinate")
async def mark_coordinate_visited(
    player_id: str,
    coordinate_data: dict,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Mark a coordinate as visited for a player"""
    # Get the player and verify ownership
    player = await game_manager.get_player(player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )
    
    # Verify the player belongs to the current user (skip for anonymous users)
    if not current_user or player.user_id != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own player's data"
        )
    
    x = coordinate_data.get('x')
    y = coordinate_data.get('y')
    biome = coordinate_data.get('biome')
    biome_color = coordinate_data.get('biome_color')
    
    if x is None or y is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="x and y coordinates are required"
        )
    
    coord_key = f"{x},{y}"
    
    # Update player's visited coordinates
    if coord_key not in player.visited_coordinates:
        player.visited_coordinates.append(coord_key)
    
    if biome:
        player.visited_biomes[coord_key] = biome
        logger.info(f"[Player Coordinates] Saved biome '{biome}' for coordinate ({x},{y})")
    
    if biome_color and biome:
        player.biome_colors[biome] = biome_color
        logger.info(f"[Player Coordinates] Saved biome color '{biome_color}' for biome '{biome}'")
    
    # Save updated player data
    await game_manager.db.set_player(player_id, player.dict())
    
    logger.info(f"[Player Coordinates] Marked coordinate ({x},{y}) as visited for player {player_id}")
    logger.info(f"[Player Coordinates] Current visited_biomes: {player.visited_biomes}")
    logger.info(f"[Player Coordinates] Current biome_colors: {player.biome_colors}")
    return {"success": True, "message": f"Coordinate ({x},{y}) marked as visited"}

# Clear combat state endpoint (requires auth)
@app.post("/player/{player_id}/clear-combat-state")
async def clear_combat_state(
    player_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Clear any active combat state for a player (used when rejoining)"""
    logger.info(f"[Clear Combat] Clearing combat state for player {player_id}")
    
    try:
        # Get the player and verify ownership
        player = await game_manager.get_player(player_id)
        if not player:
            logger.warning(f"[Clear Combat] Player {player_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Player not found"
            )
        
        # Verify the player belongs to the current user (skip for anonymous users)
        if not current_user or player.user_id != current_user['id']:
            logger.warning(f"[Clear Combat] Player {player_id} does not belong to user {current_user['id']}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only clear your own player's combat state"
            )
        
        # Clear from global duel_pending dictionary
        global duel_pending
        cleared_pending_duels = 0
        duels_to_remove = []
        
        for duel_id, duel_info in duel_pending.items():
            if (player_id == duel_info.get('player1_id') or 
                player_id == duel_info.get('player2_id')):
                logger.info(f"[Clear Combat] Removing player {player_id} from duel_pending duel {duel_id}")
                duels_to_remove.append(duel_id)
                cleared_pending_duels += 1
        
        # Remove duels from pending
        for duel_id in duels_to_remove:
            del duel_pending[duel_id]
        
        # Clear from global duel_moves dictionary
        global duel_moves
        cleared_moves = 0
        
        for duel_id, moves in duel_moves.items():
            if player_id in moves:
                logger.info(f"[Clear Combat] Removing player {player_id} moves from duel {duel_id}")
                del moves[player_id]
                cleared_moves += 1
                # If no moves left, remove the entire duel
                if not moves:
                    del duel_moves[duel_id]
        
        # Clear any monster combat history
        try:
            from .monster_behavior import monster_behavior_manager
            monster_behavior_manager._clear_player_combat_history(player_id)
            logger.info(f"[Clear Combat] Cleared monster combat history for player {player_id}")
        except Exception as e:
            logger.warning(f"[Clear Combat] Failed to clear monster combat history: {str(e)}")
        
        logger.info(f"[Clear Combat] Cleared {cleared_moves} duel moves and {cleared_pending_duels} pending duels for player {player_id}")
        return {
            "success": True, 
            "message": f"Cleared {cleared_moves} duel moves and {cleared_pending_duels} pending duels",
            "cleared_moves": cleared_moves,
            "cleared_pending_duels": cleared_pending_duels
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Clear Combat] Unexpected error clearing combat state for player {player_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear combat state"
        )

# Get player messages endpoint (requires auth)
@app.get("/player/{player_id}/messages")
async def get_player_messages(
    player_id: str,
    limit: int = 10,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Get recent messages for a specific player"""
    # Verify the player belongs to the current user
    player = await game_manager.get_player(player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )
    
    if not current_user or player.user_id != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own player's messages"
        )
    
    try:
        logger.info(f"[Player Messages] Fetching messages for player {player_id} with limit {limit}")
        messages = await game_manager.db.get_player_messages(player_id, limit)
        logger.info(f"[Player Messages] Retrieved {len(messages)} messages for player {player_id}")
        for i, msg in enumerate(messages):
            logger.info(f"[Player Messages] Message {i+1}: {msg.get('message', 'No message')[:50]}... (type: {msg.get('message_type', 'unknown')})")
        return {"messages": messages}
    except Exception as e:
        logger.error(f"[Player Messages] Error fetching messages for player {player_id}: {str(e)}")
        import traceback
        logger.error(f"[Player Messages] Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=str(e))

# Get specific player endpoint (requires auth)
@app.get("/player/{player_id}")
async def get_player_by_id(
    player_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    """Get a specific player (must belong to current user; guests allowed)"""
    player = await game_manager.get_player(player_id)
    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found"
        )
    
    # Verify the player belongs to the current user (skip for anonymous users)
    if not current_user or player.user_id != current_user['id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own players"
        )
    
    return player

# Action endpoint with streaming support (requires auth)
@app.post("/action/stream")
async def process_action_stream(
    action_request: ActionRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_current_user),
    game_manager: GameManager = Depends(get_game_manager)
):
    import time
    request_start = time.time()
    logger.info(f"⏱️ [TIMING] Action request received: {action_request.action[:50]}...")

    # Validate that the user owns this player (skip for guest players)
    player = await game_manager.get_player(action_request.player_id)
    if not player or (not current_user or player.user_id != current_user['id']):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only perform actions for your own player"
        )

    logger.info(f"⏱️ [TIMING] Player validation: {(time.time() - request_start)*1000:.2f}ms")

    async def event_generator():
        try:
            generator_start = time.time()
            # Check if player is in a duel - but also check if the duel is actually active
            for duel_id, duel_info in duel_pending.items():
                if (action_request.player_id == duel_info['player1_id'] or 
                    action_request.player_id == duel_info['player2_id']):
                    # Check if this is an active duel (not completed)
                    if duel_info.get('is_active', True):  # Default to True for backwards compatibility
                        logger.info(f"[Action Stream] Player {action_request.player_id} is in active duel {duel_id}")
                        # Player is in a duel - don't process normal actions
                        yield json.dumps({
                            "type": "final",
                            "content": "⚔️ You are in a duel! Use the chat input to submit your combat move.",
                            "updates": {}
                        })
                        return
                    else:
                        logger.info(f"[Action Stream] Player {action_request.player_id} was in completed duel {duel_id}, clearing from duel_pending")
                        # Remove completed duel from pending
                        del duel_pending[duel_id]

            # Get initial state
            db_start = time.time()
            player_data = await game_manager.db.get_player(action_request.player_id)
            logger.info(f"⏱️ [TIMING] Get player data: {(time.time() - db_start)*1000:.2f}ms")
            if not player_data:
                yield json.dumps({"error": "Player not found"})
                return

            # Clear rejoin immunity when player takes an action
            if player_data.get('rejoin_immunity', False):
                logger.info(f"[Action Stream] Clearing rejoin immunity for player {action_request.player_id}")
                player_data['rejoin_immunity'] = False
                await game_manager.db.set_player(action_request.player_id, player_data)
                
                # Also clear rejoin_safe flags from monsters in the room
                room_data = await game_manager.db.get_room(player_data.get('current_room', ''))
                if room_data and room_data.get('monsters'):
                    for monster_id in room_data.get('monsters', []):
                        try:
                            monster_data = await game_manager.db.get_monster(monster_id)
                            if monster_data and monster_data.get('rejoin_safe', False):
                                monster_data['rejoin_safe'] = False
                                # Restore original aggressiveness if it was changed
                                if monster_data.get('aggressiveness') == 'neutral':
                                    monster_data['aggressiveness'] = 'aggressive'
                                await game_manager.db.set_monster(monster_id, monster_data)
                                logger.info(f"[Action Stream] Cleared rejoin_safe flag for monster {monster_id}")
                        except Exception as e:
                            logger.warning(f"[Action Stream] Error clearing monster {monster_id} rejoin_safe flag: {str(e)}")

            player = Player(**player_data)

            db_start = time.time()
            logger.info(f"[Stream] Looking for room: {player.current_room}")
            try:
                room_data = await game_manager.db.get_room(player.current_room)
                logger.info(f"⏱️ [TIMING] Get room data: {(time.time() - db_start)*1000:.2f}ms")
                if not room_data:
                    logger.error(f"[Stream] Room not found: {player.current_room}")
                    yield json.dumps({"error": "Room not found"})
                    return
            except Exception as e:
                logger.error(f"[Stream] Error getting room {player.current_room}: {str(e)}")
                yield json.dumps({"error": f"Database error: {str(e)}"})
                return

            room = Room(**room_data)

            db_start = time.time()
            game_state_data = await game_manager.db.get_game_state()
            logger.info(f"⏱️ [TIMING] Get game state: {(time.time() - db_start)*1000:.2f}ms")
            game_state = GameState(**game_state_data)

            # Store the player's action as a message
            try:
                from .models import ChatMessage
                from datetime import datetime as dt
                action_message = ChatMessage(
                    player_id=action_request.player_id,
                    room_id=player.current_room,
                    message=f">> {action_request.action}",
                    message_type="system",
                    timestamp=dt.utcnow()
                )
                logger.info(f"[Stream] Attempting to store player action: {action_request.action} for player {action_request.player_id}")
                result = await game_manager.db.store_player_message(action_request.player_id, action_message)
                logger.info(f"[Stream] Player action storage result: {result}")
            except Exception as e:
                logger.error(f"[Stream] Failed to store player action as message: {str(e)}")
                import traceback
                logger.error(f"[Stream] Traceback: {traceback.format_exc()}")

            # Get NPCs in the room
            db_start = time.time()
            npcs = []
            for npc_id in room.npcs:
                npc_data = await game_manager.db.get_npc(npc_id)
                if npc_data:
                    npcs.append(NPC(**npc_data))
            logger.info(f"⏱️ [TIMING] Get {len(npcs)} NPCs: {(time.time() - db_start)*1000:.2f}ms")

            # Get monster details for AI context
            db_start = time.time()
            monsters = []
            for monster_id in room.monsters:
                monster_data = await game_manager.db.get_monster(monster_id)
                if monster_data:
                    monsters.append(monster_data)
            logger.info(f"⏱️ [TIMING] Get {len(monsters)} monsters: {(time.time() - db_start)*1000:.2f}ms")

            # Fetch last 10 chat messages for this room (newest-first)
            db_start = time.time()
            try:
                recent_chat = await game_manager.db.get_chat_history(room_id=room.id, limit=10)
            except Exception as e:
                logger.warning(f"[Stream] Failed to fetch recent chat for room {room.id}: {str(e)}")
                recent_chat = []
            logger.info(f"⏱️ [TIMING] Get chat history: {(time.time() - db_start)*1000:.2f}ms")

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
            logger.info(f"⏱️ [TIMING] Data loading complete: {(time.time() - generator_start)*1000:.2f}ms")

            # AI will determine item discovery and rewards based on context using the unified system

            # Use AI processing for all actions (including movement)
            logger.info(f"[Stream] AI context includes {len(monsters)} monsters: {[m.get('name', 'Unknown') for m in monsters]}")
            ai_start = time.time()
            first_chunk_time = None
            chunk_count = 0
            last_chunk_time = None
            async for chunk in game_manager.ai_handler.stream_action(
                action=action_request.action,
                player=player,
                room=room,
                game_state=game_state,
                npcs=npcs,
                monsters=monsters,
                chat_history=recent_chat
            ):
                chunk_start = time.time()
                chunk_count += 1
                
                if first_chunk_time is None:
                    first_chunk_time = time.time()
                    logger.info(f"⏱️ [TIMING] First AI chunk received: {(first_chunk_time - ai_start)*1000:.2f}ms")
                else:
                    if last_chunk_time:
                        time_since_last = (chunk_start - last_chunk_time) * 1000
                        logger.info(f"⏱️ [TIMING] Time between chunks {chunk_count-1} and {chunk_count}: {time_since_last:.2f}ms")
                
                last_chunk_time = chunk_start

                if isinstance(chunk, dict):
                    # Ensure chunk has the expected structure
                    if "updates" not in chunk:
                        logger.warning(f"[Stream] Chunk missing 'updates' field: {chunk}")
                        chunk["updates"] = {}

                    # OPTIMIZATION: Handle room_data chunks - skip for now, we'll send after movement processing
                    if chunk.get("type") == "room_data":
                        logger.info(f"⏱️ [TIMING] Room data chunk received at {(time.time() - request_start)*1000:.2f}ms - will process after movement")
                        # Don't send yet - movement logic needs to run first to get correct room ID
                        # Continue to process the final chunk which will handle everything
                        continue

                    # Store the AI response as a message
                    if chunk.get("type") == "final" and "response" in chunk:
                        try:
                            from .models import ChatMessage
                            from datetime import datetime as dt
                            ai_response_message = ChatMessage(
                                player_id=action_request.player_id,
                                room_id=player.current_room,
                                message=chunk["response"],
                                message_type="ai_response",
                                timestamp=dt.utcnow(),
                                is_ai_response=True
                            )
                            logger.info(f"[Stream] Attempting to store AI response for player {action_request.player_id}")
                            result = await game_manager.db.store_player_message(action_request.player_id, ai_response_message)
                            logger.info(f"[Stream] AI response storage result: {result}")
                        except Exception as e:
                            logger.error(f"[Stream] Failed to store AI response as message: {str(e)}")
                            import traceback
                            logger.error(f"[Stream] Traceback: {traceback.format_exc()}")

                    # Apply updates BEFORE yielding the final response
                    if "player" in chunk["updates"]:
                        player_updates = chunk["updates"]["player"]
                        if "direction" in player_updates:
                            movement_start = time.time()
                            direction = player_updates["direction"]

                            # Skip movement processing if direction is None (non-movement actions)
                            if direction is None:
                                logger.info(f"[Stream] Player direction is None, skipping movement processing")
                            else:
                                logger.info(f"[Stream] Player attempting to move {direction} from {player.current_room}")
                                logger.info(f"⏱️ [TIMING] Starting movement processing")

                                # Structured movement blocking: compute retreat and check monsters
                                room_data_current = await game_manager.db.get_room(player.current_room)
                                connections_raw = room_data_current.get('connections', {}) if room_data_current else {}
                                # Normalize connection keys to lowercase strings (handle Enum keys)
                                connections = {}
                                try:
                                    for k, v in connections_raw.items():
                                        key = getattr(k, 'value', k)
                                        if isinstance(key, str):
                                            connections[key.lower()] = v
                                except Exception:
                                    connections = {str(k).lower(): v for k, v in connections_raw.items()}
                                last_room = monster_behavior_manager.player_last_room.get(action_request.player_id)
                                target_room = connections.get(direction.lower())
                                is_retreat = (last_room is not None and target_room == last_room)
                                
                                print(f"\n🚨 [Movement] Retreat check:")
                                print(f"   player: {action_request.player_id}")
                                print(f"   last_room: {last_room}")
                                print(f"   target_room: {target_room}")
                                print(f"   is_retreat: {is_retreat}")
                                print(f"   All player_last_room entries: {monster_behavior_manager.player_last_room}")
                                logger.info(f"[Movement] Retreat check: player={action_request.player_id}, last_room={last_room}, target_room={target_room}, is_retreat={is_retreat}")
                                logger.info(f"[Movement] All player_last_room entries: {monster_behavior_manager.player_last_room}")

                                # Aggressive blocking (allows retreat internally)
                                aggressive_block = None
                                if not is_retreat:
                                    logger.info(f"[Movement] Not a retreat - checking aggressive monster blocking")
                                    aggressive_block = await monster_behavior_manager.check_aggressive_monster_blocking(
                                        action_request.player_id, player.current_room, direction, game_manager
                                    )
                                else:
                                    logger.info(f"[Movement] Retreat detected - skipping aggressive monster blocking")
                                if aggressive_block:
                                    monster_id, _ = aggressive_block
                                    combat_message = await monster_behavior_manager.handle_aggressive_combat_initiation(
                                        action_request.player_id, monster_id, player.current_room, direction, game_manager
                                    )
                                    try:
                                        monster_data = await game_manager.db.get_monster(monster_id)
                                    except Exception:
                                        monster_data = None
                                    monster_name = (monster_data or {}).get('name', 'Unknown Monster')
                                    try:
                                        player1_max_vital = 5
                                        player2_max_vital = await get_monster_max_vital(monster_data or {})
                                    except Exception:
                                        player1_max_vital = 5
                                        player2_max_vital = 5
                                    yield json.dumps({
                                        "type": "final",
                                        "content": combat_message,
                                        "updates": {
                                            "duel": {
                                                "is_monster_duel": True,
                                                "opponent_id": monster_id,
                                                "opponent_name": monster_name,
                                                "player1_max_vital": player1_max_vital,
                                                "player2_max_vital": player2_max_vital
                                            }
                                        }
                                    })
                                    return

                                # Territorial blocking (skip on retreat)
                                territorial_block = None
                                if not is_retreat:
                                    territorial_block = await monster_behavior_manager.check_territorial_blocking(
                                        action_request.player_id, player.current_room, direction, game_manager
                                    )
                                else:
                                    logger.info(f"[Movement] Retreat detected - skipping territorial monster blocking")
                                if territorial_block:
                                        monster_id, _ = territorial_block
                                        combat_message = await monster_behavior_manager.handle_territorial_combat_initiation(
                                            action_request.player_id, monster_id, player.current_room, direction, game_manager
                                        )
                                        try:
                                            monster_data = await game_manager.db.get_monster(monster_id)
                                        except Exception:
                                            monster_data = None
                                        monster_name = (monster_data or {}).get('name', 'Unknown Monster')
                                        try:
                                            player1_max_vital = 5
                                            player2_max_vital = await get_monster_max_vital(monster_data or {})
                                        except Exception:
                                            player1_max_vital = 5
                                            player2_max_vital = 5
                                        yield json.dumps({
                                            "type": "final",
                                            "content": combat_message,
                                            "updates": {
                                                "duel": {
                                                    "is_monster_duel": True,
                                                    "opponent_id": monster_id,
                                                    "opponent_name": monster_name,
                                                    "player1_max_vital": player1_max_vital,
                                                    "player2_max_vital": player2_max_vital
                                                }
                                            }
                                        })
                                        return

                                # Proceed with movement
                                # Clear rejoin immunity when player moves to a different room
                                if player.rejoin_immunity:
                                    player.rejoin_immunity = False
                                    logger.info(f"[Stream] Cleared rejoin immunity for player {action_request.player_id} due to movement")

                                logger.info(f"⏱️ [TIMING] Monster blocking checks: {(time.time() - movement_start)*1000:.2f}ms")

                                # CRITICAL: Use GameManager's coordinate-based room movement logic to prevent duplicate coordinates
                                room_gen_start = time.time()
                                actual_room_id, new_room = await game_manager.handle_room_movement_by_direction(
                                    player, room, direction
                                )
                                logger.info(f"⏱️ [TIMING] Room generation/retrieval: {(time.time() - room_gen_start)*1000:.2f}ms")

                                # Update player's destination to the actual room ID
                                player_updates["current_room"] = actual_room_id
                                player.current_room = actual_room_id  # CRITICAL: Also update the player object itself
                                new_room_id = actual_room_id

                                logger.info(f"[Stream] Player moving to room: {new_room_id}")

                                # Room movement is now handled entirely by GameManager
                                # Remove the direction from updates since it's been processed
                                del player_updates["direction"]

                                # OPTIMIZATION: Send room_update immediately with new room data
                                logger.info(f"⏱️ [TIMING] Fetching room data for immediate room_update at {(time.time() - request_start)*1000:.2f}ms")
                                try:
                                    room_fetch_start = time.time()
                                    new_room_data = await game_manager.db.get_room(new_room_id)
                                    logger.info(f"⏱️ [TIMING] Room data fetched in {(time.time() - room_fetch_start)*1000:.2f}ms")

                                    # Send room_update with complete room data
                                    room_update_payload = {
                                        "type": "room_update",
                                        "updates": {
                                            "player": {**player_updates, "current_room": new_room_id},
                                            "room": new_room_data
                                        }
                                    }
                                    yield json.dumps(room_update_payload)
                                    logger.info(f"⏱️ [TIMING] Sent room_update to client at {(time.time() - request_start)*1000:.2f}ms")
                                except Exception as e:
                                    logger.error(f"[Stream] Error sending room_update: {str(e)}")

                                # CRITICAL: Update player data in database BEFORE broadcasting
                                # Preserve latest inventory unless explicitly updated to avoid stale overwrites
                                db_update_start = time.time()
                                try:
                                    latest_player_data = await game_manager.db.get_player(action_request.player_id)
                                except Exception:
                                    latest_player_data = None
                                base_player_dict = player.dict()
                                if latest_player_data and isinstance(latest_player_data, dict):
                                    # Prefer the most recent inventory from DB if not included in updates
                                    if 'player' in chunk.get('updates', {}) and 'inventory' not in chunk['updates']['player']:
                                        base_player_dict['inventory'] = latest_player_data.get('inventory', base_player_dict.get('inventory', []))
                                # Build updated player preserving inventory when not sent by updates
                                merged_player_dict = {**base_player_dict, **player_updates}
                                # If updates explicitly include inventory, trust it
                                if 'player' in chunk.get('updates', {}) and 'inventory' in chunk['updates']['player']:
                                    merged_player_dict['inventory'] = chunk['updates']['player']['inventory']
                                updated_player = Player(**merged_player_dict)
                                await game_manager.db.set_player(action_request.player_id, updated_player.dict())
                                logger.info(f"⏱️ [TIMING] Update player in DB (inventory-safe): {(time.time() - db_update_start)*1000:.2f}ms; inv_count={len(updated_player.inventory) if hasattr(updated_player, 'inventory') else 'n/a'}")

                                # CRITICAL: Update room player lists in database
                                db_update_start = time.time()
                                old_room_id = player.current_room
                                await game_manager.db.remove_from_room_players(old_room_id, action_request.player_id)
                                await game_manager.db.add_to_room_players(new_room_id, action_request.player_id)
                                logger.info(f"⏱️ [TIMING] Update room player lists: {(time.time() - db_update_start)*1000:.2f}ms")
                                logger.info(f"[Stream] Updated room player lists: removed from {old_room_id}, added to {new_room_id}")

                                # Clear combat history when player leaves a room
                                try:
                                    monster_behavior_manager._clear_player_combat_history(action_request.player_id)
                                except Exception as e:
                                    logger.error(f"[Stream] Error clearing combat history: {str(e)}")

                                # Handle monster behaviors when entering new room
                                try:
                                    behavior_start = time.time()
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
                                        # Safety check for None direction
                                        if direction is not None:
                                            entry_direction = opposite_directions.get(direction.lower(), direction)
                                        else:
                                            entry_direction = "unknown"

                                        logger.info(f"[MonsterBehavior] Player moved {direction}, entered from {entry_direction}")
                                        logger.info(f"[MonsterBehavior] Calling handle_player_room_entry: player={action_request.player_id}, new_room={new_room_id}, old_room={old_room_id}")

                                        behavior_messages = await monster_behavior_manager.handle_player_room_entry(
                                            action_request.player_id, new_room_id, old_room_id, entry_direction, new_room_data, game_manager
                                        )

                                        logger.info(f"⏱️ [TIMING] Monster behavior handling: {(time.time() - behavior_start)*1000:.2f}ms")
                                        logger.info(f"[MonsterBehavior] handle_player_room_entry completed, player_last_room now: {monster_behavior_manager.player_last_room}")

                                        # Send behavior messages to player if any
                                        for behavior_message in behavior_messages:
                                            await manager.send_to_player(new_room_id, action_request.player_id, {
                                                "type": "system_message",
                                                "message": behavior_message,
                                                "timestamp": datetime.now().isoformat()
                                            })

                                        # Aggressive monster descriptions are now included in atmospheric_presence via room info

                                except Exception as e:
                                    logger.error(f"[Stream] Error handling monster behaviors: {str(e)}")

                                # CRITICAL: Handle presence updates for room movement
                                # Notify old room that player is leaving BEFORE they disconnect
                                broadcast_start = time.time()
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
                                    logger.info(f"⏱️ [TIMING] Broadcast presence update: {(time.time() - broadcast_start)*1000:.2f}ms")
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
                        is_movement = ("player" in chunk.get("updates", {}) and "direction" in chunk["updates"].get("player", {}))
                        additional_content = ""
                        
                        # Also check if this was a movement action by looking at the original action
                        action_lower = (action_request.action or "").lower()
                        cardinal_dirs = {"north", "south", "east", "west", "up", "down"}
                        is_movement_action = action_lower in cardinal_dirs or action_lower.startswith(("move ", "go ", "walk ", "run ", "head "))

                        # If user sent a bare cardinal direction (e.g. button press) and AI omitted updates,
                        # inject a movement update so retreat logic runs.
                        if (not is_movement) and (action_lower in cardinal_dirs):
                            logger.info(f"[Stream] Injecting movement update for bare cardinal action '{action_lower}'")
                            if "updates" not in chunk or not isinstance(chunk.get("updates"), dict):
                                chunk["updates"] = {}
                            if "player" not in chunk["updates"] or not isinstance(chunk["updates"].get("player"), dict):
                                chunk["updates"]["player"] = {}
                            chunk["updates"]["player"]["direction"] = action_lower
                            is_movement = True
                        
                        logger.info(f"[Stream] Action analysis: is_movement={is_movement}, is_movement_action={is_movement_action}, action='{action_request.action}'")

                        if not is_movement and not is_movement_action:
                                logger.info(f"[Stream] Non-movement action detected - checking aggressive monster blocking")
                                
                                # Handle item awarding from AI (unified system) - MOVED HERE FOR NON-MOVEMENT ACTIONS
                                try:
                                    # Check for unified item_award system
                                    item_award_info = chunk.get("updates", {}).get("item_award")
                                    if item_award_info is not None:
                                        award_type = item_award_info.get("type")
                                        awarded_item_name = item_award_info.get("item_name")
                                        rarity = item_award_info.get("rarity", 1)

                                        # Ensure updates scaffolding exists
                                        if "updates" not in chunk or not isinstance(chunk["updates"], dict):
                                            chunk["updates"] = {}
                                        if "player" not in chunk["updates"] or not isinstance(chunk["updates"].get("player"), dict):
                                            chunk["updates"]["player"] = {}

                                        logger.info(f"[Item System] Processing item award: type={award_type}, name={awarded_item_name}, rarity={rarity}")

                                        # Process unified item award system
                                        item_id = None
                                        item_data = None
                                        
                                        if award_type == "room_item" and awarded_item_name:
                                            # Award specific room item
                                            logger.info(f"[Item System] AI awarded room item: {awarded_item_name}")
                                            
                                            if room.items:
                                                # Find the matching room item
                                                item_found = False
                                                for room_item_id in room.items[:]:
                                                    if item_found:
                                                        break
                                                    try:
                                                        room_item_data = await game_manager.db.get_item(room_item_id)
                                                        if room_item_data and room_item_data['name'] == awarded_item_name:
                                                            # Award this specific room item
                                                            item_id = room_item_id
                                                            item_data = room_item_data
                                                            
                                                            # Remove from room
                                                            room.items.remove(room_item_id)
                                                            await game_manager.db.set_room(room.id, room.dict())
                                                            
                                                            # Add to player inventory
                                                            player.inventory.append(item_id)
                                                            await game_manager.db.set_player(action_request.player_id, player.dict())
                                                            
                                                            logger.info(f"[Item System] AI awarded room item '{item_data['name']}' to player {action_request.player_id}")
                                                            item_found = True
                                                            break
                                                    except Exception as e:
                                                        logger.warning(f"[Item System] Failed to check room item {room_item_id}: {str(e)}")
                                        
                                        elif award_type == "generate_item":
                                            # Generate new item
                                            logger.info(f"[Item System] AI requested generated item with rarity: {rarity}")
                                            
                                            try:
                                                from .templates.items import AIItemGenerator
                                                item_generator = AIItemGenerator()
                                                
                                                item_context = {
                                                    'world_seed': game_state.world_seed,
                                                    'world_theme': WORLD_CONFIG['setting_secondary'],
                                                    'main_quest': game_state.main_quest_summary,
                                                    'room_description': room.description,
                                                    'room_biome': room.biome or 'unknown',
                                                    'player_action': action_request.action,
                                                    'situation_context': 'basic_environmental_item',
                                                    'desired_rarity': rarity,
                                                    'database': game_manager.db  # Pass database for recent items context
                                                }
                                                
                                                # Generate item
                                                item_data = await item_generator.generate_item(game_manager.ai_handler, item_context)
                                                
                                                # Create unique item ID and store in database
                                                import uuid
                                                item_id = f"item_{str(uuid.uuid4())}"
                                                item_data['id'] = item_id
                                                await game_manager.db.set_item(item_id, item_data)
                                                
                                                # Add to player inventory
                                                player.inventory.append(item_id)
                                                await game_manager.db.set_player(action_request.player_id, player.dict())
                                                
                                                logger.info(f"[Item System] Generated item '{item_data['name']}' (rarity {rarity}) for player {action_request.player_id}")
                                                
                                            except Exception as e:
                                                logger.error(f"[Item System] Failed to generate item: {str(e)}")
                                        
                                        # Send item notifications if an item was awarded
                                        if item_id and item_data:
                                            # Update response to include item information
                                            chunk["updates"]["player"]["inventory"] = player.inventory
                                            chunk["updates"]["new_item"] = {
                                                "id": item_id,
                                                "name": item_data['name'],
                                                "description": item_data['description'],
                                                "rarity": item_data['rarity'],
                                                "capabilities": item_data['capabilities'],
                                                "properties": {}
                                            }
                                            
                                            # Send item obtained notification via WebSocket
                                            await manager.send_to_player(room.id, action_request.player_id, {
                                                "type": "item_obtained",
                                                "player_id": action_request.player_id,
                                                "item_id": item_id,
                                                "item_name": item_data['name'],
                                                "item_rarity": item_data['rarity'],
                                                "rarity_stars": "★" * item_data['rarity'] + "☆" * (4 - item_data['rarity']),
                                                "message": f"📦 You obtained: {'★' * item_data['rarity']}{'☆' * (4 - item_data['rarity'])} {item_data['name']}",
                                                "timestamp": datetime.now().isoformat()
                                            })
                                            
                                            logger.info(f"[Item System] Sent item obtained notification for '{item_data['name']}' to player {action_request.player_id}")
                                    
                                    # Handle item combination from AI
                                    item_combination_info = chunk.get("updates", {}).get("item_combination")
                                    if item_combination_info is not None:
                                        item_ids = item_combination_info.get("item_ids", [])
                                        combination_description = item_combination_info.get("combination_description", "")
                                        
                                        if item_ids and len(item_ids) >= 2:
                                            logger.info(f"[Item Combination] AI requested combination of {len(item_ids)} items: {item_ids}")
                                            
                                            try:
                                                # Call the combine_items function
                                                combination_result = await game_manager.combine_items(
                                                    action_request.player_id, 
                                                    item_ids, 
                                                    combination_description
                                                )
                                                
                                                if combination_result["success"]:
                                                    # Update the chunk with the combination results
                                                    chunk["updates"]["player"] = combination_result["updates"]["player"]
                                                    chunk["updates"]["new_item"] = combination_result["updates"]["new_item"]
                                                    
                                                    # Send item combination notification via WebSocket
                                                    await manager.send_to_player(room.id, action_request.player_id, {
                                                        "type": "item_obtained",
                                                        "player_id": action_request.player_id,
                                                        "item_id": combination_result["updates"]["new_item"]["id"],
                                                        "item_name": combination_result["updates"]["new_item"]["name"],
                                                        "item_rarity": combination_result["updates"]["new_item"]["rarity"],
                                                        "rarity_stars": "★" * combination_result["updates"]["new_item"]["rarity"] + "☆" * (4 - combination_result["updates"]["new_item"]["rarity"]),
                                                        "message": f"🔨 You crafted: {'★' * combination_result['updates']['new_item']['rarity']}{'☆' * (4 - combination_result['updates']['new_item']['rarity'])} {combination_result['updates']['new_item']['name']}",
                                                        "timestamp": datetime.now().isoformat()
                                                    })
                                                    
                                                    logger.info(f"[Item Combination] Successfully combined items into '{combination_result['updates']['new_item']['name']}'")
                                                else:
                                                    logger.warning(f"[Item Combination] Failed to combine items: {combination_result['message']}")
                                                    
                                            except Exception as e:
                                                logger.error(f"[Item Combination] Error combining items: {str(e)}")
                                        else:
                                            logger.warning(f"[Item Combination] Invalid item combination request: {item_combination_info}")

                                except Exception as e:
                                    logger.error(f"[Item Handling] Unexpected error: {str(e)}")

                                # Handle explicit combat intent signaled by AI
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
                                            try:
                                                monster_data = await game_manager.db.get_monster(target_monster_id)
                                            except Exception:
                                                monster_data = None
                                            monster_name = (monster_data or {}).get('name', 'Unknown Monster')
                                            try:
                                                player1_max_vital = 5
                                                player2_max_vital = await get_monster_max_vital(monster_data or {})
                                            except Exception:
                                                player1_max_vital = 5
                                                player2_max_vital = 5
                                            yield json.dumps({
                                                "type": "final",
                                                "content": combat_message,
                                                "updates": {
                                                    "duel": {
                                                        "is_monster_duel": True,
                                                        "opponent_id": target_monster_id,
                                                        "opponent_name": monster_name,
                                                        "player1_max_vital": player1_max_vital,
                                                        "player2_max_vital": player2_max_vital
                                                    }
                                                }
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
                                    try:
                                        monster_data = await game_manager.db.get_monster(monster_id)
                                    except Exception:
                                        monster_data = None
                                    monster_name = (monster_data or {}).get('name', 'Unknown Monster')
                                    try:
                                        player1_max_vital = 5
                                        player2_max_vital = await get_monster_max_vital(monster_data or {})
                                    except Exception:
                                        player1_max_vital = 5
                                        player2_max_vital = 5
                                    yield json.dumps({
                                        "type": "final",
                                        "content": combat_message,
                                        "updates": {
                                            "duel": {
                                                "is_monster_duel": True,
                                                "opponent_id": monster_id,
                                                "opponent_name": monster_name,
                                                "player1_max_vital": player1_max_vital,
                                                "player2_max_vital": player2_max_vital
                                            }
                                        }
                                    })
                                    return
                        else:
                                logger.info(f"[Stream] Movement action detected - skipping aggressive monster blocking (retreat logic already handled)")

                                # Fallback monster auto-reply disabled: only respond when AI explicitly sets updates.monster_interaction earlier

                        # NOW yield the final response with updated player data (default path)
                        try:
                            # Quest tracking integration
                            quest_completion_message = None
                            try:
                                from .quest_manager import QuestManager
                                quest_manager = QuestManager(game_manager.db)

                                # Track movement (only if direction variable exists in scope)
                                if 'direction' in locals() and direction:
                                    quest_result = await quest_manager.check_objectives(
                                        action_request.player_id, action_request.action, 'move', {}
                                    )
                                    if quest_result and quest_result.get('type') == 'quest_completed':
                                        quest_completion_message = quest_result

                                # Track "look" command
                                if 'look' in action_request.action.lower():
                                    quest_result = await quest_manager.check_objectives(
                                        action_request.player_id, action_request.action, 'command', {'command': 'look'}
                                    )
                                    if quest_result and quest_result.get('type') == 'quest_completed':
                                        quest_completion_message = quest_result

                                # Track NPC interactions (talk to, speak with, etc.)
                                npc_interaction_keywords = ['talk', 'speak', 'chat', 'converse', 'ask', 'tell', 'greet']
                                npc_dialogue_generated = False
                                if any(keyword in action_request.action.lower() for keyword in npc_interaction_keywords):
                                    # Check if there's an NPC in the room that matches the interaction
                                    target_npc = None

                                    # First, check if AI identified an NPC in updates
                                    npc_data = None
                                    if chunk.get('updates', {}).get('npc'):
                                        npc_data = chunk['updates']['npc']
                                    elif chunk.get('updates', {}).get('npcs') and len(chunk['updates']['npcs']) > 0:
                                        npc_data = chunk['updates']['npcs'][0]  # Get first NPC

                                    # If AI identified an NPC, find it in the room's NPCs
                                    if npc_data and npc_data.get('name'):
                                        npc_name = npc_data.get('name', '')
                                        for room_npc in npcs:
                                            if room_npc.name.lower() == npc_name.lower():
                                                target_npc = room_npc
                                                break

                                    # If no NPC identified by AI, but action contains talk keywords and there's only one NPC in room
                                    if not target_npc and len(npcs) == 1:
                                        target_npc = npcs[0]

                                    # If we found an NPC to talk to, generate their dialogue
                                    if target_npc:
                                        try:
                                            from .ai_handler import AIHandler

                                            # Get NPC's relevant memories (last 5 interactions)
                                            relevant_memories = target_npc.memory_log[-5:] if hasattr(target_npc, 'memory_log') and target_npc.memory_log else []

                                            # Generate NPC dialogue
                                            npc_response, npc_memory = await AIHandler.process_npc_interaction(
                                                message=action_request.action,
                                                npc=target_npc,
                                                player=player,
                                                room=room,
                                                relevant_memories=relevant_memories
                                            )

                                            # Update NPC's memory and dialogue history
                                            if hasattr(target_npc, 'memory_log'):
                                                target_npc.memory_log.append(npc_memory)
                                            else:
                                                target_npc.memory_log = [npc_memory]

                                            if hasattr(target_npc, 'dialogue_history'):
                                                target_npc.dialogue_history.append({
                                                    'player_id': action_request.player_id,
                                                    'player_message': action_request.action,
                                                    'npc_response': npc_response,
                                                    'timestamp': datetime.now().isoformat()
                                                })

                                            # Save updated NPC
                                            await game_manager.db.set_npc(target_npc.id, target_npc.dict())

                                            # Append NPC dialogue to the response
                                            if chunk.get("response"):
                                                chunk["response"] += f"\n\n{npc_response}"
                                            else:
                                                chunk["response"] = npc_response

                                            npc_dialogue_generated = True
                                            logger.info(f"[NPC Dialogue] Generated dialogue from {target_npc.name} for player {action_request.player_id}")

                                        except Exception as e:
                                            logger.error(f"[NPC Dialogue] Error generating NPC dialogue: {str(e)}")

                                        # Track quest objectives
                                        quest_result = await quest_manager.check_objectives(
                                            action_request.player_id, action_request.action, 'talk_npc', {'npc_name': target_npc.name}
                                        )
                                        if quest_result and quest_result.get('type') == 'quest_completed':
                                            quest_completion_message = quest_result
                                        logger.info(f"[Quest] Tracked NPC interaction with '{target_npc.name}' for player {action_request.player_id}")

                                # Track item taken (check if item was awarded and variables exist)
                                if 'item_id' in locals() and 'item_data' in locals() and item_id and item_data:
                                    quest_result = await quest_manager.check_objectives(
                                        action_request.player_id, action_request.action, 'take_item', {'item_name': item_data.get('name', '')}
                                    )
                                    if quest_result and quest_result.get('type') == 'quest_completed':
                                        quest_completion_message = quest_result

                                # Track biome visit (on room entry after movement - only if variables exist)
                                if 'direction' in locals() and 'new_room' in locals() and direction and new_room:
                                    biome = new_room.biome
                                    if biome:
                                        quest_result = await quest_manager.check_objectives(
                                            action_request.player_id, action_request.action, 'visit_biome', {'biome': biome}
                                        )
                                        if quest_result and quest_result.get('type') == 'quest_completed':
                                            quest_completion_message = quest_result

                                # Track find_item (when entering a room with quest items)
                                # Check both new_room (after movement) and current room (for look/other actions)
                                check_room = None
                                if 'new_room' in locals() and new_room:
                                    check_room = new_room
                                else:
                                    # For non-movement actions, check current room
                                    check_room = room

                                if check_room and check_room.items:
                                    for room_item_id in check_room.items[:]:
                                        try:
                                            room_item_data = await game_manager.db.get_item(room_item_id)
                                            if not room_item_data:
                                                logger.warning(f"[Quest] Item {room_item_id} not found in database")
                                                continue

                                            # Check if it's a quest item (stored as string "True")
                                            quest_item_value = room_item_data.get('properties', {}).get('quest_item')
                                            is_quest_item = quest_item_value in ['True', 'true', True]

                                            logger.debug(f"[Quest] Checking item {room_item_data.get('name')} - quest_item={quest_item_value}, is_quest_item={is_quest_item}, properties={room_item_data.get('properties')}")

                                            if is_quest_item:
                                                # Check if this quest item belongs to this player
                                                spawned_for = room_item_data.get('properties', {}).get('spawned_for_player_id')

                                                # Only process if it's the player's item or it's a shared quest item (no owner)
                                                if spawned_for and spawned_for != action_request.player_id:
                                                    logger.debug(f"[Quest] Item '{room_item_data.get('name')}' belongs to player {spawned_for}, skipping for {action_request.player_id}")
                                                    continue

                                                # This is a quest item for this player - check if it completes an objective
                                                logger.info(f"[Quest] Found quest item '{room_item_data.get('name')}' for player {action_request.player_id} - checking objectives")
                                                quest_result = await quest_manager.check_objectives(
                                                    action_request.player_id,
                                                    action_request.action,
                                                    'room_has_item',
                                                    {'item_name': room_item_data.get('name', '')}
                                                )
                                                logger.info(f"[Quest] check_objectives returned: {quest_result}")

                                                if quest_result:
                                                    # Quest objective completed - auto-take the quest item
                                                    logger.info(f"[Quest] Player {action_request.player_id} found quest item '{room_item_data.get('name')}' - auto-taking")

                                                    # Remove from room
                                                    check_room.items.remove(room_item_id)
                                                    await game_manager.db.set_room(check_room.id, check_room.dict())

                                                    # Add to player inventory
                                                    player.inventory.append(room_item_id)
                                                    await game_manager.db.set_player(action_request.player_id, player.dict())

                                                    # Update chunk to reflect inventory change
                                                    if "updates" not in chunk:
                                                        chunk["updates"] = {}
                                                    if "player" not in chunk["updates"]:
                                                        chunk["updates"]["player"] = {}
                                                    chunk["updates"]["player"]["inventory"] = player.inventory

                                                    # Add discovery notification to updates
                                                    chunk["updates"]["quest_item_found"] = {
                                                        "id": room_item_id,
                                                        "name": room_item_data['name'],
                                                        "description": room_item_data['description'],
                                                        "rarity": room_item_data.get('rarity', 1)
                                                    }

                                                    # Send item obtained notification via WebSocket (same as regular items)
                                                    # Use the player's current room (where they're still connected) not the new room
                                                    websocket_room = room.id if room else check_room.id
                                                    try:
                                                        await manager.send_to_player(websocket_room, action_request.player_id, {
                                                            "type": "item_obtained",
                                                            "player_id": action_request.player_id,
                                                            "item_id": room_item_id,
                                                            "item_name": room_item_data['name'],
                                                            "item_rarity": room_item_data.get('rarity', 1),
                                                            "rarity_stars": "★" * room_item_data.get('rarity', 1) + "☆" * (4 - room_item_data.get('rarity', 1)),
                                                            "message": f"📦 You obtained: {'★' * room_item_data.get('rarity', 1)}{'☆' * (4 - room_item_data.get('rarity', 1))} {room_item_data['name']}",
                                                            "timestamp": datetime.now().isoformat()
                                                        })
                                                        logger.info(f"[Quest] Sent item_obtained WebSocket notification for '{room_item_data['name']}' to player {action_request.player_id} in room {websocket_room}")
                                                    except Exception as ws_error:
                                                        logger.error(f"[Quest] Failed to send item_obtained WebSocket notification: {str(ws_error)}")

                                                    logger.info(f"[Quest] Successfully auto-took quest item '{room_item_data.get('name')}' for player {action_request.player_id}")

                                                    # Check if quest was completed
                                                    if quest_result.get('type') == 'quest_completed':
                                                        quest_completion_message = quest_result

                                                    # Only process one quest item per action
                                                    break
                                        except Exception as e:
                                            logger.warning(f"[Quest] Error checking room item {room_item_id} for quest: {str(e)}")

                            except Exception as e:
                                logger.error(f"[Quest] Error tracking quest objectives: {str(e)}")

                            # Extract only the narrative response, not the full JSON structure
                            narrative_response = chunk.get("response", "")
                            if not narrative_response:
                                logger.warning(f"[Stream] No narrative response found in chunk: {chunk}")
                                narrative_response = "You perform the action."

                            final_content = narrative_response + (f"\n\n{additional_content}" if additional_content else "")

                            final_response_time = time.time()
                            logger.info(f"⏱️ [TIMING] About to send final response to client: {(final_response_time - request_start)*1000:.2f}ms from request start")
                            yield json.dumps({
                                "type": "final",
                                "content": final_content,
                                "updates": chunk.get("updates", {})
                            })
                            logger.info(f"⏱️ [TIMING] Final response sent to client")

                            # Send quest completion as a separate message if quest was completed
                            if quest_completion_message:
                                quest_data = quest_completion_message.get('quest', {})
                                quest_name = quest_data.get('name', 'Unknown Quest') if quest_data else 'Unknown Quest'
                                gold_reward = quest_completion_message.get('gold_reward', 0)
                                badge_id = quest_completion_message.get('badge_id', '')
                                # Get badge name if badge_id exists (for now just use badge_id)
                                badge_name = badge_id if badge_id else ''

                                completion_text = f"🎉 **Quest Complete: {quest_name}**\n"
                                completion_text += f"💰 Earned {gold_reward} gold"
                                if badge_name:
                                    completion_text += f" and the '{badge_name}' badge!"
                                else:
                                    completion_text += "!"

                                # Get next quest details with objectives for the client
                                next_quest_info = None
                                next_quest = quest_completion_message.get('next_quest')
                                if next_quest:
                                    try:
                                        # Get objectives for the next quest
                                        next_objectives = await quest_manager._get_quest_objectives(next_quest['id'])
                                        next_quest_info = {
                                            'quest': next_quest,
                                            'objectives': next_objectives
                                        }
                                        logger.info(f"[Quest] Including next quest info: {next_quest['name']} with {len(next_objectives)} objectives")
                                    except Exception as e:
                                        logger.error(f"[Quest] Error getting next quest objectives: {str(e)}")

                                logger.info(f"[Quest] Player {action_request.player_id} completed quest: {quest_name}")

                                yield json.dumps({
                                    "type": "quest_complete",
                                    "content": completion_text,
                                    "quest_data": quest_completion_message,
                                    "next_quest_info": next_quest_info
                                })

                                # Send next quest storyline immediately after completion if available
                                if next_quest:
                                    try:
                                        storyline_chunks = await quest_manager.get_storyline_chunks(
                                            next_quest['id'],
                                            chunk_size=80
                                        )

                                        for chunk in storyline_chunks:
                                            yield json.dumps({
                                                'type': 'quest_storyline',
                                                'message': chunk
                                            })

                                        # Mark storyline as shown for the new quest
                                        player_quest = await quest_manager._get_player_quest(
                                            action_request.player_id,
                                            next_quest['id']
                                        )
                                        if player_quest:
                                            player_quest['storyline_shown'] = True
                                            await quest_manager._save_player_quest(player_quest)
                                            logger.info(f"[Quest] Sent storyline for new quest {next_quest['name']} to player {action_request.player_id}")
                                    except Exception as e:
                                        logger.error(f"[Quest] Error sending next quest storyline: {str(e)}")
                        except Exception as e:
                            logger.error(f"[Stream] Error generating final response: {str(e)}")
                            # Fallback response to prevent freezing
                            yield json.dumps({
                                "type": "final",
                                "content": "You perform the action.",
                                "updates": {}
                            })
                else:
                    # This is a text chunk
                    before_yield = time.time()
                    logger.info(f"⏱️ [TIMING] About to yield text chunk {chunk_count} at {(before_yield - request_start)*1000:.2f}ms")
                    yield json.dumps({
                        "type": "chunk",
                        "content": chunk
                    })
                    after_yield = time.time()
                    logger.info(f"⏱️ [TIMING] Chunk {chunk_count} yielded, took {(after_yield - before_yield)*1000:.2f}ms")

        except Exception as e:
            logger.error(f"[Stream] Critical error in event generator: {str(e)}")
            import traceback
            logger.error(f"[Stream] Traceback: {traceback.format_exc()}")
            yield json.dumps({
                "type": "error",
                "content": "An error occurred while processing your action. Please try again.",
                "updates": {}
            })

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
    """Generate aggressive monster descriptions for atmospheric presence"""
    try:
        if not room_data or not room_data.get('monsters'):
            return ""
        
        # Get aggressive monster descriptions
        room_id = room_data.get('id', '')
        aggressive_monster_desc = await get_room_monsters_description(room_id, game_manager)
        
        return aggressive_monster_desc
        
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
        
        # CRITICAL: Only update room presence lists, don't modify player data
        # This prevents accidentally overwriting health or other critical fields
        # when a player re-enters a room (especially after death/respawn)
        if player.current_room != request.room_id:
            # Update room presence lists
            await game_manager.db.remove_from_room_players(player.current_room, request.player_id)
            await game_manager.db.add_to_room_players(request.room_id, request.player_id)
            logger.info(f"[Presence] Player {request.player_id} moved from {player.current_room} to {request.room_id}")
        else:
            # Player already in this room, just ensure they're in the player list
            await game_manager.db.add_to_room_players(request.room_id, request.player_id)
            logger.info(f"[Presence] Player {request.player_id} already in room {request.room_id}, ensuring presence")

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
        # Store the chat message in player history only
        await game_manager.db.store_player_message(message.player_id, message)
        
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