import React, { useState, useRef, useEffect } from 'react';
import useGameStore from '@/store/gameStore';
import apiService from '@/services/api';
import websocketService from '@/services/websocket';
import { ChatMessage, Player } from '@/types/game';
import { PaperAirplaneIcon, FaceSmileIcon } from '@heroicons/react/24/solid';

const ChatInput: React.FC = () => {
    const [input, setInput] = useState('');
    const [isEmote, setIsEmote] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const streamMessageIdRef = useRef<string | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const {
        player,
        currentRoom,
        isInDuel,
        duelOpponent,
        myDuelMove,
        bothMovesSubmitted,
        addMessage,
        updateMessage,
        submitDuelMove
    } = useGameStore();

    useEffect(() => {
        // Focus input on mount
        inputRef.current?.focus();
    }, []);

    // Clear input when duel move is submitted or when duel ends
    useEffect(() => {
        if (myDuelMove || !isInDuel) {
            setInput('');
        }
    }, [myDuelMove, isInDuel]);

    // Prevent form submission when already submitted a move
    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && isInDuel && myDuelMove) {
            e.preventDefault();
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || !player || !currentRoom) return;

        const trimmedInput = input.trim();
        setInput('');

        // Check if we're in a duel first
        if (isInDuel && duelOpponent) {
            // Handle duel move
            if (!myDuelMove) {
                // Submit our move
                submitDuelMove(trimmedInput);
                websocketService.sendDuelMove(duelOpponent.id, trimmedInput);
                
                // Add message showing we submitted our move (but not what it was)
                const duelMessage: ChatMessage = {
                    player_id: player.id,
                    room_id: currentRoom.id,
                    message: `⚔️ You prepare your combat move...`,
                    message_type: 'system',
                    timestamp: new Date().toISOString()
                };
                addMessage(duelMessage);
            } else {
                // Already submitted our move, just show a message
                const message: ChatMessage = {
                    player_id: player.id,
                    room_id: currentRoom.id,
                    message: "You've already submitted your move. Waiting for your opponent...",
                    message_type: 'system',
                    timestamp: new Date().toISOString()
                };
                addMessage(message);
            }
            return;
        }

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

                        // CRITICAL: Process player updates from the response
                        if (response.updates?.player) {
                            console.log('[ChatInput] Processing player updates:', response.updates.player);
                            const store = useGameStore.getState();
                            
                            // Update player state with any changes
                            if (store.player) {
                                const updatedPlayer = { ...store.player, ...(response.updates.player as Partial<Player>) };
                                store.setPlayer(updatedPlayer);
                                console.log('[ChatInput] Updated player state, new current_room:', updatedPlayer.current_room);
                                console.log('[ChatInput] Updated player inventory:', updatedPlayer.inventory);
                            }
                        }

                        // Handle duel initiation via action stream fallback (e.g., if WebSocket was closed)
                        const duelUpdates = response.updates?.duel as { is_monster_duel?: boolean; opponent_id?: string; opponent_name?: string; player1_max_vital?: number; player2_max_vital?: number } | undefined;
                        if (duelUpdates?.is_monster_duel) {
                            const store = useGameStore.getState();
                            const opponentId = duelUpdates.opponent_id || '';
                            const opponentName = duelUpdates.opponent_name || 'Opponent';
                            store.startDuel({ id: opponentId, name: opponentName });
                            const p1Max = duelUpdates.player1_max_vital ?? 6;
                            const p2Max = duelUpdates.player2_max_vital ?? 6;
                            useGameStore.getState().setMaxVitals(p1Max, p2Max);
                            console.log('[ChatInput] Started monster duel via stream updates:', { opponentId, opponentName, p1Max, p2Max });
                        }

                        setIsStreaming(false);
                        streamMessageIdRef.current = null;
                    },
                    // Handle errors
                    (error) => {
                        console.error('[ChatInput] Action error:', error);
                        const friendly = "That didn’t go through. Please try again.";
                        if (streamMessageIdRef.current) {
                            updateMessage(streamMessageIdRef.current, (prev) => ({
                                ...prev,
                                message: friendly,
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

    const toggleEmote = () => {
        setIsEmote(!isEmote);
    };

    return (
        <div className="bg-black border-t border-amber-900">
            {/* Condition Display for Duels */}
            {/* Removed duel condition overlay above input while in battle mode */}
            
            <form onSubmit={handleSubmit} className="flex items-center gap-2 p-3">
            <button
                type="button"
                    onClick={toggleEmote}
                    className={`p-2 rounded transition-colors ${
                        isEmote 
                            ? 'bg-amber-600 text-amber-100' 
                            : 'bg-amber-900/50 text-amber-400 hover:bg-amber-800/50'
                    }`}
                    disabled={isStreaming || isInDuel}
            >
                    <FaceSmileIcon className="w-5 h-5" />
            </button>

                <div className="relative flex-1">
                <input
                    ref={inputRef}
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                        placeholder={
                            isInDuel 
                                ? (myDuelMove ? "Waiting for opponent..." : "Enter your combat move...")
                                : (isEmote ? "Express an action..." : "What do you want to do?")
                        }
                    className="w-full pl-10 py-2.5 bg-black text-green-400 font-mono text-xl border border-amber-900 focus:border-amber-500 focus:outline-none rounded"
                        disabled={isStreaming || (isInDuel && !!myDuelMove && !bothMovesSubmitted)}
                    readOnly={isInDuel && !!myDuelMove}
                />
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <span className="text-amber-400 text-xl font-mono">{'>'}</span>
                    </div>
            </div>

            <button
                type="submit"
                    disabled={isStreaming || !input.trim() || (isInDuel && !!myDuelMove && !bothMovesSubmitted)}
                    className="p-2 bg-amber-600 text-amber-100 rounded hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
                <PaperAirplaneIcon className="w-6 h-6" />
            </button>
        </form>
        </div>
    );
};

export default ChatInput;