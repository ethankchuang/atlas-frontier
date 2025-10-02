import React, { useState, useEffect } from 'react';
import Image from 'next/image';
import useGameStore from '@/store/gameStore';

const MAX_RETRIES = 3;

const RoomDisplay: React.FC = () => {
    const { currentRoom, isAttemptingMovement, showMovementAnimation, movementFailed, isRoomGenerating } = useGameStore();
    const [imageError, setImageError] = useState(false);
    const [retryCount, setRetryCount] = useState(0);
    const [isImageLoading, setIsImageLoading] = useState(true);

    // Reset error state when room changes
    useEffect(() => {
        const imageStartTime = performance.now();
        console.log('[RoomDisplay] Room changed, resetting image state:', {
            roomId: currentRoom?.id,
            imageUrl: currentRoom?.image_url,
            imageStatus: currentRoom?.image_status
        });
        console.log(`⏱️ [IMAGE TIMING] Starting to load image for room ${currentRoom?.id}`);
        setImageError(false);
        setRetryCount(0);
        setIsImageLoading(true);
    }, [currentRoom?.id, currentRoom?.image_url, currentRoom?.image_status]);

    const handleImageLoad = () => {
        console.log('[RoomDisplay] Image loaded successfully:', currentRoom?.image_url);
        setIsImageLoading(false);
        setImageError(false);
    };

    const handleImageError = (error: React.SyntheticEvent<HTMLImageElement, Event>) => {
        console.error('[RoomDisplay] Image failed to load:', currentRoom?.image_url, error);
        setIsImageLoading(false);
        setImageError(true);
        setRetryCount(prev => prev + 1);
    };

    if (!currentRoom) {
        return (
            <div className="w-full h-full flex items-center justify-center bg-black">
                <div className="text-gray-400">No room loaded</div>
            </div>
        );
    }

    // Format the room title with biome in parenthesis if present
    const formattedTitle = currentRoom.biome
        ? `${currentRoom.title} (${currentRoom.biome})`
        : currentRoom.title;

    return (
        <div className="w-full h-full bg-black">
            {/* Room Image */}
            <div className={`relative w-full h-full overflow-hidden bg-black ${
                showMovementAnimation ? 'movement-attempting' : ''
            } ${movementFailed ? 'movement-failed' : ''} ${
                isAttemptingMovement && !showMovementAnimation ? 'opacity-80' : ''
            }`}>
                {/* Movement attempting overlay - only show after first text chunk */}
                {showMovementAnimation && !movementFailed && (
                    <div className="absolute inset-0 pointer-events-none z-30">
                        {/* Pulsing border */}
                        <div className="absolute inset-0 border-4 border-amber-500 movement-overlay"></div>

                        {/* Corner indicators */}
                        <div className="absolute top-4 left-4 w-8 h-8 border-l-4 border-t-4 border-amber-500 movement-overlay"></div>
                        <div className="absolute top-4 right-4 w-8 h-8 border-r-4 border-t-4 border-amber-500 movement-overlay"></div>
                        <div className="absolute bottom-4 left-4 w-8 h-8 border-l-4 border-b-4 border-amber-500 movement-overlay"></div>
                        <div className="absolute bottom-4 right-4 w-8 h-8 border-r-4 border-b-4 border-amber-500 movement-overlay"></div>

                        {/* Scanning line effect */}
                        <div className="absolute inset-0 overflow-hidden">
                            <div className="absolute inset-x-0 h-1 bg-gradient-to-r from-transparent via-amber-500 to-transparent movement-overlay"
                                 style={{ top: '50%', transform: 'translateY(-50%)' }}></div>
                        </div>
                    </div>
                )}

                {/* Movement failed overlay */}
                {movementFailed && (
                    <div className="absolute inset-0 pointer-events-none z-30">
                        <div className="absolute inset-0 border-4 border-red-500 opacity-50"></div>
                        <div className="absolute inset-0 bg-red-500 opacity-10"></div>
                    </div>
                )}

                {(isImageLoading || isRoomGenerating) && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black">
                        <div className="flex flex-col items-center justify-center">
                            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-400"></div>
                            <div className="text-gray-400 text-sm mt-2">
                                {isRoomGenerating ? 'Generating room...' : 'Loading image...'}
                            </div>
                        </div>
                    </div>
                )}
                {imageError && retryCount >= MAX_RETRIES && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black">
                        <div className="text-red-500 text-center">
                            <div className="text-lg mb-2">Failed to load image</div>
                            <div className="text-sm">Please try again later</div>
                        </div>
                    </div>
                )}
                {currentRoom.image_url && !imageError && (
                    <Image
                        src={currentRoom.image_url}
                        alt={formattedTitle}
                        fill
                        className="object-cover"
                        onLoad={handleImageLoad}
                        onError={handleImageError}
                        style={{ display: isImageLoading ? 'none' : 'block' }}
                        priority={true}
                        unoptimized={true}
                    />
                )}
            </div>
            {/* Room Title Overlay */}
            <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-black bg-opacity-70 px-6 py-2 rounded shadow-lg z-20">
                <span className="text-2xl font-bold text-amber-400 font-mono">{formattedTitle}</span>
            </div>
        </div>
    );
};

export default RoomDisplay;