import { io, Socket } from 'socket.io-client';
import useGameStore from '@/store/gameStore';
import { ChatMessage, Player, Room } from '@/types/game';

class WebSocketService {
    private socket: WebSocket | null = null;
    private roomId: string | null = null;
    private playerId: string | null = null;
    private pendingRoomUpdate: Room | null = null;
    private nextRoomId: string | null = null;
    private isReconnecting: boolean = false;

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
        useGameStore.getState().setIsConnected(false);
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

    private handlePresenceUpdate(data: { player_id: string; status: 'joined' | 'disconnected' }) {
        const store = useGameStore.getState();
        const players = store.playersInRoom.filter(p => p.id !== data.player_id);
        store.setPlayersInRoom(players);
    }

    private handleActionUpdate(data: { player_id: string; action: string; message: string; updates?: any }) {
        console.log('[WebSocket] Handling action update - FULL DATA:', data);
        const message: ChatMessage = {
            player_id: data.player_id,
            room_id: this.roomId!,
            message: data.message,
            message_type: 'system',
            timestamp: new Date().toISOString()
        };
        console.log('[WebSocket] Adding action message to chat:', message);
        useGameStore.getState().addMessage(message);

        // Handle any game state updates
        if (data.updates) {
            console.log('[WebSocket] Processing game state updates:', data.updates);
            const store = useGameStore.getState();

            if (data.updates.player) {
                console.log('[WebSocket] Updating player state:', data.updates.player);
                store.setPlayer(data.updates.player);

                // Handle room change
                if (data.updates.player.current_room && data.updates.player.current_room !== this.roomId) {
                    console.log('[WebSocket] Player moved to new room, initiating reconnect:', {
                        oldRoom: this.roomId,
                        newRoom: data.updates.player.current_room,
                        hasRoom: !!data.updates.room
                    });

                    // Store the room update if we have it
                    if (data.updates.room) {
                        console.log('[WebSocket] Storing room data for after reconnect');
                        this.pendingRoomUpdate = data.updates.room;

                        // Add room description to chat
                        const roomMessage: ChatMessage = {
                            player_id: 'system',
                            room_id: data.updates.room.id,
                            message: '',
                            message_type: 'room_description',
                            timestamp: new Date().toISOString(),
                            title: data.updates.room.title,
                            description: data.updates.room.description,
                            players: store.playersInRoom
                        };
                        store.addMessage(roomMessage);
                    }

                    this.isReconnecting = true;
                    // Reconnect WebSocket to new room
                    this.connect(data.updates.player.current_room, this.playerId!);
                }
            }

            // Only update room if we're not in the middle of a room transition
            if (data.updates.room && !this.isReconnecting) {
                console.log('[WebSocket] Updating room state from action:', {
                    currentRoom: store.currentRoom?.id,
                    newRoom: data.updates.room.id,
                    title: data.updates.room.title,
                    isReconnecting: this.isReconnecting
                });
                store.setCurrentRoom(data.updates.room);
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

            // Add room description to chat
            const roomMessage: ChatMessage = {
                player_id: 'system',
                room_id: room.id,
                message: '',
                message_type: 'room_description',
                timestamp: new Date().toISOString(),
                title: room.title,
                description: room.description,
                players: store.playersInRoom
            };
            store.addMessage(roomMessage);
            return;
        }

        // If this is our current room, update it
        if (store.currentRoom?.id === room.id || room.id === this.roomId) {
            console.log('[WebSocket] Updating current room:', {
                currentTitle: store.currentRoom?.title,
                newTitle: room.title,
                currentImage: store.currentRoom?.image_url,
                newImage: room.image_url
            });
            store.setCurrentRoom(room);

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
                    players: store.playersInRoom
                };
                store.addMessage(roomMessage);
            }
            return;
        }

        console.log('[WebSocket] Update for different room, ignoring. Current:', store.currentRoom?.id, 'Connecting to:', this.roomId, 'Update:', room.id);
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

    sendAction(action: string) {
        if (!this.socket || !this.roomId || !this.playerId) {
            console.log('[WebSocket] Cannot send action - not connected:', {
                socket: !!this.socket,
                roomId: this.roomId,
                playerId: this.playerId
            });
            return;
        }

        const message = {
            type: 'action',
            player_id: this.playerId,
            room_id: this.roomId,
            action
        };
        console.log('[WebSocket] Sending action:', message);
        this.socket.send(JSON.stringify(message));
    }
}

// Create a singleton instance
const websocketService = new WebSocketService();
export default websocketService;