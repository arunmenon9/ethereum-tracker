import redis.asyncio as redis
import json
import logging
from typing import Optional, Any
from src.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# Redis client
redis_client = None
if settings.REDIS_URL:
    redis_client = redis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        health_check_interval=30
    )

class CacheManager:
    def __init__(self):
        self.client = redis_client
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.client:
            return None
        
        try:
            value = await self.client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning(f"Cache get error for key {key}: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache with TTL"""
        if not self.client:
            return False
        
        try:
            serialized_value = json.dumps(value, default=str)
            await self.client.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.warning(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        if not self.client:
            return False
        
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error for key {key}: {e}")
            return False
    
    def get_cache_key(self, prefix: str, *args) -> str:
        """Generate cache key"""
        return f"{prefix}:{':'.join(str(arg) for arg in args)}"
    

    async def clear_all(self) -> bool:
        """Clear all cache entries"""
        if not self.client:
            return False
        
        try:
            await self.client.flushdb()
            logger.info("All cache entries cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to clear all cache: {e}")
            return False

cache_manager = CacheManager()