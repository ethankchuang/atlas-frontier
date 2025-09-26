import React, { useMemo, useState, useRef, useCallback } from 'react';
import useGameStore from '@/store/gameStore';

interface FullscreenMinimapProps {
    onClose: () => void;
}

// Generate a pastel color from a string (for unknown biomes)
function pastelColorFromString(str: string) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = hash % 360;
    return `hsl(${h}, 60%, 80%)`;
}

const FullscreenMinimap: React.FC<FullscreenMinimapProps> = ({ onClose }) => {
    const { currentRoom, player, visitedCoordinates, visitedBiomes, biomeColors } = useGameStore();
    
    // Drag and zoom state
    const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
    const [isDragging, setIsDragging] = useState(false);
    const [lastMousePos, setLastMousePos] = useState({ x: 0, y: 0 });
    const [zoom, setZoom] = useState(1);
    const mapRef = useRef<HTMLDivElement>(null);

    // Reset map position and zoom
    const handleReset = useCallback(() => {
        setDragOffset({ x: 0, y: 0 });
        setZoom(1);
    }, []);

    // Handle mouse wheel for zoom
    const handleWheel = useCallback((event: React.WheelEvent) => {
        event.preventDefault();
        const delta = event.deltaY > 0 ? 0.9 : 1.1;
        setZoom(prev => Math.max(0.5, Math.min(3, prev * delta)));
    }, []);

    // Handle mouse down for drag start
    const handleMouseDown = useCallback((event: React.MouseEvent) => {
        setIsDragging(true);
        setLastMousePos({ x: event.clientX, y: event.clientY });
    }, []);

    // Handle mouse move for dragging
    const handleMouseMove = useCallback((event: React.MouseEvent) => {
        if (!isDragging) return;
        
        const deltaX = event.clientX - lastMousePos.x;
        const deltaY = event.clientY - lastMousePos.y;
        
        setDragOffset(prev => ({
            x: prev.x + deltaX,
            y: prev.y + deltaY
        }));
        
        setLastMousePos({ x: event.clientX, y: event.clientY });
    }, [isDragging, lastMousePos]);

    // Handle mouse up for drag end
    const handleMouseUp = useCallback(() => {
        setIsDragging(false);
    }, []);

    // Handle mouse leave for drag end
    const handleMouseLeave = useCallback(() => {
        setIsDragging(false);
    }, []);

    // Handle keyboard shortcuts
    React.useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                onClose();
            } else if (event.key === 'r' || event.key === 'R') {
                handleReset();
            } else if (event.key === '+' || event.key === '=') {
                event.preventDefault();
                setZoom(prev => Math.min(3, prev * 1.1));
            } else if (event.key === '-') {
                event.preventDefault();
                setZoom(prev => Math.max(0.5, prev * 0.9));
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [onClose, handleReset]);

    const generateVisitedRooms = useCallback(() => {
        if (!currentRoom || !player) return [];
        
        const visitedRooms = [];
        const playerX = currentRoom.x;
        const playerY = currentRoom.y;
        
        // Debug logging
        console.log('[FullscreenMinimap] Generating visited rooms:', {
            visitedCoordinates: Array.from(visitedCoordinates),
            visitedBiomes,
            biomeColors
        });
        
        // Create a larger grid around the player (15x15 instead of just visited coordinates)
        const gridSize = 15;
        const centerOffset = Math.floor(gridSize / 2);
        
        for (let y = 0; y < gridSize; y++) {
            for (let x = 0; x < gridSize; x++) {
                const worldX = playerX + (x - centerOffset);
                const worldY = playerY - (y - centerOffset);
                const isPlayerPosition = x === centerOffset && y === centerOffset;
                const coordKey = `${worldX},${worldY}`;
                const isVisited = visitedCoordinates.has(coordKey);
                const biome = isVisited ? visitedBiomes[coordKey]?.toLowerCase() : undefined;
                
                // Debug logging for visited coordinates
                if (isVisited) {
                    console.log(`[FullscreenMinimap] Visited coordinate ${coordKey}:`, {
                        biome,
                        biomeColor: biome ? biomeColors[biome] : undefined
                    });
                }
                
                visitedRooms.push({
                    x: worldX,
                    y: worldY,
                    isPlayerPosition,
                    isVisited,
                    biome,
                });
            }
        }
        
        return visitedRooms;
    }, [currentRoom, player, visitedCoordinates, visitedBiomes, biomeColors]);

    const visitedRooms = useMemo(() => generateVisitedRooms(), [generateVisitedRooms]);
    const visitedCount = visitedCoordinates.size;

    if (!currentRoom || !player) {
        return null;
    }

    const playerX = currentRoom.x;
    const playerY = currentRoom.y;

    return (
        <div className="fixed inset-0 bg-black z-50 flex flex-col">
            {/* Top bar with close button */}
            <div className="flex items-center justify-between p-4 bg-black border-b-2 border-green-700">
                <h2 className="text-2xl text-green-500 font-mono">
                    WORLD MAP
                </h2>
                <div className="flex items-center gap-4">
                    <div className="text-green-500 font-mono text-sm">
                        Zoom: {Math.round(zoom * 100)}% | Drag to move | Scroll/+/- to zoom | R to reset | ESC to close
                    </div>
                    <button
                        onClick={handleReset}
                        className="text-green-500 hover:text-green-300 text-lg font-mono px-3 py-1 border border-green-700 hover:border-green-500 rounded transition-colors"
                        title="Reset map position and zoom"
                    >
                        RESET
                    </button>
                    <button
                        onClick={onClose}
                        className="text-green-500 hover:text-green-300 text-xl font-mono px-4 py-2 border border-green-700 hover:border-green-500 rounded transition-colors"
                    >
                        CLOSE [X]
                    </button>
                </div>
            </div>

            {/* Map container with drag and zoom */}
            <div 
                ref={mapRef}
                className={`flex-1 relative overflow-hidden ${isDragging ? 'cursor-grabbing' : 'cursor-grab'}`}
                onWheel={handleWheel}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseLeave}
            >
                <div 
                    className="absolute inset-0 flex items-center justify-center"
                    style={{
                        transform: `translate(${dragOffset.x}px, ${dragOffset.y}px) scale(${zoom})`,
                        transformOrigin: 'center center',
                        transition: isDragging ? 'none' : 'transform 0.1s ease-out'
                    }}
                >
                    <div className="relative">
                        {visitedRooms.map((tile) => {
                            // Calculate position relative to player
                            const relativeX = (tile.x - playerX) * 28; // 24px tile + 4px gap
                            const relativeY = (playerY - tile.y) * 28; // Invert Y to fix north/south orientation
                            
                            if (tile.isVisited && tile.biome) {
                                const color = biomeColors[tile.biome] || pastelColorFromString(tile.biome);
                                return (
                                    <div
                                        key={`${tile.x},${tile.y}`}
                                        className={`w-6 h-6 absolute border ${tile.isPlayerPosition ? 'animate-pulse' : ''} hover:scale-110 transition-transform duration-150 ${isDragging ? 'pointer-events-none' : ''}`}
                                        style={{ 
                                            background: color, 
                                            borderColor: color,
                                            left: `${relativeX}px`,
                                            top: `${relativeY}px`
                                        }}
                                        title={`${tile.x}, ${tile.y}${tile.isPlayerPosition ? ' (You)' : ''} ${tile.biome ? `- ${tile.biome}` : ''}`}
                                    >
                                        {tile.isPlayerPosition && (
                                            <div className="absolute inset-0 flex items-center justify-center">
                                                <div className="w-1.5 h-1.5 bg-black rounded-full"></div>
                                            </div>
                                        )}
                                    </div>
                                );
                            } else if (tile.isVisited) {
                                return (
                                    <div
                                        key={`${tile.x},${tile.y}`}
                                        className={`w-6 h-6 absolute bg-green-600 border-green-500 border ${tile.isPlayerPosition ? 'animate-pulse' : ''} hover:scale-110 transition-transform duration-150 ${isDragging ? 'pointer-events-none' : ''}`}
                                        style={{
                                            left: `${relativeX}px`,
                                            top: `${relativeY}px`
                                        }}
                                        title={`${tile.x}, ${tile.y}${tile.isPlayerPosition ? ' (You)' : ''}`}
                                    >
                                        {tile.isPlayerPosition && (
                                            <div className="absolute inset-0 flex items-center justify-center">
                                                <div className="w-1.5 h-1.5 bg-black rounded-full"></div>
                                            </div>
                                        )}
                                    </div>
                                );
                            } else {
                                // Unvisited coordinates - show as dark/empty
                                return (
                                    <div
                                        key={`${tile.x},${tile.y}`}
                                        className={`w-6 h-6 absolute bg-black border-gray-800 border ${tile.isPlayerPosition ? 'animate-pulse' : ''} hover:scale-110 transition-transform duration-150 ${isDragging ? 'pointer-events-none' : ''}`}
                                        style={{
                                            left: `${relativeX}px`,
                                            top: `${relativeY}px`
                                        }}
                                        title={`${tile.x}, ${tile.y}${tile.isPlayerPosition ? ' (You)' : ''} (Unvisited)`}
                                    >
                                        {tile.isPlayerPosition && (
                                            <div className="absolute inset-0 flex items-center justify-center">
                                                <div className="w-1.5 h-1.5 bg-white rounded-full"></div>
                                            </div>
                                        )}
                                    </div>
                                );
                            }
                        })}
                    </div>
                </div>
            </div>

            {/* Stats and Legend - Separate section at bottom */}
            <div className="absolute bottom-0 left-0 right-0 bg-black/90 text-white">
                <div className="p-4">
                    <div className="grid grid-cols-2 gap-6">
                        {/* Stats */}
                        <div>
                            <h3 className="font-bold text-lg mb-3 text-yellow-400">Exploration Stats</h3>
                            <div className="text-sm space-y-2">
                                <div className="flex justify-between">
                                    <span>Visited Locations:</span>
                                    <span className="font-mono text-green-400">{visitedCount}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span>Current Position:</span>
                                    <span className="font-mono text-blue-400">({currentRoom?.x}, {currentRoom?.y})</span>
                                </div>
                            </div>
                        </div>
                        
                        {/* Biome Legend */}
                        <div>
                            <h3 className="font-bold text-lg mb-3 text-yellow-400">Biome Colors</h3>
                            <div className="text-sm space-y-2">
                                {Object.entries(biomeColors).length > 0 ? (
                                    Object.entries(biomeColors).map(([biome, color]) => (
                                        <div key={biome} className="flex items-center gap-3">
                                            <div 
                                                className="w-4 h-4 rounded border-2 border-white" 
                                                style={{ backgroundColor: color }}
                                            ></div>
                                            <span className="capitalize font-medium">{biome.replace('_', ' ')}</span>
                                        </div>
                                    ))
                                ) : (
                                    <div className="text-gray-400 italic">No biomes discovered yet</div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

        </div>
    );
};

export default FullscreenMinimap; 