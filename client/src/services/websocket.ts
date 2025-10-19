import useGameStore, { DUEL_MAX_HEALTH } from '@/store/gameStore';
import { ChatMessage, Player, Room, NPC, Monster } from '@/types/game';
import apiService from './api';

class WebSocketService {
    private socket: WebSocket | null = null;
    private roomId: string | null = null;
    private playerId: string | null = null;
    private pendingRoomUpdate: Room | null = null;
    private nextRoomId: string | null = null;
    private isReconnecting: boolean = false;
    private playerListUpdateTimeout: NodeJS.Timeout | null = null;
    private heartbeatInterval: NodeJS.Timeout | null = null;

    setNextRoom(roomId: string) {
        console.log('[WebSocket] Setting next room:', roomId);
        this.nextRoomId = roomId;
    }

    private getCloseCodeMessage(code: number): string {
        // WebSocket close codes: https://developer.mozilla.org/en-US/docs/Web/API/CloseEvent
        switch (code) {
            case 1000:
                return 'Connection closed normally';
            case 1001:
                return 'Server is going away or browser navigating away';
            case 1002:
                return 'Protocol error';
            case 1003:
                return 'Unsupported data received';
            case 1006:
                return 'Connection lost - check your internet connection';
            case 1007:
                return 'Invalid data format';
            case 1008:
                return 'Policy violation';
            case 1009:
                return 'Message too large';
            case 1010:
                return 'Server did not negotiate required extension';
            case 1011:
                return 'Server encountered an unexpected error';
            case 1012:
                return 'Service is restarting';
            case 1013:
                return 'Service is temporarily overloaded';
            case 1014:
                return 'Bad gateway';
            case 1015:
                return 'TLS handshake failed';
            default:
                return `Connection closed with code ${code}`;
        }
    }

    private get url(): string {
        return `${process.env.NEXT_PUBLIC_API_URL?.replace('http', 'ws')}/ws/${this.roomId}/${this.playerId}`;
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
            // Don't clear nextRoomId here - wait until room description is added
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

        // Stop heartbeat
        this.stopHeartbeat();

        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
        this.roomId = null;
        this.playerId = null;
        this.pendingRoomUpdate = null;
        // Don't clear nextRoomId - we need it to persist through reconnection
        // this.nextRoomId = null;
        this.isReconnecting = false;
        useGameStore.getState().setIsConnected(false);
        
        // Clear any pending player list updates
        if (this.playerListUpdateTimeout) {
            clearTimeout(this.playerListUpdateTimeout);
            this.playerListUpdateTimeout = null;
        }
    }

    private startHeartbeat() {
        // Clear any existing heartbeat
        this.stopHeartbeat();
        
        // Send ping every 30 seconds
        this.heartbeatInterval = setInterval(() => {
            if (this.socket && this.socket.readyState === WebSocket.OPEN) {
                console.log('[WebSocket] Sending heartbeat ping');
                this.socket.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000); // 30 seconds
    }

    private stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
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

            // Start heartbeat
            this.startHeartbeat();

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
            const closeInfo = {
                code: event.code,
                reason: event.reason,
                wasClean: event.wasClean
            };
            console.log('[WebSocket] Connection closed:', closeInfo);

            // Provide more helpful error messages based on close code
            if (!event.wasClean) {
                const errorMessage = this.getCloseCodeMessage(event.code);
                console.warn('[WebSocket] Abnormal close:', errorMessage);
                useGameStore.getState().setError(errorMessage);
            }

            useGameStore.getState().setIsConnected(false);
        };

        this.socket.onerror = (error) => {
            // WebSocket errors don't contain much info - the close event has details
            console.error('[WebSocket] Connection error event fired');
            console.error('[WebSocket] Error object:', error);
            console.error('[WebSocket] WebSocket URL:', this.url);
            console.error('[WebSocket] WebSocket state:', this.socket?.readyState);

            // Don't set error here - wait for onclose which has better info
            // useGameStore.getState().setError('WebSocket connection error');
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
            
            // Handle messages that have message_type but no type field (chat messages)
            let type = data.type;
            if (!type && data.message_type) {
                console.log('[WebSocket] Message has message_type but no type, treating as chat message');
                type = 'chat';
            }

            // AGGRESSIVE: Clear stuck duel state on every message
            const store = useGameStore.getState();
            if (store.isInDuel && !store.duelOpponent) {
                console.warn('[WebSocket] Detected stuck duel state, clearing');
                store.forceClearDuelState();
            }

            console.log('[WebSocket] Processing message type:', type);
            switch (type) {
                case 'pong':
                    console.log('[WebSocket] Received heartbeat pong');
                    break;
                case 'chat':
                    this.handleChatMessage(data);
                    break;
                case 'presence':
                    this.handlePresenceUpdate(data);
                    break;
                case 'action':
                    this.handleActionUpdate(data);
                    break;
                case 'item_obtained':
                    this.handleItemObtained(data);
                    break;
                case 'duel_challenge':
                    this.handleDuelChallenge(data);
                    break;
                case 'duel_response':
                    this.handleDuelResponse(data);
                    break;
                case 'duel_move':
                    this.handleDuelMove(data);
                    break;
                case 'duel_cancel':
                    this.handleDuelCancel(data);
                    break;
                case 'duel_outcome':
                    this.handleDuelOutcome(data);
                    break;
                case 'duel_round_result':
                    this.handleDuelRoundResult(data);
                    break;
                case 'duel_next_round':
                    this.handleDuelNextRound(data);
                    break;
                case 'monster_combat_outcome':
                    this.handleMonsterCombatOutcome(data);
                    break;
                case 'system':
                    this.handleSystemMessage(data);
                    break;
                case 'quest_storyline':
                    this.handleQuestStoryline(data);
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
                case 'player_death':
                    this.handlePlayerDeath(data);
                    break;
                default:
                    console.log('[WebSocket] Unknown message type:', type);
            }
        };
    }

    private handleChatMessage(message: ChatMessage) {
        useGameStore.getState().addMessage(message);
    }

    private handleSystemMessage(data: { message: string; timestamp: string }) {
        console.log('[WebSocket] Handling system message:', data);
        const systemMessage: ChatMessage = {
            player_id: 'system',
            room_id: '', // Will be filled by the store
            message: data.message,
            message_type: 'system',
            timestamp: data.timestamp
        };
        useGameStore.getState().addMessage(systemMessage);
    }

    private questStorylineChunks: string[] = [];
    private questStorylineTimer: NodeJS.Timeout | null = null;

    private handleQuestStoryline(data: { message: string; timestamp?: string }) {
        console.log('[WebSocket] Handling quest storyline chunk:', data.message);
        this.questStorylineChunks.push(data.message);
        
        // Clear any existing timer
        if (this.questStorylineTimer) {
            clearTimeout(this.questStorylineTimer);
        }
        
        // Set a new timer to combine chunks after a brief delay
        this.questStorylineTimer = setTimeout(() => {
            if (this.questStorylineChunks.length > 0) {
                // Send all chunks as a special multi-chunk storyline message
                console.log('[WebSocket] Adding quest storyline with chunks:', this.questStorylineChunks.length);
                const questMessage: ChatMessage = {
                    player_id: 'system',
                    room_id: this.roomId || '',
                    message: this.questStorylineChunks.join(''), // Full text for fallback
                    message_type: 'quest_storyline',
                    timestamp: data.timestamp || new Date().toISOString(),
                    quest_data: { chunks: this.questStorylineChunks } // Store chunks separately
                };
                useGameStore.getState().addMessage(questMessage);
                this.questStorylineChunks = []; // Clear chunks after adding
            }
            this.questStorylineTimer = null;
        }, 500); // Wait 500ms for all chunks to arrive
    }

    private handlePresenceUpdate(data: { player_id: string; status: 'joined' | 'disconnected' | 'left'; player_data?: Player }) {
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
            } else {
                // Update existing player data
                const updatedPlayers = store.playersInRoom.map(p => 
                    p.id === data.player_id ? data.player_data! : p
                );
                store.setPlayersInRoom(updatedPlayers);
                console.log('[WebSocket] Updated player in room:', data.player_data.name);
            }
        }
    }

    private handleActionUpdate(data: { 
        player_id: string; 
        action: string; 
        message: string; 
        updates?: {
            player?: Partial<Player>;
            room?: Room;
            new_room?: { room_id: string; image_url: string };
            npcs?: unknown;
        }
    }) {
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
            if (data.updates?.player && (data.updates.player as Player).id !== this.playerId) {
                console.log('[WebSocket] Updating other player state:', data.updates.player);
                // Update other players in the room, not the current player
                const players = store.playersInRoom.map(p =>
                    p.id === (data.updates?.player as Player).id ? (data.updates?.player as Player) : p
                );
                store.setPlayersInRoom(players);

                // Handle room change for other players (not the current player)
                if ((data.updates.player as Player).current_room && (data.updates.player as Player).current_room !== this.roomId) {
                    console.log('[WebSocket] Other player moved to new room:', {
                        playerId: data.player_id,
                        oldRoom: this.roomId,
                        newRoom: (data.updates.player as Player).current_room,
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
                        if (data.updates.room && data.updates.room.id === this.roomId) {
                            store.addVisitedCoordinate(data.updates.room.x, data.updates.room.y, data.updates.room.biome);
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
                store.addVisitedCoordinate(data.updates.room.x, data.updates.room.y, data.updates.room.biome);
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
                store.setNPCs(data.updates.npcs as NPC[]);
            }
        }
    }

    private handleItemObtained(data: { player_id: string; item_name: string; item_rarity: number; rarity_stars: string; message: string; timestamp: string; item_id?: string }) {
        console.log('[WebSocket] Handling item obtained update:', data);
        console.log('[WebSocket] Current player ID:', this.playerId);
        
        // Only show item obtained messages for the current player
        if (data.player_id === this.playerId) {
            const itemMessage: ChatMessage = {
                player_id: 'system',
                room_id: this.roomId!,
                message: data.message,
                message_type: 'item_obtained',
                timestamp: data.timestamp,
                item_name: data.item_name,
                item_rarity: data.item_rarity,
                rarity_stars: data.rarity_stars
            };
            const store = useGameStore.getState();
            store.addMessage(itemMessage);
            console.log('[WebSocket] Added item obtained message to chat:', data.message);
        } else {
            console.log('[WebSocket] Item obtained message not for current player, ignoring');
        }
    }

    private handleDuelChallenge(data: { type: 'duel_challenge'; challenger_id: string; target_id: string; room_id: string; timestamp: string }) {
        console.log('[WebSocket] Handling duel challenge:', data);
        const store = useGameStore.getState();
        const player = store.player;
        
        // Only show challenge popup if this player is the target
        if (player && data.target_id === player.id) {
            // Find challenger's name
            const challenger = store.playersInRoom.find(p => p.id === data.challenger_id);
            if (challenger) {
                console.log('[WebSocket] Received duel challenge from:', challenger.name);
                store.setDuelChallenge({
                    challengerName: challenger.name,
                    challengerId: data.challenger_id
                });
            } else {
                console.error('[WebSocket] Challenger not found in playersInRoom!');
            }
        }
    }

    private handleDuelResponse(data: { type: 'duel_response'; challenger_id: string; responder_id: string; response: 'accept' | 'decline'; room_id: string; timestamp: string; monster_name?: string; is_monster_duel?: boolean }) {
        console.log('[WebSocket] Handling duel response:', data);
        const store = useGameStore.getState();
        const player = store.player;

        if (!player) {
            console.error('[WebSocket] Player not found for duel response.');
            return;
        }

        // Handle monster duels
        if ((data as { is_monster_duel?: boolean }).is_monster_duel && data.monster_name) {
            if (data.response === 'accept') {
                console.log('[WebSocket] Monster duel accepted! Starting duel with:', data.monster_name);
                
                // Start the duel with the monster
                if (player.id === data.challenger_id) {
                    // Player challenged monster, monster accepted
                    console.log('[WebSocket] Starting monster duel as challenger');
                    store.startDuel({ id: data.responder_id, name: data.monster_name });
                    // Apply max vitals immediately if provided
                    try {
                        const p1Max = (data as { player1_max_vital?: number }).player1_max_vital ?? DUEL_MAX_HEALTH;
                        const p2Max = (data as { player2_max_vital?: number }).player2_max_vital ?? DUEL_MAX_HEALTH;
                        
                        if (typeof p1Max === 'number' && typeof p2Max === 'number') {
                            useGameStore.getState().setMaxVitals(p1Max, p2Max);
                        } else {
                            console.error('[WebSocket] Invalid max vital values for monster duel:', { p1Max, p2Max });
                        }
                    } catch (error) {
                        console.error('[WebSocket] Error setting max vitals for monster duel:', error);
                    }
                    
                    const message = `The ${data.monster_name} accepts your challenge! The duel begins!`;
                    store.addMessage({
                        player_id: 'system',
                        room_id: data.room_id,
                        message,
                        message_type: 'system',
                        timestamp: data.timestamp
                    });
                }
            }
            return;
        }

        // Handle regular player duels (existing code)
        const responder = store.playersInRoom.find(p => p.id === data.responder_id) || 
                         (player.id === data.responder_id ? player : null);
        const challenger = store.playersInRoom.find(p => p.id === data.challenger_id) || 
                          (player.id === data.challenger_id ? player : null);
        
        console.log('[WebSocket] DEBUG: Looking for players in room:', {
            responder_id: data.responder_id,
            challenger_id: data.challenger_id,
            current_player_id: player.id,
            players_in_room: store.playersInRoom.map(p => ({ id: p.id, name: p.name })),
            responder_found: !!responder,
            challenger_found: !!challenger
        });
        
        if (responder && challenger) {
            console.log('DEBUG: data.response =', data.response, 'Type:', typeof data.response, 'Is "accept"?', data.response === 'accept'); // Added for debugging
            if (data.response === 'accept') {
                console.log('[WebSocket] Duel accepted! Starting duel for player:', player.name);

                // Start the duel for both players
                if (player.id === data.challenger_id) {
                    // Challenger starts duel with responder
                    console.log('[WebSocket] Challenger starting duel with:', responder.name);
                    store.startDuel({ id: data.responder_id, name: responder.name });
                } else if (player.id === data.responder_id) {
                    // Responder starts duel with challenger
                    console.log('[WebSocket] Responder starting duel with:', challenger.name);
                    store.startDuel({ id: data.challenger_id, name: challenger.name });
                }

                // Apply max vitals for player duels (same as monster duels)
                try {
                    const p1Max = (data as { player1_max_vital?: number }).player1_max_vital ?? DUEL_MAX_HEALTH;
                    const p2Max = (data as { player2_max_vital?: number }).player2_max_vital ?? DUEL_MAX_HEALTH;

                    if (typeof p1Max === 'number' && typeof p2Max === 'number') {
                        useGameStore.getState().setMaxVitals(p1Max, p2Max);
                        console.log('[WebSocket] Set max vitals for player duel:', { p1Max, p2Max });
                    } else {
                        console.error('[WebSocket] Invalid max vital values for player duel:', { p1Max, p2Max });
                    }
                } catch (error) {
                    console.error('[WebSocket] Error setting max vitals for player duel:', error);
                }

                const message = `${responder.name} accepted ${challenger.name}'s duel challenge! The duel begins!`;
                store.addMessage({
                    player_id: 'system',
                    room_id: data.room_id,
                    message,
                    message_type: 'system',
                    timestamp: data.timestamp
                });
            } else {
                const message = `${responder.name} declined ${challenger.name}'s duel challenge.`;
                store.addMessage({
                    player_id: 'system',
                    room_id: data.room_id,
                    message,
                    message_type: 'system',
                    timestamp: data.timestamp
                });
            }
        } else {
            console.log('[WebSocket] ERROR: Could not find responder or challenger in playersInRoom:', {
                responder_id: data.responder_id,
                challenger_id: data.challenger_id,
                current_player_id: player.id,
                players_in_room: store.playersInRoom.map(p => ({ id: p.id, name: p.name }))
            });
            
            // Fallback: if we can't find the players in the room, try to start the duel anyway
            if (data.response === 'accept') {
                console.log('[WebSocket] Fallback: Starting duel with available player data');
                if (player.id === data.challenger_id) {
                    // We're the challenger, start duel with responder
                    store.startDuel({ id: data.responder_id, name: 'Opponent' });
                } else if (player.id === data.responder_id) {
                    // We're the responder, start duel with challenger
                    store.startDuel({ id: data.challenger_id, name: 'Opponent' });
                }

                // Apply max vitals for player duels (same as monster duels)
                try {
                    const p1Max = (data as { player1_max_vital?: number }).player1_max_vital ?? DUEL_MAX_HEALTH;
                    const p2Max = (data as { player2_max_vital?: number }).player2_max_vital ?? DUEL_MAX_HEALTH;

                    if (typeof p1Max === 'number' && typeof p2Max === 'number') {
                        useGameStore.getState().setMaxVitals(p1Max, p2Max);
                        console.log('[WebSocket] Set max vitals for player duel (fallback):', { p1Max, p2Max });
                    } else {
                        console.error('[WebSocket] Invalid max vital values for player duel (fallback):', { p1Max, p2Max });
                    }
                } catch (error) {
                    console.error('[WebSocket] Error setting max vitals for player duel (fallback):', error);
                }

                const message = `Duel challenge accepted! The duel begins!`;
                store.addMessage({
                    player_id: 'system',
                    room_id: data.room_id,
                    message,
                    message_type: 'system',
                    timestamp: data.timestamp
                });
            }
        }
    }

    private handleDuelMove(data: { type: 'duel_move'; player_id: string; opponent_id?: string; move: string; room_id: string; timestamp: string; is_monster_move?: boolean; monster_name?: string }) {
        console.log('[WebSocket] Handling duel move:', data);
        const store = useGameStore.getState();
        const player = store.player;

        if (!player) {
            console.error('[WebSocket] Player not found for duel move.');
            return;
        }

        // Handle monster moves
        if (data.is_monster_move && data.monster_name) {
            console.log('[WebSocket] Received monster duel move:', data.monster_name);
            store.setOpponentMove(data.move);
            
            // Check if both moves have been submitted
            if (store.myDuelMove && store.opponentDuelMove) {
                console.log('[WebSocket] Both moves submitted, setting flag');
                store.setBothMovesSubmitted(true);
            }
            
            // Add a message that the monster is preparing
            store.addMessage({
                player_id: 'system',
                room_id: data.room_id,
                message: `⚔️ The ${data.monster_name} prepares its combat move...`,
                message_type: 'system',
                timestamp: data.timestamp
            });
            return;
        }

        // If this is the opponent's move, store it but don't show in chat yet
        if (player.id !== data.player_id) {
            console.log('[WebSocket] Received opponent duel move (keeping secret):', data.move);
            store.setOpponentMove(data.move);
            
            // Check if both moves have been submitted
            if (store.myDuelMove && store.opponentDuelMove) {
                console.log('[WebSocket] Both moves submitted, setting flag');
                store.setBothMovesSubmitted(true);
            }
            
            // Don't add message to chat - keep the move secret until both are submitted
        } else {
            // This is our own move - check if both moves are now submitted
            if (store.myDuelMove && store.opponentDuelMove) {
                console.log('[WebSocket] Both moves submitted, setting flag');
                store.setBothMovesSubmitted(true);
            }
        }
    }

    private handleDuelCancel(data: { type: 'duel_cancel'; player_id: string; opponent_id: string; room_id: string; timestamp: string }) {
        console.log('[WebSocket] Handling duel cancel:', data);
        const store = useGameStore.getState();
        const player = store.player;

        if (!player) {
            console.error('[WebSocket] Player not found for duel cancel.');
            return;
        }

        if (player.id === data.player_id) {
            // This is the current player's cancel.
            // We need to send it to the opponent.
            this.sendDuelCancel(data.opponent_id);
        } else {
            // This is an opponent's cancel.
            // We need to update the game state in the store.
            // For now, we'll just log it.
            console.log('[WebSocket] Received opponent duel cancel.');
        }
    }

    private handleDuelOutcome(data: { type: 'duel_outcome'; winner_id: string; loser_id: string; analysis: string; room_id: string; timestamp: string }) {
        console.log('[WebSocket] Handling duel outcome:', data);
        const store = useGameStore.getState();
        const player = store.player;

        if (!player) {
            console.error('[WebSocket] Player not found for duel outcome.');
            return;
        }

        // Show both players' moves now that the duel is resolved
        if (store.myDuelMove) {
            store.addMessage({
                player_id: 'system',
                room_id: data.room_id,
                message: `⚔️ You prepared: "${store.myDuelMove}"`,
                message_type: 'system',
                timestamp: data.timestamp
            });
        }
        
        if (store.opponentDuelMove) {
            const opponent = store.duelOpponent;
            const opponentName = opponent?.name || 'Unknown';
            store.addMessage({
                player_id: 'system',
                room_id: data.room_id,
                message: `⚔️ ${opponentName} prepared: "${store.opponentDuelMove}"`,
                message_type: 'system',
                timestamp: data.timestamp
            });
        }

        // Add the analysis to chat
        store.addMessage({
            player_id: 'system',
            room_id: data.room_id,
            message: data.analysis,
            message_type: 'system',
            timestamp: data.timestamp
        });

        // End the duel
        store.endDuel();

        // Add winner/loser message to chat
        if (player.id === data.winner_id) {
            store.addMessage({
                player_id: 'system',
                room_id: data.room_id,
                message: `🏆 ${player.name} won the duel!`,
                message_type: 'system',
                timestamp: data.timestamp
            });
        } else if (player.id === data.loser_id) {
            store.addMessage({
                player_id: 'system',
                room_id: data.room_id,
                message: `💀 ${player.name} lost the duel.`,
                message_type: 'system',
                timestamp: data.timestamp
            });
        } else if (data.winner_id === null || data.winner_id === 'null') {
            store.addMessage({
                player_id: 'system',
                room_id: data.room_id,
                message: `⚔️ The duel ended in a draw!`,
                message_type: 'system',
                timestamp: data.timestamp
            });
        }
    }

    private handleMonsterCombatOutcome(data: {
        round: number;
        monster_name: string;
        player_move: string;
        monster_move: string;
        player_condition: string;
        monster_condition: string;
        narrative: string;
        combat_ends: boolean;
        monster_defeated: boolean;
        player_severity?: number;
    }) {
        console.log('[WebSocket] Handling monster combat outcome:', data);
        const store = useGameStore.getState();
        const player = store.player;

        if (!player) {
            console.error('[WebSocket] Player not found for monster combat outcome.');
            return;
        }

        // Show the combat moves
        store.addMessage({
            player_id: 'system',
            room_id: player.current_room,
            message: `⚔️ Round ${data.round}: You attempt "${data.player_move}"`,
            message_type: 'system',
            timestamp: new Date().toISOString()
        });

        store.addMessage({
            player_id: 'system',
            room_id: player.current_room,
            message: `⚔️ ${data.monster_name} ${data.monster_move}`,
            message_type: 'system',
            timestamp: new Date().toISOString()
        });

        // Show the narrative
        store.addMessage({
            player_id: 'system',
            room_id: player.current_room,
            message: data.narrative,
            message_type: 'monster_combat_outcome',
            timestamp: new Date().toISOString()
        });

        // Show result and conditions
        let resultMessage = '';
        if (data.combat_ends) {
            if (data.monster_defeated) {
                resultMessage = `🏆 Victory! You have defeated the ${data.monster_name}!`;
            } else if ((data.player_severity ?? 0) >= 50) {
                resultMessage = `💀 Defeat! The ${data.monster_name} has overwhelmed you...`;
            } else {
                resultMessage = `⚔️ Combat ends. Both combatants withdraw...`;
            }
        } else {
            resultMessage = `⚔️ Combat continues... (Your condition: ${data.player_condition}, ${data.monster_name} condition: ${data.monster_condition})`;
        }

        store.addMessage({
            player_id: 'system',
            room_id: player.current_room,
            message: resultMessage,
            message_type: 'system',
            timestamp: new Date().toISOString()
        });
    }

    private handleDuelRoundResult(data: { 
        type: 'duel_round_result'; 
        round: number; 
        player1_id: string; 
        player2_id: string; 
        player1_move: string; 
        player2_move: string; 
        player1_health?: number; 
        player2_health?: number; 
        player1_control?: number; 
        player2_control?: number; 
        player1_max_health?: number;
        player2_max_health?: number;
        description: string; 
        combat_ends: boolean; 
        room_id: string; 
        timestamp: string; 
    }) {
        console.log('[WebSocket] Handling duel round result:', data);
        const store = useGameStore.getState();
        const player = store.player;

        if (!player) {
            console.error('[WebSocket] Player not found for duel round result.');
            return;
        }

        // Determine if current player is player1 or player2
        const isPlayer1 = player.id === data.player1_id;
        const isPlayer2 = player.id === data.player2_id;

        if (!isPlayer1 && !isPlayer2) {
            console.error('[WebSocket] Current player not found in duel result data.');
            return;
        }

        // Get moves and opponent info based on player perspective
        const myMove = isPlayer1 ? data.player1_move : data.player2_move;
        const opponentMove = isPlayer1 ? data.player2_move : data.player1_move;
        const opponent = store.duelOpponent;
        const opponentName = opponent?.name || 'Unknown';

        // Show what each side prepared
        if (myMove) {
            store.addMessage({
                player_id: 'system',
                room_id: data.room_id,
                message: `⚔️ You prepared: "${myMove}"`,
                message_type: 'system',
                timestamp: data.timestamp
            });
        }
        if (opponentMove) {
            store.addMessage({
                player_id: 'system',
                room_id: data.room_id,
                message: `⚔️ ${opponentName} prepared: "${opponentMove}"`,
                message_type: 'system',
                timestamp: data.timestamp
            });
        }

        // Add the round description to chat
        store.addMessage({
            player_id: 'system',
            room_id: data.room_id,
            message: data.description,
            message_type: 'system',
            timestamp: data.timestamp
        });

        // Update duel clocks based on player perspective
        if (typeof data.player1_health === 'number' && typeof data.player2_health === 'number') {
            const myHealth = isPlayer1 ? data.player1_health : data.player2_health;
            const opponentHealth = isPlayer1 ? data.player2_health : data.player1_health;
            const myControl = isPlayer1 ? (data.player1_control ?? store.player1Control) : (data.player2_control ?? store.player1Control);
            const opponentControl = isPlayer1 ? (data.player2_control ?? store.player2Control) : (data.player1_control ?? store.player2Control);
            
            store.updateDuelClocks(
                myHealth,
                opponentHealth,
                myControl,
                opponentControl
            );
        }

        // Persist dynamic max health for rendering if present
        if (typeof (data as { player1_max_health?: number }).player1_max_health === 'number' || typeof (data as { player2_max_health?: number }).player2_max_health === 'number') {
            try {
                const p1Max = (data as { player1_max_health?: number }).player1_max_health ?? (useGameStore.getState().player1MaxVital ?? 6);
                const p2Max = (data as { player2_max_health?: number }).player2_max_health ?? (useGameStore.getState().player2MaxVital ?? 6);
                
                // Ensure we have valid numbers
                if (typeof p1Max !== 'number' || typeof p2Max !== 'number') {
                    console.error('[WebSocket] Invalid max health values:', { p1Max, p2Max });
                    return;
                }
                
                // Set max health based on player perspective
                const myMaxHealth = isPlayer1 ? p1Max : p2Max;
                const opponentMaxHealth = isPlayer1 ? p2Max : p1Max;
                
                // Ensure the computed values are valid numbers
                if (typeof myMaxHealth === 'number' && typeof opponentMaxHealth === 'number') {
                    useGameStore.getState().setMaxVitals(myMaxHealth, opponentMaxHealth);
                } else {
                    console.error('[WebSocket] Invalid computed max health values:', { myMaxHealth, opponentMaxHealth, isPlayer1 });
                }
            } catch (error) {
                console.error('[WebSocket] Error setting max health:', error);
            }
        }

        if (data.combat_ends) {
            // Combat is over - end the duel
            store.endDuel();
        } else {
            // Combat continues - prepare for next round
            store.prepareNextRound(data.round + 1);
        }
    }

    private handleDuelNextRound(data: { 
        type: 'duel_next_round'; 
        round: number;
        room_id: string; 
        timestamp: string 
    }) {
        console.log('[WebSocket] Handling duel next round:', data);
        const store = useGameStore.getState();
        const player = store.player;

        if (!player) {
            console.error('[WebSocket] Player not found for duel next round.');
            return;
        }

        // Update duel state for next round
        store.prepareNextRound(data.round);

        // Add a message to chat about the next round
        store.addMessage({
            player_id: 'system',
            room_id: data.room_id,
            message: `🔄 Round ${data.round} begins! Both players prepare their next moves...`,
            message_type: 'system',
            timestamp: data.timestamp
        });
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
            store.addVisitedCoordinate(room.x, room.y, room.biome);

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
                biome: room.biome,
                players: store.playersInRoom, // Use current player list
                monsters: [], // Will be populated by room info API
                atmospheric_presence: '',
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

            // Clear room generation state if the room is ready
            if (room.image_status === 'ready' || room.image_status === 'content_ready') {
                console.log('[WebSocket] Room is ready, clearing generation state');
                store.setIsRoomGenerating(false);
            }

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
            store.addVisitedCoordinate(room.x, room.y, room.biome);

            // Add room description to chat if this is a new room
            if (this.nextRoomId === room.id) {
                console.log('[WebSocket] Adding room description for new room with atmospheric presence');
                
                // Get atmospheric presence from room info API
                apiService.getRoomInfo(room.id)
                    .then((roomInfo: { atmospheric_presence?: string; players?: Player[]; monsters?: unknown[] }) => {
                        const atmosphericPresence = roomInfo.atmospheric_presence || '';
                        console.log('[WebSocket] Got atmospheric presence for room message:', atmosphericPresence);
                        
                        const roomMessage: ChatMessage = {
                            player_id: 'system',
                            room_id: room.id,
                            message: '',
                            message_type: 'room_description',
                            timestamp: new Date().toISOString(),
                            title: room.title,
                            description: room.description,
                            biome: room.biome,
                            players: roomInfo.players || [],
                            monsters: (roomInfo.monsters as Monster[]) || [],
                            atmospheric_presence: atmosphericPresence,
                            x: room.x,
                            y: room.y
                        };
                        store.addMessage(roomMessage);
                        
                        // Clear nextRoomId after successfully adding the message
                        this.nextRoomId = null;
                    })
                    .catch((error: Error) => {
                        console.error('[WebSocket] Failed to get room info for atmospheric presence:', error);
                        // Fallback: add room message without atmospheric presence
                        const roomMessage: ChatMessage = {
                            player_id: 'system',
                            room_id: room.id,
                            message: '',
                            message_type: 'room_description',
                            timestamp: new Date().toISOString(),
                            title: room.title,
                            description: room.description,
                            biome: room.biome,
                            players: store.playersInRoom,
                            monsters: [],
                            x: room.x,
                            y: room.y
                        };
                        store.addMessage(roomMessage);
                        
                        // Clear nextRoomId after adding fallback message too
                        this.nextRoomId = null;
                    });
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

            // Filter out null/undefined values and the current player from the list
            const otherPlayerIds = playerIds.filter(id => id && id !== currentPlayer?.id);
            
            if (otherPlayerIds.length === 0) {
                store.setPlayersInRoom([]);
                return;
            }
            
            // Fetch player data for all other players in the room
            const playerPromises = otherPlayerIds.map(async (playerId) => {
                try {
                    console.log(`[WebSocket] Fetching player data for: ${playerId}`);
                    const apiService = (await import('./api')).default;
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    const playerData = await (apiService as any).request(`/players/${playerId}`, {
                        method: 'GET'
                    });
                    console.log(`[WebSocket] Successfully fetched player data for ${playerId}:`, playerData.name);
                    return playerData;
                } catch (error) {
                    console.error(`[WebSocket] Failed to fetch player ${playerId}:`, error);
                    return null;
                }
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
            // CRITICAL: When updating current player, preserve health and inventory to prevent
            // stale data from overwriting fresh state (e.g., after death/respawn, during movement)
            const store = useGameStore.getState();
            const currentPlayer = store.player;

            if (currentPlayer) {
                // Merge incoming updates with current state, preferring current health and inventory
                const mergedPlayer = {
                    ...player,
                    // Prefer current health if it's set (prevents overwrites from stale data)
                    health: currentPlayer.health !== undefined ? currentPlayer.health : player.health,
                    // Preserve current inventory if incoming update doesn't include it (prevents inventory loss during movement/other updates)
                    inventory: player.inventory !== undefined ? player.inventory : currentPlayer.inventory
                };
                console.log('[WebSocket] Updating current player with health and inventory safeguard:', {
                    incomingHealth: player.health,
                    currentHealth: currentPlayer.health,
                    finalHealth: mergedPlayer.health,
                    hasIncomingInventory: player.inventory !== undefined,
                    inventoryCount: mergedPlayer.inventory?.length || 0
                });
                store.setPlayer(mergedPlayer);
            } else {
                // No current player state, use incoming data as-is
                console.log('[WebSocket] No current player state, using incoming data');
                store.setPlayer(player);
            }
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

    sendDuelChallenge(targetPlayerId: string) {
        if (!this.socket || !this.roomId || !this.playerId) {
            console.error('[WebSocket] Cannot send duel challenge - missing required data');
            return;
        }

        const duelMessage = {
            type: 'duel_challenge',
            challenger_id: this.playerId,
            target_id: targetPlayerId,
            room_id: this.roomId,
            timestamp: new Date().toISOString()
        };

        console.log('[WebSocket] Sending duel challenge to:', targetPlayerId);
        this.socket.send(JSON.stringify(duelMessage));
    }

    sendDuelResponse(challengerId: string, response: 'accept' | 'decline') {
        if (!this.socket || !this.roomId || !this.playerId) return;

        const duelResponse = {
            type: 'duel_response',
            challenger_id: challengerId,
            responder_id: this.playerId,
            response,
            room_id: this.roomId,
            timestamp: new Date().toISOString()
        };

        this.socket.send(JSON.stringify(duelResponse));
    }

    sendDuelMove(opponentId: string, move: string) {
        if (!this.socket || !this.roomId || !this.playerId) return;

        const duelMove = {
            type: 'duel_move',
            player_id: this.playerId,
            opponent_id: opponentId,
            move,
            room_id: this.roomId,
            timestamp: new Date().toISOString()
        };

        this.socket.send(JSON.stringify(duelMove));
    }

    sendDuelCancel(opponentId: string) {
        if (!this.socket || !this.roomId || !this.playerId) return;

        const duelCancel = {
            type: 'duel_cancel',
            player_id: this.playerId,
            opponent_id: opponentId,
            room_id: this.roomId,
            timestamp: new Date().toISOString()
        };

        this.socket.send(JSON.stringify(duelCancel));
    }

    private handlePlayerDeath(data: { message: string; new_room: Room; player?: Player; timestamp: string }) {
        console.log('[WebSocket] Handling player death:', data);
        
        // Add death message to chat
        const deathMessage: ChatMessage = {
            player_id: 'system',
            room_id: this.roomId || '',
            message: data.message,
            message_type: 'system',
            timestamp: data.timestamp
        };
        useGameStore.getState().addMessage(deathMessage);
        
        // Update player's current room to the spawn room
        if (data.new_room) {
            const store = useGameStore.getState();
            console.log('[WebSocket] Player teleported to spawn room:', data.new_room.id);
            
            // Update player state if provided (includes health restoration, immunity, etc.)
            if (data.player && store.player) {
                // CRITICAL: Preserve inventory when updating player after death
                const currentInventory = store.player.inventory;
                const updatedPlayer = {
                    ...store.player,
                    ...data.player,
                    // Preserve inventory if not included in death update
                    inventory: data.player.inventory !== undefined ? data.player.inventory : currentInventory
                } as Player;
                store.setPlayer(updatedPlayer);
                console.log('[WebSocket] Updated player state after death:', {
                    health: updatedPlayer.health,
                    rejoin_immunity: updatedPlayer.rejoin_immunity,
                    current_room: updatedPlayer.current_room,
                    inventoryCount: updatedPlayer.inventory?.length || 0
                });
            }
            
            // Set pending room update BEFORE disconnecting
            // This ensures the room_update from server will be properly applied
            this.pendingRoomUpdate = data.new_room;
            
            // Disconnect from current room and reconnect to spawn room
            const savedPlayerId = this.playerId; // Save playerId before disconnect clears it
            this.disconnect();
            
            // Set reconnection state AFTER disconnect (which resets it to false)
            this.isReconnecting = true;
            
            this.connect(data.new_room.id, savedPlayerId!);
        }
    }


}

// Create a singleton instance
const websocketService = new WebSocketService();
export default websocketService;