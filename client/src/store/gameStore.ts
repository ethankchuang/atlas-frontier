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

    // Connection state
    isConnected: boolean;
    setIsConnected: (connected: boolean) => void;

    // Loading states
    isLoading: boolean;
    setIsLoading: (loading: boolean) => void;

    // Error state
    error: string | null;
    setError: (error: string | null) => void;
}

const useGameStore = create<GameStore>((set) => ({
    // Initial states
    player: null,
    currentRoom: null,
    npcs: [],
    playersInRoom: [],
    gameState: null,
    messages: [],
    isConnected: false,
    isLoading: false,
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
    setIsConnected: (connected) => set({ isConnected: connected }),
    setIsLoading: (loading) => set({ isLoading: loading }),
    setError: (error) => set({ error })
}));

export default useGameStore;