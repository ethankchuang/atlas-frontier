import React from 'react';
import useGameStore from '@/store/gameStore';
import { UserCircleIcon } from '@heroicons/react/24/solid';

const PlayersInRoom: React.FC = () => {
    const { playersInRoom, player } = useGameStore();

    // Filter out the current player from the display
    const otherPlayers = playersInRoom.filter(p => p.id !== player?.id);

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
                        className="flex items-center bg-amber-900 bg-opacity-50 rounded px-2 py-0.5 border border-amber-700"
                    >
                        <UserCircleIcon className="h-3 w-3 mr-1 text-amber-500" />
                        <span className="text-amber-100 text-xs font-medium">{player.name}</span>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default PlayersInRoom; 