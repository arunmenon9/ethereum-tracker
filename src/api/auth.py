from fastapi import HTTPException, Security, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from datetime import datetime
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.database import database

settings = get_settings()
logger = logging.getLogger(__name__)

security = HTTPBearer()

async def verify_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """Verify API key authentication"""
    api_key = credentials.credentials
    
    # Simple API key validation (in production, use more sophisticated validation)
    if api_key != settings.API_KEY:
        logger.warning(f"Invalid API key attempt from {request.client.host}")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    
    return api_key

def setup_auth_middleware(app):
    """Setup authentication middleware"""
    
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        # Skip auth for health check and docs
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            response = await call_next(request)
            return response
        
        # Check for API key in protected routes
        if request.url.path.startswith("/api/"):
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JSONResponse(
                    status_code=401,
                    content={"error": True, "message": "API key required"}
                )
        
        response = await call_next(request)
        return response