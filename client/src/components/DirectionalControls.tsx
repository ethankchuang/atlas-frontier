import React, { useState, useRef } from 'react';
import useGameStore from '@/store/gameStore';
import apiService from '@/services/api';
import { ChevronUpIcon, ChevronDownIcon, ChevronLeftIcon, ChevronRightIcon, EyeIcon, ChatBubbleLeftIcon, BoltIcon } from '@heroicons/react/24/solid';

const DirectionalControls: React.FC = () => {
    const { player, currentRoom, addMessage, updateMessage, isInDuel, myDuelMove, bothMovesSubmitted, isEmote, setIsEmote } = useGameStore();
    const [isProcessing, setIsProcessing] = useState(false);

    const handleDirection = async (direction: string) => {
        if (!player || !currentRoom || isProcessing) return;

        setIsProcessing(true);

        // Add user command message
        const userCommandMessage = {
            player_id: player.id,
            room_id: currentRoom.id,
            message: `>> ${direction}`,
            message_type: 'system' as const,
            timestamp: new Date().toISOString()
        };
        addMessage(userCommandMessage);

        // Add streaming message with spinner
        const streamMessageId = `stream-${Date.now()}`;
        const streamingMessage = {
            id: streamMessageId,
            player_id: player.id,
            room_id: currentRoom.id,
            message: '⠋',
            message_type: 'system' as const,
            timestamp: new Date().toISOString(),
            isStreaming: true
        };
        addMessage(streamingMessage);

        try {
            await apiService.processActionStream(
                {
                    player_id: player.id,
                    action: direction,
                    room_id: currentRoom.id
                },
                (chunk: string) => {
                    updateMessage(streamMessageId, (prev) => ({
                        ...prev,
                        message: prev.message === '⠋' ? chunk : prev.message + chunk
                    }));
                },
                (response) => {
                    updateMessage(streamMessageId, (prev) => ({
                        ...prev,
                        message: response.message,
                        isStreaming: false
                    }));

                    // Update player if needed
                    if (response.updates?.player) {
                        const store = useGameStore.getState();
                        if (store.player) {
                            const updatedPlayer = { ...store.player, ...response.updates.player };
                            store.setPlayer(updatedPlayer);
                        }
                    }

                    setIsProcessing(false);
                },
                () => {
                    updateMessage(streamMessageId, (prev) => ({
                        ...prev,
                        message: "That didn't go through. Please try again.",
                        isStreaming: false
                    }));
                    setIsProcessing(false);
                }
            );
        } catch (error) {
            console.error('Failed to process direction:', error);
            setIsProcessing(false);
        }
    };

    // Disable buttons when processing, in duel, or duel move already submitted
    const isDisabled = isProcessing || (isInDuel && (!!myDuelMove && !bothMovesSubmitted));

    const toggleChatMode = () => {
        setIsEmote(!isEmote);
    };

    return (
        <div className="flex flex-col items-center gap-1 mt-2">
            {/* Eye button, Up arrow, and Chat mode toggle */}
            <div className="flex gap-1 items-center">
                <button
                    onClick={() => handleDirection('look around')}
                    disabled={isDisabled}
                    className="w-6 h-6 flex items-center justify-center bg-amber-900 bg-opacity-30 border border-amber-700 border-opacity-40 rounded hover:bg-opacity-50 hover:border-opacity-60 transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                    aria-label="Look Around"
                    title="Look Around"
                >
                    <EyeIcon className="w-4 h-4 text-amber-500 opacity-50" />
                </button>

                <button
                    onClick={() => handleDirection('north')}
                    disabled={isDisabled}
                    className="w-6 h-6 flex items-center justify-center bg-green-900 bg-opacity-30 border border-green-700 border-opacity-40 rounded hover:bg-opacity-50 hover:border-opacity-60 transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                    aria-label="Go North"
                    title="North"
                >
                    <ChevronUpIcon className="w-4 h-4 text-green-500 opacity-50" />
                </button>

                <button
                    onClick={toggleChatMode}
                    disabled={isInDuel}
                    className={`w-6 h-6 flex items-center justify-center rounded transition-all cursor-pointer ${
                        isEmote
                            ? 'bg-gray-800 bg-opacity-30 border border-gray-600 border-opacity-40 hover:bg-opacity-50 hover:border-opacity-60'
                            : 'bg-gray-800 bg-opacity-30 border border-gray-600 border-opacity-40 hover:bg-opacity-50 hover:border-opacity-60'
                    } disabled:opacity-30 disabled:cursor-not-allowed`}
                    aria-label={isEmote ? "Switch to Action Mode" : "Switch to Chat Mode"}
                    title={isEmote ? "Action Mode" : "Chat Mode"}
                >
                    {isEmote ? (
                        <BoltIcon className="w-4 h-4 text-gray-400 opacity-60" />
                    ) : (
                        <ChatBubbleLeftIcon className="w-4 h-4 text-gray-400 opacity-60" />
                    )}
                </button>
            </div>

            {/* Left, Down, Right arrows */}
            <div className="flex gap-1">
                <button
                    onClick={() => handleDirection('west')}
                    disabled={isDisabled}
                    className="w-6 h-6 flex items-center justify-center bg-green-900 bg-opacity-30 border border-green-700 border-opacity-40 rounded hover:bg-opacity-50 hover:border-opacity-60 transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                    aria-label="Go West"
                    title="West"
                >
                    <ChevronLeftIcon className="w-4 h-4 text-green-500 opacity-50" />
                </button>

                <button
                    onClick={() => handleDirection('south')}
                    disabled={isDisabled}
                    className="w-6 h-6 flex items-center justify-center bg-green-900 bg-opacity-30 border border-green-700 border-opacity-40 rounded hover:bg-opacity-50 hover:border-opacity-60 transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                    aria-label="Go South"
                    title="South"
                >
                    <ChevronDownIcon className="w-4 h-4 text-green-500 opacity-50" />
                </button>

                <button
                    onClick={() => handleDirection('east')}
                    disabled={isDisabled}
                    className="w-6 h-6 flex items-center justify-center bg-green-900 bg-opacity-30 border border-green-700 border-opacity-40 rounded hover:bg-opacity-50 hover:border-opacity-60 transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
                    aria-label="Go East"
                    title="East"
                >
                    <ChevronRightIcon className="w-4 h-4 text-green-500 opacity-50" />
                </button>
            </div>
        </div>
    );
};

export default DirectionalControls;
