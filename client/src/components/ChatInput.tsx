import React, { useState, useRef, useEffect } from 'react';
import useGameStore from '@/store/gameStore';
import apiService from '@/services/api';
import websocketService from '@/services/websocket';
import { ChatMessage } from '@/types/game';
import { PaperAirplaneIcon, FaceSmileIcon } from '@heroicons/react/24/solid';

const ChatInput: React.FC = () => {
    const [input, setInput] = useState('');
    const [isEmote, setIsEmote] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const streamMessageIdRef = useRef<string | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const { player, currentRoom, messages, addMessage, updateMessage } = useGameStore();

    useEffect(() => {
        // Focus input on mount
        inputRef.current?.focus();
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || !player || !currentRoom) return;

        const trimmedInput = input.trim();
        setInput('');

        // Only add command to history if it's not a chat or emote
        if (!isEmote && !trimmedInput.startsWith('/')) {
            // Add the user's typed command to chat history
            const userCommandMessage: ChatMessage = {
                player_id: player.id,
                room_id: currentRoom.id,
                message: `>> ${trimmedInput}`,
                message_type: 'system',
                timestamp: new Date().toISOString()
            };
            addMessage(userCommandMessage);
        }

        if (isEmote) {
            // Handle emote
            const message: ChatMessage = {
                player_id: player.id,
                room_id: currentRoom.id,
                message: trimmedInput,
                message_type: 'emote',
                timestamp: new Date().toISOString()
            };

            try {
                await apiService.sendChat(message);
                websocketService.sendChatMessage(trimmedInput, 'emote');
            } catch (error) {
                console.error('Failed to send emote:', error);
            }
        } else if (trimmedInput.startsWith('/')) {
            // Handle chat command
            const message: ChatMessage = {
                player_id: player.id,
                room_id: currentRoom.id,
                message: trimmedInput,
                message_type: 'chat',
                timestamp: new Date().toISOString()
            };

            try {
                await apiService.sendChat(message);
                websocketService.sendChatMessage(trimmedInput);
            } catch (error) {
                console.error('Failed to send chat:', error);
            }
        } else {
            // Handle game action with streaming
            try {
                setIsStreaming(true);
                streamMessageIdRef.current = `stream-${Date.now()}`;
                console.log('[ChatInput] Processing action:', trimmedInput);

                // Send action to websocket
                websocketService.sendAction(trimmedInput);

                // Add initial streaming message
                const streamingMessage: ChatMessage = {
                    id: streamMessageIdRef.current,
                    player_id: player.id,
                    room_id: currentRoom.id,
                    message: '',
                    message_type: 'system',
                    timestamp: new Date().toISOString(),
                    isStreaming: true
                };
                addMessage(streamingMessage);

                await apiService.processActionStream(
                    {
                        player_id: player.id,
                        action: trimmedInput,
                        room_id: currentRoom.id
                    },
                    // Handle streaming chunks
                    (chunk: string) => {
                        // console.log('[ChatInput] Received chunk:', chunk);
                        if (streamMessageIdRef.current) {
                            updateMessage(streamMessageIdRef.current, (prev) => ({
                                ...prev,
                                message: prev.message + chunk
                            }));
                        }
                    },
                    // Handle final response
                    (response) => {
                        console.log('[ChatInput] Received final response:', response);
                        if (streamMessageIdRef.current) {
                            // Update the streaming message with final content
                            updateMessage(streamMessageIdRef.current, (prev) => ({
                                ...prev,
                                message: response.message,
                                isStreaming: false
                            }));
                        }
                        setIsStreaming(false);
                        streamMessageIdRef.current = null;
                    },
                    // Handle errors
                    (error) => {
                        console.error('[ChatInput] Action error:', error);
                        if (streamMessageIdRef.current) {
                            updateMessage(streamMessageIdRef.current, (prev) => ({
                                ...prev,
                                message: `Error: ${error}`,
                                isStreaming: false
                            }));
                        }
                        setIsStreaming(false);
                        streamMessageIdRef.current = null;
                    }
                );
            } catch (error) {
                console.error('[ChatInput] Failed to process action:', error);
                const errorMessage: ChatMessage = {
                    player_id: 'system',
                    room_id: currentRoom.id,
                    message: `Error: ${error}`,
                    message_type: 'system',
                    timestamp: new Date().toISOString()
                };
                addMessage(errorMessage);
                setIsStreaming(false);
                streamMessageIdRef.current = null;
            }
        }

        // Reset emote mode
        setIsEmote(false);
    };

    return (
        <form onSubmit={handleSubmit} className="flex items-center gap-2 p-3 bg-black border-t border-amber-900">
            <button
                type="button"
                onClick={() => setIsEmote(!isEmote)}
                className={`p-2.5 rounded ${
                    isEmote ? 'bg-yellow-600' : 'bg-amber-900'
                } hover:bg-yellow-700 transition-colors`}
                title="Toggle emote mode"
                disabled={isStreaming}
            >
                <FaceSmileIcon className="w-6 h-6 text-amber-100" />
            </button>

            <div className="flex-1 relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-amber-500 font-mono text-xl">{'>'}{'>'}</span>
                <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder={isEmote ? "Express an action..." : "What do you want to do?"}
                    className="w-full pl-10 py-2.5 bg-black text-green-400 font-mono text-xl border border-amber-900 focus:border-amber-500 focus:outline-none rounded"
                    disabled={isStreaming}
                />
            </div>

            <button
                type="submit"
                disabled={!input.trim() || isStreaming}
                className="p-2.5 bg-amber-900 text-amber-100 rounded hover:bg-amber-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
                <PaperAirplaneIcon className="w-6 h-6" />
            </button>
        </form>
    );
};

export default ChatInput;