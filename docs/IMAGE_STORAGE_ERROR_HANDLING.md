# Image Storage Error Handling Improvements

## Problem
The image upload to Supabase Storage was failing with blank error messages in the logs:
```
ERROR:app.image_storage:[upload_image_to_supabase] [Image Storage] Error uploading image to Supabase: 
```

## Root Cause
The `StorageException` class from the `storage3` library doesn't convert properly to string using `str()`. The exception object has structured attributes (`name`, `message`, `code`, `status`) that need to be accessed directly via `getattr()`.

## Solution Applied

### 1. Enhanced Error Handling in `image_storage.py`
- Added explicit import of `StorageException` from `storage3.utils`
- Added specific exception handler for `StorageException` before the generic exception handler
- Improved error logging to extract and display all error attributes:
  - Name
  - Message
  - Code
  - Status
- Added detailed traceback logging for non-storage exceptions

### 2. Improved Upload Function
- Added null check for Supabase client
- Added nested try-catch specifically around the upload call
- Added logging of successful upload responses

### 3. Created Diagnostic Tool
Created `test_storage_connection.py` to:
- Verify Supabase configuration
- Test database connection
- Test storage bucket accessibility
- Test upload capability with actual image data
- List available storage buckets

## Test Results
All tests passed successfully:
- ✓ Supabase client initialization
- ✓ Database connection
- ✓ Storage bucket accessibility
- ✓ Image upload (PNG format)
- ✓ File cleanup

## Next Steps
With the improved error handling in place, if image uploads fail in the future, you will now see detailed error information including:
- The specific error type
- The error message
- The error code
- The HTTP status code
- Full traceback

This will make it much easier to diagnose and fix any future issues.

## Usage

### Run Diagnostic Test
```bash
cd /Users/ethanchuang/Projects/worlds/server
python3 test_storage_connection.py
```

### Check Server Logs
Look for detailed error messages in the format:
```
[Image Storage] StorageException uploading image to Supabase:
  - Name: [error name]
  - Message: [detailed message]
  - Code: [error code]
  - Status: [HTTP status]
```

## Common Issues and Solutions

### Issue: Bucket Not Found
**Error**: `Bucket not found`  
**Solution**: Create the bucket in Supabase dashboard or ensure `STORAGE_BUCKET` name matches

### Issue: Permission Denied
**Error**: `Permission denied` or `Unauthorized`  
**Solution**: Check that `SUPABASE_SERVICE_ROLE_KEY` is set correctly

### Issue: Unsupported MIME Type
**Error**: `mime type X is not supported`  
**Solution**: Check bucket settings in Supabase dashboard to allow the required MIME types (image/png, image/jpeg, image/webp)

### Issue: File Size Limit
**Error**: `File size limit exceeded`  
**Solution**: Check bucket size limits in Supabase dashboard and adjust if needed

