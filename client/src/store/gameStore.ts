import { create } from 'zustand';
import { Player, Room, NPC, GameState, ChatMessage } from '@/types/game';

// Extend ChatMessage type to support streaming
interface ExtendedChatMessage extends ChatMessage {
    id?: string;
    isStreaming?: boolean;
}

interface GameStore {
    // Player state
    player: Player | null;
    setPlayer: (player: Player) => void;

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

    // Connection state
    isConnected: boolean;
    setIsConnected: (connected: boolean) => void;

    // Loading states
    isLoading: boolean;
    setIsLoading: (loading: boolean) => void;
    
    // Movement loading state
    isMovementLoading: boolean;
    setIsMovementLoading: (loading: boolean) => void;
    
    // Room generation loading state (for rooms that aren't preloaded yet)
    isRoomGenerating: boolean;
    setIsRoomGenerating: (generating: boolean) => void;

    // Error state
    error: string | null;
    setError: (error: string | null) => void;

    // Minimap fullscreen state
    isMinimapFullscreen: boolean;
    setIsMinimapFullscreen: (fullscreen: boolean) => void;

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
    player1Tags: Array<{ name: string; severity: number; type: 'positive' | 'negative' }>;
    player2Tags: Array<{ name: string; severity: number; type: 'positive' | 'negative' }>;
    player1TotalSeverity: number;
    player2TotalSeverity: number;
    
    // Duel actions
    startDuel: (opponent: { id: string; name: string }) => void;
    submitDuelMove: (move: string) => void;
    setOpponentMove: (move: string) => void;
    setBothMovesSubmitted: (submitted: boolean) => void;
    updateDuelConditions: (player1Condition: string, player2Condition: string) => void;
    updateDuelTags: (player1Tags: any[], player2Tags: any[], player1TotalSeverity: number, player2TotalSeverity: number) => void;
    prepareNextRound: (round: number) => void;
    endDuel: () => void;
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
    isRoomGenerating: false,
    error: null,
    isMinimapFullscreen: false,
    duelChallenge: null,
    isInDuel: false,
    duelOpponent: null,
    myDuelMove: null,
    opponentDuelMove: null,
    bothMovesSubmitted: false,
    currentRound: 1,
    player1Condition: "Healthy",
    player2Condition: "Healthy",
    player1Tags: [],
    player2Tags: [],
    player1TotalSeverity: 0,
    player2TotalSeverity: 0,

    // Setters
    setPlayer: (player) => set({ player }),
    setCurrentRoom: (room) => set((state) => {
        const coordKey = `${room.x},${room.y}`;
        const newVisitedCoordinates = new Set(state.visitedCoordinates);
        newVisitedCoordinates.add(coordKey);
        const newVisitedBiomes = { ...state.visitedBiomes };
        let newBiomeColors = { ...state.biomeColors };
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
        let newBiomeColors = { ...state.biomeColors };
        if (biome) {
            newVisitedBiomes[coordKey] = biome;
            // Use pastel fallback for coordinates added without room data
            if (!newBiomeColors[biome]) {
                newBiomeColors[biome] = pastelColorFromString(biome);
            }
        }
        return { visitedCoordinates: newVisitedCoordinates, visitedBiomes: newVisitedBiomes, biomeColors: newBiomeColors };
    }),
    isCoordinateVisited: (x: number, y: number) => {
        const state = get();
        const coordKey = `${x},${y}`;
        return state.visitedCoordinates.has(coordKey);
    },
    setIsConnected: (connected) => set({ isConnected: connected }),
    setIsLoading: (loading) => set({ isLoading: loading }),
    setIsMovementLoading: (loading) => set({ isMovementLoading: loading }),
    setIsRoomGenerating: (generating) => set({ isRoomGenerating: generating }),
    setError: (error) => set({ error }),
    setIsMinimapFullscreen: (fullscreen) => set({ isMinimapFullscreen: fullscreen }),
    setDuelChallenge: (challenge) => set({ duelChallenge: challenge }),
    
    // Duel actions
    startDuel: (opponent) => {
        console.log('[GameStore] Starting duel with opponent:', opponent);
        set({ 
            isInDuel: true, 
            duelOpponent: opponent, 
            myDuelMove: null,
            opponentDuelMove: null,
            bothMovesSubmitted: false,
            currentRound: 1,
            player1Condition: "Healthy",
            player2Condition: "Healthy",
            player1Tags: [],
            player2Tags: [],
            player1TotalSeverity: 0,
            player2TotalSeverity: 0,
        });
        console.log('[GameStore] Duel state updated');
    },
    submitDuelMove: (move) => set((state) => {
        const newState: any = { 
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
        const newState: any = { opponentDuelMove: move };
        
        // If current player has already submitted their move, both moves are ready
        if (state.myDuelMove) {
            newState.bothMovesSubmitted = true;
        }
        
        return newState;
    }),
    setBothMovesSubmitted: (submitted) => set({ bothMovesSubmitted: submitted }),
    updateDuelConditions: (player1Condition, player2Condition) => set({ player1Condition, player2Condition }),
    updateDuelTags: (player1Tags, player2Tags, player1TotalSeverity, player2TotalSeverity) => set({ player1Tags, player2Tags, player1TotalSeverity, player2TotalSeverity }),
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
        player1Tags: [],
        player2Tags: [],
        player1TotalSeverity: 0,
        player2TotalSeverity: 0,
    })
}));

export default useGameStore;