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
        
        // Get all visited coordinates
        for (const coordKey of visitedCoordinates) {
            const [x, y] = coordKey.split(',').map(Number);
            const isPlayerPosition = x === playerX && y === playerY;
            const biome = visitedBiomes[coordKey]?.toLowerCase();
            
            visitedRooms.push({
                x,
                y,
                isPlayerPosition,
                isVisited: true,
                biome,
            });
        }
        
        return visitedRooms;
    }, [currentRoom, player, visitedCoordinates, visitedBiomes]);

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
                            const relativeY = (tile.y - playerY) * 28;
                            
                            if (tile.biome) {
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
                            } else {
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
                            }
                        })}
                    </div>
                </div>
            </div>

            {/* Bottom legend */}
            <div className="p-4 bg-black border-t-2 border-green-700">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Stats */}
                    <div className="text-green-500 font-mono">
                        <div className="text-lg mb-2 border-b border-green-700 pb-1">STATISTICS</div>
                        <div className="space-y-1 text-sm">
                            <div>Visited Locations: {visitedCount}</div>
                            <div>Current Position: ({playerX}, {playerY})</div>
                            <div>Biomes Discovered: {Object.keys(biomeColors).length}</div>
                        </div>
                    </div>

                    {/* Legend */}
                    <div className="text-green-500 font-mono">
                        <div className="text-lg mb-2 border-b border-green-700 pb-1">LEGEND</div>
                        <div className="space-y-2 text-sm">
                            <div className="flex items-center gap-2">
                                <div className="w-4 h-4 bg-yellow-500 border border-yellow-300"></div>
                                <span>Your Position</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="w-4 h-4 bg-green-600 border border-green-500"></div>
                                <span>Visited Location</span>
                            </div>
                        </div>
                    </div>
                    
                    {/* Biome Legend */}
                    {Object.keys(biomeColors).length > 0 && (
                        <div className="text-green-500 font-mono">
                            <div className="text-lg mb-2 border-b border-green-700 pb-1">BIOMES</div>
                            <div className="grid grid-cols-2 gap-1 text-xs max-h-32 overflow-y-auto">
                                {Object.entries(biomeColors).map(([biome, color]) => (
                                    <div key={biome} className="flex items-center gap-1">
                                        <div 
                                            className="w-3 h-3 border border-gray-600"
                                            style={{ background: color }}
                                        ></div>
                                        <span className="capitalize">{biome}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default FullscreenMinimap; 