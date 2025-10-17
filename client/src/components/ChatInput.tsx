import React, { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import useGameStore from '@/store/gameStore';
import apiService from '@/services/api';
import websocketService from '@/services/websocket';
import { ChatMessage, Player, NPC } from '@/types/game';
import { PaperAirplaneIcon, ChatBubbleLeftIcon, BoltIcon } from '@heroicons/react/24/solid';

// ASCII spinner frames like Claude Code
const SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];

const ChatInput: React.FC = () => {
    const [input, setInput] = useState('');
    const [isStreaming, setIsStreaming] = useState(false);
    const [isNPCLoading, setIsNPCLoading] = useState(false);
    const [spinnerFrame, setSpinnerFrame] = useState(0);
    const [showNPCAutocomplete, setShowNPCAutocomplete] = useState(false);
    const [autocompleteIndex, setAutocompleteIndex] = useState(0);
    const [filteredNPCs, setFilteredNPCs] = useState<NPC[]>([]);
    const [autocompletePosition, setAutocompletePosition] = useState({ top: 0, left: 0, width: 0 });
    const streamMessageIdRef = useRef<string | null>(null);
    const npcLoadingMessageIdRef = useRef<string | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const spinnerIntervalRef = useRef<NodeJS.Timeout | null>(null);
    const isSubmittingRef = useRef<boolean>(false);
    const autocompleteRef = useRef<HTMLDivElement>(null);
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
        submitDuelMove,
        isEmote,
        setIsEmote,
        chatInputPrefill,
        setChatInputPrefill,
        npcs
    } = useGameStore();

    // Removed auto-focus on mount to avoid interrupting user when expanding chat

    // Watch for chat input prefill (e.g., from clicking an NPC)
    useEffect(() => {
        if (chatInputPrefill) {
            setInput(chatInputPrefill);
            setChatInputPrefill(''); // Clear after using
            inputRef.current?.focus();
        }
    }, [chatInputPrefill, setChatInputPrefill]);

    // Watch for @ to show NPC autocomplete
    useEffect(() => {
        if (!input.startsWith('@')) {
            setShowNPCAutocomplete(false);
            setFilteredNPCs([]);
            setAutocompleteIndex(0);
            return;
        }

        // Get the part after @
        const searchTerm = input.substring(1).toLowerCase();
        
        // Filter NPCs by name (case-insensitive)
        const filtered = npcs.filter(npc => 
            npc.name.toLowerCase().includes(searchTerm)
        );

        setFilteredNPCs(filtered);
        setShowNPCAutocomplete(filtered.length > 0);
        setAutocompleteIndex(0);

        // Calculate position for portal
        if (filtered.length > 0 && inputRef.current) {
            const rect = inputRef.current.getBoundingClientRect();
            setAutocompletePosition({
                top: rect.top,
                left: rect.left,
                width: rect.width
            });
        }
    }, [input, npcs]);

    // Animate spinner when streaming or waiting for NPC
    useEffect(() => {
        if ((isStreaming && streamMessageIdRef.current) || (isNPCLoading && npcLoadingMessageIdRef.current)) {
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
    }, [isStreaming, isNPCLoading]);

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
        if (isNPCLoading && npcLoadingMessageIdRef.current) {
            updateMessage(npcLoadingMessageIdRef.current, (msg) => {
                // Only update if the message is still just a spinner frame
                if (SPINNER_FRAMES.includes(msg.message)) {
                    return { ...msg, message: SPINNER_FRAMES[spinnerFrame] };
                }
                return msg;
            });
        }
    }, [spinnerFrame, isStreaming, isNPCLoading, updateMessage]);

    // Clear input when duel move is submitted or when duel ends
    useEffect(() => {
        if (myDuelMove || !isInDuel) {
            setInput('');
        }
    }, [myDuelMove, isInDuel]);

    // Handle autocomplete selection
    const selectNPC = (npc: NPC) => {
        setInput(`@${npc.name} `);
        setShowNPCAutocomplete(false);
        inputRef.current?.focus();
    };

    // Prevent form submission when already submitted a move, handle autocomplete navigation
    const handleKeyDown = (e: React.KeyboardEvent) => {
        // Handle autocomplete navigation
        if (showNPCAutocomplete && filteredNPCs.length > 0) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setAutocompleteIndex(prev => (prev + 1) % filteredNPCs.length);
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                setAutocompleteIndex(prev => (prev - 1 + filteredNPCs.length) % filteredNPCs.length);
                return;
            }
            if (e.key === 'Tab' || (e.key === 'Enter' && input.indexOf(' ') === -1)) {
                e.preventDefault();
                selectNPC(filteredNPCs[autocompleteIndex]);
                return;
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                setShowNPCAutocomplete(false);
                return;
            }
        }

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
        } else if (trimmedInput.startsWith('@')) {
            // Handle NPC interaction
            // Remove the @ prefix
            const withoutAt = trimmedInput.substring(1);
            
            // Try to match against available NPCs (supports multi-word names)
            let targetNPC = null;
            let message = '';
            
            // Sort NPCs by name length (longest first) to match "Professor Elara Voss" before "Professor"
            const sortedNPCs = [...npcs].sort((a, b) => b.name.length - a.name.length);
            
            for (const npc of sortedNPCs) {
                const npcNameLower = npc.name.toLowerCase();
                const inputLower = withoutAt.toLowerCase();
                
                // Check if input starts with this NPC's name followed by a space
                if (inputLower.startsWith(npcNameLower + ' ')) {
                    targetNPC = npc;
                    message = withoutAt.substring(npc.name.length).trim();
                    break;
                }
            }
            
            if (targetNPC && message) {
                try {
                    // Add player's message to chat
                    const playerMessage: ChatMessage = {
                        player_id: player.id,
                        room_id: currentRoom.id,
                        message: trimmedInput,
                        message_type: 'chat',
                        timestamp: new Date().toISOString()
                    };
                    addMessage(playerMessage);
                    
                    // Add loading indicator
                    setIsNPCLoading(true);
                    npcLoadingMessageIdRef.current = `npc-loading-${Date.now()}`;
                    const loadingMessage: ChatMessage = {
                        id: npcLoadingMessageIdRef.current,
                        player_id: 'system',
                        room_id: currentRoom.id,
                        message: SPINNER_FRAMES[0],
                        message_type: 'system',
                        timestamp: new Date().toISOString(),
                        isStreaming: true
                    };
                    addMessage(loadingMessage);
                    
                    // Get recent chat history with this NPC for context (last 20 relevant messages)
                    const { messages } = useGameStore.getState();
                    const recentNPCChat = messages
                        .filter(m => 
                            // Include player messages to this NPC and NPC's responses
                            (m.message_type === 'chat' && m.message.toLowerCase().includes(`@${targetNPC.name.toLowerCase()}`)) ||
                            (m.message_type === 'npc_dialogue' && m.npc_id === targetNPC.id)
                        )
                        .slice(-20) // Last 20 messages
                        .map(m => ({
                            role: m.message_type === 'npc_dialogue' ? 'npc' : 'player',
                            content: m.message_type === 'npc_dialogue' ? m.message : m.message.substring(m.message.indexOf(' ') + 1), // Remove @NPCName prefix
                            timestamp: m.timestamp
                        }));
                    
                    // Send to NPC endpoint with chat history context
                    const response = await apiService.interactWithNPC({
                        player_id: player.id,
                        npc_id: targetNPC.id,
                        room_id: currentRoom.id,
                        message: message,
                        context: {
                            recent_chat: JSON.stringify(recentNPCChat)
                        }
                    });
                    
                    // Remove loading indicator
                    setIsNPCLoading(false);
                    if (npcLoadingMessageIdRef.current) {
                        updateMessage(npcLoadingMessageIdRef.current, (msg) => ({
                            ...msg,
                            message: '',
                            isStreaming: false
                        }));
                        // Actually remove the loading message by filtering it out
                        const store = useGameStore.getState();
                        store.messages = store.messages.filter(m => m.id !== npcLoadingMessageIdRef.current);
                        npcLoadingMessageIdRef.current = null;
                    }
                    
                    // Add NPC's response to chat
                    const npcMessage: ChatMessage = {
                        player_id: 'system',
                        room_id: currentRoom.id,
                        message: response.response,
                        message_type: 'npc_dialogue',
                        timestamp: new Date().toISOString(),
                        npc_id: targetNPC.id,
                        npc_name: targetNPC.name
                    };
                    addMessage(npcMessage);
                    
                    // Handle quest completion if it occurred
                    if (response.quest_completion) {
                        console.log('[NPC] Quest completed via NPC interaction:', response.quest_completion);
                        const quest_data = response.quest_completion.quest as Record<string, unknown> | undefined;
                        const quest_name = (quest_data?.name as string) || 'Unknown Quest';
                        const gold_reward = (response.quest_completion.gold_reward as number) || 0;
                        const badge_name = (response.quest_completion.badge_id as string) || '';
                        
                        let completion_text = `🎉 **Quest Complete: ${quest_name}**\n`;
                        completion_text += `💰 Earned ${gold_reward} gold`;
                        if (badge_name) {
                            completion_text += ` and the '${badge_name}' badge!`;
                        } else {
                            completion_text += '!';
                        }
                        
                        // Add quest completion message
                        const questCompletionMsg: ChatMessage = {
                            player_id: 'system',
                            room_id: currentRoom.id,
                            message: completion_text,
                            message_type: 'quest_completion',
                            timestamp: new Date().toISOString(),
                            quest_data: response.quest_completion
                        };
                        addMessage(questCompletionMsg);
                    }
                } catch (error) {
                    console.error('Failed to interact with NPC:', error);
                    
                    // Clear loading indicator on error
                    setIsNPCLoading(false);
                    if (npcLoadingMessageIdRef.current) {
                        const store = useGameStore.getState();
                        store.messages = store.messages.filter(m => m.id !== npcLoadingMessageIdRef.current);
                        npcLoadingMessageIdRef.current = null;
                    }
                    
                    const errorMessage: ChatMessage = {
                        player_id: 'system',
                        room_id: currentRoom.id,
                        message: `Failed to talk to ${targetNPC.name}. Try again.`,
                        message_type: 'system',
                        timestamp: new Date().toISOString()
                    };
                    addMessage(errorMessage);
                } finally {
                    isSubmittingRef.current = false;
                }
            } else if (!message && targetNPC) {
                // Found NPC but no message
                const errorMessage: ChatMessage = {
                    player_id: 'system',
                    room_id: currentRoom.id,
                    message: `Use format: @${targetNPC.name} your message`,
                    message_type: 'system',
                    timestamp: new Date().toISOString()
                };
                addMessage(errorMessage);
                isSubmittingRef.current = false;
            } else {
                // NPC not found or invalid format
                const errorMessage: ChatMessage = {
                    player_id: 'system',
                    room_id: currentRoom.id,
                    message: `NPC not found. Available NPCs: ${npcs.map(n => n.name).join(', ') || 'none'}`,
                    message_type: 'system',
                    timestamp: new Date().toISOString()
                };
                addMessage(errorMessage);
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

                        // Handle quest item found - load the item data into the store
                        if (response.updates?.quest_item_found) {
                            console.log('[ChatInput] Quest item found:', response.updates.quest_item_found);
                            const store = useGameStore.getState();
                            const questItemData = response.updates.quest_item_found as Record<string, unknown>;

                            // Add the quest item data to the items store
                            if (questItemData.id && questItemData.name) {
                                // Cast to unknown first, then to the expected type for upsertItems
                                store.upsertItems([questItemData as unknown as { id: string; name: string; description: string; properties: Record<string, string> }]);
                                console.log('[ChatInput] Loaded quest item data into store:', questItemData.name);
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
        // Focus the input when toggling
        inputRef.current?.focus();
    };

    return (
        <>
            {/* NPC Autocomplete Dropdown - Rendered via Portal */}
            {showNPCAutocomplete && filteredNPCs.length > 0 && typeof window !== 'undefined' && createPortal(
                <div 
                    ref={autocompleteRef}
                    className="fixed bg-black/95 border border-cyan-500 rounded-lg shadow-2xl max-h-48 overflow-y-auto z-[100]"
                    style={{
                        bottom: `${window.innerHeight - autocompletePosition.top + 8}px`,
                        left: `${autocompletePosition.left}px`,
                        width: `${autocompletePosition.width}px`,
                    }}
                >
                    {filteredNPCs.map((npc, index) => (
                        <div
                            key={npc.id}
                            onClick={() => selectNPC(npc)}
                            className={`px-4 py-2 cursor-pointer flex items-center gap-2 transition-colors ${
                                index === autocompleteIndex
                                    ? 'bg-cyan-900/80 text-cyan-100'
                                    : 'text-cyan-300 hover:bg-cyan-900/50'
                            }`}
                        >
                            <span className="text-lg">💬</span>
                            <span className="font-mono font-bold">{npc.name}</span>
                            {npc.description && (
                                <span className="text-xs text-cyan-400/70 ml-auto truncate max-w-xs">
                                    {npc.description}
                                </span>
                            )}
                        </div>
                    ))}
                </div>,
                document.body
            )}

        <div className="p-3 md:p-4 border-t border-amber-900/30 relative">

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
        </>
    );
};

export default ChatInput;