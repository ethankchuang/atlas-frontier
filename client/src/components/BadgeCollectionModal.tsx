import React, { useEffect, useState } from 'react';
import { XMarkIcon } from '@heroicons/react/24/solid';
import apiService from '@/services/api';

interface Badge {
    id: string;
    name: string;
    description: string;
    image_url?: string;
    rarity: number;
}

interface PlayerBadge {
    id: string;
    player_id: string;
    badge_id: string;
    earned_at: string;
    badge: Badge;
}

interface BadgeCollectionModalProps {
    playerId: string;
    isOpen: boolean;
    onClose: () => void;
}

const BadgeCollectionModal: React.FC<BadgeCollectionModalProps> = ({ playerId, isOpen, onClose }) => {
    const [badges, setBadges] = useState<PlayerBadge[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!isOpen) return;

        const fetchBadges = async () => {
            try {
                setLoading(true);
                const data = await apiService.getPlayerBadges(playerId);
                // Ensure badges is an array
                if (data && Array.isArray(data.badges)) {
                    setBadges(data.badges);
                } else {
                    setBadges([]);
                }
            } catch (error) {
                console.error('[BadgeCollectionModal] Failed to fetch badges:', error);
                setBadges([]);
            } finally {
                setLoading(false);
            }
        };

        fetchBadges();
    }, [playerId, isOpen]);

    if (!isOpen) return null;

    const getRarityColor = (rarity: number) => {
        switch (rarity) {
            case 1:
                return 'border-gray-500 bg-gray-900/30';
            case 2:
                return 'border-green-500 bg-green-900/30';
            case 3:
                return 'border-blue-500 bg-blue-900/30';
            case 4:
                return 'border-purple-500 bg-purple-900/30';
            case 5:
                return 'border-amber-500 bg-amber-900/30';
            default:
                return 'border-gray-500 bg-gray-900/30';
        }
    };

    const getRarityLabel = (rarity: number) => {
        switch (rarity) {
            case 1:
                return 'Common';
            case 2:
                return 'Uncommon';
            case 3:
                return 'Rare';
            case 4:
                return 'Epic';
            case 5:
                return 'Legendary';
            default:
                return 'Unknown';
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80">
            <div className="bg-gray-900 border-2 border-purple-700 rounded-lg w-full max-w-4xl max-h-[80vh] flex flex-col font-mono">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-purple-900/50">
                    <div className="flex items-center gap-3">
                        <span className="text-3xl">🏅</span>
                        <div>
                            <h2 className="text-2xl font-bold text-purple-400">Badge Collection</h2>
                            <p className="text-sm text-gray-400">
                                {badges.length} {badges.length === 1 ? 'badge' : 'badges'} earned
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white transition-colors"
                    >
                        <XMarkIcon className="w-6 h-6" />
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6">
                    {loading ? (
                        <div className="flex items-center justify-center h-full">
                            <div className="text-purple-400 text-lg animate-pulse">Loading badges...</div>
                        </div>
                    ) : badges.length > 0 ? (
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                            {badges.map((playerBadge) => (
                                <div
                                    key={playerBadge.id}
                                    className={`border-2 rounded-lg p-4 hover:scale-105 transition-transform ${getRarityColor(playerBadge.badge.rarity)}`}
                                >
                                    {/* Badge Image/Icon */}
                                    <div className="flex items-center justify-center mb-3">
                                        {playerBadge.badge.image_url ? (
                                            <img
                                                src={playerBadge.badge.image_url}
                                                alt={playerBadge.badge.name}
                                                className="w-20 h-20 object-contain"
                                            />
                                        ) : (
                                            <div className="w-20 h-20 flex items-center justify-center text-5xl">
                                                🏅
                                            </div>
                                        )}
                                    </div>

                                    {/* Badge Name */}
                                    <div className="text-center mb-2">
                                        <h3 className="text-lg font-bold text-white mb-1">
                                            {playerBadge.badge.name}
                                        </h3>
                                        <div className={`text-xs font-bold uppercase tracking-wider ${
                                            playerBadge.badge.rarity === 1 ? 'text-gray-400' :
                                            playerBadge.badge.rarity === 2 ? 'text-green-400' :
                                            playerBadge.badge.rarity === 3 ? 'text-blue-400' :
                                            playerBadge.badge.rarity === 4 ? 'text-purple-400' :
                                            'text-amber-400'
                                        }`}>
                                            {getRarityLabel(playerBadge.badge.rarity)}
                                        </div>
                                    </div>

                                    {/* Badge Description */}
                                    <p className="text-sm text-gray-400 text-center mb-3">
                                        {playerBadge.badge.description}
                                    </p>

                                    {/* Earned Date */}
                                    <div className="pt-3 border-t border-gray-700 text-xs text-gray-500 text-center">
                                        Earned: {new Date(playerBadge.earned_at).toLocaleDateString()}
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-full text-center py-12">
                            <div className="text-6xl mb-4 opacity-50">🏅</div>
                            <div className="text-gray-400 text-lg mb-2">No badges yet</div>
                            <div className="text-gray-500 text-sm">
                                Complete quests to earn badges!
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default BadgeCollectionModal;
