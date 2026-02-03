from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
from typing import List
import os


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_service_key: str  # Service role key for backend operations
    supabase_jwt_secret: str
    
    # OpenAI
    openai_api_key: str
    openai_api_key_extra: str = ""  # Additional API keys for rotation (comma-separated in env, e.g., "key1,key2,key3")
    
    # Model Configuration
    simple_model: str = "gpt-4o-mini"
    complex_model: str = "gpt-4o"  # Default complex model (can be overridden to gpt-5.2-preview)
    # Note: GPT-5.2 is available via API. To use it, set COMPLEX_MODEL=gpt-5.2-preview in .env
    # If gpt-5.2-preview is not available, the system will automatically fallback to gpt-4o
    
    # Credit costs
    simple_model_cost: float = 1.0
    complex_model_cost: float = 20.0  # Adjust if using GPT-5.2 (typically higher cost)
    
    # Lemon Squeezy
    lemon_squeezy_webhook_secret: str = ""
    
    # App settings
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    try:
        return Settings()
    except Exception as e:
        missing_vars = []
        required_vars = ["supabase_url", "supabase_service_key", "supabase_jwt_secret", "openai_api_key"]
        for var in required_vars:
            if not os.getenv(var.upper()):
                missing_vars.append(var.upper())
        
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}. "
                f"Please check your .env file."
            ) from e
        raise
