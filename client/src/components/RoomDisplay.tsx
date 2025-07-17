import React, { useState, useEffect } from 'react';
import useGameStore from '@/store/gameStore';

const MAX_RETRIES = 3;

const RoomDisplay: React.FC = () => {
    const { currentRoom } = useGameStore();
    const [imageError, setImageError] = useState(false);
    const [retryCount, setRetryCount] = useState(0);
    const [isImageLoading, setIsImageLoading] = useState(true);
    const { isRoomGenerating } = useGameStore();

    // Reset error state when room changes
    useEffect(() => {
        setImageError(false);
        setRetryCount(0);
        setIsImageLoading(true);
    }, [currentRoom?.id]);

    const handleImageLoad = () => {
        setIsImageLoading(false);
        setImageError(false);
    };

    const handleImageError = () => {
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

    return (
        <div className="w-full h-full bg-black">
            {/* Room Image */}
            <div className="relative w-full h-full overflow-hidden bg-black">
                {(isImageLoading || isRoomGenerating) && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black">
                        <div className="flex justify-center">
                            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-400"></div>
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
                    <img
                        src={currentRoom.image_url}
                        alt={currentRoom.title}
                        className="w-full h-full object-cover"
                        onLoad={handleImageLoad}
                        onError={handleImageError}
                        style={{ display: isImageLoading ? 'none' : 'block' }}
                    />
                )}
            </div>
        </div>
    );
};

export default RoomDisplay;