# Railway Deployment Guide

This guide explains how to deploy the Worlds Game Server to Railway using Nixpacks.

## Prerequisites

1. A Railway account (https://railway.app)
2. Git repository with your code
3. Required external services:
   - Supabase database
   - Redis instance (can be added as Railway service)

## Files Added for Deployment

### `nixpacks.toml`
Configures the Nixpacks build process:
- Sets up Python 3.9 environment
- Installs system dependencies (gcc, pkg-config)
- Installs Python dependencies
- Configures the start command

### `Procfile`
Backup process definition for Railway.

### `railway.json`
Railway-specific configuration:
- Specifies Nixpacks as the builder
- Sets up health checks on `/health` endpoint
- Configures restart policies

### `.env.example`
Template for required environment variables.

## Deployment Steps

### 1. Connect Repository to Railway

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository
5. Select the `server` directory as the root

### 2. Add Redis Service (Optional)

If you need Redis:
1. In your Railway project, click "New Service"
2. Select "Redis"
3. Railway will automatically provide Redis connection variables

### 3. Configure Environment Variables

Set these environment variables in Railway:

#### Required Variables:
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_ANON_KEY`: Your Supabase anonymous key
- `JWT_SECRET_KEY`: A secure random string for JWT signing

#### Optional Variables:
- `OPENAI_API_KEY`: If using OpenAI features
- `ANTHROPIC_API_KEY`: If using Anthropic features
- `REDIS_HOST`: Auto-provided if using Railway Redis
- `REDIS_PORT`: Auto-provided if using Railway Redis
- `REDIS_DB`: Database number (default: 0)

### 4. Deploy

1. Push your code to the connected repository
2. Railway will automatically detect the `nixpacks.toml` and build
3. The service will start using the command in `nixpacks.toml`

## Health Checks

The server includes a health check endpoint at `/health` that Railway will use to monitor the service.

## Troubleshooting

### Build Issues
- Check the build logs in Railway dashboard
- Ensure all dependencies are listed in `requirements.txt`
- Verify Python version compatibility

### Runtime Issues
- Check the deployment logs
- Verify all environment variables are set
- Test the health endpoint: `https://your-app.railway.app/health`

### Database Connection Issues
- Verify Supabase URL and key are correct
- Check network connectivity between Railway and Supabase

## Production Considerations

1. **Security**:
   - Use strong JWT secret keys
   - Configure CORS properly in production
   - Use environment-specific Supabase keys

2. **Performance**:
   - Consider using Railway's Redis for caching
   - Monitor resource usage and scale as needed

3. **Monitoring**:
   - Set up logging and monitoring
   - Use Railway's built-in metrics
   - Implement proper error handling

## Local Development

To run locally:
```bash
cd server
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
uvicorn app.main:app --reload
```

## Support

- Railway Docs: https://docs.railway.app
- FastAPI Docs: https://fastapi.tiangolo.com
- Nixpacks Docs: https://nixpacks.com
