import React, { useEffect, useState, useCallback, useRef } from 'react';
import { ChatMessage } from '@/types/game';

interface QuestStorylineOverlayProps {
    message: ChatMessage;
    onDismiss: () => void;
}

const QuestStorylineOverlay: React.FC<QuestStorylineOverlayProps> = ({ message, onDismiss }) => {
    const [isVisible, setIsVisible] = useState(false);
    const [currentChunkIndex, setCurrentChunkIndex] = useState(0);
    const [displayedText, setDisplayedText] = useState('');
    const [isTyping, setIsTyping] = useState(false);
    const typewriterTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    
    // Get chunks from quest_data or split the message
    const chunks = message.quest_data?.chunks || [message.message];
    const currentChunk = chunks[currentChunkIndex] || '';
    const isLastChunk = currentChunkIndex >= chunks.length - 1;

    const handleDismiss = useCallback(() => {
        setIsVisible(false);
        setTimeout(onDismiss, 500);
    }, [onDismiss]);

    const handleNext = useCallback(() => {
        if (isTyping) {
            // If still typing, skip to end
            setDisplayedText(currentChunk);
            setIsTyping(false);
            if (typewriterTimeoutRef.current) {
                clearTimeout(typewriterTimeoutRef.current);
            }
        } else if (isLastChunk) {
            handleDismiss();
        } else {
            setCurrentChunkIndex(prev => prev + 1);
        }
    }, [isLastChunk, handleDismiss, isTyping, currentChunk]);

    // Typewriter effect for current chunk
    useEffect(() => {
        if (currentChunk) {
            setDisplayedText('');
            setIsTyping(true);
            
            const words = currentChunk.split(' ');
            let wordIndex = 0;
            
            const typeNextWords = () => {
                if (wordIndex < words.length) {
                    // Show 3 words at a time, or remaining words if less than 3
                    const wordsToShow = Math.min(3, words.length - wordIndex);
                    setDisplayedText(words.slice(0, wordIndex + wordsToShow).join(' '));
                    wordIndex += wordsToShow;
                    typewriterTimeoutRef.current = setTimeout(typeNextWords, 300); // 300ms per 3 words
                } else {
                    setIsTyping(false);
                }
            };
            
            // Start typing after a brief delay
            typewriterTimeoutRef.current = setTimeout(typeNextWords, 200);
        }

        return () => {
            if (typewriterTimeoutRef.current) {
                clearTimeout(typewriterTimeoutRef.current);
            }
        };
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
                    <div className="text-2xl md:text-4xl font-bold bg-gradient-to-r from-amber-400 via-yellow-500 to-amber-400 bg-clip-text text-transparent leading-relaxed whitespace-pre-wrap drop-shadow-2xl">
                        {displayedText}
                        {isTyping && (
                            <span className="inline-block w-0.5 h-8 md:h-12 bg-amber-400 ml-1 animate-pulse">
                                |
                            </span>
                        )}
                    </div>
                    <div className="mt-6 text-sm text-amber-300/70">
                        {isTyping 
                            ? 'Typing...' 
                            : isLastChunk 
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

