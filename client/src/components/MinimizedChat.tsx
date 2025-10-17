import React from 'react';
import { ChatMessage } from '@/types/game';
import { ChevronUpIcon, ChatBubbleLeftIcon } from '@heroicons/react/24/solid';

interface MinimizedChatProps {
    messages: ChatMessage[];
    onExpand: () => void;
    unreadCount?: number;
}

const MinimizedChat: React.FC<MinimizedChatProps> = ({ messages, onExpand, unreadCount = 0 }) => {
    // Get the last non-important message (exclude quest_storyline, room_description, item_obtained)
    const transientMessages = messages.filter(m => 
        !['quest_storyline', 'room_description', 'item_obtained'].includes(m.message_type)
    );
    
    const lastMessage = transientMessages[transientMessages.length - 1];

    const formatLastMessage = (message: ChatMessage | undefined): string => {
        if (!message) return 'No messages yet...';
        return message.message;
    };

    return (
        <div 
            onClick={onExpand}
            className="cursor-pointer bg-black/40 backdrop-blur-sm hover:bg-black/60 transition-all duration-200 border-t border-amber-900/50"
        >
            <div className="flex items-center justify-between px-3 md:px-4 py-2 gap-2">
                {/* Message preview */}
                <div className="flex items-center gap-2 flex-1 min-w-0">
                    <ChatBubbleLeftIcon className="w-4 h-4 md:w-5 md:h-5 text-amber-500 flex-shrink-0" />
                    <div className="text-xs md:text-sm text-green-400 truncate flex-1">
                        {formatLastMessage(lastMessage)}
                    </div>
                    {unreadCount > 0 && (
                        <span className="flex-shrink-0 bg-amber-500 text-black text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                            {unreadCount}
                        </span>
                    )}
                </div>

                {/* Expand button */}
                <button 
                    className="text-amber-400 hover:text-amber-300 transition-colors p-1 flex-shrink-0"
                    aria-label="Expand chat"
                >
                    <ChevronUpIcon className="w-4 h-4 md:w-5 md:h-5" />
                </button>
            </div>
        </div>
    );
};

export default MinimizedChat;

