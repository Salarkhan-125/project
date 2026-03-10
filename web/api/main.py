"""
ctfWithAi API Server - VulnForge Edition
==========================================
Main FastAPI application with VulnForge Lab Chat integration.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import os
import sys
from pathlib import Path
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

# ── FIX: limiter is now created in limiter.py to avoid circular import ────────
# Previously created here: limiter = Limiter(key_func=get_remote_address)
# auth.py imports limiter — if it was defined here that caused a circular crash
from web.api.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Add core/ to sys.path BEFORE any router imports ──────────────────────────
# vfdb.py lives in PROJECT_ROOT/core/ — lab.py and bridge.py do bare
# `import vfdb` so the core directory must be on the path at import time.
CORE_PATH = PROJECT_ROOT / "core"
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))
# ─────────────────────────────────────────────────────────────────────────────

from web.api.config import logger, CORS_ORIGINS

# ══════════════════════════════════════════════════════════════════════════════
# Initialize FastAPI app
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="ctfWithAi API",
    description="VulnForge Lab - AI-Powered Vulnerable Machine Generation",
    version="3.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Initialize Sentry for Error Tracking and Alerts
SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        enable_tracing=True,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        integrations=[FastApiIntegration()],
    )
    logger.info("✓ Sentry SDK initialized for Monitoring & Alerting")

# Wire up rate limiter
app.state.limiter = limiter

async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(f"[SECURITY ALERT] Rate limit exceeded on {request.url.path} from {request.client.host}")
    return _rate_limit_exceeded_handler(request, exc)

app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)

# ══════════════════════════════════════════════════════════════════════════════
# CORS Configuration
# ══════════════════════════════════════════════════════════════════════════════

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,   
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin"
    response.headers["Permissions-Policy"] = "geolocation=()"
    return response

# ══════════════════════════════════════════════════════════════════════════════
# Import Routers
# ══════════════════════════════════════════════════════════════════════════════

# VulnForge Lab Chat
try:
    from web.api.routes.lab import router as lab_router
    app.include_router(lab_router)
    logger.info("✓ VulnForge Lab routes loaded")
except ImportError as e:
    logger.error(f"Failed to load Lab routes: {e}", exc_info=True)
except Exception as e:
    logger.error(f"Unexpected error loading Lab routes: {e}", exc_info=True)

# User Authentication
try:
    from web.api.routes.auth import router as auth_router
    app.include_router(auth_router)
    logger.info("✓ Auth routes loaded")
except ImportError as e:
    logger.warning(f"Auth routes not available: {e}")
except Exception as e:
    logger.error(f"Unexpected error loading Auth routes: {e}", exc_info=True)

# User Management
try:
    from web.api.routes.users import router as users_router
    app.include_router(users_router)
    logger.info("✓ User routes loaded")
except ImportError as e:
    logger.warning(f"User routes not available: {e}")
except Exception as e:
    logger.error(f"Unexpected error loading User routes: {e}", exc_info=True)

# Machines (VulnForge machines from MySQL)
try:
    from web.api.routes.machines import router as machines_router
    app.include_router(machines_router)
    logger.info("✓ Machines routes loaded")
except ImportError as e:
    logger.warning(f"Machines routes not available: {e}")
except Exception as e:
    logger.error(f"Unexpected error loading Machines routes: {e}", exc_info=True)

# Stats (dashboard statistics)
try:
    from web.api.routes.stats import router as stats_router
    app.include_router(stats_router)
    logger.info("✓ Stats routes loaded")
except ImportError as e:
    logger.warning(f"Stats routes not available: {e}")
except Exception as e:
    logger.error(f"Unexpected error loading Stats routes: {e}", exc_info=True)

# Docker Control
try:
    from web.api.routes.docker import router as docker_router
    app.include_router(docker_router)
    logger.info("✓ Docker routes loaded")
except ImportError as e:
    logger.warning(f"Docker routes not available: {e}")
except Exception as e:
    logger.error(f"Unexpected error loading Docker routes: {e}", exc_info=True)

# Leaderboard
try:
    from web.api.routes.leaderboard import router as leaderboard_router
    app.include_router(leaderboard_router)
    logger.info("✓ Leaderboard routes loaded")
except ImportError as e:
    logger.warning(f"Leaderboard routes not available: {e}")
except Exception as e:
    logger.error(f"Unexpected error loading Leaderboard routes: {e}", exc_info=True)

# Campaigns
try:
    from web.api.routes.campaigns import router as campaigns_router
    app.include_router(campaigns_router)
    logger.info("✓ Campaigns routes loaded")
except ImportError as e:
    logger.warning(f"Campaigns routes not available: {e}")
except Exception as e:
    logger.error(f"Unexpected error loading Campaigns routes: {e}", exc_info=True)


# Flags
try:
    from web.api.routes.flags import router as flags_router
    app.include_router(flags_router)
    logger.info("✓ Flags routes loaded")
except ImportError as e:
    logger.warning(f"Flags routes not available: {e}")
except Exception as e:
    logger.error(f"Unexpected error loading Flags routes: {e}", exc_info=True)

# Student Management (Enterprise Staff)
try:
    from web.api.routes.students import router as students_router
    app.include_router(students_router)
    logger.info("✓ Students routes loaded")
except ImportError as e:
    logger.warning(f"Students routes not available: {e}")
except Exception as e:
    logger.error(f"Unexpected error loading Students routes: {e}", exc_info=True)

# Machine Assignments (Enterprise Staff)
try:
    from web.api.routes.assignments import router as assignments_router
    app.include_router(assignments_router)
    logger.info("✓ Assignments routes loaded")
except ImportError as e:
    logger.warning(f"Assignments routes not available: {e}")
except Exception as e:
    logger.error(f"Unexpected error loading Assignments routes: {e}", exc_info=True)


# ══════════════════════════════════════════════════════════════════════════════
# Health Check
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "message": "ctfWithAi VulnForge API is running",
        "version": "3.0.0"
    }

@app.get("/api/status")
async def system_status():
    """Extended status with VulnForge info"""
    try:
        import vfdb as DB

        try:
            job_count = len(DB.list_jobs(limit=1000))
        except Exception:
            job_count = 0

        try:
            cve_count = DB.get_vulhub_count()
        except Exception:
            cve_count = 0

        return {
            "status": "operational",
            "version": "3.0.0",
            "vulnforge": {
                "enabled": True,
                "jobs": job_count,
                "cve_recipes": cve_count,
                "chat_url": "/vuln-ai"
            }
        }
    except Exception as e:
        logger.warning(f"VulnForge stats unavailable: {e}")
        return {
            "status": "operational",
            "version": "3.0.0",
            "vulnforge": "initializing"
        }

# ══════════════════════════════════════════════════════════════════════════════
# Global Exception Handler
# ══════════════════════════════════════════════════════════════════════════════

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": "An unexpected error occurred. Please try again later."}
    )

# ══════════════════════════════════════════════════════════════════════════════
# Startup Event
# ══════════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    # Strip any accidental port from SERVER_HOST so we never get "http://ip:3000:8000"
    import re as _re
    _raw    = os.getenv("SERVER_HOST", "http://localhost").rstrip("/")
    _server = _re.sub(r':\d+$', '', _raw)   # remove trailing ":port" if present
    _port   = os.getenv("APP_PORT", "8000")
    logger.info("=" * 60)
    logger.info("ctfWithAi VulnForge API Starting")
    logger.info("=" * 60)
    logger.info(f"Frontend:      {os.getenv('FRONTEND_URL', 'http://localhost:3000')}")
    logger.info(f"API Docs:      {_server}:{_port}/api/docs")
    logger.info(f"Lab Status:    {_server}:{_port}/api/lab/status")
    logger.info(f"VulnAI Chat:   /vuln-ai")
    logger.info("=" * 60)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
