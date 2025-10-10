'use client';

import React, { useState } from 'react';
import apiService from '@/services/api';
import useGameStore from '@/store/gameStore';
import { supabase } from '@/lib/supabase';

interface GuestConversionModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

const GuestConversionModal: React.FC<GuestConversionModalProps> = ({ isOpen, onClose, onSuccess }) => {
    const [formData, setFormData] = useState({
        email: '',
        password: '',
        username: ''
    });
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null);
    const [usernameCheckLoading, setUsernameCheckLoading] = useState(false);

    const { player } = useGameStore();

    // Username validation
    const validateUsername = (username: string): string | null => {
        if (username.length < 3) return 'Username must be at least 3 characters';
        if (username.length > 20) return 'Username must be less than 20 characters';
        if (!/^[a-zA-Z][a-zA-Z0-9]*$/.test(username)) return 'Username must start with a letter and contain only letters and numbers';
        return null;
    };

    // Check username availability (debounced)
    React.useEffect(() => {
        if (formData.username && validateUsername(formData.username) === null) {
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
    }, [formData.username]);

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

            // Convert anonymous user to permanent user using Supabase
            const { data: updateData, error: updateError } = await supabase.auth.updateUser({
                email: formData.email,
                password: formData.password
            });

            if (updateError) {
                throw new Error(`Failed to update user: ${updateError.message}`);
            }

            if (!updateData.user) {
                throw new Error('Failed to update user: No user data returned');
            }

            // Get the new session token
            const { data: sessionData } = await supabase.auth.getSession();

            // Update the player with the new user information
            await apiService.convertGuestToUser({
                email: formData.email,
                password: formData.password,
                username: formData.username,
                guest_player_id: player?.id || '',
                new_user_id: updateData.user.id
            });

            // Store the updated session token
            if (sessionData.session?.access_token) {
                localStorage.setItem('auth_token', sessionData.session.access_token);
            }
            
            // Update the user state
            useGameStore.getState().setUser({
                id: updateData.user.id,
                username: formData.username,
                email: formData.email,
                is_anonymous: false
            });
            useGameStore.getState().setIsAuthenticated(true);
            
            // Update the player state with the new name
            if (player) {
                // Immediately update with new name
                useGameStore.getState().setPlayer({
                    ...player,
                    name: formData.username,
                    user_id: updateData.user.id
                });
                
                // Also refresh the player data from the server to ensure full sync
                try {
                    const updatedPlayer = await apiService.getPlayer(player.id);
                    useGameStore.getState().setPlayer(updatedPlayer);
                    console.log('[GuestConversion] Player successfully updated to:', updatedPlayer.name);
                } catch (err) {
                    console.warn('[GuestConversion] Failed to refresh player data after conversion:', err);
                    // Non-critical, we already updated locally
                }
                
                // Reconnect WebSocket to update presence with new name
                try {
                    const websocketService = (await import('@/services/websocket')).default;
                    if (player.current_room) {
                        console.log('[GuestConversion] Reconnecting WebSocket with new name:', formData.username);
                        websocketService.disconnect();
                        // Small delay to ensure clean disconnect
                        await new Promise(resolve => setTimeout(resolve, 100));
                        websocketService.connect(player.current_room, player.id);
                    }
                } catch (err) {
                    console.warn('[GuestConversion] Failed to reconnect WebSocket:', err);
                    // Non-critical, but other players might see old name until refresh
                }
            }

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

    if (!isOpen) return null;

    return (
        <div className="absolute inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="absolute inset-0 bg-black bg-opacity-70"
                onClick={onClose}
            />

            {/* Modal */}
            <div className="relative z-10 w-full max-w-md mx-auto bg-gray-800 rounded-lg shadow-xl p-6">
                <div className="text-center mb-6">
                    <h2 className="text-2xl font-bold text-white mb-2">
                        Create Account
                    </h2>
                    <p className="text-gray-300">
                        Save your progress by creating an account
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
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
                            placeholder="your.email@example.com"
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
                            placeholder="Enter your password..."
                            required
                            minLength={8}
                        />
                    </div>

                    {error && (
                        <div className="p-3 bg-red-600/20 border border-red-500 rounded-lg">
                            <p className="text-red-400 text-sm">{error}</p>
                        </div>
                    )}

                    <div className="flex space-x-3">
                        <button
                            type="button"
                            onClick={onClose}
                            className="flex-1 py-2 px-4 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors focus:outline-none focus:ring-2 focus:ring-gray-500"
                        >
                            Cancel
                        </button>
                        <button
                            type="submit"
                            disabled={
                                isLoading ||
                                usernameCheckLoading ||
                                usernameAvailable === false
                            }
                            className="flex-1 py-2 px-4 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors focus:outline-none focus:ring-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {isLoading ? 'Creating Account...' : 'Create Account'}
                        </button>
                    </div>
                </form>

                <div className="mt-4 text-sm text-gray-400 text-center">
                    <p>Your current progress will be preserved.</p>
                </div>
            </div>
        </div>
    );
};

export default GuestConversionModal;
