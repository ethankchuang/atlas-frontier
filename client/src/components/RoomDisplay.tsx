import React, { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import useGameStore from '@/store/gameStore';
import { UserCircleIcon } from '@heroicons/react/24/solid';

const RoomDisplay: React.FC = () => {
    const { currentRoom } = useGameStore();
    const [imageError, setImageError] = useState(false);
    const [isImageLoading, setIsImageLoading] = useState(true);
    const [currentImageUrl, setCurrentImageUrl] = useState<string | null>(null);
    const [retryCount, setRetryCount] = useState(0);
    const MAX_RETRIES = 3;

    const loadImage = useCallback((url: string) => {
        console.log('[RoomDisplay] Attempting to load image:', url);
        const img = new window.Image();
        img.src = url;

        return new Promise<void>((resolve, reject) => {
            img.onload = () => {
                console.log('[RoomDisplay] Image preloaded successfully:', url);
                resolve();
            };
            img.onerror = () => {
                console.error('[RoomDisplay] Image preload failed:', url);
                reject(new Error('Image failed to load'));
            };
        });
    }, []);

    // Reset loading state when room changes
    useEffect(() => {
        console.log('[RoomDisplay] Room changed - FULL DATA:', {
            room: currentRoom,
            imageError,
            isImageLoading,
            currentImageUrl,
            retryCount
        });

        if (!currentRoom) {
            console.log('[RoomDisplay] No room data available');
            return;
        }

        // Always reset error state on room change
        setImageError(false);
        setRetryCount(0);

        // Handle image status and URL updates
        if (currentRoom.image_url && currentRoom.image_url !== currentImageUrl) {
            console.log('[RoomDisplay] Setting new image URL:', {
                url: currentRoom.image_url,
                status: currentRoom.image_status,
                previousUrl: currentImageUrl
            });

            // Try to preload the image
            loadImage(currentRoom.image_url)
                .then(() => {
                    if (currentRoom.image_url) {  // Check again to ensure URL hasn't changed
                        setCurrentImageUrl(currentRoom.image_url);
                        setIsImageLoading(false);
                        setImageError(false);
                    }
                })
                .catch(() => {
                    console.error('[RoomDisplay] Initial image load failed');
                    setIsImageLoading(true);
                    // Don't set error yet, let the retry mechanism handle it
                });
        }

        // Handle specific image states
        if (currentRoom.image_status === 'generating') {
            console.log('[RoomDisplay] Image status is generating');
            setIsImageLoading(true);
        } else if (currentRoom.image_status === 'error') {
            console.log('[RoomDisplay] Image status is error');
            setImageError(true);
            setIsImageLoading(false);
        }
    }, [currentRoom?.id, currentRoom?.image_url, currentRoom?.image_status, loadImage]);

    // Handle image retry logic
    useEffect(() => {
        if (imageError && retryCount < MAX_RETRIES && currentRoom?.image_url) {
            const imageUrl = currentRoom.image_url;  // Store URL to ensure it doesn't change during retry
            console.log(`[RoomDisplay] Retrying image load (attempt ${retryCount + 1}/${MAX_RETRIES})`);
            const timer = setTimeout(() => {
                setIsImageLoading(true);
                setImageError(false);
                loadImage(imageUrl)
                    .then(() => {
                        if (currentRoom.image_url === imageUrl) {  // Only update if URL hasn't changed
                            setCurrentImageUrl(imageUrl);
                            setIsImageLoading(false);
                            setImageError(false);
                        }
                    })
                    .catch(() => {
                        setRetryCount(prev => prev + 1);
                        setImageError(true);
                        setIsImageLoading(false);
                    });
            }, Math.min(1000 * Math.pow(2, retryCount), 5000)); // Exponential backoff, max 5 seconds

            return () => clearTimeout(timer);
        }
    }, [imageError, retryCount, currentRoom?.image_url, loadImage]);

    if (!currentRoom) {
        return (
            <div className="flex items-center justify-center h-full bg-black">
                <div className="text-white text-xl">Loading room...</div>
            </div>
        );
    }

    return (
        <div className="relative h-full bg-black">
            {/* Room Image */}
            <div className="relative w-full h-full overflow-hidden bg-black">
                {isImageLoading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black">
                        <div className="text-center">
                            <div className="text-green-400 mb-2 text-2xl">
                                {currentRoom.image_status === 'generating' ? (
                                    'Generating room image...'
                                ) : (
                                    'Loading image...'
                                )}
                            </div>
                            {currentRoom.image_status === 'generating' && (
                                <div className="text-xl text-amber-500">
                                    This may take a few moments...
                                </div>
                            )}
                        </div>
                    </div>
                )}
                {imageError && retryCount >= MAX_RETRIES && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black">
                        <div className="text-red-500 text-center">
                            <div>Failed to load room image</div>
                            <div className="text-sm mt-2">Please try refreshing the page</div>
                        </div>
                    </div>
                )}
                {currentImageUrl && (
                    <Image
                        src={currentImageUrl}
                        alt={currentRoom.title}
                        fill
                        style={{ objectFit: 'cover', objectPosition: 'center' }}
                        onLoad={() => {
                            console.log('[RoomDisplay] Image loaded successfully');
                            setIsImageLoading(false);
                            setImageError(false);
                        }}
                        onError={(e) => {
                            console.error('[RoomDisplay] Image failed to load:', e);
                            setImageError(true);
                            setIsImageLoading(false);
                        }}
                        priority={true}
                        className={`transition-opacity duration-300 ${isImageLoading ? 'opacity-0' : 'opacity-100'}`}
                    />
                )}
            </div>
            
            {/* Coordinate Display Overlay */}
            <div className="absolute top-4 left-4 bg-black bg-opacity-75 border-2 border-amber-500 px-3 py-2 rounded font-mono text-amber-400 text-lg z-10">
                <div className="text-center">
                    <div className="text-sm text-amber-300">COORDINATES</div>
                    <div className="text-xl font-bold">
                        ({currentRoom.x ?? 0}, {currentRoom.y ?? 0})
                    </div>
                </div>
            </div>
        </div>
    );
};

export default RoomDisplay;