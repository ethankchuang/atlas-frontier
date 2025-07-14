import React, { useEffect } from 'react';
import useGameStore from '@/store/gameStore';
import RoomDisplay from './RoomDisplay';
import ChatDisplay from './ChatDisplay';
import ChatInput from './ChatInput';
import Minimap from './Minimap';
import apiService from '@/services/api';
import websocketService from '@/services/websocket';
import { ChatMessage } from '@/types/game';

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
        addVisitedCoordinate
    } = useGameStore();

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

                // Mark initial room as visited on minimap
                addVisitedCoordinate(roomInfo.room.x, roomInfo.room.y);

                // Add initial room description to chat
                const roomMessage: ChatMessage = {
                    player_id: 'system',
                    room_id: roomInfo.room.id,
                    message: '',
                    message_type: 'room_description',
                    timestamp: new Date().toISOString(),
                    title: roomInfo.room.title,
                    description: roomInfo.room.description,
                    players: roomInfo.players,
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
                console.log('[GameLayout] Got room info:', roomInfo);

                // Only update if we're still in the same room AND we haven't received a WebSocket update
                // Check image_url to determine if we've received a WebSocket update
                if (currentRoom.id === roomInfo.room.id && currentRoom.image_url === roomInfo.room.image_url) {
                    console.log('[GameLayout] Updating room state with fresh data');
                    setCurrentRoom(roomInfo.room);
                    setNPCs(roomInfo.npcs);
                    setPlayersInRoom(roomInfo.players);
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
        </div>
    );
};

export default GameLayout;