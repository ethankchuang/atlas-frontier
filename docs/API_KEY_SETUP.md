# API Key Authentication Setup

This document explains the API key authentication system implemented between the client and server.

## How It Works

1. **Server-side validation**: The FastAPI server checks for `X-API-Key` header on all requests (except `/health`)
2. **Next.js proxy routes**: Client requests go through Next.js API routes that add the API key server-side
3. **Hidden from browser**: The API key is never exposed to the client browser - it's only on your servers

## Environment Variables

### Server (Railway/Backend)
```bash
# Optional - if not set, API key authentication is disabled
API_KEY=your_secure_api_key_here
```

### Client (Vercel/Frontend)
```bash
# Required if server has API_KEY set
API_KEY=same_secure_api_key_here
```

## Security Benefits

1. **Client-server authentication**: Prevents unauthorized access to your API
2. **Hidden from browser**: API key never appears in browser dev tools or network requests
3. **Server-to-server**: Only your Next.js app can access your FastAPI backend
4. **Optional**: Can be disabled by not setting the API_KEY environment variable

## Implementation Details

### Server Side (`server/app/api_key_auth.py`)
- Middleware that checks `X-API-Key` header
- Automatically disabled if `API_KEY` environment variable is empty
- Allows health check endpoint to bypass authentication

### Client Side (Next.js API Routes)
- `/api/auth/register` - Proxy for user registration
- `/api/auth/login` - Proxy for user login  
- `/api/game/[...slug]` - Proxy for all game endpoints including streaming

### Modified Client Service
- Auth endpoints now use Next.js API routes
- Game endpoints use the proxy route
- Streaming endpoints properly forwarded with API key

## Deployment Steps

1. **Generate a secure API key**:
   ```bash
   # Generate a random 32-character key
   openssl rand -hex 32
   ```

2. **Set environment variables**:
   - Railway (server): Set `API_KEY=your_generated_key`
   - Vercel (client): Set `API_KEY=your_generated_key`

3. **Deploy both services**

4. **Test the setup**:
   - Try accessing the health endpoint directly: should work
   - Try accessing other endpoints directly: should return 401
   - Use your app normally: should work through the proxy

## Disabling API Key Auth

To disable API key authentication:
1. Remove or leave empty the `API_KEY` environment variable on the server
2. The middleware will automatically disable itself
3. Client proxy routes will still work but won't send the API key header

## Troubleshooting

- **401 errors**: Check that API_KEY is set on both server and client
- **500 errors**: Check server logs for API key validation issues
- **Direct API access blocked**: This is expected - use your frontend app
- **Health check fails**: Health endpoint should always work regardless of API key
