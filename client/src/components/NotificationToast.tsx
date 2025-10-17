import React, { useEffect, useState } from 'react';
import { ChatMessage } from '@/types/game';

interface NotificationToastProps {
    message: ChatMessage;
    onDismiss: () => void;
    autoDismissMs?: number;
}

const NotificationToast: React.FC<NotificationToastProps> = ({ 
    message, 
    onDismiss, 
    autoDismissMs = 5000 
}) => {
    const [isVisible, setIsVisible] = useState(false);
    const [isPinned, setIsPinned] = useState(false);

    useEffect(() => {
        // Fade in animation
        setTimeout(() => setIsVisible(true), 50);

        // Auto-dismiss timer
        if (!isPinned && autoDismissMs > 0) {
            const timer = setTimeout(() => {
                setIsVisible(false);
                setTimeout(onDismiss, 300); // Wait for fade out animation
            }, autoDismissMs);

            return () => clearTimeout(timer);
        }
    }, [onDismiss, autoDismissMs, isPinned]);

    const handlePin = (e: React.MouseEvent) => {
        e.stopPropagation();
        setIsPinned(!isPinned);
    };

    const handleDismiss = () => {
        setIsVisible(false);
        setTimeout(onDismiss, 300);
    };

    if (message.message_type === 'room_description') {
        return (
            <div 
                className={`transition-all duration-300 transform ${
                    isVisible ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-4'
                }`}
            >
                <div className="bg-black/80 backdrop-blur-md border-2 border-amber-500/50 rounded-lg p-3 md:p-4 max-w-2xl mx-auto shadow-2xl">
                    <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 text-sm md:text-base text-green-400 leading-relaxed">
                            <span className="text-amber-300/70 text-xs md:text-sm">({message.x ?? 0}, {message.y ?? 0})</span> {message.description}
                            {message.atmospheric_presence && (
                                <div className="text-sm md:text-base text-yellow-400 mt-2 font-bold">
                                    {message.atmospheric_presence}
                                </div>
                            )}
                        </div>
                        <div className="flex gap-1 flex-shrink-0">
                            <button
                                onClick={handlePin}
                                className={`text-xs px-1.5 py-1 rounded transition-colors ${
                                    isPinned 
                                        ? 'bg-amber-500 text-black' 
                                        : 'bg-amber-900/30 text-amber-400 hover:bg-amber-900/50'
                                }`}
                                title={isPinned ? "Unpin" : "Pin"}
                            >
                                📌
                            </button>
                            <button
                                onClick={handleDismiss}
                                className="text-amber-400 hover:text-amber-200 text-xl leading-none px-1"
                                title="Dismiss"
                            >
                                ×
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    if (message.message_type === 'item_obtained') {
        return (
            <div 
                className={`transition-all duration-300 transform ${
                    isVisible ? 'opacity-100 translate-x-0 scale-100' : 'opacity-0 translate-x-8 scale-95'
                }`}
            >
                <div className="bg-gradient-to-r from-purple-900/90 to-purple-800/90 backdrop-blur-md border-2 border-purple-400 rounded-lg p-3 md:p-4 shadow-2xl animate-bounce-once">
                    <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                            <span className="text-2xl">✨</span>
                            <div className="text-sm md:text-lg font-bold text-purple-200">
                                {message.message}
                            </div>
                        </div>
                        <button
                            onClick={handleDismiss}
                            className="text-purple-200 hover:text-white text-xl leading-none"
                        >
                            ×
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return null;
};

export default NotificationToast;

