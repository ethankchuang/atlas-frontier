'use client';

import React, { useState } from 'react';
import GameLayout from '@/components/GameLayout';

export default function Home() {
    const [playerName, setPlayerName] = useState('');
    const [isPlaying, setIsPlaying] = useState(false);

    const handleStartGame = (e: React.FormEvent) => {
        e.preventDefault();
        if (playerName.trim()) {
            setIsPlaying(true);
        }
    };

    if (isPlaying) {
        return <GameLayout playerId={playerName} />;
    }

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-900">
            <div className="max-w-md w-full p-6 bg-gray-800 rounded-lg shadow-xl">
                <h1 className="text-3xl font-bold text-white text-center mb-8">
                    AI-Powered MUD Game
                </h1>

                <form onSubmit={handleStartGame} className="space-y-6">
                    <div>
                        <label
                            htmlFor="playerName"
                            className="block text-sm font-medium text-gray-300 mb-2"
                        >
                            Enter Your Name
                        </label>
                        <input
                            type="text"
                            id="playerName"
                            value={playerName}
                            onChange={(e) => setPlayerName(e.target.value)}
                            className="w-full px-4 py-2 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="Your adventurer's name..."
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        className="w-full py-3 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                        Begin Adventure
                    </button>
                </form>

                <div className="mt-8 text-sm text-gray-400 text-center">
                    <p>Welcome to our AI-powered MUD game!</p>
                    <p className="mt-2">
                        Explore a dynamic world, interact with AI NPCs, and embark on epic quests.
                    </p>
                </div>
            </div>
        </div>
    );
}
