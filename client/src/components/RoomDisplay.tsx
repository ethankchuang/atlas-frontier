import React, { useState, useEffect, lazy, Suspense } from 'react';
import Image from 'next/image';
import useGameStore from '@/store/gameStore';

// Lazy load 3D viewer to avoid SSR issues and reduce initial bundle
const Room3DViewer = lazy(() => import('./Room3DViewer'));

const MAX_RETRIES = 1; // Reduced retries since Replicate URLs expire quickly

// Biome-themed gradient backgrounds for fallback
const BIOME_GRADIENTS: Record<string, string> = {
    forest: 'from-green-900 via-green-800 to-emerald-900',
    desert: 'from-yellow-800 via-orange-700 to-amber-900',
    mountain: 'from-gray-700 via-slate-800 to-gray-900',
    ocean: 'from-blue-900 via-cyan-900 to-indigo-900',
    swamp: 'from-green-950 via-teal-900 to-emerald-950',
    tundra: 'from-cyan-950 via-blue-950 to-slate-900',
    volcanic: 'from-red-900 via-orange-900 to-amber-900',
    bloodplain: 'from-red-950 via-rose-900 to-red-900',
    default: 'from-gray-900 via-slate-900 to-gray-800'
};

const RoomDisplay: React.FC = () => {
    const { currentRoom, isAttemptingMovement, showMovementAnimation, movementFailed, isRoomGenerating } = useGameStore();
    const [imageError, setImageError] = useState(false);
    const [retryCount, setRetryCount] = useState(0);
    const [isImageLoading, setIsImageLoading] = useState(true);
    const [imageHeight, setImageHeight] = useState(0);
    const imageRef = React.useRef<HTMLDivElement>(null);

    // 3D model state
    const [show3D, setShow3D] = useState(false);
    const [model3DError, setModel3DError] = useState(false);
    const [is3DLoading, setIs3DLoading] = useState(true);

    // Determine if we should show 3D view
    useEffect(() => {
        const has3DModel = currentRoom?.model_3d_status === 'ready' && currentRoom?.model_3d_url;
        const shouldShow3D = has3DModel && !model3DError;

        console.log('[RoomDisplay] 3D Model Check:', {
            roomId: currentRoom?.id,
            model_3d_status: currentRoom?.model_3d_status,
            model_3d_url: currentRoom?.model_3d_url?.slice(0, 80),
            has3DModel,
            model3DError,
            shouldShow3D,
            is3DLoading,
            willRender: shouldShow3D ? '3D Viewer' : '2D Image'
        });

        setShow3D(!!shouldShow3D);
    }, [currentRoom?.model_3d_status, currentRoom?.model_3d_url, model3DError, is3DLoading]);

    // Reset error state when room changes
    useEffect(() => {
        console.log('[RoomDisplay] Room changed, resetting image state:', {
            roomId: currentRoom?.id,
            imageUrl: currentRoom?.image_url,
            imageStatus: currentRoom?.image_status,
            model3dStatus: currentRoom?.model_3d_status,
            model3dUrl: currentRoom?.model_3d_url
        });
        setImageError(false);
        setRetryCount(0);
        setIsImageLoading(true);
        setModel3DError(false);
        setIs3DLoading(true);
    }, [currentRoom?.id, currentRoom?.image_url, currentRoom?.image_status]);

    const handleImageLoad = () => {
        console.log('[RoomDisplay] Image loaded successfully');
        setIsImageLoading(false);
        setImageError(false);

        // Measure image height after load
        if (imageRef.current) {
            const height = imageRef.current.offsetHeight;
            setImageHeight(height);
        }
    };

    // Update image height on window resize
    useEffect(() => {
        const updateHeight = () => {
            if (imageRef.current) {
                setImageHeight(imageRef.current.offsetHeight);
            }
        };

        window.addEventListener('resize', updateHeight);
        return () => window.removeEventListener('resize', updateHeight);
    }, []);

    const handleImageError = () => {
        console.error('[RoomDisplay] Image failed to load (likely expired URL)');
        setIsImageLoading(false);
        setImageError(true);
        setRetryCount(prev => prev + 1);
    };

    const getBiomeGradient = (biome?: string): string => {
        if (!biome) return BIOME_GRADIENTS.default;
        const normalizedBiome = biome.toLowerCase();
        return BIOME_GRADIENTS[normalizedBiome] || BIOME_GRADIENTS.default;
    };

    const handle3DError = () => {
        console.warn('[RoomDisplay] 3D model failed to load, falling back to 2D');
        setModel3DError(true);
        setShow3D(false);
        setIs3DLoading(false);
    };

    const handle3DSuccess = () => {
        console.log('[RoomDisplay] 3D model loaded successfully');
        setIs3DLoading(false);
    };

    if (!currentRoom) {
        return (
            <div className="w-full h-full flex items-center justify-center bg-black">
                <div className="text-gray-400">No room loaded</div>
            </div>
        );
    }

    // Use room title without biome (biome now shown in minimap)
    const formattedTitle = currentRoom.title;

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
                    </div>
                )}

                {/* Movement failed overlay */}
                {movementFailed && (
                    <div className="absolute inset-0 pointer-events-none z-30">
                        <div className="absolute inset-0 border-4 border-red-500 opacity-50"></div>
                        <div className="absolute inset-0 bg-red-500 opacity-10"></div>
                    </div>
                )}

                {/* 2D Image View - always shown as base layer (visible during 3D load, fallback if 3D fails) */}
                <>
                        {(isImageLoading || isRoomGenerating) && !imageError && (
                            <div className="absolute inset-0 flex items-center justify-center bg-black">
                                <div className="flex flex-col items-center justify-center">
                                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-400"></div>
                                    <div className="text-gray-400 text-sm mt-2">
                                        {isRoomGenerating ? 'Generating room...' : 'Loading image...'}
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Fallback gradient background when image fails to load or expires */}
                        {(imageError && retryCount >= MAX_RETRIES) && (
                            <div className={`absolute inset-0 bg-gradient-to-br ${getBiomeGradient(currentRoom.biome)} flex items-center justify-center`}>
                                <div className="text-center text-gray-300 px-4 md:px-8 max-w-2xl">
                                    <div className="text-lg md:text-2xl font-bold mb-2 md:mb-4 text-amber-300">{formattedTitle}</div>
                                    <div className="text-sm md:text-base opacity-80 leading-relaxed">
                                        {currentRoom.description}
                                    </div>
                                    <div className="text-xs mt-2 md:mt-4 opacity-60">
                                        (Image temporarily unavailable)
                                    </div>
                                </div>
                            </div>
                        )}

                        {currentRoom.image_url && !imageError && (
                            <>
                                {/* Main image - fills horizontally edge to edge, min 60% height on mobile */}
                                <div ref={imageRef} className="absolute top-0 left-0 right-0 w-full h-auto min-h-[60vh] z-[5]">
                                    <Image
                                        src={currentRoom.image_url}
                                        alt={formattedTitle}
                                        width={1024}
                                        height={1024}
                                        className="w-full h-full object-cover object-top"
                                        onLoad={handleImageLoad}
                                        onError={handleImageError}
                                        style={{
                                            display: isImageLoading ? 'none' : 'block',
                                            minHeight: '60vh'
                                        }}
                                        priority={true}
                                        unoptimized={true}
                                    />
                                </div>
                                {/* Mirrored image at bottom to fill space - only show if there's space below the image */}
                                {!isImageLoading && imageHeight > 0 && (
                                    <div
                                        className="absolute left-0 right-0 overflow-hidden pointer-events-none z-[1]"
                                        style={{
                                            top: `${imageHeight}px`,
                                            height: `calc(100% - ${imageHeight}px)`
                                        }}
                                    >
                                        <Image
                                            src={currentRoom.image_url}
                                            alt=""
                                            width={1024}
                                            height={1024}
                                            className="w-full object-cover scale-y-[-1]"
                                            unoptimized={true}
                                            style={{
                                                objectPosition: 'center bottom',
                                                height: imageHeight
                                            }}
                                        />
                                    </div>
                                )}
                            </>
                        )}
                </>


                {/* 3D Model View - overlays on top of 2D when available */}
                {show3D && currentRoom.model_3d_url && (
                    <div className="absolute inset-0 z-10">
                        <Suspense fallback={null}>
                            <Room3DViewer
                                modelUrl={currentRoom.model_3d_url}
                                onLoadError={handle3DError}
                                onLoadSuccess={handle3DSuccess}
                            />
                        </Suspense>
                    </div>
                )}

                {/* 3D loading indicator - subtle, positioned well above messages area */}
                {show3D && is3DLoading && (
                    <div className="absolute bottom-48 left-1/2 -translate-x-1/2 z-30 pointer-events-none">
                        <div className="bg-black/30 backdrop-blur-sm px-3 py-1 rounded text-xs text-white/40 flex items-center gap-1.5">
                            <div className="animate-spin rounded-full h-2.5 w-2.5 border border-white/30 border-t-transparent"></div>
                            <span>Loading 3D</span>
                        </div>
                    </div>
                )}

                {/* 3D generation status indicator */}
                {currentRoom.model_3d_status === 'generating' && (
                    <div className="absolute top-16 right-4 bg-black bg-opacity-70 px-3 py-1 rounded text-xs text-green-400 z-20 flex items-center gap-2">
                        <div className="animate-spin rounded-full h-3 w-3 border-b border-green-400"></div>
                        Generating 3D world...
                    </div>
                )}
            </div>
            {/* Room Title Overlay */}
            <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-black bg-opacity-70 px-3 md:px-6 py-1 md:py-2 rounded shadow-lg z-20">
                <span className="text-sm md:text-2xl font-bold text-amber-400 font-mono">{formattedTitle}</span>
            </div>
        </div>
    );
};

export default RoomDisplay;