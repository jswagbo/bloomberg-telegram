"""Main FastAPI application"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import time

from app.core.config import settings
from app.core.database import init_db, close_db
from app.core.redis import redis_manager
from app.core.qdrant import qdrant_manager
from app.api import api_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Bloomberg Telegram Signal Intelligence Engine")
    
    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    
    # Initialize Redis
    logger.info("Connecting to Redis...")
    await redis_manager.connect()
    
    # Initialize Qdrant (optional - for vector similarity features)
    try:
        logger.info("Connecting to Qdrant...")
        qdrant_manager.connect()
        await qdrant_manager.init_collection()
        logger.info("Qdrant connected successfully")
    except Exception as e:
        logger.warning(f"Qdrant connection failed: {e}. Vector similarity features will be disabled.")
    
    logger.info("Startup complete!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    
    await close_db()
    await redis_manager.disconnect()
    try:
        qdrant_manager.close()
    except Exception:
        pass  # Qdrant was not connected
    
    logger.info("Shutdown complete!")


# Create FastAPI app
app = FastAPI(
    title="Bloomberg Telegram",
    description="Signal Intelligence Engine for Crypto Telegram Channels",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.app_version,
    }


# Root redirect
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Bloomberg Telegram Signal Intelligence Engine",
        "version": settings.app_version,
        "docs": "/docs",
    }


# Include API routes
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
