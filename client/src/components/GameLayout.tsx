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
import { ChatMessage } from '@/types/game';
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

                // Get player data
                const playerData = await apiService.createPlayer(playerId);
                setPlayer(playerData);

                // Get initial room data
                const roomInfo = await apiService.getRoomInfo(playerData.current_room);
                setCurrentRoom(roomInfo.room);
                setNPCs(roomInfo.npcs);
                setPlayersInRoom(roomInfo.players);
                upsertItems(roomInfo.items || []);

                // Mark initial room as visited on minimap
                addVisitedCoordinate(roomInfo.room.x, roomInfo.room.y);

                // Add initial room description to chat
                const atmosphericPresence = (roomInfo as any).atmospheric_presence || '';
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
                    roomId: playerData.current_room,
                    playerId: playerData.id
                });
                websocketService.connect(playerData.current_room, playerData.id);

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
    }, [playerId]);

    // Update room data when current room changes
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
                    atmosphericPresence: (roomInfo as any).atmospheric_presence || 'none'
                });
                console.log('[GameLayout] Full room info:', roomInfo);

                // Only update room state, but don't add duplicate room messages on initial load
                if (currentRoom.id === roomInfo.room.id && currentRoom.image_url === roomInfo.room.image_url) {
                    console.log('[GameLayout] Updating room state with fresh data (no duplicate message)');
                    setCurrentRoom(roomInfo.room);
                    setNPCs(roomInfo.npcs);
                    setPlayersInRoom(roomInfo.players);
                    upsertItems(roomInfo.items || []);
                    
                    // Don't add room description message here - it was already added during initialization
                    // This prevents duplicate room messages
                } else {
                    console.log('[GameLayout] Skipping room update - already have newer data');
                }

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
    }, [currentRoom?.id]);

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
                                        <span className="ml-auto text-gray-400">{p1Max - Math.min(p1Max, Math.max(0, player1Vital))}/{p1Max}</span>
                                    </div>
                                    <div className="w-40 h-1.5 bg-gray-700 rounded overflow-hidden">
                                        <div className="h-1.5 bg-red-600" style={{width: `${Math.min(100, Math.max(0, (((p1Max - Math.min(p1Max, Math.max(0, player1Vital)))/p1Max)*100)))}%`}} />
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
                                        <span className="ml-auto text-gray-400">{p2Max - Math.min(p2Max, Math.max(0, player2Vital))}/{p2Max}</span>
                                    </div>
                                    <div className="w-40 h-1.5 bg-gray-700 rounded overflow-hidden">
                                        <div className="h-1.5 bg-red-400" style={{width: `${Math.min(100, Math.max(0, (((p2Max - Math.min(p2Max, Math.max(0, player2Vital)))/p2Max)*100)))}%`}} />
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