import React, { useEffect } from 'react';
import useGameStore from '@/store/gameStore';

const InventoryList: React.FC = () => {
    const { player, itemsById } = useGameStore();

    // Debug logging for inventory changes
    useEffect(() => {
        console.log('[InventoryList] Player inventory updated:', player?.inventory);
        console.log('[InventoryList] ItemsById updated:', Object.keys(itemsById));
    }, [player?.inventory, itemsById]);

    if (!player) {
        return <div className="text-gray-400">No player loaded.</div>;
    }

    const inventory = player.inventory || [];

    if (inventory.length === 0) {
        return (
            <div className="text-green-300 font-mono text-xl">Your inventory is empty.</div>
        );
    }

    // Helper function to generate rarity stars
    const getRarityStars = (rarity?: number) => {
        if (!rarity) return '';
        const stars = "★".repeat(rarity) + "☆".repeat(4 - rarity);
        return stars;
    };

    // Helper function to get rarity color
    const getRarityColor = (rarity?: number) => {
        switch (rarity) {
            case 1: return 'text-gray-300';    // Common
            case 2: return 'text-green-400';   // Uncommon  
            case 3: return 'text-blue-400';    // Rare
            case 4: return 'text-purple-400';  // Legendary
            default: return 'text-gray-300';
        }
    };

    // Helper function to get rarity name
    const getRarityName = (rarity?: number) => {
        switch (rarity) {
            case 1: return 'Common';
            case 2: return 'Uncommon';
            case 3: return 'Rare';
            case 4: return 'Legendary';
            default: return 'Unknown';
        }
    };

    return (
        <div className="space-y-4 max-h-[50vh] overflow-y-auto pr-1">
            {inventory.map((itemId) => {
                const item = itemsById[itemId];
                const rarityStars = getRarityStars(item?.rarity);
                const rarityColor = getRarityColor(item?.rarity);
                const rarityName = getRarityName(item?.rarity);
                
                return (
                    <div key={itemId} className={`p-4 bg-black border rounded-lg ${item?.rarity ? 'border-amber-700' : 'border-amber-900'}`}>
                        {/* Header with name and rarity */}
                        <div className="flex items-start justify-between mb-3">
                            <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                    <div className="text-2xl font-mono text-amber-300">
                                        {item ? item.name : 'Unknown Item'}
                                    </div>
                                    {rarityStars && (
                                        <div className={`text-xl ${rarityColor}`}>
                                            {rarityStars}
                                        </div>
                                    )}
                                </div>
                                <div className="flex items-center gap-3 text-sm">
                                    {item?.rarity && (
                                        <span className={`font-mono font-bold ${rarityColor}`}>
                                            {rarityName}
                                        </span>
                                    )}
                                    <span className="text-amber-500 font-mono">ID: {itemId.substring(0, 8)}...</span>
                                </div>
                            </div>
                        </div>

                        {item ? (
                            <div className="space-y-3">
                                {/* Description */}
                                {item.description && (
                                    <div className="text-green-300 font-mono text-base leading-relaxed">
                                        {item.description}
                                    </div>
                                )}

                                {/* Capabilities */}
                                {item.capabilities && item.capabilities.length > 0 && (
                                    <div>
                                        <div className="text-cyan-400 font-mono text-lg mb-2 flex items-center gap-2">
                                            <span>⚡</span>
                                            <span>Capabilities</span>
                                        </div>
                                        <div className="grid grid-cols-1 gap-1">
                                            {item.capabilities.map((capability, index) => (
                                                <div key={index} className="flex items-center gap-2">
                                                    <span className="text-cyan-300 text-sm">•</span>
                                                    <span className="text-cyan-200 font-mono text-sm">
                                                        {capability}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Properties/Stats */}
                                {item.properties && Object.keys(item.properties).length > 0 && (
                                    <div>
                                        <div className="text-amber-400 font-mono text-lg mb-2 flex items-center gap-2">
                                            <span>📊</span>
                                            <span>Properties</span>
                                        </div>
                                        <div className="grid grid-cols-1 gap-1">
                                            {Object.entries(item.properties).map(([key, value]) => (
                                                <div key={key} className="flex items-center justify-between">
                                                    <span className="text-amber-300 font-mono text-sm capitalize">
                                                        {key.replace(/_/g, ' ')}:
                                                    </span>
                                                    <span className="text-green-400 font-mono text-sm">
                                                        {String(value)}
                                                    </span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Debug info (only show if no other info available) */}
                                {!item.description && !item.capabilities?.length && !Object.keys(item.properties || {}).length && (
                                    <div className="text-gray-400 font-mono text-sm italic">
                                        Item data is loading...
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-gray-400 font-mono">
                                <div className="animate-pulse">Loading item details...</div>
                            </div>
                        )}
                    </div>
                );
            })}
        </div>
    );
};

export default InventoryList; 