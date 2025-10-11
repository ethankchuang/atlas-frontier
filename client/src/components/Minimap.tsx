import React, { useMemo } from 'react';
import useGameStore from '@/store/gameStore';

interface MinimapProps {
    className?: string;
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

const Minimap: React.FC<MinimapProps> = ({ className = '' }) => {
    const { currentRoom, player, isCoordinateVisited, visitedCoordinates, visitedBiomes, biomeColors, setIsMinimapFullscreen } = useGameStore();

    const playerX = currentRoom?.x || 0;
    const playerY = currentRoom?.y || 0;
    const gridSize = 5;
    const centerOffset = Math.floor(gridSize / 2);

    const generateGrid = () => {
        const grid = [];
        for (let y = 0; y < gridSize; y++) {
            const row = [];
            for (let x = 0; x < gridSize; x++) {
                const worldX = playerX + (x - centerOffset);
                const worldY = playerY - (y - centerOffset);
                const isPlayerPosition = x === centerOffset && y === centerOffset;
                const isVisited = isCoordinateVisited(worldX, worldY);
                let biome: string | undefined = undefined;
                const coordKey = `${worldX},${worldY}`;
                if (isVisited && visitedBiomes[coordKey]) {
                    biome = visitedBiomes[coordKey].toLowerCase();
                }
                row.push({
                    x: worldX,
                    y: worldY,
                    isPlayerPosition,
                    isVisited,
                    biome,
                });
            }
            grid.push(row);
        }
        return grid;
    };

    const grid = useMemo(generateGrid, [playerX, playerY, visitedBiomes, centerOffset, isCoordinateVisited]);
    const visitedCount = visitedCoordinates.size;

    if (!currentRoom || !player) {
        return null;
    }

    const handleMinimapClick = (event: React.MouseEvent) => {
        event.stopPropagation();
        setIsMinimapFullscreen(true);
    };

    return (
        <div 
            className={`minimap ${className} cursor-pointer hover:border-green-500 transition-colors`}
            onClick={handleMinimapClick}
            title="Click to expand map"
        >
            <div className="text-xs text-green-500 mb-2 font-mono border-b border-green-700 pb-1 flex items-center justify-between">
                <span>MINIMAP</span>
                <span className="text-green-400 text-xs">[CLICK]</span>
            </div>
            <div className="grid grid-cols-5 gap-1">
                {grid.map((row) =>
                    row.map((tile) => {
                        let bgColor = 'bg-black';
                        let borderColor = 'border-green-900';
                        if (tile.isPlayerPosition) {
                            bgColor = 'bg-yellow-500';
                            borderColor = 'border-yellow-300';
                        } else if (tile.isVisited) {
                            if (tile.biome) {
                                const color = biomeColors[tile.biome] || pastelColorFromString(tile.biome);
                                bgColor = '';
                                borderColor = '';
                                return (
                                    <div
                                        key={`${tile.x},${tile.y}`}
                                        className={`w-4 h-4 relative border-2 ${tile.isPlayerPosition ? 'animate-pulse' : ''} hover:scale-110 transition-transform duration-150`}
                                        style={{ background: color, borderColor: color }}
                                        title={`${tile.x}, ${tile.y}${tile.isPlayerPosition ? ' (You)' : ''} ${tile.biome ? `- ${tile.biome}` : ''}`}
                                    >
                                        {tile.isPlayerPosition && (
                                            <div className="absolute inset-0 flex items-center justify-center">
                                                <div className="w-1 h-1 bg-black rounded-full"></div>
                                            </div>
                                        )}
                                    </div>
                                );
                            } else {
                                bgColor = 'bg-green-600';
                                borderColor = 'border-green-500';
                            }
                        }
                        return (
                            <div
                                key={`${tile.x},${tile.y}`}
                                className={`w-4 h-4 relative ${bgColor} ${borderColor} border ${tile.isPlayerPosition ? 'animate-pulse' : ''} hover:scale-110 transition-transform duration-150`}
                                title={`${tile.x}, ${tile.y}${tile.isPlayerPosition ? ' (You)' : ''}`}
                            >
                                {tile.isPlayerPosition && (
                                    <div className="absolute inset-0 flex items-center justify-center">
                                        <div className="w-1 h-1 bg-black rounded-full"></div>
                                    </div>
                                )}
                            </div>
                        );
                    })
                )}
            </div>
            <div className="text-xs text-green-600 mt-2 font-mono border-t border-green-700 pt-1">
                <div className="flex items-center justify-between">
                    <span>{visitedCount} visited</span>
                    <div className="flex items-center gap-1">
                        <div className="w-2 h-2 bg-yellow-500 border border-yellow-300"></div>
                        <span className="text-xs">You</span>
                    </div>
                </div>
                <div className="text-xs text-green-400 mt-1 font-mono">
                    Position: ({playerX}, {playerY})
                </div>
                {currentRoom?.biome && (
                    <div className="text-[10px] text-green-500 mt-0.5 font-mono truncate" title={currentRoom.biome}>
                        Biome: {currentRoom.biome}
                    </div>
                )}
            </div>
        </div>
    );
};

export default Minimap; 