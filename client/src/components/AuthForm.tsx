'use client';

import React, { useState, useEffect } from 'react';
import { RegisterRequest, LoginRequest } from '@/types/auth';
import apiService from '@/services/api';
import useGameStore from '@/store/gameStore';
import { supabase } from '@/lib/supabase';

interface AuthFormProps {
    onSuccess: () => void;
    autoGuestLogin?: boolean;
}

type FormMode = 'login' | 'register' | 'guest';

const AuthForm: React.FC<AuthFormProps> = ({ onSuccess, autoGuestLogin = false }) => {
    const [mode, setMode] = useState<FormMode>('guest');
    const [formData, setFormData] = useState({
        email: '',
        password: '',
        username: ''
    });
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null);
    const [usernameCheckLoading, setUsernameCheckLoading] = useState(false);

    const { setUser, setIsAuthenticated, setPlayer } = useGameStore();

    // Auto-guest login effect
    useEffect(() => {
        if (autoGuestLogin && !isLoading) {
            // Automatically trigger guest login by calling the guest authentication directly
            const performGuestLogin = async () => {
                setIsLoading(true);
                setError(null);

                try {
                    // Sign in anonymously with Supabase
                    const { data, error } = await supabase.auth.signInAnonymously();
                    
                    if (error) {
                        throw new Error(`Anonymous sign-in failed: ${error.message}`);
                    }
                    
                    if (!data.user) {
                        throw new Error('Anonymous sign-in failed: No user data returned');
                    }
                    
                    // Create a guest player using the anonymous user ID
                    const guestResponse = await apiService.createGuestPlayer(data.user.id);
                    
                    // Store the Supabase session token
                    if (data.session?.access_token) {
                        localStorage.setItem('auth_token', data.session.access_token);
                    }
                    
                    // Store player ID for session restoration
                    localStorage.setItem('player_id', guestResponse.player.id);
                    console.log('[Session] Saved guest player on creation:', guestResponse.player.id);
                    
                    setUser({
                        id: data.user.id,
                        username: guestResponse.player.name,
                        email: data.user.email || 'anonymous@example.com',
                        is_anonymous: true
                    });
                    setPlayer(guestResponse.player); // Set the player in the store
                    setIsAuthenticated(true); // Anonymous users are authenticated in Supabase
                    onSuccess();
                } catch (error) {
                    if (error instanceof Error) {
                        setError(error.message);
                    } else {
                        setError('An unexpected error occurred');
                    }
                } finally {
                    setIsLoading(false);
                }
            };

            performGuestLogin();
        }
    }, [autoGuestLogin, isLoading, setUser, setPlayer, setIsAuthenticated, onSuccess]);

    // Username validation
    const validateUsername = (username: string): string | null => {
        if (username.length < 3) return 'Username must be at least 3 characters';
        if (username.length > 20) return 'Username must be less than 20 characters';
        if (!/^[a-zA-Z][a-zA-Z0-9]*$/.test(username)) return 'Username must start with a letter and contain only letters and numbers';
        return null;
    };

    // Check username availability (debounced)
    useEffect(() => {
        if (mode === 'register' && formData.username && validateUsername(formData.username) === null) {
            const timeoutId = setTimeout(async () => {
                setUsernameCheckLoading(true);
                try {
                    const result = await apiService.checkUsernameAvailability(formData.username);
                    setUsernameAvailable(result.available);
                } catch (error) {
                    console.error('Username check failed:', error);
                } finally {
                    setUsernameCheckLoading(false);
                }
            }, 500);

            return () => clearTimeout(timeoutId);
        } else {
            setUsernameAvailable(null);
        }
    }, [formData.username, mode]);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value
        });
        setError(null);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);

        try {
            if (mode === 'register') {
                // Validate username
                const usernameError = validateUsername(formData.username);
                if (usernameError) {
                    setError(usernameError);
                    setIsLoading(false);
                    return;
                }

                if (usernameAvailable === false) {
                    setError('Username is not available');
                    setIsLoading(false);
                    return;
                }

                const registerData: RegisterRequest = {
                    email: formData.email,
                    password: formData.password,
                    username: formData.username
                };

                await apiService.register(registerData);
                
                // Auto-login after registration
                const loginData: LoginRequest = {
                    email: formData.email,
                    password: formData.password
                };

                const authResponse = await apiService.login(loginData);
                setUser(authResponse.user);
                setIsAuthenticated(true);
                onSuccess();
            } else if (mode === 'guest') {
                // Sign in anonymously with Supabase
                const { data, error } = await supabase.auth.signInAnonymously();
                
                if (error) {
                    throw new Error(`Anonymous sign-in failed: ${error.message}`);
                }
                
                if (!data.user) {
                    throw new Error('Anonymous sign-in failed: No user data returned');
                }
                
                // Create a guest player using the anonymous user ID
                const guestResponse = await apiService.createGuestPlayer(data.user.id);
                
                // Store the Supabase session token
                if (data.session?.access_token) {
                    localStorage.setItem('auth_token', data.session.access_token);
                }
                
                // Store player ID for session restoration
                localStorage.setItem('player_id', guestResponse.player.id);
                console.log('[Session] Saved guest player on creation:', guestResponse.player.id);
                
                setUser({
                    id: data.user.id,
                    username: guestResponse.player.name,
                    email: data.user.email || 'anonymous@example.com',
                    is_anonymous: true
                });
                setPlayer(guestResponse.player); // Set the player in the store
                setIsAuthenticated(true); // Anonymous users are authenticated in Supabase
                onSuccess();
            } else {
                const loginData: LoginRequest = {
                    email: formData.email,
                    password: formData.password
                };

                const authResponse = await apiService.login(loginData);
                setUser(authResponse.user);
                setIsAuthenticated(true);
                onSuccess();
            }
        } catch (error) {
            if (error instanceof Error) {
                setError(error.message);
            } else {
                setError('An unexpected error occurred');
            }
        } finally {
            setIsLoading(false);
        }
    };

    const getUsernameInputStyle = () => {
        if (!formData.username || validateUsername(formData.username) !== null) {
            return "w-full px-4 py-2 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500";
        }
        
        if (usernameCheckLoading) {
            return "w-full px-4 py-2 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-yellow-500 border border-yellow-500";
        }
        
        if (usernameAvailable === true) {
            return "w-full px-4 py-2 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 border border-green-500";
        }
        
        if (usernameAvailable === false) {
            return "w-full px-4 py-2 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-red-500 border border-red-500";
        }
        
        return "w-full px-4 py-2 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500";
    };

    const getUsernameMessage = () => {
        const validationError = validateUsername(formData.username);
        if (validationError) return { text: validationError, color: 'text-red-400' };
        
        if (usernameCheckLoading) return { text: 'Checking availability...', color: 'text-yellow-400' };
        if (usernameAvailable === true) return { text: 'Username available!', color: 'text-green-400' };
        if (usernameAvailable === false) return { text: 'Username taken', color: 'text-red-400' };
        
        return null;
    };

    return (
        <div className="w-full max-w-md mx-4 p-6 bg-black/70 backdrop-blur-xl rounded-2xl shadow-2xl border-2 border-amber-500/30">
            {/* Hero Title */}
            <div className="text-center mb-6">
                <h1 className="text-4xl md:text-5xl font-bold mb-1 bg-gradient-to-r from-amber-400 via-yellow-300 to-amber-400 bg-clip-text text-transparent drop-shadow-[0_0_30px_rgba(251,191,36,0.5)]">
                    Atlas Frontier
                </h1>
                <p className="text-sm text-amber-200/60 mb-2 italic">formerly Eternal Engine</p>
                <div className="h-1 w-32 mx-auto bg-gradient-to-r from-transparent via-amber-500 to-transparent rounded-full mb-3" />
                <p className="text-base text-amber-200/90 font-medium">
                    Infinite AI-Powered Adventure Awaits
                </p>
            </div>

            {/* Tab Navigation */}
            <div className="flex gap-2 mb-6">
                <button
                    type="button"
                    onClick={() => setMode('guest')}
                    className={`flex-1 py-3 px-4 rounded-xl font-bold leading-none cursor-pointer text-center ${
                        mode === 'guest'
                            ? 'bg-gradient-to-r from-emerald-600 to-green-600 text-white shadow-lg shadow-green-500/30'
                            : 'bg-gray-800/60 text-gray-300 hover:bg-gray-700/60'
                    }`}
                >
                    🎮 Play Now
                </button>
                <button
                    type="button"
                    onClick={() => setMode('login')}
                    className={`flex-1 py-3 px-4 rounded-xl font-bold leading-none cursor-pointer text-center ${
                        mode === 'login'
                            ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/30'
                            : 'bg-gray-800/60 text-gray-300 hover:bg-gray-700/60'
                    }`}
                >
                    🔐 Login
                </button>
                <button
                    type="button"
                    onClick={() => setMode('register')}
                    className={`flex-1 py-3 px-4 rounded-xl font-bold leading-none cursor-pointer text-center ${
                        mode === 'register'
                            ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/30'
                            : 'bg-gray-800/60 text-gray-300 hover:bg-gray-700/60'
                    }`}
                >
                    ⚡ Register
                </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
                {mode === 'guest' && (
                    <div className="space-y-4">
                        {/* Feature highlights */}
                        <div className="grid grid-cols-3 gap-3 text-center py-1">
                            <div className="flex flex-col items-center gap-1">
                                <div className="text-3xl">✨</div>
                                <div className="text-xs text-amber-300 font-semibold">AI Powered</div>
                            </div>
                            <div className="flex flex-col items-center gap-1">
                                <div className="text-3xl">🗺️</div>
                                <div className="text-xs text-amber-300 font-semibold">Infinite Worlds</div>
                            </div>
                            <div className="flex flex-col items-center gap-1">
                                <div className="text-3xl">🤝</div>
                                <div className="text-xs text-amber-300 font-semibold">Meet Players</div>
                            </div>
                        </div>

                        {/* Guest mode benefits */}
                        <div className="bg-emerald-900/30 border border-emerald-500/30 rounded-lg p-3">
                            <div className="flex items-start gap-2">
                                <div className="text-xl">✨</div>
                                <div>
                                    <h3 className="text-emerald-300 font-bold text-base mb-1">Jump Right In!</h3>
                                    <p className="text-emerald-200/80 text-sm">
                                        No sign-up needed. Start your adventure instantly. Create an account anytime to save your progress.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
                
                {mode === 'register' && (
                    <div>
                        <label htmlFor="username" className="block text-sm font-medium text-gray-300 mb-2">
                            Choose a Username
                        </label>
                        <input
                            type="text"
                            id="username"
                            name="username"
                            value={formData.username}
                            onChange={handleInputChange}
                            className={getUsernameInputStyle()}
                            placeholder="Enter your username"
                            required
                            maxLength={20}
                        />
                        {formData.username && (() => {
                            const message = getUsernameMessage();
                            return message ? (
                                <p className={`text-xs mt-1 ${message.color}`}>
                                    {message.text}
                                </p>
                            ) : null;
                        })()}
                    </div>
                )}

                {(mode === 'login' || mode === 'register') && (
                    <>
                        <div>
                            <label htmlFor="email" className="block text-sm font-medium text-gray-300 mb-2">
                                Email
                            </label>
                            <input
                                type="email"
                                id="email"
                                name="email"
                                value={formData.email}
                                onChange={handleInputChange}
                                className="w-full px-4 py-2 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                placeholder="Enter your email"
                                required
                            />
                        </div>

                        <div>
                            <label htmlFor="password" className="block text-sm font-medium text-gray-300 mb-2">
                                Password
                            </label>
                            <input
                                type="password"
                                id="password"
                                name="password"
                                value={formData.password}
                                onChange={handleInputChange}
                                className="w-full px-4 py-2 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                                placeholder="Enter your password"
                                required
                                minLength={8}
                            />
                        </div>
                    </>
                )}

                {error && (
                    <div className="p-3 bg-red-600/20 border border-red-500 rounded-lg">
                        <p className="text-red-400 text-sm">{error}</p>
                    </div>
                )}

                <button
                    type="submit"
                    disabled={
                        isLoading ||
                        (mode === 'register' && (
                            usernameCheckLoading || // wait for in-flight check
                            usernameAvailable === false // block only if explicitly taken
                        ))
                    }
                    className={`
                        w-full py-4 px-6
                        text-xl font-bold text-white leading-none
                        rounded-xl
                        cursor-pointer
                        focus:outline-none
                        disabled:opacity-50 disabled:cursor-not-allowed
                        shadow-lg
                        ${mode === 'guest'
                            ? 'bg-gradient-to-r from-emerald-600 to-green-600 hover:from-emerald-500 hover:to-green-500 shadow-green-500/30'
                            : 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 shadow-blue-500/30'
                        }
                    `}
                >
                    {isLoading ? (
                        <span className="flex items-center justify-center gap-2">
                            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                            </svg>
                            {mode === 'guest' ? 'Entering World...' : 'Please wait...'}
                        </span>
                    ) : mode === 'register' ? (
                        <span className="flex items-center justify-center gap-2">
                            ⚡ Create Free Account
                        </span>
                    ) : mode === 'guest' ? (
                        <span className="flex items-center justify-center gap-2">
                            🚀 Start Playing Now
                        </span>
                    ) : (
                        'Login'
                    )}
                </button>
            </form>

            {/* Footer text */}
            <div className="mt-4 pt-4 border-t border-amber-500/20">
                <p className="text-sm text-amber-200/80 text-center leading-relaxed">
                    {mode === 'register'
                        ? 'Create an account to save your progress and unlock the full adventure.'
                        : mode === 'guest'
                        ? (
                            <>
                                Join you friends in exploring infinite AI-generated worlds. Every quest is unique, every story is yours.
                            </>
                        )
                        : 'Welcome back! Your adventure continues...'
                    }
                </p>
            </div>
        </div>
    );
};

export default AuthForm;