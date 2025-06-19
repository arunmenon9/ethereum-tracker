from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from contextlib import asynccontextmanager
import logging
import time
from datetime import datetime

from src.config import get_settings
from src.database import database, engine, Base
from src.cache import redis_client

from src.api.transactions import router as transactions_router
from src.api.exports import router as exports_router
from src.api.analytics import router as analytics_router
from src.api.cache import router as cache_router
from src.api.report import router as reports_router

from src.api.auth import setup_auth_middleware
from src.utils.logging import setup_logging

settings = get_settings()
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Ethereum Transaction Tracker")
    await database.connect()
    
    # Tables are already created by Docker init script
    # Just verify connection works
    try:
        await database.fetch_one("SELECT 1")
        logger.info("Database connection verified")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Ethereum Transaction Tracker")
    await database.disconnect()
    if redis_client:
        await redis_client.close()

app = FastAPI(
    title="Ethereum Transaction Tracker",
    description="Production-ready API for tracking Ethereum transactions",
    version="1.0.0",
    lifespan=lifespan
)

# Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Request logging middleware
# Update the existing request logging middleware in main.py

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Extract wallet address from path if present
    wallet_address = None
    path_parts = request.url.path.split('/')
    
    # Handle different endpoint patterns
    for i, part in enumerate(path_parts):
        if part == "transactions" and i + 1 < len(path_parts):
            potential_address = path_parts[i + 1]
            if potential_address.startswith("0x") and len(potential_address) == 42:
                wallet_address = potential_address.lower()
                break
        elif part == "exports" and i + 1 < len(path_parts):
            potential_address = path_parts[i + 1]
            if potential_address.startswith("0x") and len(potential_address) == 42:
                wallet_address = potential_address.lower()
                break
        elif part == "reports" and i + 1 < len(path_parts):
            if i + 2 < len(path_parts):
                potential_address = path_parts[i + 2]
                if potential_address.startswith("0x") and len(potential_address) == 42:
                    wallet_address = potential_address.lower()
                    break
    
    # Also check for wallet_address in request body for POST requests
    if not wallet_address and request.method == "POST":
        try:
            # Read the request body without consuming it
            body = await request.body()
            if body:
                # Reset the body for the actual endpoint to consume
                request._body = body
                
                import json
                body_data = json.loads(body.decode())
                if "wallet_address" in body_data:
                    wallet_address = body_data["wallet_address"].lower()
        except (json.JSONDecodeError, UnicodeDecodeError, KeyError):
            pass  # If we can't parse the body, continue without wallet_address
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response_time_ms = int(process_time * 1000)
    
    # Log to database if this is an API endpoint
    if request.url.path.startswith("/api/v1") and wallet_address:
        try:
            # Determine endpoint name
            endpoint = "unknown"
            if "/transactions/" in request.url.path:
                if request.url.path.endswith("/summary"):
                    endpoint = "get_transaction_summary"
                else:
                    endpoint = "get_transactions"
            elif "/exports/" in request.url.path:
                endpoint = "csv_export"
            elif "/reports/" in request.url.path:
                if "/generate" in request.url.path:
                    endpoint = "generate_report"
                elif "/status/" in request.url.path:
                    endpoint = "get_report_status"
                elif "/download/" in request.url.path:
                    endpoint = "download_report"
                elif "/clear/" in request.url.path:
                    endpoint = "clear_report"
                else:
                    endpoint = "reports_endpoint"
            
            # Get client IP
            client_ip = request.client.host
            if "x-forwarded-for" in request.headers:
                client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
            
            # Insert usage record
            query = """
                INSERT INTO api_usage 
                (wallet_address, endpoint, request_timestamp, response_time_ms, status_code, ip_address)
                VALUES (:wallet_address, :endpoint, :timestamp, :response_time_ms, :status_code, :ip_address)
            """
            values = {
                "wallet_address": wallet_address,
                "endpoint": endpoint,
                "timestamp": datetime.utcnow(),
                "response_time_ms": response_time_ms,
                "status_code": response.status_code,
                "ip_address": client_ip
            }
            await database.execute(query, values)
        except Exception as e:
            logger.warning(f"Failed to log API usage: {e}")
    
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )
    
    return response
# Setup authentication
setup_auth_middleware(app)

# Include routers
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(exports_router, prefix="/api/v1")
app.include_router(cache_router, prefix="/api/v1")
app.include_router(analytics_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1") 

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database
        await database.fetch_one("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Check Redis
    redis_status = "healthy"
    if redis_client:
        try:
            await redis_client.ping()
        except Exception as e:
            redis_status = f"unhealthy: {str(e)}"
    else:
        redis_status = "not configured"
    
    return {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": db_status,
            "redis": redis_status
        }
    }

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path)
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Custom handler for Pydantic validation errors"""
    
    errors = []
    for error in exc.errors():
        # Extract field name and error details
        field_name = ".".join(str(loc) for loc in error["loc"])
        error_type = error["type"]
        error_msg = error["msg"]
        
        # Custom messages for common validation errors
        if error_type == "string_pattern_mismatch" and "wallet_address" in field_name:
            custom_error = {
                "field": field_name,
                "error": "Invalid Ethereum address format",
                "message": "Ethereum address must be exactly 42 characters long (0x followed by 40 hexadecimal characters)",
                "provided_value": error.get("input", ""),
                "example": "0x742d35Cc63aB4747B8bc21bB6c2d65bb0E4e8b5d"
            }
        else:
            custom_error = {
                "field": field_name,
                "error": error_type,
                "message": error_msg,
                "provided_value": error.get("input", "")
            }
        
        errors.append(custom_error)
    
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "type": "validation_error",
            "message": "Request validation failed",
            "details": errors,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path)
        }
    )

@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    """Custom handler for direct Pydantic validation errors"""
    
    errors = []
    for error in exc.errors():
        field_name = ".".join(str(loc) for loc in error["loc"])
        errors.append({
            "field": field_name,
            "error": error["type"],
            "message": error["msg"],
            "provided_value": error.get("input", "")
        })
    
    return JSONResponse(
        status_code=400,
        content={
            "error": True,
            "type": "validation_error", 
            "message": "Data validation failed",
            "details": errors,
            "timestamp": datetime.utcnow().isoformat(),
            "path": str(request.url.path)
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )