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
    players: List[str] = Field(default_factory=list)  # List of Player IDs
    visited: bool = False
    properties: Dict[str, Any] = Field(default_factory=dict)

class Player(BaseModel):
    id: str
    name: str
    current_room: str
    inventory: List[str] = Field(default_factory=list)  # List of Item IDs
    quest_progress: Dict[str, str] = Field(default_factory=dict)
    memory_log: List[str] = Field(default_factory=list)
    last_action: Optional[str] = None  # ISO format datetime string
    last_action_text: Optional[str] = None  # Store the actual action text
    pending_item_type: Optional[Dict[str, Any]] = None  # Store pending item type for discovery

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