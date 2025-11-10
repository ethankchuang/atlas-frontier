from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid

class Direction(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    UP = "up"
    DOWN = "down"

class Item(BaseModel):
    id: str
    name: str
    description: str
    is_takeable: bool = True
    properties: Dict[str, str] = Field(default_factory=dict)

class Monster(BaseModel):
    id: str
    name: str
    description: str
    aggressiveness: str  # passive, aggressive, neutral, territorial
    intelligence: str    # human, subhuman, animal, omnipotent
    size: str           # colossal, dinosaur, horse, human, chicken, insect
    special_effects: str = ""  # AI-generated special abilities
    location: str       # room_id
    health: int = 5  # Default to player base health, will be calculated based on size
    is_alive: bool = True
    properties: Dict[str, str] = Field(default_factory=dict)

class NPC(BaseModel):
    id: str
    name: str
    description: str
    location: str  # room_id
    dialogue_history: List[Dict[str, str]] = Field(default_factory=list)
    memory_log: List[str] = Field(default_factory=list)
    last_interaction: Optional[datetime] = None
    properties: Dict[str, str] = Field(default_factory=dict)

class Room(BaseModel):
    id: str
    title: str
    description: str
    x: int = 0  # X coordinate
    y: int = 0  # Y coordinate
    biome: Optional[str] = None
    image_url: Optional[str] = None
    image_status: Optional[str] = "pending"  # "pending", "generating", "content_ready", "ready", "error"
    image_prompt: Optional[str] = None
    connections: Dict[Direction, str] = Field(default_factory=dict)  # direction -> room_id
    npcs: List[str] = Field(default_factory=list)  # List of NPC IDs
    items: List[str] = Field(default_factory=list)  # List of Item IDs
    monsters: List[str] = Field(default_factory=list)  # List of Monster IDs
    players: List[str] = Field(default_factory=list)  # List of Player IDs
    visited: bool = False
    properties: Dict[str, Any] = Field(default_factory=dict)
    # 3D Model fields (optional feature)
    model_3d_url: Optional[str] = None
    model_3d_status: Optional[str] = "none"  # "none", "pending", "generating", "ready", "error"
    model_3d_job_id: Optional[str] = None  # FAL request_id for polling

class Player(BaseModel):
    id: str  # Keep the existing player ID system
    user_id: str  # Link to the user profile that owns this player
    name: str
    current_room: Optional[str] = ""
    inventory: List[str] = Field(default_factory=list)  # List of Item IDs
    quest_progress: Dict[str, str] = Field(default_factory=dict)
    memory_log: List[str] = Field(default_factory=list)
    last_action: Optional[str] = None  # ISO format datetime string
    last_action_text: Optional[str] = None  # Store the actual action text
    health: int = 5  # Player base health
    # Minimap state persistence
    visited_coordinates: List[str] = Field(default_factory=list)  # ["0,0", "1,0", etc.]
    visited_biomes: Dict[str, str] = Field(default_factory=dict)  # {"0,0": "forest", etc.}
    biome_colors: Dict[str, str] = Field(default_factory=dict)  # {"forest": "#color", etc.}
    # Rejoin immunity - temporary immunity to aggressive monsters when rejoining
    rejoin_immunity: bool = False
    # Quest system
    gold: int = 0  # Current gold balance
    active_quest_id: Optional[str] = None  # Currently active quest

class GameState(BaseModel):
    world_seed: str
    main_quest_summary: str
    active_quests: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    global_state: Dict[str, str] = Field(default_factory=dict)

class CreatePlayerRequest(BaseModel):
    name: str

class ActionRequest(BaseModel):
    player_id: str
    action: str
    room_id: str
    target: Optional[str] = None

class ActionResponse(BaseModel):
    success: bool
    message: str
    updates: Dict[str, dict] = Field(default_factory=dict)
    image_url: Optional[str] = None

class ActionRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player_id: str
    room_id: str
    action: str  # Player's input
    ai_response: str  # AI's response
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    updates: Dict[str, Any] = Field(default_factory=dict)  # Game state changes
    session_id: str  # To group actions by session
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Additional context like room title, NPCs present, etc.

class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player_id: str
    room_id: str
    message: str
    message_type: str = "chat"  # chat, emote, system
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    is_ai_response: bool = False
    ai_context: Optional[Dict[str, Any]] = None  # Store AI context for responses

class NPCInteraction(BaseModel):
    player_id: str
    npc_id: str
    room_id: str
    message: str
    context: Dict[str, str] = Field(default_factory=dict)

class PresenceRequest(BaseModel):
    player_id: str
    room_id: str

class GameSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player_id: str
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    total_actions: int = 0
    rooms_visited: List[str] = Field(default_factory=list)
    items_obtained: List[str] = Field(default_factory=list)

class ActiveDuel(BaseModel):
    duel_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player1_id: str
    player2_id: str
    room_id: str
    current_round: int = 1
    player1_condition: str = "Healthy"
    player2_condition: str = "Healthy"
    player1_vital: int = 5
    player2_vital: int = 5
    player1_control: int = 0
    player2_control: int = 0
    player1_max_vital: int = 5
    player2_max_vital: int = 5
    start_time: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

# Quest System Models
class Badge(BaseModel):
    id: str
    name: str
    description: str
    image_url: Optional[str] = None
    image_status: str = "pending"  # pending, generating, ready, error
    rarity: str = "common"  # common, rare, epic, legendary

class QuestObjective(BaseModel):
    id: str
    quest_id: str
    objective_type: str  # find_item, move_n_times, use_command, visit_biomes, talk_to_npc, win_combat, etc.
    objective_data: Dict[str, Any]  # Flexible data for each type
    order_index: int = 0
    description: str

class Quest(BaseModel):
    id: str
    name: str
    description: str
    storyline: str  # Narrative text shown in chat
    gold_reward: int = 0
    badge_id: Optional[str] = None
    order_index: int = 0
    is_daily: bool = False
    is_active: bool = True

class PlayerQuest(BaseModel):
    id: str
    player_id: str
    quest_id: str
    status: str = "available"  # available, in_progress, completed, claimed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    storyline_shown: bool = False

class PlayerQuestObjective(BaseModel):
    id: str
    player_quest_id: str
    objective_id: str
    is_completed: bool = False
    progress_data: Optional[Dict[str, Any]] = None  # {"current": 2, "required": 3}
    completed_at: Optional[datetime] = None

class PlayerBadge(BaseModel):
    id: str
    player_id: str
    badge_id: str
    earned_at: datetime = Field(default_factory=datetime.utcnow)

class GoldTransaction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    player_id: str
    amount: int  # Positive for credit, negative for debit
    transaction_type: str  # quest_reward, purchase, sale, transfer
    reference_id: Optional[str] = None
    description: Optional[str] = None
    balance_after: int
    created_at: datetime = Field(default_factory=datetime.utcnow)