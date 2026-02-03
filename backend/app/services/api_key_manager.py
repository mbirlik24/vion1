"""
OpenAI API Key Manager with rotation and rate limit handling.
Supports multiple API keys for load balancing and rate limit management.
"""
import asyncio
import time
from typing import List, Optional, Dict
from collections import defaultdict
import logging
from openai import AsyncOpenAI, RateLimitError, APIError
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# API Key pool management
class APIKeyPool:
    def __init__(self):
        self.keys: List[str] = []
        self.key_stats: Dict[str, dict] = {}  # Track usage, errors, rate limits per key
        self.current_index = 0
        self.lock = asyncio.Lock()
        self._initialize_keys()
    
    def _initialize_keys(self):
        """Initialize API keys from environment."""
        # Primary key from settings
        primary_key = settings.openai_api_key
        if primary_key:
            self.keys.append(primary_key)
            self.key_stats[primary_key] = {
                "usage_count": 0,
                "error_count": 0,
                "rate_limit_count": 0,
                "last_used": 0,
                "last_error": None,
                "is_active": True,
            }
        
        # Additional keys from environment (comma-separated)
        additional_keys_str = getattr(settings, 'openai_api_key_extra', '') or ''
        additional_keys = [k.strip() for k in additional_keys_str.split(',') if k.strip()] if additional_keys_str else []
        for key in additional_keys:
            if key and key not in self.keys:
                self.keys.append(key)
                self.key_stats[key] = {
                    "usage_count": 0,
                    "error_count": 0,
                    "rate_limit_count": 0,
                    "last_used": 0,
                    "last_error": None,
                    "is_active": True,
                }
        
        logger.info(f"Initialized API key pool with {len(self.keys)} key(s)")
    
    async def get_key(self) -> Optional[str]:
        """Get the best available API key using round-robin with health checks."""
        async with self.lock:
            if not self.keys:
                return None
            
            # Find active keys
            active_keys = [
                key for key in self.keys
                if self.key_stats[key]["is_active"]
            ]
            
            if not active_keys:
                # All keys are inactive, reset them
                logger.warning("All API keys are inactive, resetting...")
                for key in self.keys:
                    self.key_stats[key]["is_active"] = True
                active_keys = self.keys
            
            # Round-robin selection
            if active_keys:
                key = active_keys[self.current_index % len(active_keys)]
                self.current_index += 1
                self.key_stats[key]["usage_count"] += 1
                self.key_stats[key]["last_used"] = time.time()
                return key
            
            return None
    
    async def mark_key_error(self, key: str, error: Exception):
        """Mark a key as having an error."""
        async with self.lock:
            if key in self.key_stats:
                self.key_stats[key]["error_count"] += 1
                self.key_stats[key]["last_error"] = str(error)
                
                # If rate limit error, temporarily disable the key
                if isinstance(error, RateLimitError):
                    self.key_stats[key]["rate_limit_count"] += 1
                    self.key_stats[key]["is_active"] = False
                    logger.warning(f"API key rate limited, temporarily disabled. Key: {key[:10]}...")
                    
                    # Re-enable after 60 seconds
                    asyncio.create_task(self._reenable_key_after_delay(key, 60))
                elif isinstance(error, APIError) and "429" in str(error):
                    # HTTP 429 - Too Many Requests
                    self.key_stats[key]["rate_limit_count"] += 1
                    self.key_stats[key]["is_active"] = False
                    logger.warning(f"API key rate limited (429), temporarily disabled. Key: {key[:10]}...")
                    asyncio.create_task(self._reenable_key_after_delay(key, 60))
    
    async def _reenable_key_after_delay(self, key: str, delay: int):
        """Re-enable a key after a delay."""
        await asyncio.sleep(delay)
        async with self.lock:
            if key in self.key_stats:
                self.key_stats[key]["is_active"] = True
                logger.info(f"API key re-enabled: {key[:10]}...")
    
    def get_stats(self) -> Dict:
        """Get statistics about API key usage."""
        return {
            "total_keys": len(self.keys),
            "active_keys": sum(1 for stats in self.key_stats.values() if stats["is_active"]),
            "key_details": {
                key[:10] + "...": {
                    "usage_count": stats["usage_count"],
                    "error_count": stats["error_count"],
                    "rate_limit_count": stats["rate_limit_count"],
                    "is_active": stats["is_active"],
                }
                for key, stats in self.key_stats.items()
            }
        }


# Global API key pool
api_key_pool = APIKeyPool()


def get_openai_client() -> AsyncOpenAI:
    """Get an OpenAI client with a key from the pool."""
    # For now, use the primary key. In production, use key rotation.
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def get_openai_client_with_rotation() -> tuple[AsyncOpenAI, str]:
    """
    Get an OpenAI client with automatic key rotation.
    Returns: (client, key_used)
    """
    key = await api_key_pool.get_key()
    if not key:
        raise Exception("No available API keys in pool")
    
    return AsyncOpenAI(api_key=key), key


async def handle_openai_error(error: Exception, key_used: Optional[str] = None):
    """Handle OpenAI API errors and update key pool."""
    if key_used:
        await api_key_pool.mark_key_error(key_used, error)
