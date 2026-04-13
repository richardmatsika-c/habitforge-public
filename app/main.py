# app/main.py

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from contextlib import asynccontextmanager
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Annotated, Optional
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
from fastapi.templating import Jinja2Templates
import redis.asyncio as redis
from fastapi_limiter import FastAPILimiter
from fastapi.responses import RedirectResponse
from .api.web import router_slash as web_router, get_current_user_optional

# Use relative imports
from .db import create_db_tables, SessionDep, migrate_existing_users
from .api.auth import router as auth_router, get_current_active_user
from .models import User, UserPublic
from .api import habits  # import your habit router
from .api import web
from .scheduler_jobs import send_daily_reminders, log_missed_habits_summary

# Security
security = HTTPBearer()

templates = Jinja2Templates(directory="templates")

# Jobs
scheduler = AsyncIOScheduler()

# -------------------------------------
# Lifespan Event Handler
# -------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    print("Application starting up...")

    # --- (Redis connection) ---
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        redis_client = redis.from_url(
            redis_url, encoding="utf-8", decode_responses=True
        )
        await FastAPILimiter.init(redis_client)
        print("Connected to Redis and initialized rate limiter.")
    except Exception as e:
        print(f"Could not connect to Redis: {e}")

    # --- (Scheduler setup) ---
    # print("Adding scheduled jobs...")
    # scheduler.add_job(send_daily_reminders, "cron", minute="*")
    # scheduler.add_job(log_missed_habits_summary, "cron", minute="*/2")
    # scheduler.start()

    # --- 2. CALL THE CLEANED FUNCTION ---
    create_db_tables()

    migrate_existing_users()

    yield

    print("Application shutting down...")
    # scheduler.shutdown()


# -------------------------------------
# FastAPI Instance
# -------------------------------------

app = FastAPI(
    lifespan=lifespan,
    title="The Forge",
    description="A secure authentication API for HabitForge",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# -------------------------------------
# CORS Middleware
# -------------------------------------

CLIENT_ORIGIN = os.getenv("CLIENT_ORIGIN", "http://localhost:3000")

origins = [
    CLIENT_ORIGIN,  # The main client
    # You might want to keep these for local dev just in case
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------
# API Routers
# -------------------------------------

app.include_router(habits.router)
app.include_router(auth_router)
app.include_router(web_router)  # 2. Add your new web router

# -------------------------------------
# Health Check & Root Endpoints
# -------------------------------------


@app.get("/", response_class=HTMLResponse)
async def root_landing_page(request: Request):
    """
    Shows the main, public landing page that captures the soul of HabitForge.
    """
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "current_user": None,  # No user on landing page
            "forge_state": "ash",  # Starting state
        },
    )


@app.get(
    "/health", summary="Health Check", response_description="API status description"
)
async def health_check():
    """Detailed health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        "version": "1.0.0",  # Fixed the version string
    }


@app.get(
    "/protected",
    summary="Protected Route Example",
    response_description="A message for authenticated users.",
    response_model=UserPublic,
)
async def protected_route(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    """Example of a protected route that requires authentication."""
    return current_user


# -------------------------------------
# Error Handlers
# -------------------------------------


@app.exception_handler(404)
async def not_found_exception_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Resource not found"})


@app.exception_handler(500)
async def internal_server_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
