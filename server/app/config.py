from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    # API Keys and External Services
    OPENAI_API_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379"

    # Game Settings
    DEFAULT_WORLD_SEED: str = "fantasy_world_v1"
    MAX_PLAYERS_PER_ROOM: int = 10
    IMAGE_GENERATION_ENABLED: bool = True

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