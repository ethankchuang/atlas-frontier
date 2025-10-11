import { create } from 'zustand';
import { Player, Room, NPC, GameState, ChatMessage, Item } from '@/types/game';
import { User } from '@/types/auth';

// Duel combat constants
export const DUEL_MAX_HEALTH = 5;
export const DUEL_MAX_ADVANTAGE = 3;

// Extend ChatMessage type to support streaming
interface ExtendedChatMessage extends ChatMessage {
    id?: string;
    isStreaming?: boolean;
}

interface GameStore {
    // Authentication state
    user: User | null;
    setUser: (user: User | null) => void;
    isAuthenticated: boolean;
    setIsAuthenticated: (authenticated: boolean) => void;

    // Player state
    player: Player | null;
    setPlayer: (player: Player | null) => void;

    // Room state
    currentRoom: Room | null;
    setCurrentRoom: (room: Room) => void;

    // NPCs in current room
    npcs: NPC[];
    setNPCs: (npcs: NPC[]) => void;

    // Other players in room
    playersInRoom: Player[];
    setPlayersInRoom: (players: Player[]) => void;

    // Game state
    gameState: GameState | null;
    setGameState: (state: GameState) => void;

    // Chat messages
    messages: ExtendedChatMessage[];
    addMessage: (message: ExtendedChatMessage) => void;
    updateMessage: (id: string, updater: (prev: ExtendedChatMessage) => ExtendedChatMessage) => void;

    // Minimap state - track visited coordinates
    visitedCoordinates: Set<string>;
    addVisitedCoordinate: (x: number, y: number, biome?: string) => void;
    isCoordinateVisited: (x: number, y: number) => boolean;

    // Biome state - track biome for each visited coordinate
    visitedBiomes: { [key: string]: string };

    // Biome colors - track color for each biome
    biomeColors: { [key: string]: string };
    setBiomeColors: (colors: { [key: string]: string }) => void;

    // Connection state
    isConnected: boolean;
    setIsConnected: (connected: boolean) => void;

    // Loading states
    isLoading: boolean;
    setIsLoading: (loading: boolean) => void;
    
    // Movement loading state
    isMovementLoading: boolean;
    setIsMovementLoading: (loading: boolean) => void;

    // Movement animation states
    isAttemptingMovement: boolean;
    setIsAttemptingMovement: (attempting: boolean) => void;
    showMovementAnimation: boolean;
    setShowMovementAnimation: (show: boolean) => void;
    movementFailed: boolean;
    setMovementFailed: (failed: boolean) => void;

    // Room generation loading state (for rooms that aren't preloaded yet)
    isRoomGenerating: boolean;
    setIsRoomGenerating: (generating: boolean) => void;

    // Error state
    error: string | null;
    setError: (error: string | null) => void;

    // Minimap fullscreen state
    isMinimapFullscreen: boolean;
    setIsMinimapFullscreen: (fullscreen: boolean) => void;

    // Pause/Menu state
    isMenuOpen: boolean;
    setIsMenuOpen: (open: boolean) => void;
    isInventoryOpen: boolean;
    setIsInventoryOpen: (open: boolean) => void;

    // Item registry for client-side lookup
    itemsById: { [id: string]: Item };
    upsertItems: (items: Item[]) => void;

    // Duel challenge state
    duelChallenge: { challengerName: string; challengerId: string } | null;
    setDuelChallenge: (challenge: { challengerName: string; challengerId: string } | null) => void;

    // Duel state
    isInDuel: boolean;
    duelOpponent: { id: string; name: string } | null;
    myDuelMove: string | null;
    opponentDuelMove: string | null;
    bothMovesSubmitted: boolean;
    currentRound: number;
    player1Condition: string;
    player2Condition: string;
    // Health/Control clocks
    player1Vital: number;  // Keep as vital for compatibility, but represents health
    player2Vital: number;  // Keep as vital for compatibility, but represents health
    player1Control: number;
    player2Control: number;
    player1MaxVital?: number;  // Keep as MaxVital for compatibility, but represents max health
    player2MaxVital?: number;  // Keep as MaxVital for compatibility, but represents max health
    setMaxVitals: (p1Max: number, p2Max: number) => void;
    
    // Duel actions
    startDuel: (opponent: { id: string; name: string }) => void;
    submitDuelMove: (move: string) => void;
    setOpponentMove: (move: string) => void;
    setBothMovesSubmitted: (submitted: boolean) => void;
    updateDuelConditions: (player1Condition: string, player2Condition: string) => void;
    updateDuelClocks: (p1Vital: number, p2Vital: number, p1Control: number, p2Control: number) => void;
    prepareNextRound: (round: number) => void;
    endDuel: () => void;
    forceClearDuelState: () => void;
}

function pastelColorFromString(str: string) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = hash % 360;
    return `hsl(${h}, 60%, 80%)`;
}

const useGameStore = create<GameStore>((set, get) => ({
    // Authentication state
    user: null,
    isAuthenticated: false,

    // Initial states
    player: null,
    currentRoom: null,
    npcs: [],
    playersInRoom: [],
    gameState: null,
    messages: [],
    visitedCoordinates: new Set<string>(),
    visitedBiomes: {}, // NEW: mapping from 'x,y' to biome
    biomeColors: {}, // NEW: mapping from biome name to color
    isConnected: false,
    isLoading: false,
    isMovementLoading: false,
    isAttemptingMovement: false,
    showMovementAnimation: false,
    movementFailed: false,
    isRoomGenerating: false,
    error: null,
    isMinimapFullscreen: false,
    
    // Menu/Inventory state
    isMenuOpen: false,
    isInventoryOpen: false,

    // Item registry
    itemsById: {},

    duelChallenge: null,
    isInDuel: false,
    duelOpponent: null,
    myDuelMove: null,
    opponentDuelMove: null,
    bothMovesSubmitted: false,
    currentRound: 1,
    player1Condition: "Healthy",
    player2Condition: "Healthy",
    // Health/Control - Health starts at DUEL_MAX_HEALTH, Control starts at 0
    player1Vital: DUEL_MAX_HEALTH,  // represents health
    player2Vital: DUEL_MAX_HEALTH,  // represents health
    player1Control: 0,
    player2Control: 0,
    player1MaxVital: DUEL_MAX_HEALTH,
    player2MaxVital: DUEL_MAX_HEALTH,

    // Auth setters
    setUser: (user) => set({ user }),
    setIsAuthenticated: (isAuthenticated) => set({ isAuthenticated }),

    // Setters  
    setPlayer: (player) => set({ player }),
    setCurrentRoom: (room) => set((state) => {
        const coordKey = `${room.x},${room.y}`;
        const newVisitedCoordinates = new Set(state.visitedCoordinates);
        newVisitedCoordinates.add(coordKey);
        const newVisitedBiomes = { ...state.visitedBiomes };
        const newBiomeColors = { ...state.biomeColors };
        if (room.biome) {
            newVisitedBiomes[coordKey] = room.biome;
            // Use AI-generated color if available, otherwise fallback to pastel
            if (!newBiomeColors[room.biome]) {
                newBiomeColors[room.biome] = room.biome_color || pastelColorFromString(room.biome);
            }
        }
        return {
            currentRoom: room,
            visitedCoordinates: newVisitedCoordinates,
            visitedBiomes: newVisitedBiomes,
            biomeColors: newBiomeColors,
        };
    }),
    setNPCs: (npcs) => set({ npcs }),
    setPlayersInRoom: (players) => set({ playersInRoom: players }),
    setMaxVitals: (p1Max, p2Max) => set({ player1MaxVital: p1Max, player2MaxVital: p2Max }),
    setGameState: (state) => set({ gameState: state }),
    addMessage: (message) => set((state) => ({
        messages: [...state.messages, message]
    })),
    updateMessage: (id, updater) => set((state) => ({
        messages: state.messages.map((msg) =>
            msg.id === id ? updater(msg) : msg
        )
    })),
    // Minimap functions
    addVisitedCoordinate: (x: number, y: number, biome?: string) => set((state) => {
        const coordKey = `${x},${y}`;
        const newVisitedCoordinates = new Set(state.visitedCoordinates);
        newVisitedCoordinates.add(coordKey);
        const newVisitedBiomes = { ...state.visitedBiomes };
        const newBiomeColors = { ...state.biomeColors };
        if (biome) {
            newVisitedBiomes[coordKey] = biome;
            // Use pastel fallback for coordinates added without room data
            if (!newBiomeColors[biome]) {
                newBiomeColors[biome] = pastelColorFromString(biome);
            }
        }
        
        // Sync to server if we have a player
        if (state.player) {
            const biomeColor = biome ? newBiomeColors[biome] : undefined;
            // Don't await this - let it run in background
            import('../services/api').then(apiModule => {
                apiModule.default.markCoordinateVisited(state.player!.id, x, y, biome, biomeColor)
                    .catch(error => console.warn('[GameStore] Failed to sync coordinate to server:', error));
            });
        }
        
        return { visitedCoordinates: newVisitedCoordinates, visitedBiomes: newVisitedBiomes, biomeColors: newBiomeColors };
    }),
    isCoordinateVisited: (x: number, y: number) => {
        const state = get();
        const coordKey = `${x},${y}`;
        return state.visitedCoordinates.has(coordKey);
    },
    setBiomeColors: (colors) => set({ biomeColors: colors }),
    setIsConnected: (connected) => set({ isConnected: connected }),
    setIsLoading: (loading) => set({ isLoading: loading }),
    setIsMovementLoading: (loading) => set({ isMovementLoading: loading }),
    setIsAttemptingMovement: (attempting) => set({ isAttemptingMovement: attempting }),
    setShowMovementAnimation: (show) => set({ showMovementAnimation: show }),
    setMovementFailed: (failed) => set({ movementFailed: failed }),
    setIsRoomGenerating: (generating) => set({ isRoomGenerating: generating }),
    setError: (error) => set({ error }),
    setIsMinimapFullscreen: (fullscreen) => set({ isMinimapFullscreen: fullscreen }),

    // Menu/Inventory actions
    setIsMenuOpen: (open) => set({ isMenuOpen: open }),
    setIsInventoryOpen: (open) => set({ isInventoryOpen: open }),

    // Items registry actions
    upsertItems: (items: Item[]) => set((state) => {
        const updated = { ...state.itemsById };
        for (const item of items || []) {
            if (item && item.id) {
                updated[item.id] = item;
            }
        }
        return { itemsById: updated };
    }),
    setDuelChallenge: (challenge) => set({ duelChallenge: challenge }),
    
    // Duel actions
    startDuel: (opponent) => {
        console.log('[GameStore] Starting duel with opponent:', opponent);
        const state = get();
        set({
            isInDuel: true,
            duelOpponent: opponent,
            myDuelMove: null,
            opponentDuelMove: null,
            bothMovesSubmitted: false,
            currentRound: 1,
            player1Condition: "Healthy",
            player2Condition: "Healthy",
            // Reset health to maximum values when starting duel
            player1Vital: state.player1MaxVital ?? DUEL_MAX_HEALTH,
            player2Vital: state.player2MaxVital ?? DUEL_MAX_HEALTH,
            player1Control: 0,
            player2Control: 0,
        });
        console.log('[GameStore] Duel state updated');
    },
    submitDuelMove: (move) => set((state) => {
        const newState: Partial<GameStore> = { 
            myDuelMove: move,
            bothMovesSubmitted: false
        };
        
        // If opponent has already submitted their move, both moves are ready
        if (state.opponentDuelMove) {
            newState.bothMovesSubmitted = true;
        }
        
        return newState;
    }),
    setOpponentMove: (move) => set((state) => {
        const newState: Partial<GameStore> = { opponentDuelMove: move };
        
        // If current player has already submitted their move, both moves are ready
        if (state.myDuelMove) {
            newState.bothMovesSubmitted = true;
        }
        
        return newState;
    }),
    setBothMovesSubmitted: (submitted) => set({ bothMovesSubmitted: submitted }),
    updateDuelConditions: (player1Condition, player2Condition) => set({ player1Condition, player2Condition }),
    updateDuelClocks: (p1Vital: number, p2Vital: number, p1Control: number, p2Control: number) => set({ player1Vital: p1Vital, player2Vital: p2Vital, player1Control: p1Control, player2Control: p2Control }),
    prepareNextRound: (round) => set({ 
        currentRound: round,
        myDuelMove: null,
        opponentDuelMove: null,
        bothMovesSubmitted: false
    }),
    endDuel: () => set({
        isInDuel: false,
        duelOpponent: null,
        myDuelMove: null,
        opponentDuelMove: null,
        bothMovesSubmitted: false,
        currentRound: 1,
        player1Condition: "Healthy",
        player2Condition: "Healthy",
        player1Vital: 0,
        player2Vital: 0,
        player1Control: 0,
        player2Control: 0,
        player1MaxVital: DUEL_MAX_HEALTH,
        player2MaxVital: DUEL_MAX_HEALTH,
    }),
    forceClearDuelState: () => {
        console.log('[GameStore] Force clearing all duel state');
        set({
            isInDuel: false,
            duelOpponent: null,
            myDuelMove: null,
            opponentDuelMove: null,
            bothMovesSubmitted: false,
            currentRound: 1,
            player1Condition: "Healthy",
            player2Condition: "Healthy",
            player1Vital: DUEL_MAX_HEALTH,
            player2Vital: DUEL_MAX_HEALTH,
            player1Control: 0,
            player2Control: 0,
            player1MaxVital: DUEL_MAX_HEALTH,
            player2MaxVital: DUEL_MAX_HEALTH,
            duelChallenge: null
        });
        console.log('[GameStore] Force cleared all duel state');
    },
}));

export default useGameStore;