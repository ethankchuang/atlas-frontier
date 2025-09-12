'use client';

import React, { useState, useEffect } from 'react';
import { RegisterRequest, LoginRequest } from '@/types/auth';
import apiService from '@/services/api';
import useGameStore from '@/store/gameStore';

interface AuthFormProps {
    onSuccess: () => void;
}

type FormMode = 'login' | 'register';

const AuthForm: React.FC<AuthFormProps> = ({ onSuccess }) => {
    const [mode, setMode] = useState<FormMode>('login');
    const [formData, setFormData] = useState({
        email: '',
        password: '',
        username: ''
    });
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [usernameAvailable, setUsernameAvailable] = useState<boolean | null>(null);
    const [usernameCheckLoading, setUsernameCheckLoading] = useState(false);

    const { setUser, setIsAuthenticated } = useGameStore();

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
        <div className="max-w-md w-full p-6 bg-gray-800 rounded-lg shadow-xl">
            <h1 className="text-3xl font-bold text-white text-center mb-8">
                AI-Powered MUD Game
            </h1>

            <div className="flex mb-6">
                <button
                    type="button"
                    onClick={() => setMode('login')}
                    className={`flex-1 py-2 px-4 rounded-l-lg font-medium transition-colors ${
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

                <button
                    type="submit"
                    disabled={
                        isLoading ||
                        (mode === 'register' && (
                            usernameCheckLoading || // wait for in-flight check
                            usernameAvailable === false // block only if explicitly taken
                        ))
                    }
                    className="w-full py-3 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {isLoading ? 'Please wait...' : mode === 'register' ? 'Create Account' : 'Login'}
                </button>
            </form>

            <div className="mt-6 text-sm text-gray-400 text-center">
                <p>Welcome to our AI-powered MUD game!</p>
                <p className="mt-2">
                    {mode === 'register' 
                        ? 'Create an account to save your progress and begin your adventure.'
                        : 'Login to continue your adventure.'
                    }
                </p>
            </div>
        </div>
    );
};

export default AuthForm;