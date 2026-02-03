"""
Rate limiting service for managing concurrent requests and API limits.
Handles per-user rate limiting and OpenAI API key rotation.
"""
import asyncio
import time
from collections import defaultdict
from typing import Dict, Optional
import logging
from app.config import get_settings
from app.services.error_messages import RATE_LIMIT_EXCEEDED, CONCURRENT_REQUESTS_EXCEEDED, format_error

logger = logging.getLogger(__name__)
settings = get_settings()

# Per-user rate limiting
user_request_counts: Dict[str, list] = defaultdict(list)
user_request_locks: Dict[str, asyncio.Lock] = defaultdict(lambda: asyncio.Lock())

# Concurrent request limiting per user
user_active_requests: Dict[str, int] = defaultdict(int)
user_request_semaphores: Dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(5))  # Max 5 concurrent per user

# Global rate limits
MAX_REQUESTS_PER_MINUTE = 30  # Per user
MAX_CONCURRENT_REQUESTS = 5  # Per user
RATE_LIMIT_WINDOW = 60  # seconds


async def check_rate_limit(user_id: str) -> tuple[bool, Optional[str]]:
    """
    Check if user has exceeded rate limit.
    Returns: (allowed, error_message)
    """
    async with user_request_locks[user_id]:
        now = time.time()
        # Clean old requests outside the window
        user_request_counts[user_id] = [
            req_time for req_time in user_request_counts[user_id]
            if now - req_time < RATE_LIMIT_WINDOW
        ]
        
        current_count = len(user_request_counts[user_id])
        logger.info(f"📊 Rate limit kontrolü - User: {user_id}, Mevcut istek: {current_count}/{MAX_REQUESTS_PER_MINUTE}")
        
        # Check rate limit
        if current_count >= MAX_REQUESTS_PER_MINUTE:
            logger.warning(f"❌ Rate limit aşıldı - User: {user_id}, İstek sayısı: {current_count}/{MAX_REQUESTS_PER_MINUTE}")
            error_msg = format_error(
                RATE_LIMIT_EXCEEDED,
                max_requests=MAX_REQUESTS_PER_MINUTE
            )
            return False, error_msg
        
        # Add current request
        user_request_counts[user_id].append(now)
        logger.info(f"✅ Rate limit kontrolü geçti - User: {user_id}, Yeni toplam: {current_count + 1}/{MAX_REQUESTS_PER_MINUTE}")
        return True, None


async def acquire_request_slot(user_id: str) -> tuple[bool, Optional[str]]:
    """
    Acquire a slot for concurrent request.
    Returns: (success, error_message)
    """
    semaphore = user_request_semaphores[user_id]
    current_active = user_active_requests[user_id]
    
    logger.info(f"🎫 Eşzamanlı istek slotu kontrolü - User: {user_id}, Aktif: {current_active}/{MAX_CONCURRENT_REQUESTS}")
    
    # Try to acquire without blocking
    if semaphore.locked() and current_active >= MAX_CONCURRENT_REQUESTS:
        logger.warning(f"❌ Eşzamanlı istek limiti aşıldı - User: {user_id}, Aktif: {current_active}/{MAX_CONCURRENT_REQUESTS}")
        error_msg = format_error(
            CONCURRENT_REQUESTS_EXCEEDED,
            max_concurrent=MAX_CONCURRENT_REQUESTS
        )
        return False, error_msg
    
    await semaphore.acquire()
    user_active_requests[user_id] += 1
    logger.info(f"✅ Eşzamanlı istek slotu alındı - User: {user_id}, Yeni aktif: {user_active_requests[user_id]}/{MAX_CONCURRENT_REQUESTS}")
    return True, None


async def release_request_slot(user_id: str):
    """Release a concurrent request slot."""
    old_count = user_active_requests[user_id]
    user_active_requests[user_id] = max(0, user_active_requests[user_id] - 1)
    semaphore = user_request_semaphores[user_id]
    semaphore.release()
    logger.info(f"🔓 Eşzamanlı istek slotu serbest bırakıldı - User: {user_id}, Eski: {old_count}, Yeni: {user_active_requests[user_id]}/{MAX_CONCURRENT_REQUESTS}")


def get_user_request_stats(user_id: str) -> dict:
    """Get current request statistics for a user."""
    now = time.time()
    recent_requests = [
        req_time for req_time in user_request_counts[user_id]
        if now - req_time < RATE_LIMIT_WINDOW
    ]
    
    return {
        "requests_in_window": len(recent_requests),
        "max_requests_per_minute": MAX_REQUESTS_PER_MINUTE,
        "active_concurrent_requests": user_active_requests[user_id],
        "max_concurrent_requests": MAX_CONCURRENT_REQUESTS,
    }
