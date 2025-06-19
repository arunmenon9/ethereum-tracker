# src/api/cache.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
import logging
from datetime import datetime
from src.cache import cache_manager
from src.api.auth import verify_api_key

router = APIRouter(prefix="/cache", tags=["cache"])
logger = logging.getLogger(__name__)

@router.delete("/clear")
async def clear_all_cache(
    api_key: str = Depends(verify_api_key)
):
    """
    Clear all cache entries
    
    This endpoint clears all cached data including:
    - Transaction data
    - Block data
    - API response caches
    - All other cached entries
    
    **Warning**: This will force fresh API calls for all subsequent requests
    until data is cached again.
    """
    try:
        success = await cache_manager.clear_all()
        if success:
            return {
                "success": True,
                "message": "All cache entries cleared successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            return {
                "success": False,
                "message": "Cache clearing failed - Redis may be unavailable",
                "timestamp": datetime.utcnow().isoformat()
            }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )