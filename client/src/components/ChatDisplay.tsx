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
                        <div className="mb-3 text-amber-400 font-mono text-base md:text-xl italic">
                            {playerName} {message.message.substring(2)}
                        </div>
                    );
                }

                // Regular chat message
                return (
                    <div className="flex items-start gap-2 md:gap-3 mb-3 font-mono">
                        <UserCircleIcon className="w-5 h-5 md:w-6 md:h-6 text-amber-500 flex-shrink-0 mt-1" />
                        <div>
                            <span className="font-bold text-amber-500 text-base md:text-xl">{playerName}: </span>
                            <span className="text-green-400 text-base md:text-xl">{message.message}</span>
                        </div>
                    </div>
                );

            case 'emote':
                return (
                    <div className="mb-3 text-yellow-500 italic font-mono text-base md:text-xl">
                        * {playerName} {message.message}
                    </div>
                );

            case 'system':
                // Check if this is a user command (starts with ">>")
                if (message.message.startsWith('>> ')) {
                    return (
                        <div className="mb-3 text-gray-500 font-mono text-base md:text-xl">
                            {message.message}
                        </div>
                    );
                }

                return (
                    <div className="mb-3 text-cyan-400 font-mono text-base md:text-xl">
                        <span className={message.isStreaming ? 'animate-pulse' : ''}>{'>'}</span>{' '}
                        <span className={message.isStreaming && message.message === '▮' ? 'animate-blink' : ''}>
                            {message.message}
                        </span>
                    </div>
                );

            case 'ai_response':
                return (
                    <div className="mb-3 text-green-400 font-mono text-base md:text-xl">
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

            default:
                return null;
        }
    };

    return (
        <div className="relative h-full w-full">
            {/* Gradient overlay for fade effect */}
            <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-black/30 to-transparent z-10 pointer-events-none" />

            <div
                ref={scrollContainerRef}
                className="h-full overflow-y-auto p-3 md:p-4 font-mono text-base md:text-xl leading-6 md:leading-7"
            >
                {messages.map((message, index) => (
                    <div key={`${message.timestamp}-${index}`} className="px-2 md:px-3 transition-opacity duration-200">
                        {renderMessage(message)}
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>
        </div>
    );
};

export default ChatDisplay;