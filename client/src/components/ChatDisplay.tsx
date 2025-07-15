import React, { useEffect, useRef } from 'react';
import useGameStore from '@/store/gameStore';
import { ChatMessage } from '@/types/game';
import { UserCircleIcon } from '@heroicons/react/24/solid';

const ChatDisplay: React.FC = () => {
    const { messages, playersInRoom, npcs } = useGameStore();
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom when new messages arrive
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const getPlayerName = (playerId: string): string => {
        const player = playersInRoom.find(p => p.id === playerId);
        return player?.name || 'Unknown Player';
    };

    const renderMessage = (message: ChatMessage) => {
        const playerName = message.player_id === 'system' ? 'System' : getPlayerName(message.player_id);

        switch (message.message_type) {
            case 'chat':
                // Check if this is a player action (starts with ">")
                if (message.message.startsWith('> ')) {
                    return (
                        <div className="mb-3 text-amber-400 font-mono text-xl italic">
                            {playerName} {message.message.substring(2)}
                        </div>
                    );
                }

                // Regular chat message
                return (
                    <div className="flex items-start gap-3 mb-3 font-mono">
                        <UserCircleIcon className="w-6 h-6 text-amber-500 flex-shrink-0 mt-1" />
                        <div>
                            <span className="font-bold text-amber-500 text-xl">{playerName}: </span>
                            <span className="text-green-400 text-xl">{message.message}</span>
                        </div>
                    </div>
                );

            case 'emote':
                return (
                    <div className="mb-3 text-yellow-500 italic font-mono text-xl">
                        * {playerName} {message.message}
                    </div>
                );

            case 'system':
                // Check if this is a user command (starts with ">>")
                if (message.message.startsWith('>> ')) {
                    return (
                        <div className="mb-3 text-gray-500 font-mono text-xl">
                            {message.message}
                        </div>
                    );
                }

                return (
                    <div className="mb-3 text-cyan-400 font-mono text-xl">
                        <span className={message.isStreaming ? 'animate-pulse' : ''}>{'>'}</span> {message.message}
                    </div>
                );

            case 'room_description':
                return (
                    <div className="mb-6 font-mono">
                        <div className="flex items-center justify-between mb-3">
                            <div className="text-xl font-bold text-amber-500">
                                {message.title}
                            </div>
                            <div className="text-sm text-amber-300 bg-amber-900 bg-opacity-30 px-2 py-1 rounded">
                                ({message.x ?? 0}, {message.y ?? 0})
                            </div>
                        </div>
                        <div className="text-green-400 text-lg mb-5">
                            {message.description}
                        </div>
                    </div>
                );

            default:
                return null;
        }
    };

    return (
        <div className="relative h-full w-full">
            {/* Gradient overlay for fade effect */}
            <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-black to-transparent z-10 pointer-events-none" />

            <div
                ref={scrollContainerRef}
                className="h-full overflow-y-auto p-6 bg-black bg-opacity-90 font-mono text-xl leading-7"
            >
                <div className="max-w-4xl mx-auto">
                {messages.map((message, index) => (
                        <div key={`${message.timestamp}-${index}`} className="px-3 transition-opacity duration-200">
                        {renderMessage(message)}
                    </div>
                ))}
                <div ref={messagesEndRef} />
                </div>
            </div>
        </div>
    );
};

export default ChatDisplay;