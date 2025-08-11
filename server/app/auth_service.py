from typing import Optional, Dict, Any
from .supabase_client import get_supabase_client
from .auth_utils import validate_username, is_username_available
from .hybrid_database import HybridDatabase as Database
from fastapi import HTTPException, status
import logging
import uuid

logger = logging.getLogger(__name__)

class AuthService:
    """Service for handling user authentication and profile management"""
    
    @staticmethod
    async def register_user(email: str, password: str, username: str) -> Dict[str, Any]:
        """
        Register a new user with email, password, and username
        """
        try:
            # Validate username format
            if not validate_username(username):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username must be 3-20 characters, start with a letter, and contain only letters and numbers"
                )
            
            # Check if username is available (case insensitive)
            if not await is_username_available(username):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username is already taken"
                )
            
            # Create user with Supabase Auth
            client = get_supabase_client()
            auth_response = client.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if auth_response.user is None:
                logger.error(f"Failed to create auth user: {auth_response}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to create user account"
                )
            
            user_id = auth_response.user.id
            
            # Create user profile
            profile_data = {
                'id': user_id,
                'username': username.lower(),  # Store as lowercase for consistency
                'email': email,
                'current_player_id': None
            }
            
            profile_result = client.table('user_profiles').insert(profile_data).execute()
            
            if not profile_result.data:
                logger.error(f"Failed to create user profile: {profile_result}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user profile"
                )
            
            # Create initial game player for this user
            player_id = f"player_{uuid.uuid4()}"
            player_data = {
                'id': player_id,
                'name': username,  # Display name (can preserve original case)
                'current_room': '',  # Empty string instead of None for Pydantic validation
                'inventory': [],
                'quest_progress': {},
                'memory_log': [f"Player {username} joined the game!"],
                'health': 20,  # Match the model default
                'user_id': user_id  # Link to auth user
            }
            
            success = await Database.set_player(player_id, player_data)
            if not success:
                logger.error(f"Failed to create initial player for user {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create game character"
                )
            
            # Update user profile with player ID
            client.table('user_profiles').update({
                'current_player_id': player_id
            }).eq('id', user_id).execute()
            
            logger.info(f"Successfully registered user {username} with player {player_id}")
            
            return {
                'user_id': user_id,
                'username': username,
                'email': email,
                'player_id': player_id,
                'message': 'User registered successfully! Please check your email to verify your account.'
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error registering user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed"
            )
    
    @staticmethod
    async def login_user(email: str, password: str) -> Dict[str, Any]:
        """
        Login user with email and password
        """
        try:
            client = get_supabase_client()
            auth_response = client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if auth_response.user is None or auth_response.session is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            
            user_id = auth_response.user.id
            access_token = auth_response.session.access_token
            
            # Get user profile
            profile_result = client.table('user_profiles').select('*').eq('id', user_id).execute()
            
            if not profile_result.data or len(profile_result.data) == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User profile not found"
                )
            
            profile = profile_result.data[0]
            
            logger.info(f"User {profile['username']} logged in successfully")
            
            return {
                'access_token': access_token,
                'token_type': 'bearer',
                'user': {
                    'id': user_id,
                    'username': profile['username'],
                    'email': profile['email'],
                    'current_player_id': profile['current_player_id']
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error logging in user: {str(e)}")
            
            # Handle specific Supabase auth errors
            error_message = str(e)
            if "Email not confirmed" in error_message:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Please confirm your email address before logging in. Check your inbox for a confirmation link."
                )
            elif "Invalid login credentials" in error_message:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Login failed"
                )
    
    @staticmethod
    async def get_user_profile(user_id: str) -> Dict[str, Any]:
        """
        Get user profile by ID
        """
        try:
            client = get_supabase_client()
            result = client.table('user_profiles').select('*').eq('id', user_id).execute()
            
            if not result.data or len(result.data) == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User profile not found"
                )
            
            return result.data[0]
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get user profile"
            )
    
    @staticmethod
    async def update_username(user_id: str, new_username: str) -> Dict[str, Any]:
        """
        Update user's username (if available)
        """
        try:
            # Validate new username format
            if not validate_username(new_username):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username must be 3-20 characters, start with a letter, and contain only letters and numbers"
                )
            
            # Check if new username is available (case insensitive)
            if not await is_username_available(new_username):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Username is already taken"
                )
            
            client = get_supabase_client()
            
            # Update user profile
            result = client.table('user_profiles').update({
                'username': new_username.lower()
            }).eq('id', user_id).execute()
            
            if not result.data or len(result.data) == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User profile not found"
                )
            
            # Update player name as well
            profile = result.data[0]
            if profile['current_player_id']:
                player_data = await Database.get_player(profile['current_player_id'])
                if player_data:
                    player_data['name'] = new_username
                    await Database.set_player(profile['current_player_id'], player_data)
            
            logger.info(f"Username updated for user {user_id} to {new_username}")
            
            return {
                'username': new_username,
                'message': 'Username updated successfully'
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating username: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update username"
            )