'use client';

import React, { useState, useEffect } from 'react';
import GameLayout from '@/components/GameLayout';
import AuthForm from '@/components/AuthForm';
import useGameStore from '@/store/gameStore';
import apiService from '@/services/api';

// Background images from public/images/background
const BACKGROUND_IMAGES = [
    '/images/background/a.png',
    '/images/background/b.png',
    '/images/background/c.png',
    '/images/background/d.png',
    '/images/background/e.png',
];

export default function Home() {
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [randomBgImage, setRandomBgImage] = useState(BACKGROUND_IMAGES[0]);
    
    const { 
        user, 
        player, 
        isAuthenticated, 
        setUser, 
        setPlayer, 
        setIsAuthenticated 
    } = useGameStore();

    // Pick random background image on client side only
    useEffect(() => {
        setRandomBgImage(BACKGROUND_IMAGES[Math.floor(Math.random() * BACKGROUND_IMAGES.length)]);
    }, []);

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
            
            // Check if this is an anonymous user
            if (user?.is_anonymous) {
                // For anonymous users, get or create the guest player
                let guestPlayer = player;
                
                if (!guestPlayer) {
                    // Player state was lost (e.g., after page reload)
                    // Try to get or create the guest player
                    console.log('[JoinGame] Guest player not in state, fetching/creating for user:', user.id);
                    const guestResponse = await apiService.createGuestPlayer(user.id);
                    guestPlayer = guestResponse.player;
                    setPlayer(guestPlayer);
                }
                
                // Join the game with the guest player
                const result = await apiService.joinGame(guestPlayer.id);
                setPlayer(result.player);
            } else {
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
            }
            
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

    // Background container component
    const BackgroundContainer = ({ children }: { children: React.ReactNode }) => (
        <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
            {/* Random background image */}
            <div 
                className="absolute inset-0 bg-cover bg-center"
                style={{
                    backgroundImage: `url(${randomBgImage})`,
                }}
            />
            {/* Dark overlay for better readability */}
            <div className="absolute inset-0" />
            {/* Content */}
            <div className="relative z-10">
                {children}
            </div>
        </div>
    );

    // Show loading spinner while checking auth
    if (isLoading) {
        return (
            <BackgroundContainer>
                <div className="text-white text-xl">Loading...</div>
            </BackgroundContainer>
        );
    }

    // If player is in game, show game layout
    if (player && player.current_room) {
        return <GameLayout playerId={player.id} />;
    }

    // If authenticated but not in game, show join game screen
    if ((isAuthenticated || user?.is_anonymous) && user) {
        const isAnonymous = user.is_anonymous;
        
        return (
            <BackgroundContainer>
                <div className="max-w-md w-full p-6 bg-gray-800/40 backdrop-blur-md rounded-lg shadow-xl">
                    <div className="text-center mb-6">
                        <h1 className="text-3xl font-bold text-white mb-4">
                            {isAnonymous ? `Welcome, ${user.username}!` : `Welcome, ${user.username}!`}
                        </h1>
                        <p className="text-gray-300">
                            {isAnonymous ? 'Ready to try the game as a guest?' : 'Ready to begin your adventure?'}
                        </p>
                        {isAnonymous && (
                            <p className="text-sm text-yellow-400 mt-2">
                                Playing as guest - create an account to save your progress
                            </p>
                        )}
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
                            className={`w-full py-3 px-4 text-white rounded-lg transition-colors focus:outline-none focus:ring-2 disabled:opacity-50 ${
                                isAnonymous
                                    ? 'bg-green-600 hover:bg-green-700 focus:ring-green-500'
                                    : 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500'
                            }`}
                        >
                            {isLoading ? 'Entering world...' : isAnonymous ? 'Start Playing as Guest' : 'Begin Adventure'}
                        </button>
                        
                        <button
                            onClick={handleLogout}
                            className="w-full py-2 px-4 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-gray-500"
                        >
                            {isAnonymous ? 'Back to Login' : 'Logout'}
                        </button>
                    </div>

                    <div className="mt-6 text-sm text-gray-400 text-center">
                        <p>Explore a dynamic world generated completely by AI, interact with other players, and create your own adventures.</p>
                    </div>
                </div>
            </BackgroundContainer>
        );
    }

    // Not authenticated, show login/register form
    return (
        <BackgroundContainer>
            <AuthForm onSuccess={handleAuthSuccess} />
        </BackgroundContainer>
    );
}
