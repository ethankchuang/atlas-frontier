'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
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

// Component that uses useSearchParams - needs to be wrapped in Suspense
function HomeContent() {
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [randomBgImage, setRandomBgImage] = useState(BACKGROUND_IMAGES[0]);
    const [autoGuestLogin, setAutoGuestLogin] = useState(false);
    
    const searchParams = useSearchParams();
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

    // Check for auto-guest login query parameter
    useEffect(() => {
        const playParam = searchParams.get('play');
        const guestParam = searchParams.get('guest');
        const autoPlay = playParam === 'true' || guestParam === 'true' || playParam === '' || guestParam === '';
        
        if (autoPlay) {
            setAutoGuestLogin(true);
        }
    }, [searchParams]);

    // Check for existing auth token and player session on page load
    useEffect(() => {
        const checkAuthStatus = async () => {
            try {
                if (apiService.isAuthenticated()) {
                    const userProfile = await apiService.getProfile();
                    setUser(userProfile);
                    setIsAuthenticated(true);
                    
                    // Try to restore player session from localStorage
                    const storedPlayerId = localStorage.getItem('player_id');
                    if (storedPlayerId) {
                        try {
                            console.log('[Session] Restoring player session:', storedPlayerId);
                            // Try to fetch the player data to restore the session
                            const playerData = await apiService.getPlayer(storedPlayerId);
                            if (playerData && playerData.current_room) {
                                console.log('[Session] Successfully restored player session');
                                setPlayer(playerData);
                                // Player is in a room, they'll be taken directly to the game
                            } else {
                                console.log('[Session] Player data found but no current room');
                                // Clear invalid player ID
                                localStorage.removeItem('player_id');
                            }
                        } catch (error) {
                            console.warn('[Session] Failed to restore player session:', error);
                            // Clear invalid player ID
                            localStorage.removeItem('player_id');
                        }
                    }
                }
            } catch (error) {
                console.warn('Auth check failed:', error);
                // Token might be expired, clear it
                apiService.logout();
                localStorage.removeItem('player_id');
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
                
                // Persist player ID for session restoration
                localStorage.setItem('player_id', result.player.id);
                console.log('[Session] Saved guest player session:', result.player.id);
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
                
                // Persist player ID for session restoration
                localStorage.setItem('player_id', result.player.id);
                console.log('[Session] Saved player session:', result.player.id);
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
        localStorage.removeItem('player_id');
        setUser(null);
        setPlayer(null);
        setIsAuthenticated(false);
        console.log('[Session] Cleared player session on logout');
    };

    // Background container component
    const BackgroundContainer = ({ children }: { children: React.ReactNode }) => (
        <div className="flex items-center justify-center relative overflow-hidden" style={{ height: '100lvh' }}>
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
            {/* Name change note at bottom left */}
            <div className="fixed left-4 z-20" style={{ bottom: 'max(1rem, env(safe-area-inset-bottom))' }}>
                <div className="text-xs text-gray-400 bg-black/60 backdrop-blur-sm px-3 py-2 rounded-lg border border-gray-700/50">
                    <span className="italic">Formerly known as Eternal Engine</span>
                </div>
            </div>
            {/* Footer with social links */}
            <div className="fixed right-4 z-20" style={{ bottom: 'max(1rem, env(safe-area-inset-bottom))' }}>
                <div className="flex items-center gap-2 text-xs text-gray-400 bg-black/60 backdrop-blur-sm px-3 py-2 rounded-lg border border-gray-700/50">
                    <span className="hidden sm:inline">follow & contact:</span>
                    <span className="sm:hidden">follow & contact:</span>
                    <div className="flex gap-2">
                        <a
                            href="https://twitter.com/AtlasFrontierIO"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-gray-400 hover:text-blue-400 transition-colors"
                            aria-label="Twitter"
                        >
                            <TwitterIcon />
                        </a>
                        <a
                            href="https://instagram.com/atlasfrontier.io"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-gray-400 hover:text-pink-400 transition-colors"
                            aria-label="Instagram"
                        >
                            <InstagramIcon />
                        </a>
                        <a
                            href="https://tiktok.com/@atlasfrontier.io"
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
                <div className="max-w-md w-full mx-4">
                    {/* Main game card */}
                    <div className="bg-black/60 backdrop-blur-xl rounded-2xl border-2 border-amber-500/30 shadow-2xl shadow-amber-500/20 p-6">
                        {/* Glowing title card */}
                        <div className="text-center mb-6 animate-fadeIn">
                            <div className="inline-block">
                                <h1 className="text-4xl md:text-5xl font-bold mb-2 bg-gradient-to-r from-amber-400 via-yellow-300 to-amber-400 bg-clip-text text-transparent drop-shadow-[0_0_30px_rgba(251,191,36,0.5)]">
                                    {isAnonymous ? `Welcome, ${user.username}` : `Welcome, ${user.username}`}
                                </h1>
                                <div className="h-1 bg-gradient-to-r from-transparent via-amber-500 to-transparent rounded-full" />
                            </div>
                        </div>
                        {/* Game features */}
                        <div className="grid grid-cols-3 gap-3 mb-4 text-center">
                            <div className="flex flex-col items-center gap-1">
                                <div className="text-2xl">✨</div>
                                <div className="text-xs text-amber-300 font-semibold">AI Powered</div>
                            </div>
                            <div className="flex flex-col items-center gap-1">
                                <div className="text-2xl">🗺️</div>
                                <div className="text-xs text-amber-300 font-semibold">Infinite Worlds</div>
                            </div>
                            <div className="flex flex-col items-center gap-1">
                                <div className="text-2xl">🤝</div>
                                <div className="text-xs text-amber-300 font-semibold">Meet Players</div>
                            </div>
                        </div>

                        {error && (
                            <div className="mb-4 p-3 bg-red-900/40 border-2 border-red-500/50 rounded-lg backdrop-blur-sm">
                                <p className="text-red-300 text-sm font-medium text-center">{error}</p>
                            </div>
                        )}

                        {/* CTA Button */}
                        <button
                            onClick={handleJoinGame}
                            disabled={isLoading}
                            className={`
                                w-full py-4 px-6 mb-4
                                text-xl font-bold text-white leading-none
                                rounded-xl
                                cursor-pointer
                                focus:outline-none
                                disabled:opacity-50 disabled:cursor-not-allowed
                                shadow-lg
                                ${isAnonymous
                                    ? 'bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 shadow-green-500/30'
                                    : 'bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-500 hover:to-orange-500 shadow-amber-500/30'
                                }
                            `}
                        >
                            {isLoading ? (
                                <span className="flex items-center justify-center gap-2">
                                    <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                    </svg>
                                    Entering World...
                                </span>
                            ) : (
                                <span className="flex items-center justify-center gap-2">
                                    🎮 {isAnonymous ? 'Start Playing' : 'Enter the World'}
                                </span>
                            )}
                        </button>

                        {isAnonymous && (
                            <div className="mb-3 p-2 bg-yellow-900/30 border border-yellow-500/30 rounded-lg">
                                <p className="text-yellow-300 text-sm text-center">
                                    💡 <span className="font-semibold">Guest Mode:</span> Create an account to save your progress!
                                </p>
                            </div>
                        )}

                        {/* Secondary button */}
                        <button
                            onClick={handleLogout}
                            className="w-full py-2.5 px-4 bg-gray-800/60 text-gray-300 rounded-lg hover:bg-gray-700/60 cursor-pointer focus:outline-none focus:ring-2 focus:ring-gray-500/50 border border-gray-600/30"
                        >
                            {isAnonymous ? '← Back to Login' : 'Logout'}
                        </button>

                        {/* Flavor text */}
                        <div className="mt-4 pt-4 border-t border-amber-500/20">
                            <p className="text-amber-200/80 text-sm text-center leading-relaxed">
                                Embark on an <span className="text-amber-400 font-semibold">AI-generated adventure</span> where every quest is unique, every battle is strategic, and your choices shape the world.
                            </p>
                        </div>
                    </div>
                </div>
            </BackgroundContainer>
        );
    }

    // Not authenticated, show login/register form
    return (
        <BackgroundContainer>
            <AuthForm onSuccess={handleAuthSuccess} autoGuestLogin={autoGuestLogin} />
        </BackgroundContainer>
    );
}

// Main Home component with Suspense boundary
export default function Home() {
    return (
        <Suspense fallback={
            <div className="flex items-center justify-center relative overflow-hidden" style={{ height: '100lvh' }}>
                <div className="text-white text-xl">Loading...</div>
            </div>
        }>
            <HomeContent />
        </Suspense>
    );
}
