import sys
from pathlib import Path

# Safety net: ensure core/ is on the path even if this file is imported
# in isolation (e.g. during testing) before main.py has patched sys.path.
_CORE = Path(__file__).resolve().parent.parent.parent.parent / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

# labapp.py defines:  router = APIRouter(prefix="/api/lab", tags=["lab"])
from labapp import router  # noqa: E402  (import not at top — intentional)

__all__ = ["router"]
