# Supabase Anonymous Authentication Setup

This document explains how to set up Supabase anonymous authentication for the game.

## Prerequisites

1. You need a Supabase project with authentication enabled
2. Anonymous sign-ins must be enabled in your Supabase project

## Environment Variables

Add these to your client `.env.local` file:

```env
NEXT_PUBLIC_SUPABASE_URL=your_supabase_project_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
```

## Supabase Configuration

1. **Enable Anonymous Sign-ins**:
   - Go to your Supabase dashboard
   - Navigate to Authentication > Settings
   - Enable "Anonymous sign-ins"

2. **Configure RLS Policies** (if needed):
   - Anonymous users will have the `is_anonymous` claim in their JWT
   - You can use this to create different access policies for anonymous vs permanent users

## How It Works

1. **Anonymous Sign-in**: When a user clicks "Play as Guest", the app calls `supabase.auth.signInAnonymously()`
2. **Player Creation**: The anonymous user ID is used to create a guest player on the server
3. **Game Play**: Anonymous users can play the game normally
4. **Conversion**: Users can convert to permanent accounts using the existing conversion modal

## Key Changes Made

### Frontend
- Added Supabase client configuration
- Updated AuthForm to use `supabase.auth.signInAnonymously()`
- Updated GuestConversionModal to use `supabase.auth.updateUser()`
- Modified API service to handle anonymous user IDs

### Backend
- Updated authentication to handle anonymous users
- Modified guest player creation to use Supabase anonymous user IDs
- Updated player ownership checks to work with anonymous users
- Simplified guest-to-user conversion process

## Testing

1. Start the server: `cd server && python -m uvicorn app.main:app --reload`
2. Start the client: `cd client && npm run dev`
3. Click "Play as Guest" to test anonymous sign-in
4. Test the conversion flow by clicking the conversion button

## Benefits

- **Secure**: Uses Supabase's built-in anonymous authentication
- **Persistent**: Anonymous users can maintain sessions across browser refreshes
- **Convertible**: Easy conversion to permanent accounts
- **Scalable**: Leverages Supabase's infrastructure
- **Compliant**: Follows Supabase's recommended patterns
