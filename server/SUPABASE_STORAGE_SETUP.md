# Supabase Storage Setup for Room Images

This guide explains how to set up Supabase Storage for storing AI-generated room images.

## Overview

After generating images using Replicate or OpenAI, the server automatically uploads them to Supabase Storage for permanent storage. This prevents images from expiring (which happens with temporary URLs from AI providers).

## Setup Instructions

### 1. Create Storage Bucket

1. Go to your Supabase Dashboard
2. Navigate to **Storage** in the left sidebar
3. Click **New Bucket**
4. Configure the bucket:
   - **Name**: `room-images`
   - **Public bucket**: ✅ Enable (so images can be accessed via public URLs)
   - **File size limit**: Set to at least 10 MB (AI images are typically 1-5 MB)
   - **Allowed MIME types**: `image/webp`, `image/jpeg`, `image/png`

### 2. Set Storage Policies (Optional but Recommended)

If you want more control, you can set up Row Level Security (RLS) policies:

#### Policy 1: Allow Public Read Access
```sql
CREATE POLICY "Public read access for room images"
ON storage.objects FOR SELECT
USING (bucket_id = 'room-images');
```

#### Policy 2: Allow Authenticated Uploads
```sql
CREATE POLICY "Allow authenticated uploads"
ON storage.objects FOR INSERT
WITH CHECK (
  bucket_id = 'room-images'
  AND auth.role() = 'authenticated'
);
```

#### Policy 3: Allow Service Role Full Access
```sql
CREATE POLICY "Service role full access"
ON storage.objects FOR ALL
USING (
  bucket_id = 'room-images'
  AND auth.role() = 'service_role'
);
```

### 3. Verify Setup

The server will automatically use the `room-images` bucket when uploading images. You can verify it's working by:

1. Generating a new room with image generation enabled
2. Checking the Storage dashboard to see the uploaded image
3. The image URL stored in the database should look like:
   ```
   https://[your-project].supabase.co/storage/v1/object/public/room-images/rooms/[room-id].webp
   ```

## How It Works

### Image Upload Flow

1. **Generate Image**: AI provider (Replicate/OpenAI) generates image → returns temporary URL
2. **Download Image**: Server downloads image from temporary URL
3. **Upload to Supabase**: Server uploads to `room-images/rooms/{room_id}.{ext}`
4. **Get Public URL**: Supabase returns permanent public URL
5. **Store URL**: Server saves public URL in room data

### Code Reference

- **Image Storage Module**: `server/app/image_storage.py`
- **AI Handler Integration**: `server/app/ai_handler.py` (line 76-113)
- **Game Manager Integration**: `server/app/game_manager.py` (lines 1285, 1325)

### File Organization

Images are stored with the following structure:
```
room-images/
└── rooms/
    ├── room_abc123.webp
    ├── room_def456.jpg
    └── room_ghi789.png
```

## Troubleshooting

### Images Not Uploading

1. **Check Supabase credentials**: Ensure `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set in `.env`
2. **Check bucket exists**: Verify `room-images` bucket exists in Supabase Storage
3. **Check bucket is public**: Make sure the bucket has public access enabled
4. **Check logs**: Look for `[Image Storage]` log entries for detailed error messages

### Images Uploading but Not Accessible

1. **Check bucket permissions**: Ensure public read access is enabled
2. **Check CORS settings**: If accessing from browser, ensure CORS is configured properly
3. **Check file paths**: URLs should be: `/storage/v1/object/public/room-images/rooms/...`

### Migration from Local Storage

If you have existing rooms with local file URLs (`/static/room_*.webp`), you'll need to:

1. Re-generate the room images, or
2. Manually upload the local files to Supabase Storage and update the database

## Security Considerations

- **Public bucket**: Images are publicly accessible via URL (suitable for game content)
- **Service role key**: Used server-side only, never exposed to client
- **File size limits**: Consider setting reasonable limits to prevent abuse
- **Rate limiting**: Consider implementing rate limits on image generation

## Benefits

✅ **No expiration**: Images are permanently stored
✅ **Scalable**: Supabase Storage handles CDN and scaling
✅ **Reliable**: No dependency on temporary URLs from AI providers
✅ **Cost-effective**: Supabase Storage is included in free tier (up to 1 GB)
✅ **Fast**: CDN-backed for quick global access