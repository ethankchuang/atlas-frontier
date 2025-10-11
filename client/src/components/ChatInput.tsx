import React, { useState, useRef, useEffect } from 'react';
import useGameStore from '@/store/gameStore';
import apiService from '@/services/api';
import websocketService from '@/services/websocket';
import { ChatMessage, Player } from '@/types/game';
import { PaperAirplaneIcon, ChatBubbleLeftIcon, BoltIcon } from '@heroicons/react/24/solid';

// ASCII spinner frames like Claude Code
const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

const ChatInput: React.FC = () => {
    const [input, setInput] = useState('');
    const [isEmote, setIsEmote] = useState(false);
    const [isStreaming, setIsStreaming] = useState(false);
    const [spinnerFrame, setSpinnerFrame] = useState(0);
    const streamMessageIdRef = useRef<string | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const spinnerIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const isSubmittingRef = useRef<boolean>(false);
    const {
        player,
        currentRoom,
        isInDuel,
        duelOpponent,
        myDuelMove,
        opponentDuelMove,
        bothMovesSubmitted,
        currentRound,
        addMessage,
        updateMessage,
        submitDuelMove
    } = useGameStore();

    useEffect(() => {
        // Focus input on mount
        inputRef.current?.focus();
    }, []);

    // Animate spinner when streaming
    useEffect(() => {
        if (isStreaming && streamMessageIdRef.current) {
            spinnerIntervalRef.current = setInterval(() => {
                setSpinnerFrame((prev) => (prev + 1) % SPINNER_FRAMES.length);
            }, 80); // Update every 80ms for smooth animation
        } else {
            if (spinnerIntervalRef.current) {
                clearInterval(spinnerIntervalRef.current);
                spinnerIntervalRef.current = null;
            }
            setSpinnerFrame(0);
        }

        return () => {
            if (spinnerIntervalRef.current) {
                clearInterval(spinnerIntervalRef.current);
            }
        };
    }, [isStreaming]);

    // Update the spinner message when frame changes
    useEffect(() => {
        if (isStreaming && streamMessageIdRef.current) {
            updateMessage(streamMessageIdRef.current, (msg) => {
                // Only update if the message is still just a spinner frame
                if (SPINNER_FRAMES.includes(msg.message)) {
                    return { ...msg, message: SPINNER_FRAMES[spinnerFrame] };
                }
                return msg;
            });
        }
    }, [spinnerFrame, isStreaming, updateMessage]);

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

        // Prevent double submission
        if (isSubmittingRef.current) {
            console.warn('[ChatInput] Prevented double submission');
            return;
        }
        isSubmittingRef.current = true;

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
            isSubmittingRef.current = false;
            return;
        }

        // FALLBACK: If we're stuck in duel mode but no opponent, clear it
        if (isInDuel && !duelOpponent) {
            console.warn('[ChatInput] Detected stuck duel state - clearing');
            const gameStore = useGameStore.getState();
            gameStore.forceClearDuelState();
            
            const message: ChatMessage = {
                player_id: player.id,
                room_id: currentRoom.id,
                message: "Duel state cleared. You can now continue playing normally.",
                message_type: 'system',
                timestamp: new Date().toISOString()
            };
            addMessage(message);
        }

        // DEBUG: Log duel state for debugging
        if (isInDuel) {
            console.log('[ChatInput] DEBUG: Duel state detected:', {
                isInDuel,
                duelOpponent,
                myDuelMove,
                opponentDuelMove,
                bothMovesSubmitted,
                currentRound
            });
        }

        // AGGRESSIVE FALLBACK: If we're in duel mode but no opponent, force clear it
        if (isInDuel && !duelOpponent) {
            console.warn('[ChatInput] AGGRESSIVE: Force clearing stuck duel state');
            const gameStore = useGameStore.getState();
            gameStore.forceClearDuelState();
            
            const message: ChatMessage = {
                player_id: player.id,
                room_id: currentRoom.id,
                message: "Stuck duel state detected and cleared. Continuing with your action.",
                message_type: 'system',
                timestamp: new Date().toISOString()
            };
            addMessage(message);
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
            } finally {
                isSubmittingRef.current = false;
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
            } finally {
                isSubmittingRef.current = false;
            }
        } else {
            // Handle game action with streaming
            try {
                setIsStreaming(true);
                streamMessageIdRef.current = `stream-${Date.now()}`;
                console.log('[ChatInput] Processing action:', trimmedInput);

                // Add initial streaming message with ASCII spinner
                const streamingMessage: ChatMessage = {
                    id: streamMessageIdRef.current,
                    player_id: player.id,
                    room_id: currentRoom.id,
                    message: SPINNER_FRAMES[0],  // Start with first spinner frame
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
                                // Replace spinner on first chunk, then append
                                message: SPINNER_FRAMES.includes(prev.message) ? chunk : prev.message + chunk
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
                        isSubmittingRef.current = false;
                    },
                    // Handle errors
                    (error) => {
                        console.error('[ChatInput] Action error:', error);
                        const friendly = "That didn't go through. Please try again.";
                        if (streamMessageIdRef.current) {
                            updateMessage(streamMessageIdRef.current, (prev) => ({
                                ...prev,
                                message: friendly,
                                isStreaming: false
                            }));
                        }
                        setIsStreaming(false);
                        streamMessageIdRef.current = null;
                        isSubmittingRef.current = false;
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
                isSubmittingRef.current = false;
            }
        }
    };

    const toggleEmote = () => {
        setIsEmote(!isEmote);
    };

    return (
        <div className="p-3 md:p-4 border-t border-amber-900/30">
            {/* Condition Display for Duels */}
            {/* Removed duel condition overlay above input while in battle mode */}

            <form onSubmit={handleSubmit} className="flex items-center gap-2">
            <button
                type="button"
                    onClick={toggleEmote}
                    className={`p-2 rounded transition-colors cursor-pointer ${
                        isEmote 
                            ? 'bg-amber-600 text-amber-100' 
                            : 'bg-amber-900/50 text-amber-400 hover:bg-amber-800/50'
                    }`}
                    disabled={isStreaming || isInDuel}
            >
                    {isEmote ? (
                        <ChatBubbleLeftIcon className="w-5 h-5" />
                    ) : (
                        <BoltIcon className="w-5 h-5" />
                    )}
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
                                : (isEmote ? "Chat in this room..." : "What do you want to do?")
                        }
                    className="w-full pl-10 py-2.5 bg-black bg-opacity-40 text-green-400 font-mono text-xl border border-amber-900 focus:border-amber-500 focus:outline-none rounded"
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