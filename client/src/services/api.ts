import { ActionRequest, ActionResponse, ChatMessage, GameState, NPCInteraction, Player, RoomInfo, Item } from '@/types/game';
import { AuthResponse, RegisterRequest, LoginRequest, RegisterResponse, User, UsernameAvailability } from '@/types/auth';
import useGameStore from '@/store/gameStore';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class APIService {
    private getAuthToken(): string | null {
        if (typeof window === 'undefined') return null;
        return localStorage.getItem('auth_token');
    }

    private setAuthToken(token: string): void {
        if (typeof window !== 'undefined') {
            localStorage.setItem('auth_token', token);
        }
    }

    private clearAuthToken(): void {
        if (typeof window !== 'undefined') {
            localStorage.removeItem('auth_token');
        }
    }

    private async request<T>(
        endpoint: string,
        options: RequestInit & { skipAuth?: boolean } = {}
    ): Promise<T> {
        const token = this.getAuthToken();
        const headers: HeadersInit = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        // Always send auth header if token exists (including for anonymous users)
        const gameStore = useGameStore.getState();
        const isAnonymous = gameStore.user?.is_anonymous || false;
        
        // Debug logging
        console.log('[API] Request debug:', {
            endpoint,
            hasToken: !!token,
            userId: gameStore.user?.id,
            isAnonymous,
            skipAuth: options.skipAuth,
            willSendAuth: !!token
        });
        
        // Add auth header if token exists
        if (token) {
            (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`${API_URL}${endpoint}`, {
            ...options,
            headers,
        });

        if (!response.ok) {
            const error = await response.json();
            
            // Clear token if unauthorized
            if (response.status === 401) {
                this.clearAuthToken();
            }
            
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

    // Player management is now handled through authentication

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
            
            const token = this.getAuthToken();
            const headers: HeadersInit = {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
            };

            // Check if current user is anonymous - same logic as main request method
            const isAnonymous = store.user?.is_anonymous || false;
            
            // Debug logging for stream requests
            console.log('[API] Stream request debug:', {
                endpoint: '/action/stream',
                hasToken: !!token,
                userId: store.user?.id,
                isAnonymous,
                willSendAuth: !!token
            });
            
            // Add auth header if token exists
            if (token) {
                (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
            }

            // For streaming, we need to make a direct call but through our proxy
            const response = await fetch('/api/game/action/stream', {
                method: 'POST',
                headers,
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
                        } catch (error) {
                            console.error('[API] Failed to parse stream data:', dataStr, error);
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
                                console.log('[API] Processing new_item update:', data.updates.new_item);
                                const store = useGameStore.getState();
                                store.upsertItems([data.updates.new_item]);
                                console.log('[API] Item added to store, current itemsById:', Object.keys(store.itemsById));
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

    // ===============================
    // Authentication Methods
    // ===============================

    async register(data: RegisterRequest): Promise<RegisterResponse> {
        // Use Next.js API route proxy for auth endpoints
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Registration failed');
        }

        return response.json();
    }

    async login(data: LoginRequest): Promise<AuthResponse> {
        // Use Next.js API route proxy for auth endpoints
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }

        const authResponse = await response.json();
        
        // Store the token
        this.setAuthToken(authResponse.access_token);
        
        return authResponse;
    }

    async getProfile(): Promise<User> {
        return this.request<User>('/auth/profile');
    }

    async checkUsernameAvailability(username: string): Promise<UsernameAvailability> {
        return this.request<UsernameAvailability>(`/auth/check-username/${username}`);
    }

    async updateUsername(username: string): Promise<{ username: string; message: string }> {
        return this.request<{ username: string; message: string }>('/auth/username', {
            method: 'PUT',
            body: JSON.stringify({ username }),
        });
    }

    // Player Management Methods
    async getPlayers(): Promise<{ players: Player[] }> {
        return this.request<{ players: Player[] }>('/players');
    }

    async createPlayer(name: string): Promise<{ player: Player }> {
        return this.request<{ player: Player }>('/players', {
            method: 'POST',
            body: JSON.stringify({ name }),
        });
    }

    async joinGame(playerId: string): Promise<{ message: string; player: Player; room: Record<string, unknown> }> {
        // Use guest endpoint for guest players, regular endpoint for authenticated players
        const endpoint = playerId.startsWith('guest_') ? `/join/guest/${playerId}` : `/join/${playerId}`;
        return this.request<{ message: string; player: Player; room: Record<string, unknown> }>(endpoint, {
            method: 'POST',
        });
    }

    async getPlayer(playerId: string): Promise<Player> {
        return this.request<Player>(`/player/${playerId}`);
    }

    async getPlayerMessages(playerId: string, limit: number = 10): Promise<{ messages: ChatMessage[] }> {
        return this.request<{ messages: ChatMessage[] }>(`/player/${playerId}/messages?limit=${limit}`);
    }

    async getPlayerInventory(playerId: string): Promise<{ items: Item[] }> {
        return this.request<{ items: Item[] }>(`/player/${playerId}/inventory`);
    }

    async dropPlayerItem(playerId: string, itemId: string, dropToRoom: boolean = true): Promise<{ success: boolean; message: string; updates: Record<string, unknown> }> {
        return this.request<{ success: boolean; message: string; updates: Record<string, unknown> }>(`/player/${playerId}/drop-item`, {
            method: 'POST',
            body: JSON.stringify({
                item_id: itemId,
                drop_to_room: dropToRoom
            })
        });
    }

    async combinePlayerItems(playerId: string, itemIds: string[], combinationDescription: string = ''): Promise<{ success: boolean; message: string; updates: Record<string, unknown> }> {
        return this.request<{ success: boolean; message: string; updates: Record<string, unknown> }>(`/player/${playerId}/combine-items`, {
            method: 'POST',
            body: JSON.stringify({
                item_ids: itemIds,
                combination_description: combinationDescription
            })
        });
    }

    async getPlayerVisitedCoordinates(playerId: string): Promise<{ 
        visited_coordinates: string[], 
        visited_biomes: { [key: string]: string }, 
        biome_colors: { [key: string]: string } 
    }> {
        return this.request<{ 
            visited_coordinates: string[], 
            visited_biomes: { [key: string]: string }, 
            biome_colors: { [key: string]: string } 
        }>(`/player/${playerId}/visited-coordinates`);
    }

    async markCoordinateVisited(playerId: string, x: number, y: number, biome?: string, biomeColor?: string): Promise<{ success: boolean; message: string }> {
        return this.request<{ success: boolean; message: string }>(`/player/${playerId}/visit-coordinate`, {
            method: 'POST',
            body: JSON.stringify({ x, y, biome, biome_color: biomeColor })
        });
    }

    async clearCombatState(playerId: string): Promise<{ success: boolean; message: string; cleared_duels: number }> {
        return this.request<{ success: boolean; message: string; cleared_duels: number }>(`/player/${playerId}/clear-combat-state`, {
            method: 'POST'
        });
    }

    logout(): void {
        this.clearAuthToken();
    }

    isAuthenticated(): boolean {
        return this.getAuthToken() !== null;
    }

    // ===============================
    // Guest Mode Methods
    // ===============================

    async createGuestPlayer(anonymousUserId: string): Promise<{ player: Player; message: string }> {
        return this.request<{ player: Player; message: string }>('/auth/guest', {
            method: 'POST',
            body: JSON.stringify({ anonymous_user_id: anonymousUserId }),
        });
    }

    async convertGuestToUser(data: {
        email: string;
        password: string;
        username: string;
        guest_player_id: string;
        new_user_id: string;
    }): Promise<AuthResponse & { guest_converted: boolean; message: string }> {
        return this.request<AuthResponse & { guest_converted: boolean; message: string }>('/auth/guest-to-user', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }
}

// Create a singleton instance
const apiService = new APIService();
export default apiService;