import React from 'react';
import useGameStore from '@/store/gameStore';

interface MinimapProps {
    className?: string;
}

const Minimap: React.FC<MinimapProps> = ({ className = '' }) => {
    const { currentRoom, player, isCoordinateVisited } = useGameStore();
    
    if (!currentRoom || !player) {
        return null;
    }

    const playerX = currentRoom.x;
    const playerY = currentRoom.y;
    
    // Create a 5x5 grid centered on the player
    const gridSize = 5;
    const centerOffset = Math.floor(gridSize / 2); // 2 for 5x5 grid
    
    // Generate grid coordinates relative to player position
    // Note: Y-axis is flipped because screen coordinates increase downward, but world coordinates increase northward
    const generateGrid = () => {
        const grid = [];
        for (let y = 0; y < gridSize; y++) {
            const row = [];
            for (let x = 0; x < gridSize; x++) {
                const worldX = playerX + (x - centerOffset);
                // Flip Y-axis: screen Y increases downward, world Y increases northward
                const worldY = playerY - (y - centerOffset);
                const isPlayerPosition = x === centerOffset && y === centerOffset;
                const isVisited = isVisitedCoordinate(worldX, worldY);
                
                row.push({
                    x: worldX,
                    y: worldY,
                    isPlayerPosition,
                    isVisited
                });
            }
            grid.push(row);
        }
        return grid;
    };

    // Check if a coordinate has been visited using the store
    const isVisitedCoordinate = (x: number, y: number): boolean => {
        return isCoordinateVisited(x, y);
    };

    const grid = generateGrid();
    
    // Calculate total visited count from the store (all visited coordinates, not just visible ones)
    const { visitedCoordinates } = useGameStore();
    const visitedCount = visitedCoordinates.size;

    return (
        <div className={`minimap ${className}`}>
            <div className="text-xs text-green-500 mb-2 font-mono border-b border-green-700 pb-1">MINIMAP</div>
            <div className="grid grid-cols-5 gap-1">
                {grid.map((row, rowIndex) => 
                    row.map((tile, colIndex) => (
                        <div
                            key={`${tile.x},${tile.y}`}
                            className={`
                                w-4 h-4 border border-green-700 relative
                                ${tile.isPlayerPosition 
                                    ? 'bg-yellow-500 border-yellow-300 shadow-lg shadow-yellow-500/50' 
                                    : tile.isVisited 
                                        ? 'bg-green-600 border-green-500' 
                                        : 'bg-black border-green-900'
                                }
                                ${tile.isPlayerPosition ? 'animate-pulse' : ''}
                                hover:scale-110 transition-transform duration-150
                            `}
                            title={`${tile.x}, ${tile.y}${tile.isPlayerPosition ? ' (You)' : ''}`}
                        >
                            {/* Player indicator */}
                            {tile.isPlayerPosition && (
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <div className="w-1 h-1 bg-black rounded-full"></div>
                                </div>
                            )}
                        </div>
                    ))
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
            </div>
        </div>
    );
};

export default Minimap; 