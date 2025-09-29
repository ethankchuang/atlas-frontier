import React, { useEffect } from 'react';
import useGameStore from '@/store/gameStore';
import apiService from '@/services/api';
import { Item, Player, Room } from '@/types/game';

const InventoryList: React.FC = () => {
    const { player, itemsById, setPlayer, setCurrentRoom, upsertItems } = useGameStore();
    const [selectedItems, setSelectedItems] = React.useState<string[]>([]);
    const [isCombining, setIsCombining] = React.useState(false);

    const handleDropItem = async (itemId: string, itemName: string, rarity?: number) => {
        if (!player) return;
        
        // Double-check that the item is still in the inventory
        if (!player.inventory.includes(itemId)) {
            console.error(`[Inventory] Item ${itemId} not found in current inventory:`, player.inventory);
            return;
        }
        
        console.log(`[Inventory] Attempting to drop item:`, {
            itemId,
            itemName,
            rarity,
            playerId: player.id,
            currentInventory: player.inventory
        });
        
        try {
            // For 1-star items, always delete (dropToRoom = false)
            // For other items, drop to room (dropToRoom = true)
            const dropToRoom = rarity !== 1;
            
            console.log(`[Inventory] Drop parameters:`, { dropToRoom, rarity });
            
            const result = await apiService.dropPlayerItem(player.id, itemId, dropToRoom);
            
            if (result.success) {
                // Update the store with the new player data
                if (result.updates.player) {
                    setPlayer(result.updates.player as Player);
                }

                // Update room data if item was dropped to room
                if (result.updates.room) {
                    setCurrentRoom(result.updates.room as Room);
                }
                
                console.log(`[Inventory] ${result.message}`);
            } else {
                console.error(`[Inventory] Failed to drop item: ${result.message}`);
            }
        } catch (error) {
            console.error('[Inventory] Error dropping item:', error);
        }
    };

    const handleCombineItems = async () => {
        if (!player || selectedItems.length < 2) return;
        
        setIsCombining(true);
        try {
            const result = await apiService.combinePlayerItems(player.id, selectedItems);
            
            if (result.success) {
                // Update the store with the new player data
                if (result.updates.player) {
                    setPlayer(result.updates.player as Player);
                }

                // Load the new item data into the store
                if (result.updates.new_item) {
                    upsertItems([result.updates.new_item as Item]);
                    console.log(`[Inventory] Loaded new item data:`, result.updates.new_item);
                }
                
                console.log(`[Inventory] ${result.message}`);
                
                // Clear selected items
                setSelectedItems([]);
            } else {
                console.error(`[Inventory] Failed to combine items: ${result.message}`);
            }
        } catch (error) {
            console.error('[Inventory] Error combining items:', error);
        } finally {
            setIsCombining(false);
        }
    };

    const toggleItemSelection = (itemId: string) => {
        setSelectedItems(prev => {
            if (prev.includes(itemId)) {
                return prev.filter(id => id !== itemId);
            } else {
                return [...prev, itemId];
            }
        });
    };

    // Debug logging for inventory changes
    useEffect(() => {
        console.log('[InventoryList] Player inventory updated:', player?.inventory);
        console.log('[InventoryList] ItemsById updated:', Object.keys(itemsById));
        
        // Check for missing items
        if (player?.inventory) {
            const missingItems = player.inventory.filter(itemId => !itemsById[itemId]);
            if (missingItems.length > 0) {
                console.warn('[InventoryList] Missing item data for:', missingItems);
            }
        }
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

    // Check if we're still loading item data
    const missingItems = inventory.filter(itemId => !itemsById[itemId]);
    const isLoading = missingItems.length > 0;

    if (isLoading) {
        return (
            <div className="text-yellow-300 font-mono text-xl">
                Loading inventory items... ({inventory.length - missingItems.length}/{inventory.length} loaded)
            </div>
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
            {/* Combine Items Section */}
            {selectedItems.length >= 2 && (
                <div className="p-4 bg-blue-900 border border-blue-600 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="text-lg font-mono text-blue-300">
                            Combine Items ({selectedItems.length} selected)
                        </h3>
                        <button
                            onClick={handleCombineItems}
                            disabled={isCombining}
                            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded font-mono text-sm"
                        >
                            {isCombining ? 'Combining...' : '🔨 Combine'}
                        </button>
                    </div>
                    <p className="text-blue-200 text-sm">
                        Selected items will be consumed to create a new item (minimum 2-star rarity)
                    </p>
                </div>
            )}
            
            {inventory.map((itemId) => {
                const item = itemsById[itemId];
                const rarityStars = getRarityStars(item?.rarity);
                const rarityColor = getRarityColor(item?.rarity);
                const rarityName = getRarityName(item?.rarity);
                
                const isSelected = selectedItems.includes(itemId);
                
                return (
                    <div key={itemId} className={`p-4 bg-black border rounded-lg ${isSelected ? 'border-blue-500 bg-blue-900' : (item?.rarity ? 'border-amber-700' : 'border-amber-900')}`}>
                        {/* Header with name and rarity */}
                        <div className="flex items-start justify-between mb-3">
                            <div className="flex-1">
                                <div className="flex items-center gap-2 mb-1">
                                    {/* Selection checkbox */}
                                    <input
                                        type="checkbox"
                                        checked={isSelected}
                                        onChange={() => toggleItemSelection(itemId)}
                                        className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
                                    />
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
                            
                            {/* Action buttons */}
                            <div className="flex gap-2">
                                {isSelected ? (
                                    <button
                                        onClick={() => toggleItemSelection(itemId)}
                                        className="flex items-center justify-center w-8 h-8 bg-blue-600 hover:bg-blue-700 text-white rounded-full transition-colors duration-200 text-sm font-bold"
                                        title="Deselect item"
                                    >
                                        ✓
                                    </button>
                                ) : (
                                    <button
                                        onClick={() => toggleItemSelection(itemId)}
                                        className="flex items-center justify-center w-8 h-8 bg-green-600 hover:bg-green-700 text-white rounded-full transition-colors duration-200 text-sm font-bold"
                                        title="Select for combination"
                                    >
                                        +
                                    </button>
                                )}
                                <button
                                    onClick={() => handleDropItem(itemId, item?.name || 'Unknown Item', item?.rarity)}
                                    className="flex items-center justify-center w-8 h-8 bg-red-600 hover:bg-red-700 text-white rounded-full transition-colors duration-200 text-sm font-bold"
                                    title={item?.rarity === 1 ? "Discard item (1-star items are deleted)" : "Drop item to room"}
                                >
                                    ×
                                </button>
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