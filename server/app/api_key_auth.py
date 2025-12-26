from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer
from typing import Optional
import logging
from .config import settings

logger = logging.getLogger(__name__)

class APIKeyAuth:
    """
    Simple API key authentication middleware.
    Checks for X-API-Key header if API_KEY is configured.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.API_KEY
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            logger.info("API Key authentication enabled")
        else:
            logger.info("API Key authentication disabled (no API_KEY configured)")
    
    async def __call__(self, request: Request):
        # Skip API key check if not configured
        if not self.enabled:
            return
        
        # Skip API key check for health endpoint
        if request.url.path == "/health":
            return

        # Skip API key check for CORS preflight requests
        if request.method == "OPTIONS":
            return

        # Check for API key header
        api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            logger.warning(f"Missing API key for {request.url.path} from {request.client.host if request.client else 'unknown'}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required"
            )
        
        if api_key != self.api_key:
            logger.warning(f"Invalid API key for {request.url.path} from {request.client.host if request.client else 'unknown'}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key"
            )
        
        # API key is valid, continue
        return

# Global instance
api_key_auth = APIKeyAuth()
