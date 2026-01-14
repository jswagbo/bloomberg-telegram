"""Main FastAPI application"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import time
import sys
import traceback

# Early logging setup
print("[DEBUG] main.py: Starting imports...", flush=True)

try:
    print("[DEBUG] main.py: Importing config...", flush=True)
    from app.core.config import settings
    print(f"[DEBUG] main.py: Config loaded, app_version={settings.app_version}", flush=True)
except Exception as e:
    print(f"[ERROR] main.py: Failed to import config: {e}", flush=True)
    traceback.print_exc()
    raise

try:
    print("[DEBUG] main.py: Importing database...", flush=True)
    from app.core.database import init_db, close_db
    print("[DEBUG] main.py: Database module imported", flush=True)
except Exception as e:
    print(f"[ERROR] main.py: Failed to import database: {e}", flush=True)
    traceback.print_exc()
    raise

try:
    print("[DEBUG] main.py: Importing redis...", flush=True)
    from app.core.redis import redis_manager
    print("[DEBUG] main.py: Redis module imported", flush=True)
except Exception as e:
    print(f"[ERROR] main.py: Failed to import redis: {e}", flush=True)
    traceback.print_exc()
    raise

try:
    print("[DEBUG] main.py: Importing qdrant...", flush=True)
    from app.core.qdrant import qdrant_manager
    print("[DEBUG] main.py: Qdrant module imported", flush=True)
except Exception as e:
    print(f"[ERROR] main.py: Failed to import qdrant: {e}", flush=True)
    traceback.print_exc()
    raise

try:
    print("[DEBUG] main.py: Importing api_router...", flush=True)
    from app.api import api_router
    print("[DEBUG] main.py: API router imported", flush=True)
except Exception as e:
    print(f"[ERROR] main.py: Failed to import api_router: {e}", flush=True)
    traceback.print_exc()
    raise

print("[DEBUG] main.py: All imports complete!", flush=True)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    print("[DEBUG] lifespan: Starting startup sequence...", flush=True)
    logger.info("Starting Bloomberg Telegram Signal Intelligence Engine")
    
    # Initialize database
    try:
        print("[DEBUG] lifespan: Initializing database...", flush=True)
        logger.info("Initializing database...")
        await init_db()
        print("[DEBUG] lifespan: Database initialized successfully", flush=True)
    except Exception as e:
        print(f"[ERROR] lifespan: Database init failed: {e}", flush=True)
        traceback.print_exc()
        raise
    
    # Initialize Redis
    try:
        print("[DEBUG] lifespan: Connecting to Redis...", flush=True)
        logger.info("Connecting to Redis...")
        await redis_manager.connect()
        print("[DEBUG] lifespan: Redis connected successfully", flush=True)
    except Exception as e:
        print(f"[ERROR] lifespan: Redis connection failed: {e}", flush=True)
        traceback.print_exc()
        raise
    
    # Initialize Qdrant (optional - for vector similarity features)
    try:
        print("[DEBUG] lifespan: Connecting to Qdrant...", flush=True)
        logger.info("Connecting to Qdrant...")
        qdrant_manager.connect()
        await qdrant_manager.init_collection()
        print("[DEBUG] lifespan: Qdrant connected successfully", flush=True)
        logger.info("Qdrant connected successfully")
    except Exception as e:
        print(f"[DEBUG] lifespan: Qdrant connection failed (optional): {e}", flush=True)
        logger.warning(f"Qdrant connection failed: {e}. Vector similarity features will be disabled.")
    
    print("[DEBUG] lifespan: Startup complete!", flush=True)
    logger.info("Startup complete!")
    
    yield
    
    # Shutdown
    print("[DEBUG] lifespan: Starting shutdown sequence...", flush=True)
    logger.info("Shutting down...")
    
    await close_db()
    await redis_manager.disconnect()
    try:
        qdrant_manager.close()
    except Exception:
        pass  # Qdrant was not connected
    
    print("[DEBUG] lifespan: Shutdown complete!", flush=True)
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
    print("[DEBUG] health_check: Received health check request", flush=True)
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
