import React, { useState, useRef, useEffect } from 'react';
import useGameStore from '@/store/gameStore';
import { UserCircleIcon } from '@heroicons/react/24/solid';
import websocketService from '@/services/websocket';

const PlayersInRoom: React.FC = () => {
    const { playersInRoom, player, npcs } = useGameStore();
    const [selectedPlayer, setSelectedPlayer] = useState<string | null>(null);
    const [menuPosition, setMenuPosition] = useState({ x: 0, y: 0 });
    const [showMenu, setShowMenu] = useState(false);
    const [isExpanded, setIsExpanded] = useState(false);
    const [opacity, setOpacity] = useState(1);
    const menuRef = useRef<HTMLDivElement>(null);
    const playerRefs = useRef<{ [key: string]: HTMLDivElement | null }>({});
    const fadeTimerRef = useRef<NodeJS.Timeout | null>(null);

    // Filter out the current player from the display
    const otherPlayers = playersInRoom.filter(p => p.id !== player?.id);
    const totalCount = otherPlayers.length + npcs.length;

    // Auto-fade after 10 seconds of inactivity
    useEffect(() => {
        const resetFadeTimer = () => {
            if (fadeTimerRef.current) {
                clearTimeout(fadeTimerRef.current);
            }
            setOpacity(1);
            fadeTimerRef.current = setTimeout(() => {
                setOpacity(0.3);
            }, 10000);
        };

        resetFadeTimer();
        return () => {
            if (fadeTimerRef.current) {
                clearTimeout(fadeTimerRef.current);
            }
        };
    }, [totalCount, isExpanded]);

    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setShowMenu(false);
                setSelectedPlayer(null);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handlePlayerClick = (event: React.MouseEvent, playerId: string) => {
        event.preventDefault();
        event.stopPropagation();
        
        const playerElement = playerRefs.current[playerId];
        if (!playerElement) return;
        
        const rect = playerElement.getBoundingClientRect();
        setMenuPosition({
            x: rect.left + rect.width / 2,
            y: rect.bottom + 5
        });
        setSelectedPlayer(playerId);
        setShowMenu(true);
    };

    const closeMenu = () => {
        setShowMenu(false);
        setSelectedPlayer(null);
    };

    const handleFightClick = () => {
        if (selectedPlayer) {
            console.log('Sending duel challenge to player:', selectedPlayer);
            websocketService.sendDuelChallenge(selectedPlayer);
            closeMenu();
        }
    };

    const handleCloseClick = () => {
        if (selectedPlayer) {
            console.log('Close action for player:', selectedPlayer);
            // TODO: Implement close action
            closeMenu();
        }
    };

    if (totalCount === 0) {
        return null;
    }

    const handleMouseEnter = () => {
        setOpacity(1);
        if (fadeTimerRef.current) {
            clearTimeout(fadeTimerRef.current);
        }
    };

    const handleMouseLeave = () => {
        fadeTimerRef.current = setTimeout(() => {
            setOpacity(0.3);
        }, 10000);
    };

    // Compact view
    if (!isExpanded) {
        return (
            <div 
                className="transition-opacity duration-300 cursor-pointer w-auto"
                style={{ opacity }}
                onMouseEnter={handleMouseEnter}
                onMouseLeave={handleMouseLeave}
                onClick={() => setIsExpanded(true)}
            >
                <div className="bg-black/80 border border-amber-500 rounded-lg px-2 py-1.5 hover:bg-black/90 transition-colors">
                    <div className="flex items-center gap-1.5">
                        <UserCircleIcon className="h-4 w-4 text-amber-500" />
                        <span className="text-amber-400 font-bold text-sm">{totalCount}</span>
                    </div>
                </div>
            </div>
        );
    }

    // Expanded view
    return (
        <div 
            className="bg-black/90 border border-amber-500 rounded-lg p-2 transition-opacity duration-300 w-auto min-w-[160px]"
            style={{ opacity }}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
        >
            <div className="flex items-center justify-between gap-2 mb-1">
                <div className="flex items-center gap-1">
                    <UserCircleIcon className="h-3 w-3 text-amber-500" />
                    <span className="text-amber-500 font-bold text-xs">Also here:</span>
                </div>
                <button
                    onClick={() => setIsExpanded(false)}
                    className="text-amber-400 hover:text-amber-300 text-xs font-bold"
                    title="Minimize"
                >
                    ✕
                </button>
            </div>
            <div className="flex flex-wrap gap-1">
                {/* NPCs - shown in cyan/blue color */}
                {npcs.map(npc => (
                    <div
                        key={npc.id}
                        className="flex items-center bg-cyan-900 bg-opacity-50 rounded px-2 py-0.5 border border-cyan-600"
                        title={npc.description || 'An NPC'}
                    >
                        <UserCircleIcon className="h-3 w-3 mr-1 text-cyan-400" />
                        <span className="text-cyan-100 text-xs font-medium">{npc.name}</span>
                    </div>
                ))}

                {/* Other Players - shown in amber color */}
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
                            title="Challenge to Duel"
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