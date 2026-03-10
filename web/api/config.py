# forge/web/api/config.py
"""
Configuration for ctfWithAi API
"""
import os
from pathlib import Path
import logging
from dotenv import load_dotenv

# Load .env from project root (two levels up from web/api/)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ── Path Layout ───────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent.parent  # → project root
CORE_PATH = PROJECT_ROOT / "core"
DOCKER_PATH = PROJECT_ROOT / "docker" / "orchestrator"
DATABASE_PATH = Path(__file__).parent.parent / "database"
GENERATED_MACHINES_DIR = CORE_PATH / "generated_machines"

# ── Environment ───────────────────────────────────────────────────────────────
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
DEBUG        = os.environ.get("DEBUG", "True").lower() in ("true", "1", "yes")

# ── CORS ──────────────────────────────────────────────────────────────────────
# Always start with the configured FRONTEND_URL
_origins = {FRONTEND_URL.rstrip("/")}

# In dev mode also allow the common localhost variants so the dev server works
if DEBUG:
    _origins.update([
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://0.0.0.0:3000",
    ])

CORS_ORIGINS = list(_origins)

# ── Log on import ─────────────────────────────────────────────────────────────
logger.info(f"Project root: {PROJECT_ROOT}")
logger.info(f"Core path:    {CORE_PATH}")
logger.info(f"Docker path:  {DOCKER_PATH}")
logger.info(f"CORS origins: {CORS_ORIGINS}")

