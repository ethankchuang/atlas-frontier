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

// Social Media Icons
const TwitterIcon = () => (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
);

const InstagramIcon = () => (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path fillRule="evenodd" d="M12.315 2c2.43 0 2.784.013 3.808.06 1.064.049 1.791.218 2.427.465a4.902 4.902 0 011.772 1.153 4.902 4.902 0 011.153 1.772c.247.636.416 1.363.465 2.427.048 1.067.06 1.407.06 4.123v.08c0 2.643-.012 2.987-.06 4.043-.049 1.064-.218 1.791-.465 2.427a4.902 4.902 0 01-1.153 1.772 4.902 4.902 0 01-1.772 1.153c-.636.247-1.363.416-2.427.465-1.067.048-1.407.06-4.123.06h-.08c-2.643 0-2.987-.012-4.043-.06-1.064-.049-1.791-.218-2.427-.465a4.902 4.902 0 01-1.772-1.153 4.902 4.902 0 01-1.153-1.772c-.247-.636-.416-1.363-.465-2.427-.047-1.024-.06-1.379-.06-3.808v-.63c0-2.43.013-2.784.06-3.808.049-1.064.218-1.791.465-2.427a4.902 4.902 0 011.153-1.772A4.902 4.902 0 015.45 2.525c.636-.247 1.363-.416 2.427-.465C8.901 2.013 9.256 2 11.685 2h.63zm-.081 1.802h-.468c-2.456 0-2.784.011-3.807.058-.975.045-1.504.207-1.857.344-.467.182-.8.398-1.15.748-.35.35-.566.683-.748 1.15-.137.353-.3.882-.344 1.857-.047 1.023-.058 1.351-.058 3.807v.468c0 2.456.011 2.784.058 3.807.045.975.207 1.504.344 1.857.182.466.399.8.748 1.15.35.35.683.566 1.15.748.353.137.882.3 1.857.344 1.054.048 1.37.058 4.041.058h.08c2.597 0 2.917-.01 3.96-.058.976-.045 1.505-.207 1.858-.344.466-.182.8-.398 1.15-.748.35-.35.566-.683.748-1.15.137-.353.3-.882.344-1.857.048-1.055.058-1.37.058-4.041v-.08c0-2.597-.01-2.917-.058-3.96-.045-.976-.207-1.505-.344-1.858a3.097 3.097 0 00-.748-1.15 3.098 3.098 0 00-1.15-.748c-.353-.137-.882-.3-1.857-.344-1.023-.047-1.351-.058-3.807-.058zM12 6.865a5.135 5.135 0 110 10.27 5.135 5.135 0 010-10.27zm0 1.802a3.333 3.333 0 100 6.666 3.333 3.333 0 000-6.666zm5.338-3.205a1.2 1.2 0 110 2.4 1.2 1.2 0 010-2.4z" clipRule="evenodd" />
    </svg>
);

const TikTokIcon = () => (
    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-5.2 1.74 2.89 2.89 0 012.31-4.64 2.93 2.93 0 01.88.13V9.4a6.84 6.84 0 00-1-.05A6.33 6.33 0 005 20.1a6.34 6.34 0 0010.86-4.43v-7a8.16 8.16 0 004.77 1.52v-3.4a4.85 4.85 0 01-1-.1z" />
    </svg>
);

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
        <div className="flex items-center justify-center relative overflow-hidden" style={{ minHeight: '100svh' }}>
            {/* Random background image */}
            <div 
                className="absolute inset-0 bg-cover bg-center"
                style={{
                    backgroundImage: `url(${randomBgImage})`,
                    position: 'fixed',
                }}
            />
            {/* Dark overlay for better readability */}
            <div className="absolute inset-0" />
            {/* Content */}
            <div className="relative z-10">
                {children}
            </div>
            {/* Footer with social links */}
            <div className="fixed right-4 z-20" style={{ bottom: 'max(1rem, env(safe-area-inset-bottom))' }}>
                <div className="flex items-center gap-2 text-xs text-gray-400 bg-black/60 backdrop-blur-sm px-3 py-2 rounded-lg border border-gray-700/50">
                    <span className="hidden sm:inline">follow & contact:</span>
                    <span className="sm:hidden">follow & contact:</span>
                    <div className="flex gap-2">
                        <a
                            href="https://twitter.com/EternalEngineGG"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-gray-400 hover:text-blue-400 transition-colors"
                            aria-label="Twitter"
                        >
                            <TwitterIcon />
                        </a>
                        <a
                            href="https://instagram.com/eternalengine.gg"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-gray-400 hover:text-pink-400 transition-colors"
                            aria-label="Instagram"
                        >
                            <InstagramIcon />
                        </a>
                        <a
                            href="https://tiktok.com/@eternalengine.gg"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-gray-400 hover:text-white transition-colors"
                            aria-label="TikTok"
                        >
                            <TikTokIcon />
                        </a>
                    </div>
                </div>
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
