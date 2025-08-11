import re
import jwt
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .supabase_client import get_supabase_client
from .config import settings
import logging

logger = logging.getLogger(__name__)

# Security scheme for JWT tokens
security = HTTPBearer()

def validate_username(username: str) -> bool:
    """
    Validate username format:
    - Only letters and numbers
    - Must start with a letter
    - Case insensitive
    - 3-20 characters long
    """
    if not username or len(username) < 3 or len(username) > 20:
        return False
    
    # Must start with letter, then letters and numbers only
    pattern = r'^[a-zA-Z][a-zA-Z0-9]*$'
    return bool(re.match(pattern, username))

async def is_username_available(username: str) -> bool:
    """Check if a username is available (case insensitive)"""
    try:
        client = get_supabase_client()
        result = client.table('user_profiles').select('username').ilike('username', username).execute()
        return len(result.data) == 0
    except Exception as e:
        logger.error(f"Error checking username availability: {str(e)}")
        return False

def verify_jwt_token(token: str) -> Dict[str, Any]:
    """
    Verify Supabase JWT token and return user data
    """
    try:
        # Get Supabase JWT secret from settings - try JWT_SECRET first, fallback to SERVICE_ROLE_KEY
        jwt_secret = settings.SUPABASE_JWT_SECRET or settings.SUPABASE_SERVICE_ROLE_KEY
        if not jwt_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="JWT secret not configured"
            )
        
        # Decode the JWT token - Supabase uses HS256 algorithm
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_signature": True}
        )
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"JWT decode error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except Exception as e:
        logger.error(f"Error verifying JWT token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token verification failed"
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    FastAPI dependency to get the current authenticated user
    """
    try:
        # Extract token from Bearer scheme
        token = credentials.credentials
        
        # Verify the JWT token
        payload = verify_jwt_token(token)
        
        # Get user profile from database
        user_id = payload.get('sub')
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID"
            )
        
        client = get_supabase_client()
        result = client.table('user_profiles').select('*').eq('id', user_id).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        
        user_profile = result.data[0]
        
        # Combine JWT payload with profile data
        return {
            'id': user_id,
            'username': user_profile['username'],
            'email': user_profile['email'],
            'current_player_id': user_profile.get('current_player_id'),
            'jwt_payload': payload
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

async def get_optional_current_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency to get the current user if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None