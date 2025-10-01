#!/usr/bin/env python3

import sys
import os
import asyncio
import logging

# Add the server directory to the Python path so we can import from app
server_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(server_dir)

from app.logger import setup_logging
from app.supabase_database import SupabaseDatabase

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

async def test_storage_clear():
    """Test the storage bucket clearing functionality"""
    try:
        print("Testing Supabase storage bucket clearing...")
        print("This will clear the 'rooms' folder and all its contents in the room-images bucket")
        
        # Test clearing the room-images bucket
        await SupabaseDatabase.reset_world()
        
        print("✓ Storage bucket clearing test completed")
        print("Check the logs above for any errors or success messages")
        print("The 'rooms' folder and all room images should now be cleared")
        
    except Exception as e:
        logger.error(f"Error testing storage clear: {str(e)}")
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_storage_clear())
