import React, { useState, useRef, useEffect } from 'react';
import useGameStore from '@/store/gameStore';
import { UserCircleIcon } from '@heroicons/react/24/solid';

const PlayersInRoom: React.FC = () => {
    const { playersInRoom, player } = useGameStore();
    const [selectedPlayer, setSelectedPlayer] = useState<string | null>(null);
    const [menuPosition, setMenuPosition] = useState({ x: 0, y: 0 });
    const [showMenu, setShowMenu] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);
    const playerRefs = useRef<{ [key: string]: HTMLDivElement | null }>({});

    // Filter out the current player from the display
    const otherPlayers = playersInRoom.filter(p => p.id !== player?.id);

    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setShowMenu(false);
                setSelectedPlayer(null);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, []);

    const handlePlayerClick = (event: React.MouseEvent, playerId: string) => {
        event.preventDefault();
        event.stopPropagation();
        
        const playerElement = playerRefs.current[playerId];
        if (!playerElement) return;
        
        const rect = playerElement.getBoundingClientRect();
        
        // Use viewport coordinates for absolute positioning
        setMenuPosition({
            x: rect.left + rect.width / 2,
            y: rect.bottom + 5
        });
        setSelectedPlayer(playerId);
        setShowMenu(true);
    };

    const handleFightClick = () => {
        if (selectedPlayer) {
            console.log('Fight action for player:', selectedPlayer);
            // TODO: Implement fight action
            setShowMenu(false);
            setSelectedPlayer(null);
        }
    };

    const handleCloseClick = () => {
        if (selectedPlayer) {
            console.log('Close action for player:', selectedPlayer);
            // TODO: Implement close action
            setShowMenu(false);
            setSelectedPlayer(null);
        }
    };

    if (otherPlayers.length === 0) {
        return null; // Don't show anything if no other players
    }

    return (
        <div className="absolute top-4 left-4 bg-black bg-opacity-80 border border-amber-500 rounded-lg p-2 z-20">
            <div className="flex items-center gap-1 mb-1">
                <UserCircleIcon className="h-3 w-3 text-amber-500" />
                <span className="text-amber-500 font-bold text-xs">Also here:</span>
            </div>
            <div className="flex flex-wrap gap-1">
                {otherPlayers.map(player => (
                    <div 
                        key={player.id} 
                        ref={(el) => { playerRefs.current[player.id] = el; }}
                        className="flex items-center bg-amber-900 bg-opacity-50 rounded px-2 py-0.5 border border-amber-700 cursor-pointer hover:bg-amber-800 hover:border-amber-600 transition-colors"
                        onClick={(e) => handlePlayerClick(e, player.id)}
                    >
                        <UserCircleIcon className="h-3 w-3 mr-1 text-amber-500" />
                        <span className="text-amber-100 text-xs font-medium">{player.name}</span>
                    </div>
                ))}
            </div>

            {/* Player Action Menu */}
            {showMenu && selectedPlayer && (
                <div 
                    ref={menuRef}
                    className="fixed bg-black bg-opacity-95 border border-amber-500 rounded-lg p-1 z-50"
                    style={{
                        left: menuPosition.x,
                        top: menuPosition.y,
                        transform: 'translateX(-50%)'
                    }}
                >
                    <div className="flex gap-1">
                        <button
                            onClick={handleFightClick}
                            className="w-8 h-8 bg-yellow-600 hover:bg-yellow-700 text-black font-bold text-sm rounded flex items-center justify-center transition-colors"
                            title="Fight"
                        >
                            ⚔️
                        </button>
                        <button
                            onClick={handleCloseClick}
                            className="w-8 h-8 bg-black hover:bg-gray-800 text-white font-bold text-sm rounded flex items-center justify-center transition-colors border border-gray-600"
                            title="Close"
                        >
                            ❌
                        </button>
                    </div>
                    {/* Arrow pointing up to the player name */}
                    <div 
                        className="absolute w-0 h-0 border-l-4 border-r-4 border-b-4 border-transparent border-b-amber-500"
                        style={{
                            left: '50%',
                            top: '-4px',
                            transform: 'translateX(-50%)'
                        }}
                    />
                </div>
            )}
        </div>
    );
};

export default PlayersInRoom; 