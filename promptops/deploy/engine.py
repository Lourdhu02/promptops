
"""
Deployment Engine - Handles prompt serving and Redis caching
"""
import json
import os
from typing import Optional, Dict, Any

import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


class DeploymentEngine:
    """
    Manages prompt deployments and caching
    
    Architecture:
    - PostgreSQL: Source of truth
    - Redis: Fast serving layer (sub-millisecond)
    - Cache invalidation on deploy/rollback
    """
    
    def __init__(self):
        self.redis_available = False
        self.redis_client = None
        
        try:
            self.redis_client = redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2
            )
            # Test connection
            self.redis_client.ping()
            self.redis_available = True
        except Exception as e:
            print(f"Warning: Redis not available: {e}")
            print("Deployment will work but without caching")
    
    def _get_cache_key(self, environment: str, name: Optional[str] = None) -> str:
        """Generate Redis cache key"""
        if name:
            return f"promptops:prompt:{environment}:{name}"
        return f"promptops:prompt:{environment}:default"
    
    def get_from_cache(
        self,
        environment: str,
        name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch prompt from Redis cache
        Returns None if cache miss or Redis unavailable
        """
        if not self.redis_available:
            return None
        
        try:
            key = self._get_cache_key(environment, name)
            cached = self.redis_client.get(key)
            
            if cached:
                return json.loads(cached)
            
            return None
        except Exception as e:
            print(f"Cache read error: {e}")
            return None
    
    def set_cache(
        self,
        environment: str,
        prompt_data: Dict[str, Any],
        name: Optional[str] = None,
        ttl: int = 3600
    ):
        """Store prompt in Redis cache"""
        if not self.redis_available:
            return
        
        try:
            key = self._get_cache_key(environment, name)
            value = json.dumps(prompt_data, default=str)
            self.redis_client.setex(key, ttl, value)
        except Exception as e:
            print(f"Cache write error: {e}")
    
    def invalidate_cache(self, environment: str):
        """
        Invalidate all cached prompts for an environment
        Called on deploy/rollback
        """
        if not self.redis_available:
            return
        
        try:
            pattern = f"promptops:prompt:{environment}:*"
            keys = self.redis_client.keys(pattern)
            
            if keys:
                self.redis_client.delete(*keys)
                print(f"Invalidated {len(keys)} cache entries for {environment}")
        except Exception as e:
            print(f"Cache invalidation error: {e}")