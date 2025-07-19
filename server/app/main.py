from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, List, Optional
import json
import asyncio
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
    ActionRecord
)
from .game_manager import GameManager
from .config import settings
from .logger import setup_logging
from .templates.items import GenericItemTemplate
import uuid

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

def get_game_manager():
    return game_manager

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
            
            # Use AI processing for all actions (including movement)
            async for chunk in game_manager.ai_handler.stream_action(
                action=action_request.action,
                player=player,
                room=room,
                game_state=game_state,
                npcs=npcs
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
                        
                        # Generate random item for player (100% chance for testing)
                        try:
                            logger.info(f"[Item Generation] Generating random item for player {player.id}")
                            item_template = GenericItemTemplate()
                            
                            # Generate item with context
                            context = {
                                "location": room.title,
                                "theme": "fantasy"
                            }
                            
                            # Generate the item using AI
                            prompt = item_template.generate_prompt(context)
                            ai_response = await game_manager.ai_handler.generate_text(prompt)
                            item_data = item_template.parse_response(ai_response, context)
                            
                            # Create item ID and add to player's inventory
                            item_id = f"item_{str(uuid.uuid4())}"
                            item_data["id"] = item_id
                            
                            # Add item to player's inventory
                            player.inventory.append(item_id)
                            await game_manager.db.set_player(player.id, player.dict())
                            
                            # Save item to database
                            await game_manager.db.set_item(item_id, item_data)
                            
                            logger.info(f"[Item Generation] Added item '{item_data['name']}' to player {player.id}")
                            
                            # Send server message to player about the obtained item
                            rarity_stars = rarity_to_stars(item_data['rarity'])
                            item_message = f"🎁 You obtained: {item_data['name']} {rarity_stars}"
                            # Change: stars only at the end
                            item_message = f"🎁 You obtained: {item_data['name']} {rarity_stars}"
                            
                            await manager.send_to_player(
                                room_id=player.current_room,
                                player_id=action_request.player_id,
                                message={
                                    "type": "item_obtained",
                                    "player_id": action_request.player_id,
                                    "item_name": item_data['name'],
                                    "item_rarity": item_data['rarity'],
                                    "rarity_stars": rarity_stars,
                                    "message": item_message,
                                    "timestamp": datetime.utcnow().isoformat()
                                }
                            )
                            
                            # Add item acquisition to player's memory log
                            player.memory_log.append(f"Found {item_data['name']} - {item_data['special_effects']}")
                            await game_manager.db.set_player(player.id, player.dict())
                            
                        except Exception as e:
                            logger.error(f"[Item Generation] Failed to generate item for player {player.id}: {str(e)}")

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
                                "player": chunk["updates"].get("player"),
                                "npcs": chunk["updates"].get("npcs")
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
async def get_room(
    room_id: str,
    game_manager: GameManager = Depends(get_game_manager)
):
    try:
        room_info = await game_manager.get_room_info(room_id)
        return room_info
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

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
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)