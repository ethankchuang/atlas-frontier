from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions
from .config import settings
from .logger import setup_logging
import logging
import httpx

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Supabase client instance
supabase_client: Client = None

def get_supabase_client() -> Client:
    """Get or create Supabase client instance with timeout configuration"""
    global supabase_client

    if supabase_client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            logger.error("Supabase configuration missing. Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
            raise ValueError("Supabase configuration missing")

        try:
            # Create httpx client with timeout to prevent hanging
            http_client = httpx.Client(
                timeout=httpx.Timeout(10.0, connect=5.0),  # 10s total, 5s connect
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )

            # Create Supabase client options with custom http client
            options = SyncClientOptions(
                postgrest_client_timeout=10,
                storage_client_timeout=10,
            )
            # Set the httpx client on the options
            options.client = http_client

            # Create Supabase client with timeout options
            supabase_client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_ROLE_KEY,
                options=options
            )
            logger.info("Supabase client initialized successfully with 10s timeout")
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