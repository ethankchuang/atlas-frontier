import React from 'react';

interface TutorialPopupProps {
    isOpen: boolean;
    onClose: () => void;
}

const TutorialPopup: React.FC<TutorialPopupProps> = ({ isOpen, onClose }) => {
    if (!isOpen) return null;

    return (
        <div className="absolute inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black bg-opacity-80"
                onClick={onClose}
            />

            {/* Tutorial Panel */}
            <div className="relative z-10 w-full max-w-4xl mx-auto bg-black border-4 border-blue-900 rounded shadow-xl max-h-[90vh] overflow-hidden">
                <div className="p-6">
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-4xl text-blue-400 font-bold font-mono">🎮 Welcome to the Game!</h2>
                        <button
                            className="px-6 py-3 bg-blue-900/40 hover:bg-blue-800/50 border border-blue-700 rounded text-blue-200 text-xl font-mono transition-colors"
                            onClick={onClose}
                        >
                            Let&apos;s Play!
                        </button>
                    </div>
                    
                    <div className="space-y-6 text-blue-200 font-mono max-h-[70vh] overflow-y-auto pr-2">
                        <div className="bg-blue-900/20 border border-blue-700 rounded p-6">
                            <h3 className="text-2xl text-blue-300 font-bold mb-4">🎮 Basic Controls</h3>
                            <ul className="space-y-2 text-lg">
                                <li>• <strong>ESC</strong> - Open/Close the game menu</li>
                                <li>• <strong>Bottom Bar</strong> - Type any action you want to take (e.g., &quot;go north&quot;, &quot;look around&quot;, &quot;grab sword&quot;)</li>
                                <li>• <strong>Enter</strong> - Send your action to the game</li>
                                <li>• <strong>Minimap</strong> - Click the minimap in the top left to open the full-screen map</li>
                            </ul>
                        </div>
                        
                        <div className="bg-blue-900/20 border border-blue-700 rounded p-6">
                            <h3 className="text-2xl text-blue-300 font-bold mb-4">🗺️ Exploration</h3>
                            <ul className="space-y-2 text-lg">
                                <li>• Move around to discover new rooms and biomes</li>
                                <li>• Explore within each room to find items and creatures</li>
                                <li>• Use the minimap to track your progress</li>
                                <li>• Some areas may contain dangerous monsters</li>
                                <li>• To avoid aggressive monsters, return to the room you came from</li>
                            </ul>
                        </div>

                        <div className="bg-blue-900/20 border border-blue-700 rounded p-6">
                            <h3 className="text-2xl text-blue-300 font-bold mb-4">⚔️ Combat & Items</h3>
                            <ul className="space-y-2 text-lg">
                                <li>• Collect items to improve your character and enable new actions</li>
                                <li>• You need the right equipment to perform certain actions (e.g., you can&apos;t slash without a sword)</li>
                                <li>• Select multiple items from your inventory to combine them!</li>
                                <li>• Combat is turn-based - choose your moves carefully</li>
                            </ul>
                        </div>

                        <div className="bg-blue-900/20 border border-blue-700 rounded p-6">
                            <h3 className="text-2xl text-blue-300 font-bold mb-4">💬 Social Features</h3>
                            <ul className="space-y-2 text-lg">
                                <li>• Chat with other players in the same room</li>
                                <li>• Challenge other players to duels by clicking their name in the &quot;also here&quot; list</li>
                                <li>• Create an account to save your progress permanently</li>
                                <li>• Guest accounts reset when you leave the game</li>
                            </ul>
                        </div>

                        <div className="bg-green-900/20 border border-green-700 rounded p-6">
                            <h3 className="text-2xl text-green-300 font-bold mb-4">🚀 Getting Started</h3>
                            <ul className="space-y-2 text-lg">
                                <li>• Try typing &quot;look around&quot; to explore your current room</li>
                                <li>• Try &quot;go north&quot; or &quot;go east&quot; to move to new areas</li>
                                <li>• Try &quot;grab&quot; or &quot;take&quot; to pick up items you find</li>
                                <li>• Press ESC anytime to access your inventory and settings</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default TutorialPopup;
