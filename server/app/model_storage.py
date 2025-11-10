"""
3D model storage utilities for uploading GLB files to Supabase Storage.
GLB files can be 50-200MB so we need appropriate timeout/chunk handling.
FAL returns a ZIP file containing GLB + textures - we extract and upload the GLB.
"""
import aiohttp
import ssl
import certifi
import logging
import asyncio
import time
import zipfile
import io
import httpx
from typing import Optional
from supabase import create_client
from .config import settings
from .logger import setup_logging
from storage3.utils import StorageException

setup_logging()
logger = logging.getLogger(__name__)

# Supabase Storage bucket for 3D models (separate from room-images)
MODEL_BUCKET = "room-models"



def get_storage_client():
    """Get a Supabase client with extended timeout for large file uploads."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.error("Supabase configuration missing")
        return None

    try:
        # Create httpx client with very long timeout for large uploads
        http_client = httpx.Client(
            timeout=httpx.Timeout(600.0, connect=30.0),  # 10 min total, 30s connect
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )

        from supabase.lib.client_options import SyncClientOptions
        options = SyncClientOptions(
            postgrest_client_timeout=60,
            storage_client_timeout=600,  # 10 minutes for storage
        )
        options.client = http_client

        return create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
            options=options
        )
    except Exception as e:
        logger.error(f"Failed to create storage client: {e}")
        return None


async def test_model_storage_bucket() -> bool:
    """
    Test if the Supabase storage bucket for 3D models is accessible.

    Returns:
        True if bucket is accessible, False otherwise
    """
    try:
        supabase = get_storage_client()
        if not supabase:
            return False
        response = supabase.storage.from_(MODEL_BUCKET).list()
        logger.info(f"[Model Storage] Storage bucket '{MODEL_BUCKET}' is accessible")
        return True
    except StorageException as e:
        logger.error(f"[Model Storage] StorageException testing bucket:")
        logger.error(f"  - Name: {getattr(e, 'name', 'N/A')}")
        logger.error(f"  - Message: {getattr(e, 'message', str(e))}")
        logger.error(f"  - Code: {getattr(e, 'code', 'N/A')}")
        logger.error(f"  - Status: {getattr(e, 'status', 'N/A')}")
        return False
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e) if str(e) else "No error message"
        logger.error(f"[Model Storage] Storage bucket test failed - Type: {error_type}, Message: {error_msg}")
        return False


async def upload_model_to_supabase(
    model_url: str,
    room_id: str,
    timeout: int = 600,  # 10 minutes for large ZIP files (240MB+)
    max_retries: int = 3
) -> Optional[str]:
    """
    Download a 3D model from FAL's temporary URL and upload to Supabase Storage.
    FAL returns a ZIP file containing the GLB model - we extract it before uploading.

    Args:
        model_url: The temporary URL of the generated 3D model (ZIP file from FAL)
        room_id: The room ID for naming the file
        timeout: Request timeout in seconds (increased for large files)
        max_retries: Maximum retry attempts

    Returns:
        The public URL of the uploaded model in Supabase, or None if failed
    """
    if not model_url:
        logger.warning("[Model Storage] No model URL provided")
        return None

    # Download the model file
    try:
        logger.info(f"[Model Storage] Downloading 3D model from {model_url[:100]}...")

        ssl_context = ssl.create_default_context(cafile=certifi.where())

        async with aiohttp.ClientSession() as session:
            async with session.get(
                model_url,
                timeout=aiohttp.ClientTimeout(total=timeout),
                ssl=ssl_context
            ) as resp:
                if resp.status != 200:
                    logger.error(f"[Model Storage] Failed to download: HTTP {resp.status}")
                    return None

                downloaded_data = await resp.read()
                content_type = resp.headers.get('Content-Type', 'application/octet-stream')
                file_size_mb = len(downloaded_data) / (1024 * 1024)

                logger.info(f"[Model Storage] Downloaded {file_size_mb:.2f} MB, type: {content_type}")

        # Check if the downloaded file is a ZIP (FAL hunyuan_world returns ZIP with mesh layers + textures)
        if model_url.endswith('.zip') or downloaded_data[:4] == b'PK\x03\x04':
            logger.info("[Model Storage] File is a ZIP archive from hunyuan_world")
            try:
                with zipfile.ZipFile(io.BytesIO(downloaded_data)) as zf:
                    zip_contents = zf.namelist()
                    logger.info(f"[Model Storage] ZIP contents: {zip_contents}")

                    # Check if it contains the expected hunyuan_world structure (PLY + PNG)
                    has_ply = any(f.endswith('.ply') for f in zip_contents)

                    if has_ply:
                        # Store the full ZIP for complete layered scene with textures
                        model_data = downloaded_data
                        file_ext = 'zip'
                        logger.info(f"[Model Storage] Storing full ZIP ({len(model_data) / 1024 / 1024:.2f} MB)")
                    else:
                        # Try to find GLB
                        glb_files = [f for f in zip_contents if f.endswith('.glb')]
                        if glb_files:
                            model_data = zf.read(glb_files[0])
                            file_ext = 'glb'
                            logger.info(f"[Model Storage] Extracted GLB: {glb_files[0]}")
                        else:
                            logger.error("[Model Storage] No supported 3D files found in ZIP")
                            return None

            except zipfile.BadZipFile as e:
                logger.error(f"[Model Storage] Invalid ZIP file: {str(e)}")
                return None
        else:
            # Direct file (GLB or PLY)
            model_data = downloaded_data
            file_ext = 'glb' if model_url.endswith('.glb') else 'ply'

    except aiohttp.ClientError as e:
        logger.error(f"[Model Storage] Network error downloading model: {str(e)}")
        return None
    except asyncio.TimeoutError:
        logger.error(f"[Model Storage] Timeout downloading model (>{timeout}s)")
        return None
    except Exception as e:
        logger.error(f"[Model Storage] Error downloading model: {str(e)}")
        import traceback
        logger.error(f"[Model Storage] Traceback: {traceback.format_exc()}")
        return None

    # Upload to Supabase with retries
    # Use appropriate extension and MIME type based on file type
    file_path = f"models/{room_id}.{file_ext}"
    content_type_map = {
        'glb': 'model/gltf-binary',
        'ply': 'application/x-ply',
        'zip': 'application/zip'
    }
    content_type = content_type_map.get(file_ext, 'application/octet-stream')

    for attempt in range(max_retries):
        try:
            logger.info(f"[Model Storage] Uploading to Supabase: {file_path} (attempt {attempt + 1}/{max_retries})")
            logger.info(f"[Model Storage] File size: {len(model_data) / 1024 / 1024:.2f} MB")

            # Use dedicated storage client with extended timeout
            supabase = get_storage_client()
            if not supabase:
                logger.error("[Model Storage] Storage client is None")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return None

            # Upload the file (upsert=True allows overwriting if exists)
            response = supabase.storage.from_(MODEL_BUCKET).upload(
                path=file_path,
                file=model_data,
                file_options={
                    "content-type": content_type,
                    "upsert": "true"
                }
            )
            logger.info(f"[Model Storage] Upload response: {response}")

            # Get the public URL with cache-busting parameter
            public_url = supabase.storage.from_(MODEL_BUCKET).get_public_url(file_path)

            # Add cache-busting parameter
            cache_buster = int(time.time())
            if '?' in public_url:
                public_url += f"&v={cache_buster}"
            else:
                public_url += f"?v={cache_buster}"

            logger.info(f"[Model Storage] Successfully uploaded model to Supabase: {public_url}")
            return public_url

        except StorageException as upload_error:
            logger.error(f"[Model Storage] StorageException during upload (attempt {attempt + 1}/{max_retries}):")
            logger.error(f"  - Name: {getattr(upload_error, 'name', 'N/A')}")
            logger.error(f"  - Message: {getattr(upload_error, 'message', str(upload_error))}")
            logger.error(f"  - Code: {getattr(upload_error, 'code', 'N/A')}")
            logger.error(f"  - Status: {getattr(upload_error, 'status', 'N/A')}")

            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            return None

        except Exception as upload_error:
            logger.error(f"[Model Storage] Upload failed (attempt {attempt + 1}/{max_retries}) - Type: {type(upload_error).__name__}, Error: {upload_error}")

            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue

            import traceback
            logger.error(f"[Model Storage] Traceback: {traceback.format_exc()}")
            return None

    # All retries exhausted
    logger.error(f"[Model Storage] Failed to upload after {max_retries} attempts")
    return None


async def delete_model_from_supabase(room_id: str) -> bool:
    """
    Delete a room's 3D model from Supabase Storage.

    Args:
        room_id: The room ID

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        supabase = get_storage_client()
        if not supabase:
            return False

        # Try both .zip and .glb extensions
        deleted = False
        for ext in ['zip', 'glb', 'ply']:
            file_path = f"models/{room_id}.{ext}"
            try:
                supabase.storage.from_(MODEL_BUCKET).remove([file_path])
                logger.info(f"[Model Storage] Deleted model: {file_path}")
                deleted = True
            except Exception:
                pass

        if not deleted:
            logger.warning(f"[Model Storage] No model found to delete for room {room_id}")
        return deleted

    except Exception as e:
        logger.error(f"[Model Storage] Error deleting model from Supabase: {str(e)}")
        return False
