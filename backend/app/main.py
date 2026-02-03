from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
# Rate limiting temporarily disabled - will be re-enabled later
# from slowapi import Limiter, _rate_limit_exceeded_handler
# from slowapi.util import get_remote_address
# from slowapi.errors import RateLimitExceeded
from app.config import get_settings
from app.routers import chat, webhooks, user
from app.services.error_messages import INTERNAL_SERVER_ERROR, VALIDATION_ERROR, format_error, ErrorCodes
import traceback
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    settings = get_settings()
except Exception as e:
    logging.error(f"Failed to load settings: {e}")
    raise

app = FastAPI(
    title="Chatow API",
    description="AI Chat API with Smart Model Routing",
    version="1.0.0",
    debug=settings.debug,
)

# Rate limiting temporarily disabled - will be re-enabled with proper implementation
# limiter = Limiter(key_func=get_remote_address)
# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to ensure all errors return JSON with user-friendly messages."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    if settings.debug:
        error_detail = {
            "detail": format_error(INTERNAL_SERVER_ERROR),
            "type": type(exc).__name__,
            "traceback": traceback.format_exc(),
            "code": ErrorCodes.INTERNAL_SERVER_ERROR
        }
    else:
        error_detail = {
            "detail": format_error(INTERNAL_SERVER_ERROR),
            "code": ErrorCodes.INTERNAL_SERVER_ERROR
        }
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_detail,
        headers={"X-Error-Code": ErrorCodes.INTERNAL_SERVER_ERROR}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with user-friendly messages."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": format_error(VALIDATION_ERROR),
            "errors": exc.errors(),
            "code": ErrorCodes.VALIDATION_ERROR
        },
        headers={"X-Error-Code": ErrorCodes.VALIDATION_ERROR}
    )

# CORS configuration
# Get allowed origins from environment or use defaults
import os
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else []
# Add default localhost origins for development
default_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
    "https://vion1.vercel.app",
]
# Combine and filter out empty strings
allowed_origins = [origin for origin in allowed_origins + default_origins if origin]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (with rate limiting)
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(user.router, prefix="/api/user", tags=["user"])


@app.get("/")
async def root():
    return {
        "name": "Chatow API",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Enhanced health check endpoint with system status."""
    import time
    from app.services.supabase_client import supabase
    from app.config import get_settings
    
    health_status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "checks": {}
    }
    
    # Check database connection
    try:
        settings = get_settings()
        # Simple query to check DB
        result = supabase.table("profiles").select("id").limit(1).execute()
        health_status["checks"]["database"] = "ok"
    except Exception as e:
        health_status["checks"]["database"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check OpenAI API (simple check)
    try:
        from openai import AsyncOpenAI
        # Just check if key is set, don't make actual API call
        if settings.openai_api_key:
            health_status["checks"]["openai"] = "configured"
        else:
            health_status["checks"]["openai"] = "not_configured"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["checks"]["openai"] = f"error: {str(e)}"
        health_status["status"] = "degraded"
    
    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)
