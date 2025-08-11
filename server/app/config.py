from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    # API Keys and External Services
    OPENAI_API_KEY: str = ""
    REPLICATE_API_TOKEN: str = ""
    REDIS_URL: str = "redis://localhost:6379"
    
    # Supabase Settings
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # Game Settings
    DEFAULT_WORLD_SEED: str = "fantasy_world_v1"
    MAX_PLAYERS_PER_ROOM: int = 10
    IMAGE_GENERATION_ENABLED: bool = True
    IMAGE_PROVIDER: str = "replicate"  # "openai" or "replicate"
    
    # Replicate Settings - Black Forest Labs Flux Schnell
    REPLICATE_MODEL: str = "black-forest-labs/flux-schnell"  # Flux Schnell model
    REPLICATE_IMAGE_WIDTH: int = 1024
    REPLICATE_IMAGE_HEIGHT: int = 576  # 16:9 aspect ratio (landscape)

    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = "your-secret-key-here"  # Change this in production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database Settings
    CHROMA_PERSIST_DIRECTORY: str = "./data/chroma"
    CHROMA_ALLOW_RESET: bool = True  # Allow resetting ChromaDB collections
    CHROMA_TELEMETRY_ENABLED: bool = False  # Disable ChromaDB telemetry

    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

# Create a settings instance
settings = get_settings()