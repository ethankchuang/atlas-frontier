import React, { useEffect, useState, useCallback } from 'react';
import { ChatMessage } from '@/types/game';

interface QuestStorylineOverlayProps {
    message: ChatMessage;
    onDismiss: () => void;
}

const QuestStorylineOverlay: React.FC<QuestStorylineOverlayProps> = ({ message, onDismiss }) => {
    const [isVisible, setIsVisible] = useState(false);
    const [currentChunkIndex, setCurrentChunkIndex] = useState(0);
    const [textVisible, setTextVisible] = useState(false);

    // Get chunks from quest_data or split the message
    const questData = message.quest_data as { chunks?: string[] } | undefined;
    const chunks: string[] = questData?.chunks || [message.message];
    const currentChunk = chunks[currentChunkIndex] || '';
    const isLastChunk = currentChunkIndex >= chunks.length - 1;

    const handleDismiss = useCallback(() => {
        setIsVisible(false);
        setTimeout(onDismiss, 500);
    }, [onDismiss]);

    const handleNext = useCallback(() => {
        if (isLastChunk) {
            handleDismiss();
        } else {
            setCurrentChunkIndex(prev => prev + 1);
        }
    }, [isLastChunk, handleDismiss]);

    // Fade in animation for current chunk
    useEffect(() => {
        if (currentChunk) {
            setTextVisible(false);
            // Fade in text after a brief delay
            setTimeout(() => setTextVisible(true), 200);
        }
    }, [currentChunkIndex, currentChunk]);

    useEffect(() => {
        // Fade in animation
        setTimeout(() => setIsVisible(true), 100);
    }, []);

    return (
        <div 
            className={`fixed inset-0 z-50 flex items-center justify-center transition-all duration-500 ${
                isVisible ? 'opacity-100' : 'opacity-0'
            }`}
            onClick={handleNext}
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
                    <div className={`text-2xl md:text-4xl font-bold bg-gradient-to-r from-amber-400 via-yellow-500 to-amber-400 bg-clip-text text-transparent leading-relaxed whitespace-pre-wrap drop-shadow-2xl transition-opacity duration-500 ${
                        textVisible ? 'opacity-100' : 'opacity-0'
                    }`}>
                        {currentChunk}
                    </div>
                    <div className="mt-6 text-sm text-amber-300/70">
                        {isLastChunk 
                            ? 'Click to continue' 
                            : `Part ${currentChunkIndex + 1} of ${chunks.length} - Click to continue`
                        }
                    </div>
                </div>
            </div>
        </div>
    );
};

export default QuestStorylineOverlay;

