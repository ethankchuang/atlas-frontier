import React, { useEffect, useState } from 'react';
import useGameStore from '@/store/gameStore';
import InventoryList from './InventoryList';
import GuestConversionModal from './GuestConversionModal';

const PauseMenu: React.FC = () => {
    const { isMenuOpen, setIsMenuOpen, player, user } = useGameStore();
    const [view, setView] = useState<'root' | 'inventory' | 'tutorial'>('root');
    const [showGuestConversion, setShowGuestConversion] = useState(false);

    // Reset to root each time menu opens
    useEffect(() => {
        if (isMenuOpen) setView('root');
    }, [isMenuOpen]);

    if (!isMenuOpen) return null;

    return (
        <div className="absolute inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black bg-opacity-70"
                onClick={() => setIsMenuOpen(false)}
            />

            {/* Panel */}
            <div className="relative z-10 w-full max-w-2xl mx-auto bg-black border-4 border-amber-900 rounded shadow-xl">
                <div className="p-6">
                    {view === 'root' && (
                        <div>
                            <div className="mb-6 text-center">
                                <h2 className="text-3xl text-amber-400 font-bold font-mono">Game Menu</h2>
                            </div>

                            <div className="space-y-4">
                                <button
                                    className="w-full py-3 bg-amber-900/40 hover:bg-amber-800/50 border border-amber-700 rounded text-amber-200 text-2xl font-mono transition-colors"
                                    onClick={() => setView('inventory')}
                                >
                                    Inventory
                                </button>
                                <button
                                    className="w-full py-3 bg-blue-900/40 hover:bg-blue-800/50 border border-blue-700 rounded text-blue-200 text-2xl font-mono transition-colors"
                                    onClick={() => setView('tutorial')}
                                >
                                    Tutorial
                                </button>
                                <button
                                    className={`w-full py-3 border rounded text-2xl font-mono transition-colors ${
                                        user?.is_anonymous
                                            ? 'bg-green-900/30 hover:bg-green-800/40 border-green-700 text-green-300'
                                            : 'bg-gray-800 border-gray-700 text-gray-400 cursor-not-allowed'
                                    }`}
                                    title={user?.is_anonymous ? 'Create account to save progress' : 'Coming soon'}
                                    disabled={!user?.is_anonymous}
                                    onClick={() => {
                                        if (user?.is_anonymous) {
                                            // Show guest conversion modal
                                            setShowGuestConversion(true);
                                        }
                                    }}
                                >
                                    {user?.is_anonymous ? 'Create Account' : 'Save & Quit'}
                                </button>
                                <button
                                    className="w-full py-3 bg-green-900/30 hover:bg-green-800/40 border border-green-700 rounded text-green-300 text-2xl font-mono transition-colors"
                                    onClick={() => setIsMenuOpen(false)}
                                >
                                    Resume
                                </button>
                            </div>
                        </div>
                    )}

                    {view === 'inventory' && (
                        <div>
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-3xl text-amber-400 font-bold font-mono">Inventory</h2>
                                <button
                                    className="px-4 py-2 bg-amber-900/40 hover:bg-amber-800/50 border border-amber-700 rounded text-amber-200 text-xl font-mono"
                                    onClick={() => setView('root')}
                                >
                                    Back
                                </button>
                            </div>
                            <InventoryList key={player?.inventory?.length || 0} />
                        </div>
                    )}

                    {view === 'tutorial' && (
                        <div>
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-3xl text-blue-400 font-bold font-mono">Tutorial</h2>
                                <button
                                    className="px-4 py-2 bg-blue-900/40 hover:bg-blue-800/50 border border-blue-700 rounded text-blue-200 text-xl font-mono"
                                    onClick={() => setView('root')}
                                >
                                    Back
                                </button>
                            </div>
                            <div className="space-y-4 text-blue-200 font-mono max-h-96 overflow-y-auto pr-2">
                                <div className="bg-blue-900/20 border border-blue-700 rounded p-4">
                                    <h3 className="text-xl text-blue-300 font-bold mb-2">🎮 Basic Controls</h3>
                                    <ul className="space-y-1 text-sm">
                                        <li>• <strong>ESC</strong> - Open/Close this menu</li>
                                        <li>• <strong>Bottom Bar</strong> - Click to type any action you want to take, specify a direction if you want to move rooms</li>
                                        <li>• <strong>Enter</strong> - Send chat messages</li>
                                        <li>• <strong>Minimap</strong> - Click minimap on top left to open full screen map</li>
                                    </ul>
                                </div>
                                
                                <div className="bg-blue-900/20 border border-blue-700 rounded p-4">
                                    <h3 className="text-xl text-blue-300 font-bold mb-2">🗺️ Exploration</h3>
                                    <ul className="space-y-1 text-sm">
                                        <li>• Move around to discover new rooms and biomes</li>
                                        <li>• Explore within each room, discovering items and other creatures</li>
                                        <li>• Use the minimap to track your progress</li>
                                        <li>• Some areas may contain dangerous monsters</li>
                                        <li>• To avoid agressive monsters, return to the room you came from</li>
                                    </ul>
                                </div>

                                <div className="bg-blue-900/20 border border-blue-700 rounded p-4">
                                    <h3 className="text-xl text-blue-300 font-bold mb-2">⚔️ Combat & Items</h3>
                                    <ul className="space-y-1 text-sm">
                                        <li>• Collect items to improve your character</li>
                                        <li>• Items enable new actions you can take</li>
                                        <li>• For example, you can&apos;t stab anyone without something sharp</li>
                                        <li>• Select two+ items from your inventory to combine them!</li>
                                    </ul>
                                </div>

                                <div className="bg-blue-900/20 border border-blue-700 rounded p-4">
                                    <h3 className="text-xl text-blue-300 font-bold mb-2">💬 Social Features</h3>
                                    <ul className="space-y-1 text-sm">
                                        <li>• Chat with other players in the same room</li>
                                        <li>• Challenge other players to duels by clicking their name in the "also here" list on the top left</li>
                                        <li>• Create an account to save your progress</li>
                                        <li>• Guest accounts reset when you leave</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
            
            {/* Guest Conversion Modal */}
            <GuestConversionModal
                isOpen={showGuestConversion}
                onClose={() => setShowGuestConversion(false)}
                onSuccess={() => {
                    setShowGuestConversion(false);
                    setIsMenuOpen(false);
                    // The modal will have updated the user state
                }}
            />
        </div>
    );
};

export default PauseMenu; 