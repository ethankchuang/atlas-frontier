import React, { useEffect, useState } from 'react';
import useGameStore, { DUEL_MAX_HEALTH, DUEL_MAX_ADVANTAGE } from '@/store/gameStore';
import RoomDisplay from './RoomDisplay';
import ChatDisplay from './ChatDisplay';
import ChatInput from './ChatInput';
import Minimap from './Minimap';
import FullscreenMinimap from './FullscreenMinimap';
import PlayersInRoom from './PlayersInRoom';
import DuelChallengePopup from './DuelChallengePopup';
import DirectionalControls from './DirectionalControls';
import apiService from '@/services/api';
import websocketService from '@/services/websocket';
import { ChatMessage, Room } from '@/types/game';
import PauseMenu from '@/components/PauseMenu';
import { ChevronUpIcon, ChevronDownIcon, Bars3Icon } from '@heroicons/react/24/solid';

interface GameLayoutProps {
    playerId: string;
}

const GameLayout: React.FC<GameLayoutProps> = ({ playerId }) => {
    const [isChatExpanded, setIsChatExpanded] = useState(false);

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
        isMenuOpen,
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
    const p1Max = player1MaxVital ?? DUEL_MAX_HEALTH;
    const p2Max = player2MaxVital ?? DUEL_MAX_HEALTH;

    // Check if first-time user and show tutorial
    useEffect(() => {
        const hasSeenTutorial = localStorage.getItem('tutorial_seen');
        if (!hasSeenTutorial) {
            // Wait a bit for the game to initialize, then show tutorial
            const timer = setTimeout(() => {
                setIsMenuOpen(true);
            }, 1000);
            return () => clearTimeout(timer);
        }
    }, [setIsMenuOpen]);

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
                    console.log('[GameLayout] Loading visited biomes:', coordinatesData.visited_biomes);
                    console.log('[GameLayout] Loading biome colors:', coordinatesData.biome_colors);
                    
                    // Restore biome colors FIRST to preserve saved colors
                    const gameStore = useGameStore.getState();
                    gameStore.setBiomeColors(coordinatesData.biome_colors);
                    
                    // Then restore visited coordinates without overriding biome colors
                    // We need to manually update the store state to avoid the addVisitedCoordinate function
                    // which might override our saved biome colors
                    const newVisitedCoordinates = new Set(gameStore.visitedCoordinates);
                    const newVisitedBiomes = { ...gameStore.visitedBiomes };
                    
                    coordinatesData.visited_coordinates.forEach(coordKey => {
                        const biome = coordinatesData.visited_biomes[coordKey];
                        
                        newVisitedCoordinates.add(coordKey);
                        if (biome) {
                            newVisitedBiomes[coordKey] = biome;
                        }
                    });
                    
                    // Update the store state directly
                    useGameStore.setState({
                        visitedCoordinates: newVisitedCoordinates,
                        visitedBiomes: newVisitedBiomes
                    });
                    
                    // Force a re-render by logging the final state
                    console.log('[GameLayout] Final biome colors after loading:', useGameStore.getState().biomeColors);
                    
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
                addVisitedCoordinate(roomInfo.room.x, roomInfo.room.y, roomInfo.room.biome);

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
                
                // CRITICAL: Filter out the current player from the playersInRoom list
                // to prevent overwriting the current player's state with potentially stale data
                const otherPlayers = roomInfo.players.filter((p: { id: string }) => p.id !== player.id);
                setPlayersInRoom(otherPlayers);
                console.log('[GameLayout] Set players in room (excluding current player):', otherPlayers.length);
                
                upsertItems(roomInfo.items || []);

                // Mark the room as visited on minimap
                addVisitedCoordinate(roomInfo.room.x, roomInfo.room.y, roomInfo.room.biome);

                setIsLoading(false);
            } catch (error) {
                console.error('[GameLayout] Failed to update room data:', error);
                setError('Failed to update room data. Please try again.');
                setIsLoading(false);
            }
        };

        updateRoomData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [currentRoom?.id, player?.id]);

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
        <div className="h-screen bg-black text-green-500 font-['VT323',monospace] relative overflow-hidden" style={{ height: '100dvh' }}>
            {/* Full-screen Room Display with border */}
            <div className="absolute inset-0">
                <div className="absolute inset-0 border-4 md:border-8 border-double border-amber-900 pointer-events-none z-10" />
                <RoomDisplay />
            </div>

            {/* Menu button - positioned in top-left corner */}
            <button
                onClick={() => setIsMenuOpen(!isMenuOpen)}
                className="absolute top-2 left-2 md:top-4 md:left-4 z-30 bg-black bg-opacity-80 p-2 md:p-3 border border-amber-900 rounded hover:bg-opacity-100 transition-all"
                aria-label="Toggle menu"
            >
                <Bars3Icon className="w-5 h-5 md:w-6 md:h-6 text-amber-500" />
            </button>

            {/* Minimap with directional controls - positioned in top-right corner */}
            <div className="absolute top-2 right-2 md:top-4 md:right-4 z-20 bg-black bg-opacity-80 p-2 md:p-3 border border-green-700 rounded text-xs md:text-sm">
                <Minimap />
                <DirectionalControls />
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
                <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 bg-black/90 border-2 border-amber-500 rounded-lg px-4 py-3 md:px-6 md:py-4 min-w-[90vw] md:min-w-[600px] max-w-[95vw]">
                    <div className="text-amber-400 text-base md:text-lg font-bold text-center mb-2">Duel vs {duelOpponent?.name || 'Opponent'}</div>
                    <div className="grid grid-cols-2 gap-4 md:gap-8 text-xs md:text-sm">
                        {/* You */}
                        <div>
                            <div className="text-green-400 font-bold mb-1 text-sm md:text-base">You</div>
                            <div className="space-y-2">
                                <div>
                                    <div className="flex items-center gap-1 mb-1">
                                        <span className="text-base md:text-lg">❤️</span>
                                        <span className="text-gray-200">Health</span>
                                        <span className="ml-auto text-gray-400">{Math.min(p1Max, Math.max(0, player1Vital))}/{p1Max}</span>
                                    </div>
                                    <div className="w-full h-2 md:h-2.5 bg-gray-700 rounded overflow-hidden">
                                        <div className="h-full bg-red-600" style={{width: `${Math.min(100, Math.max(0, ((Math.min(p1Max, Math.max(0, player1Vital))/p1Max)*100)))}%`}} />
                                    </div>
                                </div>
                                <div>
                                    <div className="flex items-center gap-1 mb-1">
                                        <span className="text-base md:text-lg">🎯</span>
                                        <span className="text-gray-200">Advantage</span>
                                        <span className="ml-auto text-gray-400">{Math.min(DUEL_MAX_ADVANTAGE, Math.max(0, player1Control))}/{DUEL_MAX_ADVANTAGE}</span>
                                    </div>
                                    <div className="w-full h-2 md:h-2.5 bg-gray-700 rounded overflow-hidden">
                                        <div className="h-full bg-blue-500" style={{width: `${Math.min(100, Math.max(0, (Math.min(DUEL_MAX_ADVANTAGE, Math.max(0, player1Control))/DUEL_MAX_ADVANTAGE)*100))}%`}} />
                                    </div>
                                </div>
                            </div>
                        </div>
                        {/* Opponent */}
                        <div>
                            <div className="text-red-400 font-bold mb-1 text-sm md:text-base">{duelOpponent?.name || 'Opponent'}</div>
                            <div className="space-y-2">
                                <div>
                                    <div className="flex items-center gap-1 mb-1">
                                        <span className="text-base md:text-lg">❤️</span>
                                        <span className="text-gray-200">Health</span>
                                        <span className="ml-auto text-gray-400">{Math.min(p2Max, Math.max(0, player2Vital))}/{p2Max}</span>
                                    </div>
                                    <div className="w-full h-2 md:h-2.5 bg-gray-700 rounded overflow-hidden">
                                        <div className="h-full bg-red-400" style={{width: `${Math.min(100, Math.max(0, ((Math.min(p2Max, Math.max(0, player2Vital))/p2Max)*100)))}%`}} />
                                    </div>
                                </div>
                                <div>
                                    <div className="flex items-center gap-1 mb-1">
                                        <span className="text-base md:text-lg">🎯</span>
                                        <span className="text-gray-200">Advantage</span>
                                        <span className="ml-auto text-gray-400">{Math.min(DUEL_MAX_ADVANTAGE, Math.max(0, player2Control))}/{DUEL_MAX_ADVANTAGE}</span>
                                    </div>
                                    <div className="w-full h-2 md:h-2.5 bg-gray-700 rounded overflow-hidden">
                                        <div className="h-full bg-blue-300" style={{width: `${Math.min(100, Math.max(0, (Math.min(DUEL_MAX_ADVANTAGE, Math.max(0, player2Control))/DUEL_MAX_ADVANTAGE)*100))}%`}} />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Chat Display Overlay (bottom portion, translucent) */}
            <div
                className={`absolute bottom-0 left-0 right-0 flex flex-col z-20 transition-all duration-300 ${
                    isChatExpanded ? 'top-16' : 'h-[40vh]'
                }`}
                style={{
                    paddingLeft: typeof window !== 'undefined' && window.innerWidth >= 768 ? '1.5rem' : '0.75rem',
                    paddingRight: typeof window !== 'undefined' && window.innerWidth >= 768 ? '1.5rem' : '0.75rem',
                    paddingTop: typeof window !== 'undefined' && window.innerWidth >= 768 ? '1.5rem' : '0.75rem',
                    paddingBottom: typeof window !== 'undefined' && window.innerWidth >= 768
                        ? 'max(1.5rem, env(safe-area-inset-bottom))'
                        : 'max(0.75rem, env(safe-area-inset-bottom))'
                }}
            >
                <div className="w-full max-w-4xl mx-auto bg-black/60 backdrop-blur-md rounded-lg flex flex-col h-full relative">
                    {/* Expand/Collapse Button */}
                    <button
                        onClick={() => setIsChatExpanded(!isChatExpanded)}
                        className="absolute -top-2 left-1/2 -translate-x-1/2 bg-black/60 backdrop-blur-md border border-amber-900/50 rounded-full p-1.5 hover:bg-black/80 transition-colors z-30"
                        aria-label={isChatExpanded ? "Collapse chat" : "Expand chat"}
                    >
                        {isChatExpanded ? (
                            <ChevronDownIcon className="w-4 h-4 text-amber-400" />
                        ) : (
                            <ChevronUpIcon className="w-4 h-4 text-amber-400" />
                        )}
                    </button>

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