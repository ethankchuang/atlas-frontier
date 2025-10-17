import React, { useEffect, useState } from 'react';
import { ChatMessage } from '@/types/game';

interface QuestStorylineOverlayProps {
    message: ChatMessage;
    onDismiss: () => void;
}

const QuestStorylineOverlay: React.FC<QuestStorylineOverlayProps> = ({ message, onDismiss }) => {
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        // Fade in animation
        setTimeout(() => setIsVisible(true), 100);

        // Auto-dismiss after 10 seconds
        const timer = setTimeout(() => {
            handleDismiss();
        }, 10000);

        return () => clearTimeout(timer);
    }, []);

    const handleDismiss = () => {
        setIsVisible(false);
        setTimeout(onDismiss, 500);
    };

    return (
        <div 
            className={`fixed inset-0 z-50 flex items-center justify-center transition-all duration-500 ${
                isVisible ? 'opacity-100' : 'opacity-0'
            }`}
            onClick={handleDismiss}
        >
            {/* Backdrop with darkening effect */}
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            
            {/* Quest message */}
            <div 
                className={`relative z-10 max-w-4xl mx-4 px-6 py-8 md:px-12 md:py-12 transition-transform duration-500 ${
                    isVisible ? 'scale-100' : 'scale-95'
                }`}
            >
                <div className="text-center">
                    <div className="text-3xl md:text-5xl font-bold bg-gradient-to-r from-amber-400 via-yellow-500 to-amber-400 bg-clip-text text-transparent leading-relaxed whitespace-pre-wrap drop-shadow-2xl animate-pulse-slow">
                        {message.message}
                    </div>
                    <div className="mt-8 text-sm text-amber-300/70">
                        Click anywhere to continue
                    </div>
                </div>
            </div>
        </div>
    );
};

export default QuestStorylineOverlay;

