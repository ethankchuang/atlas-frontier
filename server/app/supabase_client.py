from supabase import create_client, Client
from .config import settings
from .logger import setup_logging
import logging

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Supabase client instance
supabase_client: Client = None

def get_supabase_client() -> Client:
    """Get or create Supabase client instance"""
    global supabase_client

    if supabase_client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            logger.error("Supabase configuration missing. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
            raise ValueError("Supabase configuration missing")

        try:
            # Use service role key for server-side operations
            # Note: The supabase-py library doesn't support custom http clients in the same way
            # The timeout configuration needs to be done at the httpx level when making requests
            supabase_client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY
            )
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            raise

    return supabase_client

def test_supabase_connection() -> bool:
    """Test the Supabase connection"""
    try:
        client = get_supabase_client()
        # Simple test query - check if we can access the rooms table
        result = client.table('rooms').select('count', count='exact').limit(1).execute()
        logger.info("Supabase connection test successful")
        return True
    except Exception as e:
        logger.error(f"Supabase connection test failed: {str(e)}")
        return False