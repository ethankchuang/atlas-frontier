'use client';

import React, { useState, useEffect } from 'react';
import { RegisterRequest, LoginRequest } from '@/types/auth';
import apiService from '@/services/api';
import useGameStore from '@/store/gameStore';
import { supabase } from '@/lib/supabase';

interface AuthFormProps {
    onSuccess: () => void;
}

type FormMode = 'login' | 'register' | 'guest';

const AuthForm: React.FC<AuthFormProps> = ({ onSuccess }) => {
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
        <div className="w-[448px] p-6 bg-gray-800/40 backdrop-blur-md rounded-lg shadow-xl">
            <h1 className="text-3xl font-bold text-white text-center mb-2">
                Eternal Engine
            </h1>
            <p className="text-center text-gray-400 mb-8">
                Inifinite AI-Powered Multiplayer World
            </p>

            <div className="flex mb-6">
                <button
                    type="button"
                    onClick={() => setMode('guest')}
                    className={`flex-1 py-2 px-4 rounded-l-lg font-medium transition-colors ${
                        mode === 'guest' 
                            ? 'bg-green-600 text-white' 
                            : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                >
                    Play Now
                </button>
                <button
                    type="button"
                    onClick={() => setMode('login')}
                    className={`flex-1 py-2 px-4 font-medium transition-colors ${
                        mode === 'login' 
                            ? 'bg-blue-600 text-white' 
                            : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                >
                    Login
                </button>
                <button
                    type="button"
                    onClick={() => setMode('register')}
                    className={`flex-1 py-2 px-4 rounded-r-lg font-medium transition-colors ${
                        mode === 'register' 
                            ? 'bg-blue-600 text-white' 
                            : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                >
                    Register
                </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
                {mode === 'guest' && (
                    <div className="text-center py-4">
                        <p className="text-gray-300 mb-4">
                            Play as guest. No account required.
                        </p>
                        <p className="text-sm text-gray-400">
                            Create a free account later to save your progress.
                        </p>
                    </div>
                )}
                
                {mode === 'register' && (
                    <div>
                        <label htmlFor="username" className="block text-sm font-medium text-gray-300 mb-2">
                            Username
                        </label>
                        <input
                            type="text"
                            id="username"
                            name="username"
                            value={formData.username}
                            onChange={handleInputChange}
                            className={getUsernameInputStyle()}
                            placeholder="Your unique username..."
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
                    className={`w-full py-3 px-4 text-white rounded-lg transition-colors focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed ${
                        mode === 'guest' 
                            ? 'bg-green-600 hover:bg-green-700 focus:ring-green-500' 
                            : 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500'
                    }`}
                >
                    {isLoading ? 'Please wait...' : 
                     mode === 'register' ? 'Create Free Account' : 
                     mode === 'guest' ? 'Start Playing for Free' : 'Login'}
                </button>
            </form>

            <div className="mt-6 text-sm text-gray-400 text-center">
                <p className="mt-2">
                    {mode === 'register' 
                        ? 'Create an account to save your progress and begin your adventure.'
                        : mode === 'guest'
                        ? 'Join thousands of players online in the infinite sandbox.'
                        : 'Login to continue your adventure.'
                    }
                </p>
            </div>
        </div>
    );
};

export default AuthForm;