import React, { useEffect } from 'react';
import useGameStore from '@/store/gameStore';
import RoomDisplay from './RoomDisplay';
import ChatDisplay from './ChatDisplay';
import ChatInput from './ChatInput';
import Minimap from './Minimap';
import FullscreenMinimap from './FullscreenMinimap';
import PlayersInRoom from './PlayersInRoom';
import DuelChallengePopup from './DuelChallengePopup';
import apiService from '@/services/api';
import websocketService from '@/services/websocket';
import { ChatMessage, Room } from '@/types/game';
import PauseMenu from '@/components/PauseMenu';

interface GameLayoutProps {
    playerId: string;
}

const GameLayout: React.FC<GameLayoutProps> = ({ playerId }) => {
    const {
        player,
        setPlayer,
        currentRoom,
        setCurrentRoom,
        setNPCs,
        setPlayersInRoom,
        setIsLoading,
        setError,
        setGameState,
        addVisitedCoordinate,
        isMinimapFullscreen,
        setIsMinimapFullscreen,
        setIsMenuOpen,
        upsertItems,
        isInDuel,
        player1Vital,
        player2Vital,
        player1Control,
        player2Control,
        duelOpponent,
        player1MaxVital,
        player2MaxVital
    } = useGameStore();
    const p1Max = player1MaxVital ?? 6;
    const p2Max = player2MaxVital ?? 6;

    // Initialize game state
    useEffect(() => {
        const initializeGame = async () => {
            try {
                setIsLoading(true);
                console.log('[GameLayout] Initializing game for player:', playerId);

                // Initialize game state
                const gameState = await apiService.startGame();
                setGameState(gameState);

                // Join the game with the specified player
                const joinData = await apiService.joinGame(playerId);
                setPlayer(joinData.player);

                // Set initial room data from join response
                setCurrentRoom(joinData.room as unknown as Room);
                
                // Get full room info with NPCs, items, etc.
                const roomInfo = await apiService.getRoomInfo((joinData.room as unknown as Room).id);
                setCurrentRoom(roomInfo.room);
                setNPCs(roomInfo.npcs);
                setPlayersInRoom(roomInfo.players);
                upsertItems(roomInfo.items || []);

                // Load player's previous messages
                try {
                    const messagesData = await apiService.getPlayerMessages(playerId, 10);
                    const gameStore = useGameStore.getState();
                    // Reverse the messages to display in chronological order (oldest first)
                    const reversedMessages = [...messagesData.messages].reverse();
                    reversedMessages.forEach((message: ChatMessage) => {
                        console.log('[GameLayout] Loading message:', {
                            type: message.message_type,
                            content: message.message.substring(0, 50) + '...',
                            timestamp: message.timestamp
                        });
                        gameStore.addMessage(message);
                    });
                    console.log('[GameLayout] Loaded', messagesData.messages.length, 'previous messages for player');
                } catch (error) {
                    console.warn('[GameLayout] Failed to load player messages:', error);
                    // Continue without messages - not critical
                }

                // Load player's inventory items
                try {
                    const inventoryData = await apiService.getPlayerInventory(playerId);
                    console.log('[GameLayout] Loading inventory items:', inventoryData.items.length);
                    upsertItems(inventoryData.items);
                    console.log('[GameLayout] Loaded', inventoryData.items.length, 'inventory items for player');
                } catch (error) {
                    console.warn('[GameLayout] Failed to load player inventory:', error);
                    // Continue without inventory - not critical
                }

                // Load player's visited coordinates and minimap state
                try {
                    const coordinatesData = await apiService.getPlayerVisitedCoordinates(playerId);
                    console.log('[GameLayout] Loading visited coordinates:', coordinatesData.visited_coordinates.length);
                    
                    // Restore visited coordinates to the store
                    const gameStore = useGameStore.getState();
                    coordinatesData.visited_coordinates.forEach(coordKey => {
                        const [x, y] = coordKey.split(',').map(Number);
                        const biome = coordinatesData.visited_biomes[coordKey];
                        gameStore.addVisitedCoordinate(x, y, biome);
                    });
                    
                    // Restore biome colors
                    gameStore.setBiomeColors(coordinatesData.biome_colors);
                    
                    console.log('[GameLayout] Loaded', coordinatesData.visited_coordinates.length, 'visited coordinates for player');
                } catch (error) {
                    console.warn('[GameLayout] Failed to load player coordinates:', error);
                    // Continue without coordinates - not critical
                }

                // Clear any existing duel state on rejoin - AGGRESSIVE CLEARING
                const gameStore = useGameStore.getState();
                console.log('[GameLayout] Before clearing - duel state:', {
                    isInDuel: gameStore.isInDuel,
                    duelOpponent: gameStore.duelOpponent,
                    duelChallenge: gameStore.duelChallenge
                });
                gameStore.forceClearDuelState();
                console.log('[GameLayout] After clearing - duel state:', {
                    isInDuel: gameStore.isInDuel,
                    duelOpponent: gameStore.duelOpponent,
                    duelChallenge: gameStore.duelChallenge
                });
                console.log('[GameLayout] Force cleared all duel state on rejoin');

                // Clear server-side combat state
                try {
                    const combatResult = await apiService.clearCombatState(playerId);
                    console.log('[GameLayout] Cleared server-side combat state:', combatResult.message);
                    if (combatResult.cleared_duels > 0) {
                        console.log('[GameLayout] Cleared', combatResult.cleared_duels, 'active duels from server');
                    }
                } catch (error) {
                    console.warn('[GameLayout] Failed to clear server-side combat state:', error);
                    // Continue - not critical, but force clear client state anyway
                    gameStore.forceClearDuelState();
                }

                // Mark initial room as visited on minimap
                addVisitedCoordinate(roomInfo.room.x, roomInfo.room.y);

                // Add initial room description to chat
                const atmosphericPresence = (roomInfo as { atmospheric_presence?: string }).atmospheric_presence || '';
                console.log('[GameLayout] Initial room atmospheric presence:', atmosphericPresence);
                
                const roomMessage: ChatMessage = {
                    player_id: 'system',
                    room_id: roomInfo.room.id,
                    message: '',
                    message_type: 'room_description',
                    timestamp: new Date().toISOString(),
                    title: roomInfo.room.title,
                    description: roomInfo.room.description,
                    biome: roomInfo.room.biome,
                    players: roomInfo.players,
                    monsters: roomInfo.monsters || [],
                    atmospheric_presence: atmosphericPresence,
                    x: roomInfo.room.x,
                    y: roomInfo.room.y
                };
                useGameStore.getState().addMessage(roomMessage);

                // Connect to WebSocket
                console.log('[GameLayout] Establishing WebSocket connection:', {
                    roomId: joinData.player.current_room,
                    playerId: joinData.player.id
                });
                websocketService.connect(joinData.player.current_room, joinData.player.id);

                setIsLoading(false);
            } catch (error) {
                console.error('[GameLayout] Failed to initialize game:', error);
                setError('Failed to initialize game. Please try again.');
                setIsLoading(false);
            }
        };

        if (playerId) {
            initializeGame();
        }

        // Cleanup WebSocket connection
        return () => {
            console.log('[GameLayout] Cleaning up WebSocket connection');
            websocketService.disconnect();
        };
    }, [playerId, addVisitedCoordinate, setCurrentRoom, setError, setGameState, setIsLoading, setNPCs, setPlayer, setPlayersInRoom, upsertItems]);

    // Update room data when current room ID changes (but not on every room object change)
    useEffect(() => {
        const updateRoomData = async () => {
            if (!currentRoom || !player) return;

            try {
                setIsLoading(true);
                console.log('[GameLayout] Room changed, updating data:', {
                    roomId: currentRoom.id,
                    title: currentRoom.title,
                    imageUrl: currentRoom.image_url,
                    imageStatus: currentRoom.image_status
                });

                // Update presence
                await apiService.updatePresence(player.id, currentRoom.id);
                console.log('[GameLayout] Updated presence');

                // Get updated room info
                const roomInfo = await apiService.getRoomInfo(currentRoom.id);
                console.log('[GameLayout] Got room info:', {
                    roomId: roomInfo.room.id,
                    monstersCount: roomInfo.monsters?.length || 0,
                    atmosphericPresence: (roomInfo as { atmospheric_presence?: string }).atmospheric_presence || 'none'
                });
                console.log('[GameLayout] Full room info:', roomInfo);

                // Update room state with fresh data
                console.log('[GameLayout] Updating room state with fresh data');
                setCurrentRoom(roomInfo.room);
                setNPCs(roomInfo.npcs);
                setPlayersInRoom(roomInfo.players);
                upsertItems(roomInfo.items || []);

                // Mark the room as visited on minimap
                addVisitedCoordinate(roomInfo.room.x, roomInfo.room.y);

                setIsLoading(false);
            } catch (error) {
                console.error('[GameLayout] Failed to update room data:', error);
                setError('Failed to update room data. Please try again.');
                setIsLoading(false);
            }
        };

        updateRoomData();
    }, [currentRoom?.id, player?.id, addVisitedCoordinate, setCurrentRoom, setError, setIsLoading, setNPCs, setPlayersInRoom, upsertItems]);

    // Escape key to toggle pause menu
    useEffect(() => {
        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                const { isMenuOpen } = useGameStore.getState();
                setIsMenuOpen(!isMenuOpen);
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [setIsMenuOpen]);

    if (!player || !currentRoom) {
        return (
            <div className="flex items-center justify-center h-screen bg-black">
                <div className="text-green-500 text-xl font-mono">Loading game...</div>
            </div>
        );
    }

    return (
        <div className="flex flex-col h-screen bg-black text-green-500 font-['VT323',monospace] relative overflow-hidden">
            {/* Room Display (top 65%) */}
            <div className="h-[50%] relative">
                {/* Retro border overlay */}
                <div className="absolute inset-0 border-8 border-double border-amber-900 pointer-events-none z-10" />
                <RoomDisplay />
            </div>

            {/* Minimap - positioned in top-right corner */}
            <div className="absolute top-4 right-4 z-20 bg-black bg-opacity-80 p-3 border border-green-700 rounded">
                <Minimap />
            </div>

            {/* Players in Room - positioned below minimap */}
            <PlayersInRoom />

            {/* Fullscreen Minimap */}
            {isMinimapFullscreen && (
                <FullscreenMinimap onClose={() => setIsMinimapFullscreen(false)} />
            )}

            {/* Duel Challenge Popup */}
            <DuelChallengePopup />

            {/* Duel Status Overlay */}
            {isInDuel && (
                <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 bg-black/85 border border-amber-500 rounded px-3 py-2">
                    <div className="text-amber-400 text-xs font-bold text-center">Duel vs {duelOpponent?.name || 'Opponent'}</div>
                    <div className="mt-1 grid grid-cols-2 gap-6 text-[10px]">
                        {/* You */}
                        <div>
                            <div className="text-green-400 font-bold mb-0.5">You</div>
                            <div className="space-y-1">
                                <div>
                                    <div className="flex items-center gap-1 mb-0.5">
                                        <span>❤️</span>
                                        <span className="text-gray-200">Health</span>
                                        <span className="ml-auto text-gray-400">{Math.min(p1Max, Math.max(0, player1Vital))}/{p1Max}</span>
                                    </div>
                                    <div className="w-40 h-1.5 bg-gray-700 rounded overflow-hidden">
                                        <div className="h-1.5 bg-red-600" style={{width: `${Math.min(100, Math.max(0, ((Math.min(p1Max, Math.max(0, player1Vital))/p1Max)*100)))}%`}} />
                                    </div>
                                </div>
                                <div>
                                    <div className="flex items-center gap-1 mb-0.5">
                                        <span>🎯</span>
                                        <span className="text-gray-200">Advantage</span>
                                        <span className="ml-auto text-gray-400">{Math.min(5, Math.max(0, player1Control))}/5</span>
                                    </div>
                                    <div className="w-40 h-1.5 bg-gray-700 rounded overflow-hidden">
                                        <div className="h-1.5 bg-blue-500" style={{width: `${Math.min(100, Math.max(0, (Math.min(5, Math.max(0, player1Control))/5)*100))}%`}} />
                                    </div>
                                </div>
                            </div>
                        </div>
                        {/* Opponent */}
                        <div>
                            <div className="text-red-400 font-bold mb-0.5">{duelOpponent?.name || 'Opponent'}</div>
                            <div className="space-y-1">
                                <div>
                                    <div className="flex items-center gap-1 mb-0.5">
                                        <span>❤️</span>
                                        <span className="text-gray-200">Health</span>
                                        <span className="ml-auto text-gray-400">{Math.min(p2Max, Math.max(0, player2Vital))}/{p2Max}</span>
                                    </div>
                                    <div className="w-40 h-1.5 bg-gray-700 rounded overflow-hidden">
                                        <div className="h-1.5 bg-red-400" style={{width: `${Math.min(100, Math.max(0, ((Math.min(p2Max, Math.max(0, player2Vital))/p2Max)*100)))}%`}} />
                                    </div>
                                </div>
                                <div>
                                    <div className="flex items-center gap-1 mb-0.5">
                                        <span>🎯</span>
                                        <span className="text-gray-200">Advantage</span>
                                        <span className="ml-auto text-gray-400">{Math.min(5, Math.max(0, player2Control))}/5</span>
                                    </div>
                                    <div className="w-40 h-1.5 bg-gray-700 rounded overflow-hidden">
                                        <div className="h-1.5 bg-blue-300" style={{width: `${Math.min(100, Math.max(0, (Math.min(5, Math.max(0, player2Control))/5)*100))}%`}} />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Chat Display (bottom 35%) */}
            <div className="h-[50%] flex flex-col relative">
                {/* Retro terminal border */}
                <div className="absolute inset-0 border-4 border-amber-900 pointer-events-none" />
                <div className="flex-1 flex flex-col bg-black bg-opacity-90 overflow-hidden">
                    <div className="flex-1 overflow-hidden">
                        <ChatDisplay />
                    </div>
                    <ChatInput />
                </div>
            </div>

            {/* Pause Menu Overlay */}
            <PauseMenu />
        </div>
    );
};

export default GameLayout;