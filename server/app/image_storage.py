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

setup_logging()
logger = logging.getLogger(__name__)

# Supabase Storage bucket name
STORAGE_BUCKET = "room-images"

async def upload_image_to_supabase(
    image_url: str,
    room_id: str,
    timeout: int = 30
) -> Optional[str]:
    """
    Download an AI-generated image from a temporary URL and upload it to Supabase Storage.

    Args:
        image_url: The temporary URL of the generated image
        room_id: The room ID to use for naming the file
        timeout: Request timeout in seconds

    Returns:
        The public URL of the uploaded image in Supabase, or None if upload fails
    """
    try:
        if not image_url:
            logger.warning("[Image Storage] No image URL provided")
            return None

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

        # Determine file extension from content type
        extension = "webp"
        if "jpeg" in content_type or "jpg" in content_type:
            extension = "jpg"
        elif "png" in content_type:
            extension = "png"

        # Generate file path in storage
        file_path = f"rooms/{room_id}.{extension}"

        # Upload to Supabase Storage
        logger.info(f"[Image Storage] Uploading to Supabase Storage: {file_path}")

        supabase = get_supabase_client()

        # Upload the file (upsert=True allows overwriting if exists)
        response = supabase.storage.from_(STORAGE_BUCKET).upload(
            path=file_path,
            file=image_data,
            file_options={
                "content-type": content_type,
                "upsert": "true"  # Overwrite if exists
            }
        )

        # Get the public URL
        public_url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(file_path)

        logger.info(f"[Image Storage] Successfully uploaded image to Supabase: {public_url}")
        return public_url

    except aiohttp.ClientError as e:
        logger.error(f"[Image Storage] Network error downloading image: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"[Image Storage] Error uploading image to Supabase: {str(e)}")
        return None


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