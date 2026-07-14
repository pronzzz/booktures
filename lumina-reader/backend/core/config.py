from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Lumina-Reader"
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str = "sqlite:///./lumina.db"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # API Keys
    OPENAI_API_KEY: str
    STABILITY_API_KEY: str
    
    # Feature Flags
    USE_LOCAL_SDXL: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
