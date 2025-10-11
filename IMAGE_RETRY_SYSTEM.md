# Image Upload Retry and Regeneration System

## Overview

This document describes the automatic image retry and regeneration system that handles expired/temporary image URLs.

## Problem

When image uploads to Supabase Storage fail, the system previously fell back to temporary Replicate URLs. These URLs expire quickly (typically within hours), causing 404 errors when players try to view room images later.

## Solution

The system now implements a three-part solution:

### 1. Upload Retry with Exponential Backoff

**File**: `server/app/image_storage.py`

The `upload_image_to_supabase()` function now includes:
- **Retry logic**: Up to 3 upload attempts with exponential backoff (1s, 2s, 4s)
- **Single download**: Image is downloaded once from the temporary URL, then retry logic only applies to the upload step
- **Better error handling**: Detailed logging for each retry attempt

This significantly improves upload success rates for transient network issues or temporary Supabase outages.

### 2. Temporary URL Detection

**File**: `server/app/image_storage.py`

New function `is_temporary_image_url(image_url)` that detects if an image URL is from a temporary provider:
- Checks for `replicate.delivery` domains
- Checks for OpenAI DALL-E temporary URLs
- Returns `True` for temporary URLs, `False` for permanent Supabase URLs

### 3. Automatic Image Regeneration

**File**: `server/app/game_manager.py`

The system now automatically detects and regenerates images with temporary URLs in two scenarios:

#### When Players Enter a Room
- In `handle_room_movement_by_direction()`: When loading a discovered room, checks if it has a temporary URL
- If detected, triggers background image regeneration
- Sets image status to 'pending' and broadcasts update to clients
- Generates a new image based on the room's description and biome

#### During Preload
- In `_preload_single_room()`: When preloading adjacent rooms, checks existing rooms for temporary URLs
- If detected, triggers background image regeneration
- Ensures rooms that failed upload originally get another chance

#### Regeneration Process
New function `_regenerate_room_image()`:
- Builds an image prompt from room description and biome
- Generates a completely new image using the AI provider
- Uploads to Supabase Storage with retry logic
- Updates room data and broadcasts to all clients
- On failure, keeps the temporary URL but marks as 'error'

## Benefits

1. **Resilient Uploads**: Retry logic handles transient failures automatically
2. **Self-Healing**: System automatically fixes expired URLs when rooms are visited
3. **No Manual Intervention**: Old rooms with expired URLs are fixed automatically
4. **Graceful Degradation**: Falls back to temporary URLs if all retries fail, but will retry later
5. **Transparent**: Clients receive real-time updates via WebSocket when images are regenerated

## User Experience

- **First Visit**: If upload fails, player sees temporary URL (may expire later)
- **Subsequent Visits**: System detects expired URL and generates fresh image automatically
- **During Preload**: Nearby rooms with expired images get fixed proactively
- **Real-time Updates**: WebSocket broadcasts notify clients when new images are ready

## Configuration

All retry behavior is configurable:
- `max_retries` parameter in `upload_image_to_supabase()` (default: 3)
- Exponential backoff timing: 2^attempt seconds (1s, 2s, 4s)

## Logging

All retry and regeneration attempts are logged with `[Image Retry]` prefix:
- Initial detection of temporary URLs
- Each retry attempt with attempt number
- Success/failure of regeneration
- Final upload status

## Testing

Run the test suite to verify URL detection:
```bash
cd server
python3 -c "from app.image_storage import is_temporary_image_url; print('Test passed!' if is_temporary_image_url('https://replicate.delivery/test.png') else 'Failed')"
```

## Future Improvements

Potential enhancements:
- Scheduled job to scan all rooms for expired URLs
- Configurable retry intervals
- Metrics tracking for upload success rates
- Admin dashboard to view rooms with expired images

