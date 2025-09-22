import React, { useEffect, useState } from 'react';
import useGameStore from '@/store/gameStore';
import InventoryList from './InventoryList';

const PauseMenu: React.FC = () => {
    const { isMenuOpen, setIsMenuOpen, player } = useGameStore();
    const [view, setView] = useState<'root' | 'inventory'>('root');

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
                                    className="w-full py-3 bg-gray-800 border border-gray-700 rounded text-gray-400 text-2xl font-mono cursor-not-allowed"
                                    title="Coming soon"
                                    disabled
                                >
                                    Save & Quit
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
                </div>
            </div>
        </div>
    );
};

export default PauseMenu; 