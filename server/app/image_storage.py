"""
Image storage utilities for uploading AI-generated images to Supabase Storage.
"""
import aiohttp
import ssl
import certifi
import logging
from typing import Optional
from .supabase_client import get_supabase_client
from .logger import setup_logging
from storage3.utils import StorageException

setup_logging()
logger = logging.getLogger(__name__)

# Supabase Storage bucket name
STORAGE_BUCKET = "room-images"

async def test_storage_bucket() -> bool:
    """
    Test if the Supabase storage bucket is accessible.
    
    Returns:
        True if bucket is accessible, False otherwise
    """
    try:
        supabase = get_supabase_client()
        # Try to list files in the bucket
        response = supabase.storage.from_(STORAGE_BUCKET).list()
        logger.info(f"[Image Storage] Storage bucket '{STORAGE_BUCKET}' is accessible")
        return True
    except StorageException as e:
        logger.error(f"[Image Storage] StorageException testing bucket:")
        logger.error(f"  - Name: {getattr(e, 'name', 'N/A')}")
        logger.error(f"  - Message: {getattr(e, 'message', str(e))}")
        logger.error(f"  - Code: {getattr(e, 'code', 'N/A')}")
        logger.error(f"  - Status: {getattr(e, 'status', 'N/A')}")
        return False
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e) if str(e) else "No error message"
        logger.error(f"[Image Storage] Storage bucket test failed - Type: {error_type}, Message: {error_msg}")
        return False

async def upload_image_to_supabase(
    image_url: str,
    room_id: str,
    timeout: int = 30,
    max_retries: int = 3
) -> Optional[str]:
    """
    Download an AI-generated image from a temporary URL and upload it to Supabase Storage.

    Args:
        image_url: The temporary URL of the generated image
        room_id: The room ID to use for naming the file
        timeout: Request timeout in seconds
        max_retries: Maximum number of upload retry attempts

    Returns:
        The public URL of the uploaded image in Supabase, or None if upload fails
    """
    if not image_url:
        logger.warning("[Image Storage] No image URL provided")
        return None

    # Download the image first (only once)
    try:
        logger.info(f"[Image Storage] Downloading image from {image_url[:100]}...")

        # Create SSL context with proper certificate verification
        ssl_context = ssl.create_default_context(cafile=certifi.where())

        # Download the image from the temporary URL
        async with aiohttp.ClientSession() as session:
            async with session.get(
                image_url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=ssl_context
            ) as resp:
                if resp.status != 200:
                    logger.error(f"[Image Storage] Failed to download image: HTTP {resp.status}")
                    return None

                image_data = await resp.read()
                content_type = resp.headers.get('Content-Type', 'image/webp')

                logger.info(f"[Image Storage] Downloaded {len(image_data)} bytes, type: {content_type}")

    except aiohttp.ClientError as e:
        logger.error(f"[Image Storage] Network error downloading image: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"[Image Storage] Error downloading image: {str(e)}")
        return None

    # Determine file extension from content type
    extension = "webp"
    if "jpeg" in content_type or "jpg" in content_type:
        extension = "jpg"
    elif "png" in content_type:
        extension = "png"

    # Generate file path in storage
    file_path = f"rooms/{room_id}.{extension}"

    # Retry upload with exponential backoff
    import asyncio
    for attempt in range(max_retries):
        try:
            logger.info(f"[Image Storage] Uploading to Supabase Storage: {file_path} (attempt {attempt + 1}/{max_retries})")

            supabase = get_supabase_client()
            
            if not supabase:
                logger.error("[Image Storage] Supabase client is None")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                    continue
                return None

            # Upload the file (upsert=True allows overwriting if exists)
            response = supabase.storage.from_(STORAGE_BUCKET).upload(
                path=file_path,
                file=image_data,
                file_options={
                    "content-type": content_type,
                    "upsert": "true",  # Overwrite if exists
                    "cacheControl": "no-cache"  # Prevent server-side caching
                }
            )
            logger.info(f"[Image Storage] Upload response: {response}")

            # Get the public URL with cache-busting parameter
            public_url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(file_path)
            
            # Add cache-busting parameter to prevent client caching issues
            import time
            cache_buster = int(time.time())
            if '?' in public_url:
                public_url += f"&v={cache_buster}"
            else:
                public_url += f"?v={cache_buster}"

            logger.info(f"[Image Storage] Successfully uploaded image to Supabase: {public_url}")
            return public_url

        except StorageException as upload_error:
            # Handle Supabase storage-specific errors
            logger.error(f"[Image Storage] StorageException during upload (attempt {attempt + 1}/{max_retries}):")
            logger.error(f"  - Name: {getattr(upload_error, 'name', 'N/A')}")
            logger.error(f"  - Message: {getattr(upload_error, 'message', str(upload_error))}")
            logger.error(f"  - Code: {getattr(upload_error, 'code', 'N/A')}")
            logger.error(f"  - Status: {getattr(upload_error, 'status', 'N/A')}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            return None

        except Exception as upload_error:
            logger.error(f"[Image Storage] Upload failed (attempt {attempt + 1}/{max_retries}) - Type: {type(upload_error).__name__}, Error: {upload_error}")
            if hasattr(upload_error, 'message'):
                logger.error(f"[Image Storage] Error message: {upload_error.message}")
            if hasattr(upload_error, 'args'):
                logger.error(f"[Image Storage] Error args: {upload_error.args}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            
            import traceback
            logger.error(f"[Image Storage] Traceback: {traceback.format_exc()}")
            return None

    # All retries exhausted
    logger.error(f"[Image Storage] Failed to upload after {max_retries} attempts")
    return None


def is_temporary_image_url(image_url: str) -> bool:
    """
    Check if an image URL is from a temporary provider (Replicate, OpenAI, etc.)
    
    Args:
        image_url: The image URL to check
        
    Returns:
        True if the URL is temporary, False if it's permanent (Supabase) or empty
    """
    if not image_url:
        return False
    
    temporary_domains = [
        'replicate.delivery',
        'oaidalleapiprodscus.blob.core.windows.net',  # OpenAI DALL-E temporary URLs
        'dalle-temp',
    ]
    
    return any(domain in image_url for domain in temporary_domains)


async def delete_image_from_supabase(room_id: str) -> bool:
    """
    Delete a room image from Supabase Storage.

    Args:
        room_id: The room ID

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        supabase = get_supabase_client()

        # Try all possible extensions
        for ext in ["webp", "jpg", "png"]:
            file_path = f"rooms/{room_id}.{ext}"
            try:
                supabase.storage.from_(STORAGE_BUCKET).remove([file_path])
                logger.info(f"[Image Storage] Deleted image: {file_path}")
                return True
            except:
                continue

        logger.warning(f"[Image Storage] No image found to delete for room {room_id}")
        return False

    except Exception as e:
        logger.error(f"[Image Storage] Error deleting image from Supabase: {str(e)}")
        return False