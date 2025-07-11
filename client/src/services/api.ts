import { ActionRequest, ActionResponse, ChatMessage, GameState, NPCInteraction, Player, RoomInfo } from '@/types/game';
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
            const response = await fetch(`${API_URL}/action/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(action),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to process action');
            }

            const reader = response.body!.getReader();
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
                        const data = JSON.parse(line.slice(6));
                        if (data.error) {
                            console.error('[API] Stream error:', data.error);
                            // If room not found, try to recover
                            if (data.error.includes('Room not found') || data.error.includes('Destination room')) {
                                const store = useGameStore.getState();
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
                            console.log('[API] Final stream data:', data);

                            // Handle room change
                            if (data.updates?.player?.current_room) {
                                const newRoomId = data.updates.player.current_room;
                                console.log('[API] Player moved to new room:', newRoomId);

                                // First update game state
                                onFinal({
                                    success: true,
                                    message: data.content,
                                    updates: data.updates
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
                                    updates: data.updates
                                });
                            }
                        }
                    }
                }
            }
        } catch (error) {
            console.error('[API] Stream error:', error);
            onError(error instanceof Error ? error.message : 'An error occurred');
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