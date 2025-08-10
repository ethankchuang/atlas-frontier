import React from 'react';
import useGameStore from '@/store/gameStore';

const InventoryList: React.FC = () => {
    const { player, itemsById } = useGameStore();

    if (!player) {
        return <div className="text-gray-400">No player loaded.</div>;
    }

    const inventory = player.inventory || [];

    if (inventory.length === 0) {
        return (
            <div className="text-green-300 font-mono text-xl">Your inventory is empty.</div>
        );
    }

    return (
        <div className="space-y-3 max-h-[50vh] overflow-y-auto pr-1">
            {inventory.map((itemId) => {
                const item = itemsById[itemId];
                return (
                    <div key={itemId} className="p-4 bg-black border border-amber-900 rounded">
                        <div className="flex items-start justify-between">
                            <div>
                                <div className="text-2xl font-mono text-amber-300">
                                    {item ? item.name : 'Unknown Item'}
                                </div>
                                <div className="text-sm text-amber-500 font-mono">ID: {itemId}</div>
                            </div>
                        </div>
                        {item && (
                            <div className="mt-2">
                                {item.description && (
                                    <div className="text-green-300 font-mono mb-2">{item.description}</div>
                                )}
                                {item.properties && Object.keys(item.properties).length > 0 && (
                                    <div className="mt-2">
                                        <div className="text-amber-400 font-mono text-lg mb-1">Stats</div>
                                        <ul className="list-disc list-inside space-y-1">
                                            {Object.entries(item.properties).map(([key, value]) => (
                                                <li key={key} className="text-green-400 font-mono text-base">
                                                    <span className="text-amber-300">{key}:</span> {String(value)}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        )}
                        {!item && (
                            <div className="mt-2 text-gray-400 font-mono">Details not available.</div>
                        )}
                    </div>
                );
            })}
        </div>
    );
};

export default InventoryList; 