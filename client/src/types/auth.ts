export interface User {
    id: string;
    username: string;
    email: string;
    current_player_id: string | null;
}

export interface AuthResponse {
    access_token: string;
    token_type: string;
    user: User;
}

export interface RegisterRequest {
    email: string;
    password: string;
    username: string;
}

export interface LoginRequest {
    email: string;
    password: string;
}

export interface RegisterResponse {
    user_id: string;
    username: string;
    email: string;
    player_id: string;
    message: string;
}

export interface UsernameAvailability {
    available: boolean;
    reason: string | null;
}