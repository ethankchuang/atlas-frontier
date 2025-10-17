import React, { useEffect, useRef } from 'react';
import useGameStore from '@/store/gameStore';
import { ChatMessage } from '@/types/game';
import { UserCircleIcon } from '@heroicons/react/24/solid';

interface ChatDisplayProps {
    onScrollToTop?: () => void;
}

const ChatDisplay: React.FC<ChatDisplayProps> = ({ onScrollToTop }) => {
    const { messages, playersInRoom, player } = useGameStore();
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when new messages arrive
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    // Detect scroll to top
    useEffect(() => {
        const container = scrollContainerRef.current;
        if (!container || !onScrollToTop) return;

        const handleScroll = () => {
            if (container.scrollTop <= 10) {
                onScrollToTop();
            }
        };

        container.addEventListener('scroll', handleScroll);
        return () => container.removeEventListener('scroll', handleScroll);
    }, [onScrollToTop]);

    const getPlayerName = (playerId: string): string => {
        // First check if it's the current player
        if (player && player.id === playerId) {
            return player.name;
        }
        
        // Then check other players in room
        const roomPlayer = playersInRoom.find(p => p.id === playerId);
        if (roomPlayer) {
            return roomPlayer.name;
        }
        
        // If we can't find the player, try to extract name from player_id
        // For guest players, the name might be in the format "Anon_<id>"
        if (playerId.startsWith('guest_')) {
            return `Anon_${playerId.split('_')[1]}`;
        }
        
        return 'Unknown Player';
    };

    const renderMessage = (message: ChatMessage) => {
        const playerName = message.player_id === 'system' ? 'System' : getPlayerName(message.player_id);

        switch (message.message_type) {
            case 'chat':
                // Check if this is a player action (starts with ">")
                if (message.message.startsWith('> ')) {
                    return (
                        <div className="mb-4 text-amber-300 font-mono text-sm md:text-lg italic bg-amber-900/30 px-3 py-2 rounded-lg border-l-2 border-amber-400">
                            {playerName} {message.message.substring(2)}
                        </div>
                    );
                }

                // Regular chat message
                return (
                    <div className="flex items-start gap-2 md:gap-3 mb-4 font-mono bg-black/40 px-3 py-2.5 rounded-lg border border-gray-700/50">
                        <UserCircleIcon className="w-4 h-4 md:w-5 md:h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                        <div className="flex-1">
                            <span className="font-bold text-amber-400 text-sm md:text-base">{playerName}: </span>
                            <span className="text-green-300 text-sm md:text-base leading-relaxed">{message.message}</span>
                        </div>
                    </div>
                );

            case 'emote':
                return (
                    <div className="mb-4 text-yellow-300 italic font-mono text-sm md:text-lg bg-yellow-900/30 px-3 py-2 rounded-lg border border-yellow-700/30">
                        * {playerName} {message.message}
                    </div>
                );

            case 'system':
                // Check if this is a user command (starts with ">>")
                if (message.message.startsWith('>> ')) {
                    return (
                        <div className="mb-3 text-gray-400 font-mono text-xs md:text-sm italic px-2">
                            {message.message}
                        </div>
                    );
                }

                return (
                    <div className="mb-4 text-cyan-300 font-mono text-sm md:text-lg bg-cyan-900/30 px-3 py-2.5 rounded-lg border-l-3 border-cyan-400 leading-relaxed">
                        <span className={message.isStreaming ? 'animate-pulse' : ''}>{'>'}</span>{' '}
                        <span className={message.isStreaming && message.message === '▮' ? 'animate-blink' : ''}>
                            {message.message}
                        </span>
                    </div>
                );

            case 'ai_response':
                return (
                    <div className="mb-4 text-green-300 font-mono text-sm md:text-lg bg-green-900/30 px-3 py-2.5 rounded-lg border border-green-700/30 leading-relaxed">
                        {message.message}
                    </div>
                );

            case 'room_description':
                return (
                    <div className="mb-6 font-mono">
                        <div className="flex items-center justify-between mb-2 md:mb-3">
                            <div className="text-base md:text-xl font-bold text-amber-500">
                                {message.title}{message.biome ? ` (${message.biome})` : ''}
                            </div>
                            <div className="text-xs md:text-sm text-amber-300 bg-amber-900 bg-opacity-30 px-2 py-1 rounded">
                                ({message.x ?? 0}, {message.y ?? 0})
                            </div>
                        </div>
                        <div className="text-green-400 text-sm md:text-lg mb-3">
                            {message.description}
                        </div>
                        {message.atmospheric_presence && (
                            <div className="text-yellow-400 text-sm md:text-base mb-3 font-bold">
                                {message.atmospheric_presence}
                            </div>
                        )}
                    </div>
                );

            case 'item_obtained':
                return (
                    <div className="mb-3 text-purple-400 font-mono text-base md:text-xl font-bold bg-purple-900 bg-opacity-30 px-3 md:px-4 py-2 rounded border border-purple-500">
                        {message.message}
                    </div>
                );

            case 'quest_storyline':
                return (
                    <div className="mb-6 font-mono text-center px-4">
                        <div className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-amber-400 via-yellow-500 to-amber-400 bg-clip-text text-transparent leading-relaxed whitespace-pre-wrap">
                            {message.message}
                        </div>
                    </div>
                );

            case 'quest_completion':
                return (
                    <div className="mb-3 text-yellow-300 font-mono text-base md:text-lg font-bold bg-yellow-900/30 px-3 md:px-4 py-2 rounded border border-yellow-500">
                        {message.message}
                    </div>
                );

            default:
                return null;
        }
    };

    // Filter out messages that are ONLY shown elsewhere (quest_storyline full overlay, room_description toast)
    // Keep item_obtained and quest_completion in chat for history log
    const transientMessages = messages.filter(m => 
        !['quest_storyline', 'room_description'].includes(m.message_type)
    );

    return (
        <div className="relative h-full w-full">
            {/* Gradient overlay for fade effect */}
            <div className="absolute top-0 left-0 right-0 h-24 bg-gradient-to-b from-black/40 to-transparent z-10 pointer-events-none" />

            <div
                ref={scrollContainerRef}
                className="h-full overflow-y-auto p-4 md:p-6 font-mono"
            >
                {transientMessages.length === 0 ? (
                    <div className="text-center text-gray-400 mt-12 text-sm md:text-base">
                        No messages yet. Start your adventure!
                    </div>
                ) : (
                    transientMessages.map((message, index) => (
                        <div key={`${message.timestamp}-${index}`} className="transition-opacity duration-200">
                            {renderMessage(message)}
                        </div>
                    ))
                )}
                <div ref={messagesEndRef} />
            </div>
        </div>
    );
};

export default ChatDisplay;