import React, { useEffect, useState } from 'react';
import useGameStore from '@/store/gameStore';
import InventoryList from './InventoryList';
import GuestConversionModal from './GuestConversionModal';

interface PauseMenuProps {
    onOpenQuestLog?: () => void;
    onOpenBadges?: () => void;
}

const PauseMenu: React.FC<PauseMenuProps> = ({ onOpenQuestLog, onOpenBadges }) => {
    const { isMenuOpen, setIsMenuOpen, player, user, setPlayer } = useGameStore();
    const [view, setView] = useState<'root' | 'inventory' | 'tutorial'>('root');
    const [showGuestConversion, setShowGuestConversion] = useState(false);
    const [isFirstTime, setIsFirstTime] = useState(false);

    // Reset to root or tutorial each time menu opens
    useEffect(() => {
        if (isMenuOpen) {
            const hasSeenTutorial = localStorage.getItem('tutorial_seen');
            const firstTime = !hasSeenTutorial;
            setIsFirstTime(firstTime);
            // If first time, show tutorial; otherwise show root
            setView(firstTime ? 'tutorial' : 'root');
        }
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
            <div className="relative z-10 w-full max-w-[90vw] sm:max-w-md md:max-w-lg mx-auto bg-black border-2 border-amber-900 rounded shadow-xl">
                <div className="p-3 sm:p-4">
                    {view === 'root' && (
                        <div>
                            <div className="mb-3 sm:mb-4 text-center">
                                <h2 className="text-xl sm:text-2xl text-amber-400 font-bold font-mono">Game Menu</h2>
                            </div>

                            <div className="space-y-1.5 sm:space-y-2">
                                <button
                                    className="w-full py-1.5 sm:py-2 bg-amber-900/40 hover:bg-amber-800/50 border border-amber-700 rounded text-amber-200 text-base sm:text-lg font-mono transition-colors"
                                    onClick={() => setView('inventory')}
                                >
                                    <div className="flex items-center justify-center gap-2 sm:gap-3">
                                        <span className="text-lg sm:text-xl w-5 sm:w-6 text-center">🎒</span>
                                        <span className="text-left min-w-[80px] sm:min-w-[100px]">Inventory</span>
                                    </div>
                                </button>
                                <button
                                    className="w-full py-1.5 sm:py-2 bg-yellow-900/40 hover:bg-yellow-800/50 border border-yellow-700 rounded text-yellow-200 text-base sm:text-lg font-mono transition-colors"
                                    onClick={() => {
                                        setIsMenuOpen(false);
                                        onOpenQuestLog?.();
                                    }}
                                >
                                    <div className="flex items-center justify-center gap-2 sm:gap-3">
                                        <span className="text-lg sm:text-xl w-5 sm:w-6 text-center">📖</span>
                                        <span className="text-left min-w-[80px] sm:min-w-[100px]">Quests</span>
                                    </div>
                                </button>
                                <button
                                    className="w-full py-1.5 sm:py-2 bg-purple-900/40 hover:bg-purple-800/50 border border-purple-700 rounded text-purple-200 text-base sm:text-lg font-mono transition-colors"
                                    onClick={() => {
                                        setIsMenuOpen(false);
                                        onOpenBadges?.();
                                    }}
                                >
                                    <div className="flex items-center justify-center gap-2 sm:gap-3">
                                        <span className="text-lg sm:text-xl w-5 sm:w-6 text-center">🏅</span>
                                        <span className="text-left min-w-[80px] sm:min-w-[100px]">Badges</span>
                                    </div>
                                </button>
                                <button
                                    className="w-full py-1.5 sm:py-2 bg-blue-900/40 hover:bg-blue-800/50 border border-blue-700 rounded text-blue-200 text-base sm:text-lg font-mono transition-colors"
                                    onClick={() => setView('tutorial')}
                                >
                                    <div className="flex items-center justify-center gap-2 sm:gap-3">
                                        <span className="text-lg sm:text-xl w-5 sm:w-6 text-center">📚</span>
                                        <span className="text-left min-w-[80px] sm:min-w-[100px]">Tutorial</span>
                                    </div>
                                </button>
                                
                                {/* Divider */}
                                <div className="border-t border-amber-900/50 my-1.5 sm:my-2"></div>
                                
                                <button
                                    className={`w-full py-1.5 sm:py-2 border rounded text-base sm:text-lg font-mono transition-colors ${
                                        user?.is_anonymous
                                            ? 'bg-green-900/30 hover:bg-green-800/40 border-green-700 text-green-300'
                                            : 'bg-red-900/30 hover:bg-red-800/40 border-red-700 text-red-300'
                                    }`}
                                    onClick={() => {
                                        if (user?.is_anonymous) {
                                            // Show guest conversion modal
                                            setShowGuestConversion(true);
                                        } else {
                                            // Regular users: clear player state to go back to join screen
                                            console.log('[SaveAndQuit] Returning to main menu');
                                            setPlayer(null);
                                            setIsMenuOpen(false);
                                        }
                                    }}
                                >
                                    <div className="flex items-center justify-center gap-2 sm:gap-3">
                                        <span className="text-lg sm:text-xl w-5 sm:w-6 text-center">{user?.is_anonymous ? '✨' : '💾'}</span>
                                        <span className="text-left min-w-[80px] sm:min-w-[100px]">{user?.is_anonymous ? 'Create Account' : 'Save & Quit'}</span>
                                    </div>
                                </button>
                                <button
                                    className="w-full py-1.5 sm:py-2 bg-green-900/30 hover:bg-green-800/40 border border-green-700 rounded text-green-300 text-base sm:text-lg font-mono transition-colors"
                                    onClick={() => setIsMenuOpen(false)}
                                >
                                    <div className="flex items-center justify-center gap-2 sm:gap-3">
                                        <span className="text-lg sm:text-xl w-5 sm:w-6 text-center">▶️</span>
                                        <span className="text-left min-w-[80px] sm:min-w-[100px]">Resume</span>
                                    </div>
                                </button>
                            </div>
                        </div>
                    )}

                    {view === 'inventory' && (
                        <div>
                            <div className="flex items-center justify-between mb-2 sm:mb-3">
                                <h2 className="text-xl sm:text-2xl text-amber-400 font-bold font-mono">Inventory</h2>
                                <button
                                    className="px-2 sm:px-3 py-1 sm:py-1.5 bg-amber-900/40 hover:bg-amber-800/50 border border-amber-700 rounded text-amber-200 text-sm sm:text-base font-mono"
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
                            <div className="flex items-center justify-between mb-2 sm:mb-3">
                                <h2 className="text-xl sm:text-2xl text-blue-400 font-bold font-mono">Tutorial</h2>
                                <button
                                    className="px-2 sm:px-3 py-1 sm:py-1.5 bg-blue-900/40 hover:bg-blue-800/50 border border-blue-700 rounded text-blue-200 text-sm sm:text-base font-mono"
                                    onClick={() => {
                                        if (isFirstTime) {
                                            // First time user - close menu and start playing
                                            localStorage.setItem('tutorial_seen', 'true');
                                            setIsFirstTime(false);
                                            setIsMenuOpen(false);
                                        } else {
                                            setView('root');
                                        }
                                    }}
                                >
                                    {isFirstTime ? 'Start Playing' : 'Back'}
                                </button>
                            </div>
                            <div className="space-y-2 sm:space-y-3 text-blue-200 font-mono max-h-96 overflow-y-auto pr-2">
                                <div className="bg-blue-900/20 border border-blue-700 rounded p-2 sm:p-3">
                                    <h3 className="text-base sm:text-lg text-blue-300 font-bold mb-2">🎮 Basic Controls</h3>
                                    <ul className="space-y-1 text-sm">
                                        <li>• <strong>ESC</strong> - Open/Close this menu</li>
                                        <li>• <strong>Bottom Bar</strong> - Click to type any action you want to take, specify a direction if you want to move rooms</li>
                                        <li>• <strong>Enter</strong> - Send chat messages</li>
                                        <li>• <strong>Minimap</strong> - Click minimap on top left to open full screen map</li>
                                    </ul>
                                </div>
                                
                                <div className="bg-blue-900/20 border border-blue-700 rounded p-2 sm:p-3">
                                    <h3 className="text-base sm:text-lg text-blue-300 font-bold mb-2">🗺️ Exploration</h3>
                                    <ul className="space-y-1 text-sm">
                                        <li>• Move around to discover new rooms and biomes</li>
                                        <li>• Explore within each room, discovering items and other creatures</li>
                                        <li>• Use the minimap to track your progress</li>
                                        <li>• Some areas may contain dangerous monsters</li>
                                        <li>• To avoid agressive monsters, return to the room you came from</li>
                                    </ul>
                                </div>

                                <div className="bg-blue-900/20 border border-blue-700 rounded p-2 sm:p-3">
                                    <h3 className="text-base sm:text-lg text-blue-300 font-bold mb-2">⚔️ Combat & Items</h3>
                                    <ul className="space-y-1 text-sm">
                                        <li>• Collect items to improve your character</li>
                                        <li>• Items enable new actions you can take</li>
                                        <li>• For example, you can&apos;t stab anyone without something sharp</li>
                                        <li>• Select two+ items from your inventory to combine them!</li>
                                    </ul>
                                </div>

                                <div className="bg-blue-900/20 border border-blue-700 rounded p-2 sm:p-3">
                                    <h3 className="text-base sm:text-lg text-blue-300 font-bold mb-2">💬 Social Features</h3>
                                    <ul className="space-y-1 text-sm">
                                        <li>• Chat with other players in the same room</li>
                                        <li>• Challenge other players to duels by clicking their name in the &quot;also here&quot; list on the top left</li>
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