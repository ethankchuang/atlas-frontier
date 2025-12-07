"""
Test script to diagnose Supabase storage connection issues.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.supabase_client import get_supabase_client
from app.config import settings
from app.image_storage import test_storage_bucket, STORAGE_BUCKET
from storage3.utils import StorageException
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Test Supabase storage connection and configuration."""
    
    print("=" * 60)
    print("Supabase Storage Connection Test")
    print("=" * 60)
    print()
    
    # Check configuration
    print("1. Checking Supabase Configuration...")
    print(f"   SUPABASE_URL: {'✓ Set' if settings.SUPABASE_URL else '✗ Not set'}")
    if settings.SUPABASE_URL:
        print(f"      Value: {settings.SUPABASE_URL}")
    
    print(f"   SUPABASE_SERVICE_ROLE_KEY: {'✓ Set' if settings.SUPABASE_SERVICE_ROLE_KEY else '✗ Not set'}")
    if settings.SUPABASE_SERVICE_ROLE_KEY:
        print(f"      Value: {settings.SUPABASE_SERVICE_ROLE_KEY[:20]}...{settings.SUPABASE_SERVICE_ROLE_KEY[-10:]}")
    
    print()
    
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        print("✗ ERROR: Supabase configuration is incomplete!")
        print("   Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in your .env file")
        return
    
    # Test Supabase client
    print("2. Testing Supabase Client Connection...")
    try:
        supabase = get_supabase_client()
        print("   ✓ Supabase client initialized successfully")
    except Exception as e:
        print(f"   ✗ Failed to initialize Supabase client: {e}")
        return
    
    print()
    
    # Test database connection
    print("3. Testing Database Connection...")
    try:
        result = supabase.table('rooms').select('count', count='exact').limit(1).execute()
        print("   ✓ Database connection successful")
    except Exception as e:
        print(f"   ✗ Database connection failed: {e}")
    
    print()
    
    # Test storage bucket access
    print(f"4. Testing Storage Bucket Access ('{STORAGE_BUCKET}')...")
    try:
        bucket_ok = await test_storage_bucket()
        if bucket_ok:
            print("   ✓ Storage bucket is accessible")
        else:
            print("   ✗ Storage bucket is not accessible")
    except Exception as e:
        print(f"   ✗ Storage bucket test failed: {e}")
    
    print()
    
    # List available buckets
    print("5. Listing Available Storage Buckets...")
    try:
        buckets = supabase.storage.list_buckets()
        if buckets:
            print(f"   Found {len(buckets)} bucket(s):")
            for bucket in buckets:
                bucket_name = bucket.get('name', bucket.get('id', 'unknown'))
                bucket_public = bucket.get('public', False)
                print(f"      - {bucket_name} (public: {bucket_public})")
                if bucket_name == STORAGE_BUCKET:
                    print(f"        ✓ This is the configured bucket")
        else:
            print("   No buckets found")
    except Exception as e:
        print(f"   ✗ Failed to list buckets: {e}")
    
    print()
    
    # Test creating a test file
    print("6. Testing Upload Capability...")
    try:
        # Create a minimal 1x1 pixel PNG image (valid PNG file)
        # This is a base64 encoded 1x1 transparent PNG
        import base64
        test_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        test_content = base64.b64decode(test_png_b64)
        test_path = "test/test_upload.png"
        
        response = supabase.storage.from_(STORAGE_BUCKET).upload(
            path=test_path,
            file=test_content,
            file_options={
                "content-type": "image/png",
                "upsert": "true"
            }
        )
        print(f"   ✓ Test upload successful")
        print(f"      Response: {response}")
        
        # Try to delete the test file
        try:
            supabase.storage.from_(STORAGE_BUCKET).remove([test_path])
            print(f"   ✓ Test cleanup successful")
        except Exception as cleanup_error:
            print(f"   ⚠ Test cleanup failed (not critical): {cleanup_error}")
            
    except StorageException as e:
        print(f"   ✗ Upload test failed - StorageException:")
        print(f"      - Name: {getattr(e, 'name', 'N/A')}")
        print(f"      - Message: {getattr(e, 'message', str(e))}")
        print(f"      - Code: {getattr(e, 'code', 'N/A')}")
        print(f"      - Status: {getattr(e, 'status', 'N/A')}")
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e) if str(e) else "No error message"
        print(f"   ✗ Upload test failed - Type: {error_type}, Message: {error_msg}")
        if hasattr(e, '__dict__'):
            print(f"      Error details: {e.__dict__}")
    
    print()
    print("=" * 60)
    print("Test Complete")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())

