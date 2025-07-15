import useGameStore from '@/store/gameStore';
import { ChatMessage, Player, Room } from '@/types/game';

class WebSocketService {
    private socket: WebSocket | null = null;
    private roomId: string | null = null;
    private playerId: string | null = null;
    private pendingRoomUpdate: Room | null = null;
    private nextRoomId: string | null = null;
    private isReconnecting: boolean = false;
    private playerListUpdateTimeout: NodeJS.Timeout | null = null;

    setNextRoom(roomId: string) {
        console.log('[WebSocket] Setting next room:', roomId);
        this.nextRoomId = roomId;
    }

    connect(roomId: string, playerId: string) {
        if (this.socket) {
            console.log('[WebSocket] Disconnecting existing connection');
            this.disconnect();
        }

        console.log('[WebSocket] Starting connection...', {
            apiUrl: process.env.NEXT_PUBLIC_API_URL,
            roomId,
            playerId,
            isReconnecting: this.isReconnecting,
            pendingUpdate: !!this.pendingRoomUpdate
        });

        // If we have a next room set, use that instead
        if (this.nextRoomId) {
            console.log('[WebSocket] Using next room:', this.nextRoomId, 'instead of:', roomId);
            roomId = this.nextRoomId;
            this.nextRoomId = null;
        }

        this.roomId = roomId;
        this.playerId = playerId;

        const wsUrl = `${process.env.NEXT_PUBLIC_API_URL?.replace('http', 'ws')}/ws/${roomId}/${playerId}`;
        console.log('[WebSocket] Attempting connection to:', wsUrl);

        try {
            this.socket = new WebSocket(wsUrl);
            console.log('[WebSocket] Socket created, setting up listeners');
            this.setupEventListeners();
        } catch (error) {
            console.error('[WebSocket] Failed to create socket:', error);
            useGameStore.getState().setError('Failed to create WebSocket connection');
        }
    }

    disconnect() {
        console.log('[WebSocket] Disconnecting socket:', {
            hasSocket: !!this.socket,
            readyState: this.socket?.readyState,
            roomId: this.roomId,
            playerId: this.playerId
        });

        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.roomId = null;
        this.playerId = null;
        this.pendingRoomUpdate = null;
        this.nextRoomId = null;
        this.isReconnecting = false;
        useGameStore.getState().setIsConnected(false);
        
        // Clear any pending player list updates
        if (this.playerListUpdateTimeout) {
            clearTimeout(this.playerListUpdateTimeout);
            this.playerListUpdateTimeout = null;
        }
    }

    private setupEventListeners() {
        if (!this.socket) {
            console.error('[WebSocket] Cannot setup listeners - no socket');
            return;
        }

        this.socket.onopen = () => {
            console.log('[WebSocket] Connection opened successfully', {
                roomId: this.roomId,
                isReconnecting: this.isReconnecting,
                hasPendingUpdate: !!this.pendingRoomUpdate
            });
            useGameStore.getState().setIsConnected(true);
            useGameStore.getState().setError(null);

            // If we have a pending update, apply it now
            if (this.pendingRoomUpdate && this.pendingRoomUpdate.id === this.roomId) {
                console.log('[WebSocket] Applying queued update for room:', this.roomId);
                const store = useGameStore.getState();
                store.setCurrentRoom(this.pendingRoomUpdate);
                this.pendingRoomUpdate = null;
                this.isReconnecting = false;
            }
        };

        this.socket.onclose = (event) => {
            console.log('[WebSocket] Connection closed:', {
                code: event.code,
                reason: event.reason,
                wasClean: event.wasClean
            });
            useGameStore.getState().setIsConnected(false);
        };

        this.socket.onerror = (error) => {
            console.error('[WebSocket] Connection error:', error);
            useGameStore.getState().setError('WebSocket connection error');
        };

        this.socket.onmessage = (event) => {
            console.log('[WebSocket] Raw message received:', event.data);
            let data;
            try {
                data = JSON.parse(event.data);
                console.log('[WebSocket] Parsed message data:', {
                    type: data.type,
                    hasRoom: !!data.room,
                    hasUpdates: !!data.updates,
                    messageLength: event.data.length
                });
            } catch (error) {
                console.error('[WebSocket] Failed to parse message:', error);
                return;
            }
            const { type } = data;

            console.log('[WebSocket] Processing message type:', type);
            switch (type) {
                case 'chat':
                    this.handleChatMessage(data);
                    break;
                case 'presence':
                    this.handlePresenceUpdate(data);
                    break;
                case 'action':
                    this.handleActionUpdate(data);
                    break;
                case 'room_update':
                    console.log('[WebSocket] Received room update:', {
                        roomId: data.room?.id,
                        title: data.room?.title,
                        hasImage: !!data.room?.image_url,
                        imageStatus: data.room?.image_status
                    });
                    this.handleRoomUpdate(data.room);
                    break;
                case 'player_update':
                    this.handlePlayerUpdate(data.player);
                    break;
                default:
                    console.log('[WebSocket] Unknown message type:', type);
            }
        };
    }

    private handleChatMessage(message: ChatMessage) {
        useGameStore.getState().addMessage(message);
    }

    private handlePresenceUpdate(data: { player_id: string; status: 'joined' | 'disconnected' | 'left'; player_data?: any }) {
        console.log('[WebSocket] Handling presence update:', data);
        const store = useGameStore.getState();
        
        if (data.status === 'disconnected' || data.status === 'left') {
            // Remove player from room
            const players = store.playersInRoom.filter(p => p.id !== data.player_id);
            store.setPlayersInRoom(players);
            console.log('[WebSocket] Removed player from room:', data.player_id);
        } else if (data.status === 'joined' && data.player_data) {
            // Player joined - add them to the room with their data
            console.log('[WebSocket] Player joined room:', data.player_data.name);
            const existingPlayer = store.playersInRoom.find(p => p.id === data.player_id);
            if (!existingPlayer) {
                const updatedPlayers = [...store.playersInRoom, data.player_data];
                store.setPlayersInRoom(updatedPlayers);
                console.log('[WebSocket] Added player to room:', data.player_data.name);
            }
        }
    }

    private handleActionUpdate(data: { player_id: string; action: string; message: string; updates?: any }) {
        console.log('[WebSocket] Handling action update - FULL DATA:', data);
        
        // CRITICAL: Only process action updates for OTHER players, not the current player
        if (data.player_id === this.playerId) {
            console.log('[WebSocket] Ignoring action update for current player:', data.player_id);
            return;
        }
        
        // Suppress blue/system text for other players: do NOT add to chat
        // const message: ChatMessage = {
        //     player_id: data.player_id,
        //     room_id: this.roomId!,
        //     message: data.message,
        //     message_type: 'system',
        //     timestamp: new Date().toISOString()
        // };
        // console.log('[WebSocket] Adding action message to chat for other player:', message);
        // useGameStore.getState().addMessage(message);

        // Handle any game state updates from other players
        if (data.updates) {
            console.log('[WebSocket] Processing game state updates from other player:', data.updates);
            const store = useGameStore.getState();

            // Only update player state if it's for a different player
            if (data.updates.player && data.updates.player.id !== this.playerId) {
                console.log('[WebSocket] Updating other player state:', data.updates.player);
                // Update other players in the room, not the current player
                const players = store.playersInRoom.map(p =>
                    p.id === data.updates.player.id ? data.updates.player : p
                );
                store.setPlayersInRoom(players);

                // Handle room change for other players (not the current player)
                if (data.updates.player.current_room && data.updates.player.current_room !== this.roomId) {
                    console.log('[WebSocket] Other player moved to new room:', {
                        playerId: data.player_id,
                        oldRoom: this.roomId,
                        newRoom: data.updates.player.current_room,
                        hasRoom: !!data.updates.room
                    });

                    // Remove the player from our current room since they moved away
                    const players = store.playersInRoom.filter(p => p.id !== data.player_id);
                    store.setPlayersInRoom(players);
                    console.log('[WebSocket] Removed player from room due to movement:', data.player_id);

                    // For other players moving, we don't need to reconnect our WebSocket
                    // Just update the room state if we have it
                    if (data.updates.room) {
                        console.log('[WebSocket] Updating room state for other player movement');
                        
                        // Mark room as visited on minimap (if we're in that room)
                        if (data.updates.room.id === this.roomId) {
                            store.addVisitedCoordinate(data.updates.room.x, data.updates.room.y);
                        }
                    }
                }
            }

            // Only update room if we're not in the middle of a room transition and it's for our current room
            if (data.updates.room && !this.isReconnecting && data.updates.room.id === this.roomId) {
                console.log('[WebSocket] Updating room state from other player action:', {
                    currentRoom: store.currentRoom?.id,
                    newRoom: data.updates.room.id,
                    title: data.updates.room.title,
                    isReconnecting: this.isReconnecting
                });
                store.setCurrentRoom(data.updates.room);
                
                // Mark room as visited on minimap
                store.addVisitedCoordinate(data.updates.room.x, data.updates.room.y);
            }

            if (data.updates.new_room && data.updates.new_room.image_url) {
                console.log('[WebSocket] Processing new room image update:', {
                    roomId: data.updates.new_room.room_id,
                    currentRoom: store.currentRoom?.id,
                    imageUrl: data.updates.new_room.image_url
                });
                // If we're in the room that's getting a new image, update it
                if (store.currentRoom && store.currentRoom.id === data.updates.new_room.room_id) {
                    console.log('[WebSocket] Updating current room with new image');
                    store.setCurrentRoom({
                        ...store.currentRoom,
                        image_url: data.updates.new_room.image_url,
                        image_status: 'ready'
                    });
                }
            }

            if (data.updates.npcs) {
                console.log('[WebSocket] Updating NPCs state:', data.updates.npcs);
                store.setNPCs(data.updates.npcs);
            }
        }
    }

    private handleRoomUpdate(room: Room) {
        const store = useGameStore.getState();
        console.log('[WebSocket] Received room update:', {
            roomId: room.id,
            title: room.title,
            currentRoomId: store.currentRoom?.id,
            isCurrentRoom: store.currentRoom?.id === room.id,
            connectingToRoom: this.roomId,
            isReconnecting: this.isReconnecting,
            hasPendingUpdate: !!this.pendingRoomUpdate
        });

        // If we're reconnecting and this is our pending room update, apply it
        if (this.isReconnecting && this.pendingRoomUpdate?.id === room.id) {
            console.log('[WebSocket] Applying pending room update after reconnect');
            store.setCurrentRoom(room);
            this.pendingRoomUpdate = null;
            this.isReconnecting = false;

            // Mark room as visited on minimap
            store.addVisitedCoordinate(room.x, room.y);

            // Sync player list for the room
            if (room.players && room.players.length > 0) {
                this.debouncedUpdatePlayerList(room.players);
            } else {
                store.setPlayersInRoom([]);
            }

            // Add room description to chat
            const roomMessage: ChatMessage = {
                player_id: 'system',
                room_id: room.id,
                message: '',
                message_type: 'room_description',
                timestamp: new Date().toISOString(),
                title: room.title,
                description: room.description,
                players: store.playersInRoom, // Use current player list
                x: room.x,
                y: room.y
            };
            store.addMessage(roomMessage);
            return;
        }

        // If this is our current room, update it
        // Also handle the case where we're moving to a new room
        if (store.currentRoom?.id === room.id || room.id === this.roomId || room.id === this.nextRoomId) {
            console.log('[WebSocket] Updating current room:', {
                currentTitle: store.currentRoom?.title,
                newTitle: room.title,
                currentImage: store.currentRoom?.image_url,
                newImage: room.image_url,
                playerCount: room.players?.length || 0
            });
            store.setCurrentRoom(room);

            // CRITICAL: Sync the player list from the room data
            // Note: room.players contains player IDs (strings), not Player objects
            // We need to fetch the actual player data for these IDs
            if (room.players && room.players.length > 0) {
                console.log('[WebSocket] Room update contains player IDs:', room.players);
                // Use debounced update to prevent rapid changes
                this.debouncedUpdatePlayerList(room.players);
            } else {
                // No players in room, clear the list
                console.log('[WebSocket] No players in room, clearing player list');
                store.setPlayersInRoom([]);
            }

            // Mark room as visited on minimap
            store.addVisitedCoordinate(room.x, room.y);

            // Add room description to chat if this is a new room
            if (store.currentRoom?.id !== room.id) {
                const roomMessage: ChatMessage = {
                    player_id: 'system',
                    room_id: room.id,
                    message: '',
                    message_type: 'room_description',
                    timestamp: new Date().toISOString(),
                    title: room.title,
                    description: room.description,
                    players: store.playersInRoom, // Use current player list for chat display
                    x: room.x,
                    y: room.y
                };
                store.addMessage(roomMessage);
            }
            return;
        }

        console.log('[WebSocket] Update for different room, ignoring. Current:', store.currentRoom?.id, 'Connecting to:', this.roomId, 'Update:', room.id);
    }



    private debouncedUpdatePlayerList(playerIds: string[]) {
        // Clear any existing timeout
        if (this.playerListUpdateTimeout) {
            clearTimeout(this.playerListUpdateTimeout);
        }
        
        // Set a new timeout to update the player list after a short delay
        this.playerListUpdateTimeout = setTimeout(() => {
            this.fetchPlayersForRoom(playerIds);
        }, 500); // 500ms delay to prevent rapid updates
    }

    private async fetchPlayersForRoom(playerIds: string[]) {
        try {
            const store = useGameStore.getState();
            const currentPlayer = store.player;
            
            // Filter out the current player from the list
            const otherPlayerIds = playerIds.filter(id => id !== currentPlayer?.id);
            
            if (otherPlayerIds.length === 0) {
                store.setPlayersInRoom([]);
                return;
            }
            
            // Fetch player data for all other players in the room
            const playerPromises = otherPlayerIds.map(async (playerId) => {
                try {
                    console.log(`[WebSocket] Fetching player data for: ${playerId}`);
                    const response = await fetch(`http://localhost:8000/players/${playerId}`);
                    console.log(`[WebSocket] Response status for ${playerId}:`, response.status);
                    if (response.ok) {
                        const playerData = await response.json();
                        console.log(`[WebSocket] Successfully fetched player data for ${playerId}:`, playerData.name);
                        return playerData;
                    } else {
                        console.error(`[WebSocket] Failed to fetch player ${playerId}: HTTP ${response.status}`);
                    }
                } catch (error) {
                    console.error(`[WebSocket] Failed to fetch player ${playerId}:`, error);
                }
                return null;
            });
            
            const players = await Promise.all(playerPromises);
            const validPlayers = players.filter(p => p !== null);
            
            console.log('[WebSocket] Fetched players for room:', validPlayers.map(p => p.name));
            console.log('[WebSocket] Setting players in room:', validPlayers.length, 'players');
            store.setPlayersInRoom(validPlayers);
        } catch (error) {
            console.error('[WebSocket] Error fetching players for room:', error);
        }
    }

    private handlePlayerUpdate(player: Player) {
        if (player.id === this.playerId) {
            useGameStore.getState().setPlayer(player);
        } else {
            const store = useGameStore.getState();
            const players = store.playersInRoom.map(p =>
                p.id === player.id ? player : p
            );
            store.setPlayersInRoom(players);
        }
    }

    sendChatMessage(message: string, type: 'chat' | 'emote' = 'chat') {
        if (!this.socket || !this.roomId || !this.playerId) return;

        const chatMessage: ChatMessage = {
            player_id: this.playerId,
            room_id: this.roomId,
            message,
            message_type: type,
            timestamp: new Date().toISOString()
        };

        // Add message to chat history immediately
        useGameStore.getState().addMessage(chatMessage);

        this.socket.send(JSON.stringify(chatMessage));
    }

    // sendAction method removed - actions now only go through streaming endpoint
}

// Create a singleton instance
const websocketService = new WebSocketService();
export default websocketService;