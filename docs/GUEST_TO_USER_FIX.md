# Guest-to-User Conversion Fix

## Problem
When a guest user converted their anonymous account to a registered account (from guest menu → login), the user profile was not being created in Supabase's `user_profiles` table. This caused login failures on new browser tabs because the login endpoint couldn't find the user profile.

## Root Cause
The `/auth/guest-to-user` endpoint in `server/app/main.py` was only:
1. Updating the guest player's `user_id` field
2. NOT creating a user profile in the `user_profiles` table

When the user tried to log in later, the `login_user()` function in `auth_service.py` would fail because it tried to fetch the user profile from the `user_profiles` table (lines 130-136).

## Solution
Updated the `/auth/guest-to-user` endpoint in `server/app/main.py` (lines 899-971) to:

1. **Validate username format** - Ensures username meets requirements (3-20 chars, starts with letter, etc.)
2. **Check username availability** - Prevents duplicate usernames (case-insensitive)
3. **Create user profile in Supabase** - This was the missing critical step!
4. **Update guest player** - Updates both `user_id` and `name` fields
5. **Proper error handling** - Returns appropriate HTTP errors for validation failures

### Code Changes

#### Added Imports
```python
from .auth_utils import get_current_user, get_optional_current_user, validate_username, is_username_available
from .supabase_client import get_supabase_client
```

#### Updated Endpoint Logic
The endpoint now creates the user profile:

```python
# Create user profile in Supabase
# This is crucial - without this, the user can't log in later!
supabase = get_supabase_client()
profile_data = {
    'id': request.new_user_id,
    'username': request.username.lower(),  # Store as lowercase for consistency
    'email': request.email
}

profile_result = supabase.table('user_profiles').insert(profile_data).execute()

if not profile_result.data:
    logger.error(f"Failed to create user profile: {profile_result}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to create user profile"
    )
```

## Testing Instructions

To verify the fix works:

1. **Start as Guest**:
   - Open the app
   - Click "Play as Guest"
   - Play for a bit to create some progress

2. **Convert to User**:
   - Open the pause menu (ESC)
   - Click "Create Account"
   - Fill in email, password, and username
   - Submit the form

3. **Verify Conversion**:
   - You should see a success message
   - Your guest player data should be preserved

4. **Test Login on New Tab**:
   - Open a new browser tab (or incognito window)
   - Go to the app
   - Click "Login"
   - Enter the email and password you just created
   - **You should now be able to log in successfully!**

5. **Verify Player Data**:
   - After logging in, check that your inventory and progress were preserved
   - Your character should have the same stats as before conversion

## Flow Diagram

### Before Fix ❌
```
Guest User → Convert Account → supabase.auth.updateUser() ✓
                             → Backend updates player.user_id ✓
                             → Backend SKIPS user_profiles creation ✗
New Tab → Login → Backend looks for user_profiles entry ✗
                → NOT FOUND → Login Fails ✗
```

### After Fix ✅
```
Guest User → Convert Account → supabase.auth.updateUser() ✓
                             → Backend validates username ✓
                             → Backend checks availability ✓
                             → Backend CREATES user_profiles entry ✓
                             → Backend updates player.user_id ✓
New Tab → Login → Backend finds user_profiles entry ✓
                → Returns user data & token ✓
                → Login Succeeds ✓
```

## Related Files
- `server/app/main.py` - Updated `/auth/guest-to-user` endpoint
- `server/app/auth_service.py` - Contains `login_user()` that requires user profile
- `server/app/auth_utils.py` - Contains validation utilities
- `client/src/components/GuestConversionModal.tsx` - Client-side conversion UI
- `client/src/services/api.ts` - API service for guest conversion

## Notes
- User profiles are stored with lowercase usernames for consistency
- The endpoint now has proper validation to match the registration endpoint
- Guest players are automatically updated with the new username
- This fix aligns the guest-to-user conversion with the standard registration flow

