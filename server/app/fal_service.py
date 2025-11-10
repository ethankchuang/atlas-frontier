"""
FAL AI service for 3D model generation using hunyuan_world model.
Uses polling (not webhooks) to check job completion.
"""
import logging
import os
from typing import Optional, Dict, Any, Tuple
from .config import settings
from .logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class FALService:
    """Service for generating 3D models from images using FAL AI"""

    @staticmethod
    async def submit_3d_generation(image_url: str, room_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Submit a 3D generation job to FAL AI.

        Args:
            image_url: Public URL of the room image
            room_id: Room ID for logging

        Returns:
            Tuple of (request_id, error_message)
            request_id is None if submission failed
        """
        if not settings.FAL_KEY:
            logger.warning("[FAL] FAL_KEY not configured")
            return None, "FAL_KEY not configured"

        if not settings.MODEL_3D_GENERATION_ENABLED:
            logger.info("[FAL] 3D generation is disabled")
            return None, "3D generation disabled"

        try:
            import fal_client
            os.environ["FAL_KEY"] = settings.FAL_KEY

            logger.info(f"[FAL] Submitting 3D generation for room {room_id}")
            logger.info(f"[FAL] Image URL: {image_url[:100]}...")

            # Submit async job using queue mode
            # export_drc=True enables Draco compression for smaller GLB files
            handler = fal_client.submit(
                settings.FAL_MODEL,
                arguments={
                    "image_url": image_url,
                    "labels_fg1": "trees, rocks, structures, buildings",
                    "labels_fg2": "paths, water, details, ground",
                    "classes": "nature, landscape",
                    "export_drc": True
                }
            )

            request_id = handler.request_id
            logger.info(f"[FAL] Job submitted for room {room_id}, request_id: {request_id}")
            return request_id, None

        except Exception as e:
            logger.error(f"[FAL] Error submitting job for room {room_id}: {str(e)}")
            import traceback
            logger.error(f"[FAL] Traceback: {traceback.format_exc()}")
            return None, str(e)

    @staticmethod
    async def poll_job_status(request_id: str) -> Dict[str, Any]:
        """
        Poll the status of a FAL job.

        Args:
            request_id: The FAL request ID

        Returns:
            Dict with 'status' ('queued', 'in_progress', 'completed', 'failed')
            and optionally 'result_url' (the world_file URL) or 'error'
        """
        if not settings.FAL_KEY:
            return {"status": "failed", "error": "FAL_KEY not configured"}

        try:
            import fal_client
            os.environ["FAL_KEY"] = settings.FAL_KEY

            # Check the status of the job
            status = fal_client.status(settings.FAL_MODEL, request_id, with_logs=False)

            logger.debug(f"[FAL] Status for {request_id}: {status}")

            # Check if completed
            if isinstance(status, fal_client.Completed):
                # Get the result
                result = fal_client.result(settings.FAL_MODEL, request_id)
                world_file = result.get("world_file", {})
                result_url = world_file.get("url")
                file_size = world_file.get("file_size", 0)

                logger.info(f"[FAL] Job {request_id} completed, file size: {file_size} bytes")
                return {
                    "status": "completed",
                    "result_url": result_url,
                    "file_size": file_size
                }
            elif isinstance(status, fal_client.InProgress):
                return {"status": "in_progress"}
            elif isinstance(status, fal_client.Queued):
                position = getattr(status, 'position', 0)
                return {"status": "queued", "position": position}
            else:
                # Unknown status type - might be a dict or have error info
                if hasattr(status, 'error'):
                    return {"status": "failed", "error": str(status.error)}
                return {"status": "unknown", "raw_status": str(status)}

        except Exception as e:
            logger.error(f"[FAL] Error polling job {request_id}: {str(e)}")
            import traceback
            logger.error(f"[FAL] Traceback: {traceback.format_exc()}")
            return {"status": "failed", "error": str(e)}

    @staticmethod
    async def cancel_job(request_id: str) -> bool:
        """
        Cancel a pending FAL job.

        Args:
            request_id: The FAL request ID to cancel

        Returns:
            True if cancellation was successful
        """
        if not settings.FAL_KEY:
            return False

        try:
            import fal_client
            os.environ["FAL_KEY"] = settings.FAL_KEY

            fal_client.cancel(settings.FAL_MODEL, request_id)
            logger.info(f"[FAL] Cancelled job {request_id}")
            return True

        except Exception as e:
            logger.error(f"[FAL] Error cancelling job {request_id}: {str(e)}")
            return False
