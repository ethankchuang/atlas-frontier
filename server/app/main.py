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
    Direction
)
from .game_manager import GameManager
from .config import settings
from .logger import setup_logging

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)


app = FastAPI(title="AI MUD Game Server")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
                logger.info(f"[WebSocket] Processing action from player {player_id}: {message['action']}")
                # Process action through game manager
                response, updates = await game_manager.process_action(
                    player_id=message['player_id'],
                    action=message['action']
                )
                # Broadcast action result with updates
                await manager.broadcast_to_room(
                    room_id=room_id,
                    message={
                        'type': 'action',
                        'player_id': message['player_id'],
                        'action': message['action'],
                        'message': response,
                        'updates': updates
                    },
                    exclude_player=player_id
                )
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

            # Start streaming the response
            async for chunk in game_manager.ai.stream_action(
                action=action_request.action,
                player=player,
                room=room,
                game_state=game_state,
                npcs=npcs
            ):
                if isinstance(chunk, dict):
                    # This is the final message with updates
                    yield json.dumps({
                        "type": "final",
                        "content": chunk["response"],
                        "updates": chunk["updates"]
                    })

                    # Apply updates
                    if "player" in chunk["updates"]:
                        player_updates = chunk["updates"]["player"]
                        if "current_room" in player_updates and player_updates["current_room"] != player.current_room:
                            new_room_id = player_updates["current_room"]
                            new_room_data = await game_manager.db.get_room(new_room_id)

                            if not new_room_data:
                                # Generate the new room
                                title, description, image_prompt = await game_manager.ai.generate_room_description(
                                    context={
                                        "previous_room": room.dict(),
                                        "action": action_request.action,
                                        "player": player.dict()
                                    }
                                )

                                # Determine directions based on action
                                action_lower = action_request.action.lower()
                                if "north" in action_lower:
                                    forward_dir = Direction.NORTH
                                    back_dir = Direction.SOUTH
                                elif "south" in action_lower:
                                    forward_dir = Direction.SOUTH
                                    back_dir = Direction.NORTH
                                elif "east" in action_lower:
                                    forward_dir = Direction.EAST
                                    back_dir = Direction.WEST
                                elif "west" in action_lower:
                                    forward_dir = Direction.WEST
                                    back_dir = Direction.EAST
                                elif "up" in action_lower or "climb" in action_lower:
                                    forward_dir = Direction.UP
                                    back_dir = Direction.DOWN
                                elif "down" in action_lower or "descend" in action_lower:
                                    forward_dir = Direction.DOWN
                                    back_dir = Direction.UP
                                else:
                                    # Default to north/south if no direction is specified
                                    forward_dir = Direction.NORTH
                                    back_dir = Direction.SOUTH

                                # Create new room with a placeholder image first
                                new_room = Room(
                                    id=new_room_id,
                                    title=title,
                                    description=description,
                                    image_url="",  # Start with empty image URL
                                    connections={
                                        # Add connection back to the previous room
                                        back_dir: player.current_room
                                    },
                                    npcs=[],
                                    items=[],
                                    players=[action_request.player_id],  # Initialize with the moving player
                                    visited=True,
                                    properties={}
                                )

                                # Update the current room's connections
                                room.connections[forward_dir] = new_room_id
                                await game_manager.db.set_room(room.id, room.dict())

                                # Generate the image first
                                image_url = await game_manager.ai.generate_room_image(image_prompt)
                                new_room.image_url = image_url

                                # Save the new room with the generated image
                                await game_manager.db.set_room(new_room_id, new_room.dict())

                                # First update WebSocket connection to new room
                                logger.info(f"[WebSocket] Attempting to update connection - Current room: {player.current_room}, New room: {new_room_id}")
                                logger.info(f"[WebSocket] Active connections before update: {manager.get_connection_summary()}")

                                if action_request.player_id in manager.active_connections.get(player.current_room, {}):
                                    websocket = manager.active_connections[player.current_room].pop(action_request.player_id)
                                    if not manager.active_connections[player.current_room]:
                                        manager.active_connections.pop(player.current_room)
                                    if new_room_id not in manager.active_connections:
                                        manager.active_connections[new_room_id] = {}
                                    manager.active_connections[new_room_id][action_request.player_id] = websocket
                                    logger.info(f"[WebSocket] Updated connection for player {action_request.player_id} from room {player.current_room} to {new_room_id}")
                                    logger.info(f"[WebSocket] Active connections after update: {manager.get_connection_summary()}")
                                else:
                                    logger.warning(f"[WebSocket] Could not find connection for player {action_request.player_id} in room {player.current_room}")
                                    logger.warning(f"[WebSocket] Available connections: {manager.get_connection_summary()}")

                                # Now broadcast room updates
                                logger.info(f"[WebSocket] Broadcasting new room update for {new_room_id}")
                                await manager.broadcast_to_room(
                                    room_id=new_room_id,
                                    message={
                                        "type": "room_update",
                                        "room": new_room.dict()
                                    }
                                )

                                # Also broadcast update to the previous room
                                logger.info(f"[WebSocket] Broadcasting update for previous room {room.id}")
                                await manager.broadcast_to_room(
                                    room_id=room.id,
                                    message={
                                        "type": "room_update",
                                        "room": room.dict()
                                    }
                                )

                                # Now update player location in database
                                await game_manager.db.remove_from_room_players(player.current_room, player.id)
                                await game_manager.db.add_to_room_players(new_room_id, player.id)

                                # Add the new room info to the updates, but remove room data to prevent double updates
                                chunk["updates"]["player"] = player_updates
                                chunk["updates"]["room"] = {}
                                chunk["updates"]["new_room"] = {}

                        # Update last_action timestamp and text
                        current_time = datetime.utcnow()
                        player_updates["last_action"] = current_time.isoformat()
                        player_updates["last_action_text"] = action_request.action

                        player = Player(**{**player.dict(), **player_updates})
                        await game_manager.db.set_player(player.id, player.dict())

                    if "room" in chunk["updates"]:
                        # Only update the current room, not the new room we just created
                        if not chunk["updates"].get("new_room"):
                            logger.info(f"[WebSocket] Updating room {room.id}")
                            room_updates = chunk["updates"]["room"]
                            if "players" not in room_updates:
                                room_updates["players"] = await game_manager.db.get_room_players(room.id)
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
            message={"type": "presence", "player_id": request.player_id, "status": "joined"},
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)