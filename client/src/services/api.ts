import { ActionRequest, ActionResponse, ChatMessage, GameState, NPCInteraction, Player, RoomInfo, Monster } from '@/types/game';
import useGameStore from '@/store/gameStore';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class APIService {
    private async request<T>(
        endpoint: string,
        options: RequestInit = {}
    ): Promise<T> {
        const response = await fetch(`${API_URL}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'An error occurred');
        }

        return response.json();
    }

    // Game initialization
    async startGame(): Promise<GameState> {
        return this.request<GameState>('/start', {
            method: 'POST',
        });
    }

    // Player management
    async createPlayer(name: string): Promise<Player> {
        return this.request<Player>('/player', {
            method: 'POST',
            body: JSON.stringify({ name }),
        });
    }

    // Room information
    async getRoomInfo(roomId: string): Promise<RoomInfo> {
        try {
            return await this.request<RoomInfo>(`/room/${roomId}`);
        } catch (error) {
            console.error('[API] Failed to get room info:', error);
            // If room not found, try to get player's current room
            if (error instanceof Error && error.message.includes('Room not found')) {
                const store = useGameStore.getState();
                const player = store.player;
                if (player && player.current_room && player.current_room !== roomId) {
                    console.log('[API] Attempting to recover by fetching player\'s current room:', player.current_room);
                    return this.request<RoomInfo>(`/room/${player.current_room}`);
                }
            }
            throw error;
        }
    }

    // Action processing with streaming
    async processActionStream(
        action: ActionRequest,
        onChunk: (chunk: string) => void,
        onFinal: (response: ActionResponse) => void,
        onError: (error: string) => void
    ): Promise<void> {
        try {
            const store = useGameStore.getState();
            
            // Check if this is a movement action
            const isMovement = /(north|south|east|west|up|down|move)/i.test(action.action);
            
            // Don't set movement loading state here - we'll determine it based on backend response
            // The loading spinner should only show when the room is actually being generated
            
            const response = await fetch(`${API_URL}/action/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'text/event-stream',
                },
                body: JSON.stringify(action),
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('[API] Stream error response:', errorText);
                
                // Clear movement loading state on error
                if (isMovement) {
                    store.setIsMovementLoading(false);
                }
                
                if (response.status === 404) {
                    // Room not found - try to recover
                    const player = store.player;
                    if (player && player.current_room) {
                        console.log('[API] Room error detected. Attempting to reconnect to current room:', player.current_room);
                        const websocketService = (await import('./websocket')).default;

                        // First try to get the current room info
                        try {
                            const roomInfo = await this.getRoomInfo(player.current_room);
                            store.setCurrentRoom(roomInfo.room);
                            store.setNPCs(roomInfo.npcs);
                            store.setPlayersInRoom(roomInfo.players);

                            // Reconnect WebSocket to current room
                            websocketService.setNextRoom(player.current_room);
                            websocketService.disconnect();
                            websocketService.connect(player.current_room, player.id);

                            onError('Room transition failed. Staying in current room.');
                        } catch (roomError) {
                            console.error('[API] Failed to recover room state:', roomError);
                            onError('Failed to recover room state. Please refresh the page.');
                        }
                        return;
                    }
                }
                onError(errorText);
                return;
            }

            const reader = response.body?.getReader();
            if (!reader) {
                throw new Error('No response body');
            }

            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.slice(6);
                        if (dataStr.trim() === '') continue;

                        let data;
                        try {
                            data = JSON.parse(dataStr);
                        } catch (e) {
                            console.error('[API] Failed to parse stream data:', dataStr);
                            continue;
                        }

                        if (data.error) {
                            console.error('[API] Stream error:', data.error);
                            
                            // Clear movement loading state on error
                            if (isMovement) {
                                store.setIsMovementLoading(false);
                            }
                            
                            // Graceful user-facing message
                            onError('That didn’t go through. Please try again.');
                            
                            if (typeof data.error === 'string' && data.error.includes('Room not found')) {
                                const player = store.player;
                                if (player && player.current_room) {
                                    console.log('[API] Room error detected. Attempting to reconnect to current room:', player.current_room);
                                    const websocketService = (await import('./websocket')).default;

                                    // First try to get the current room info
                                    try {
                                        const roomInfo = await this.getRoomInfo(player.current_room);
                                        store.setCurrentRoom(roomInfo.room);
                                        store.setNPCs(roomInfo.npcs);
                                        store.setPlayersInRoom(roomInfo.players);

                                        // Reconnect WebSocket to current room
                                        websocketService.setNextRoom(player.current_room);
                                        websocketService.disconnect();
                                        websocketService.connect(player.current_room, player.id);

                                        onError('Room transition failed. Staying in current room.');
                                    } catch (roomError) {
                                        console.error('[API] Failed to recover room state:', roomError);
                                        onError('Failed to recover room state. Please refresh the page.');
                                    }
                                    return;
                                }
                            }
                            onError(data.error);
                            return;
                        }
                        if (data.type === 'chunk') {
                            onChunk(data.content);
                        } else if (data.type === 'final') {
                            // Guard against malformed updates by ensuring object shape
                            if (data.updates && typeof data.updates !== 'object') {
                                console.warn('[API] Malformed updates payload; prompting retry');
                                onError('That didn’t go through. Please try again.');
                                return;
                            }
                            console.log('[API] Final stream data:', data);

                            // Handle room generation status
                            if (data.updates?.room_generation) {
                                const roomGen = data.updates.room_generation;
                                console.log('[API] Room generation status:', roomGen);
                                
                                if (roomGen.is_generating) {
                                    console.log('[API] Room is being generated, showing loading spinner');
                                    store.setIsRoomGenerating(true);
                                } else {
                                    console.log('[API] Room is ready, hiding loading spinner');
                                    store.setIsRoomGenerating(false);
                                }
                            }

                            // Upsert any newly created item from updates to populate inventory UI
                            if (data.updates?.new_item) {
                                const store = useGameStore.getState();
                                store.upsertItems([data.updates.new_item]);
                            }

                            // Handle room change
                            if (data.updates?.player?.current_room) {
                                const newRoomId = data.updates.player.current_room;
                                console.log('[API] Player moved to new room:', newRoomId);

                                // First update game state
                                onFinal({
                                    success: true,
                                    message: data.content,
                                    updates: data.updates || {}
                                });

                                // Then update WebSocket's roomId and reconnect
                                const websocketService = (await import('./websocket')).default;
                                websocketService.setNextRoom(newRoomId);
                                websocketService.disconnect();
                                websocketService.connect(newRoomId, action.player_id);
                            } else {
                                onFinal({
                                    success: true,
                                    message: data.content,
                                    updates: data.updates || {}
                                });
                            }
                        }
                    }
                }
            }
                    } catch (error) {
                console.error('[API] Stream error:', error);
                
                // Clear movement loading state on error
                const store = useGameStore.getState();
                const isMovement = /(north|south|east|west|up|down|move)/i.test(action.action);
                if (isMovement) {
                    store.setIsMovementLoading(false);
                }
                
                onError('That didn’t go through. Please try again.');
            }
    }

    // Legacy action processing - REMOVED
    // Now only using streaming endpoint for all actions

    // Player presence
    async updatePresence(playerId: string, roomId: string): Promise<{ success: boolean }> {
        return this.request<{ success: boolean }>('/presence', {
            method: 'POST',
            body: JSON.stringify({ player_id: playerId, room_id: roomId })
        });
    }

    // Chat
    async sendChat(message: ChatMessage): Promise<{ success: boolean }> {
        return this.request<{ success: boolean }>('/chat', {
            method: 'POST',
            body: JSON.stringify(message),
        });
    }

    // NPC interaction
    async interactWithNPC(
        interaction: NPCInteraction
    ): Promise<{ success: boolean; response: string }> {
        return this.request<{ success: boolean; response: string }>('/npc', {
            method: 'POST',
            body: JSON.stringify(interaction),
        });
    }

    // Health check
    async healthCheck(): Promise<{ status: string }> {
        return this.request<{ status: string }>('/health');
    }
}

// Create a singleton instance
const apiService = new APIService();
export default apiService;