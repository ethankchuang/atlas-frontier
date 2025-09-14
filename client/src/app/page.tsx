'use client';

import React, { useState, useEffect } from 'react';
import GameLayout from '@/components/GameLayout';
import AuthForm from '@/components/AuthForm';
import useGameStore from '@/store/gameStore';
import apiService from '@/services/api';

export default function Home() {
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    
    const { 
        user, 
        player, 
        isAuthenticated, 
        setUser, 
        setPlayer, 
        setIsAuthenticated 
    } = useGameStore();

    // Check for existing auth token on page load
    useEffect(() => {
        const checkAuthStatus = async () => {
            try {
                if (apiService.isAuthenticated()) {
                    const userProfile = await apiService.getProfile();
                    setUser(userProfile);
                    setIsAuthenticated(true);
                    
                    // Player will be loaded when joining the game
                }
            } catch (error) {
                console.warn('Auth check failed:', error);
                // Token might be expired, clear it
                apiService.logout();
                setIsAuthenticated(false);
                setUser(null);
            } finally {
                setIsLoading(false);
            }
        };

        checkAuthStatus();
    }, [setUser, setPlayer, setIsAuthenticated]);

    const handleAuthSuccess = () => {
        // Auth form will have already set user state
        // No additional action needed
    };

    const handleJoinGame = async () => {
        try {
            setIsLoading(true);
            setError(null);
            
            // Get user's players
            const playersData = await apiService.getPlayers();
            
            let playerId: string;
            if (playersData.players.length === 0) {
                // No players exist, create one
                const newPlayerData = await apiService.createPlayer(user?.username || 'Player');
                playerId = newPlayerData.player.id;
                setPlayer(newPlayerData.player);
            } else {
                // Use the first player (for now - later we can add player selection)
                playerId = playersData.players[0].id;
                setPlayer(playersData.players[0]);
            }
            
            // Join game with the player
            const result = await apiService.joinGame(playerId);
            setPlayer(result.player);
            
        } catch (error) {
            if (error instanceof Error) {
                setError(error.message);
            } else {
                setError('Failed to join game');
            }
        } finally {
            setIsLoading(false);
        }
    };

    const handleLogout = () => {
        apiService.logout();
        setUser(null);
        setPlayer(null);
        setIsAuthenticated(false);
    };

    // Show loading spinner while checking auth
    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-900">
                <div className="text-white">Loading...</div>
            </div>
        );
    }

    // If player is in game, show game layout
    if (player && player.current_room) {
        return <GameLayout playerId={player.id} />;
    }

    // If authenticated but not in game, show join game screen
    if (isAuthenticated && user) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-gray-900">
                <div className="max-w-md w-full p-6 bg-gray-800 rounded-lg shadow-xl">
                    <div className="text-center mb-6">
                        <h1 className="text-3xl font-bold text-white mb-4">
                            Welcome, {user.username}!
                        </h1>
                        <p className="text-gray-300">
                            Ready to begin your adventure?
                        </p>
                    </div>

                    {error && (
                        <div className="mb-4 p-3 bg-red-600/20 border border-red-500 rounded-lg">
                            <p className="text-red-400 text-sm">{error}</p>
                        </div>
                    )}

                    <div className="space-y-4">
                        <button
                            onClick={handleJoinGame}
                            disabled={isLoading}
                            className="w-full py-3 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                        >
                            {isLoading ? 'Entering world...' : 'Begin Adventure'}
                        </button>
                        
                        <button
                            onClick={handleLogout}
                            className="w-full py-2 px-4 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-gray-500"
                        >
                            Logout
                        </button>
                    </div>

                    <div className="mt-6 text-sm text-gray-400 text-center">
                        <p>Explore a dynamic world, interact with AI NPCs, and embark on epic quests.</p>
                    </div>
                </div>
            </div>
        );
    }

    // Not authenticated, show login/register form
    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-900">
            <AuthForm onSuccess={handleAuthSuccess} />
        </div>
    );
}
