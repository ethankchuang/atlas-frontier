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
    addVisitedCoordinate: (x: number, y: number) => void;
    isCoordinateVisited: (x: number, y: number) => boolean;

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
    isConnected: false,
    isLoading: false,
    isMovementLoading: false,
    isRoomGenerating: false,
    error: null,

    // Setters
    setPlayer: (player) => set({ player }),
    setCurrentRoom: (room) => set({ currentRoom: room }),
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
    addVisitedCoordinate: (x: number, y: number) => set((state) => {
        const coordKey = `${x},${y}`;
        const newVisitedCoordinates = new Set(state.visitedCoordinates);
        newVisitedCoordinates.add(coordKey);
        return { visitedCoordinates: newVisitedCoordinates };
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
    setError: (error) => set({ error })
}));

export default useGameStore;