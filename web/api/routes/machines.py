# web/api/routes/machines.py
"""
Machine management endpoints — VulnForge edition.

Data source: MySQL generated_machines table (written by bridge.py).
Every completed VulnForge job is registered in MySQL by bridge.py, and
the Machines tab reads exclusively from there.

vfdb (SQLite) is no longer queried by this file — it remains a job queue
only. Docker control endpoints are completely unchanged.

Response shape is kept 100% compatible with the existing Machines.jsx so
NO frontend changes are required.
"""

import sys
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from web.api.config import logger, CORE_PATH, GENERATED_MACHINES_DIR, PROJECT_ROOT
from web.api.dependencies import db   # MySQL DatabaseManager
from web.api.routes.auth import require_roles

router = APIRouter(prefix="/api/machines", tags=["machines"])


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_machine_dir(raw_dir: str) -> Path:
    p = Path(raw_dir)
    if p.is_absolute():
        return p
    return (Path(PROJECT_ROOT) / p).resolve()


def _get_docker_client():
    """Return a Docker client or None if Docker is unavailable."""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return client
    except Exception as e:
        logger.warning(f"Docker unavailable: {e}")
        return None


def _find_container(client, machine_id: str) -> dict | None:
    # Try SDK first
    if client:
        try:
            for c in client.containers.list(all=True):
                name = c.name or ""
                if machine_id in name or machine_id[:12] in name:
                    return {
                        "container_id":   c.id,
                        "container_name": c.name,
                        "status":         c.status,
                        "ports":          c.ports,
                    }
        except Exception as e:
            logger.warning(f"SDK container lookup failed: {e}")

    # Fallback: use subprocess docker ps
    try:
        import subprocess, json
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{json .}}"],
            capture_output=True, text=True
        )
        for line in result.stdout.strip().splitlines():
            c = json.loads(line)
            name = c.get("Names", "")
            if machine_id in name:
                status = c.get("State", c.get("Status", "unknown")).lower()
                if " " in status:
                    status = status.split()[0]
                return {
                    "container_id":   c.get("ID", c.get("Id", "")),
                    "container_name": name,
                    "status":         status,
                    "ports":          c.get("Ports", ""),
                }
    except Exception as e:
        logger.warning(f"Subprocess container lookup failed: {e}")

    return None

def _mysql_row_to_machine(row: dict, container: dict | None) -> dict:
    machine_id = row["machine_id"]
    cve_id     = row["cve_id"]
    difficulty = row["difficulty"]
    port       = row["port"]
    access_url = row["access_url"] or (f"http://localhost:{port}" if port else None)

    diff_map = {"easy": 1, "medium": 2, "hard": 4}
    diff_int = diff_map.get(str(difficulty).lower(), 2)

    is_running = container is not None and container.get("status") == "running"

    flag_obj = {
        "content":  row.get("flag_content", ""),
        "location": row.get("flag_location", "/flag.txt"),
    }

    return {
        "machine_id":    machine_id,
        "variant":       cve_id,
        "difficulty":    diff_int,
        "blueprint_id":  cve_id,
        "flag":          flag_obj,
        "directory":     row.get("machine_dir", ""),
        "campaign_id":   None,
        "campaign_name": None,
        "solved":        False,
        "attempts":      0,
        "points_earned": 0,
        "container":  container,
        "is_running": is_running,
        "url":        access_url if is_running else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@router.get("")
async def list_machines(current_user: dict = Depends(require_roles("individual"))):
    try:
        docker_client = _get_docker_client()
        rows = db.list_generated_machines(user_id=current_user.get("sub"))

        machines = []
        for row in rows:
            machine_dir = _resolve_machine_dir(row["machine_dir"])
            if not machine_dir.exists():
                logger.debug(f"Skipping {row['machine_id']} — dir gone ({machine_dir})")
                continue

            container = _find_container(docker_client, row["machine_id"])
            machines.append(_mysql_row_to_machine(row, container))

        logger.info(f"Returning {len(machines)} VulnForge machines")
        return machines

    except Exception as e:
        logger.error(f"Error listing machines: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list machines: {str(e)}")


@router.get("/{machine_id}")
async def get_machine(machine_id: str, current_user: dict = Depends(require_roles("individual"))):
    try:
        row = db.get_generated_machine(machine_id)
        if not row:
            raise HTTPException(status_code=404, detail="Machine not found")

        docker_client = _get_docker_client()
        container     = _find_container(docker_client, machine_id)

        return _mysql_row_to_machine(row, container)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting machine {machine_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{machine_id}/stats")
async def get_machine_stats(machine_id: str):
    return {
        "machine_id":    machine_id,
        "solved":        False,
        "attempts":      0,
        "points_earned": 0,
        "solvers":       [],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  DOCKER CONTROL
# ══════════════════════════════════════════════════════════════════════════════

def _container_action(container_id: str, action: str) -> dict:
    client = _get_docker_client()
    if not client:
        raise HTTPException(status_code=503, detail="Docker is not available")
    try:
        container = client.containers.get(container_id)
        getattr(container, action)()
        return {"success": True, "action": action, "container_id": container_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{machine_id}/docker/start")
async def start_machine_container(machine_id: str):
    import subprocess
    row = db.get_generated_machine(machine_id)
    if not row:
        raise HTTPException(status_code=404, detail="Machine not found")

    machine_dir = _resolve_machine_dir(row.get("machine_dir", ""))  # ← fixed (was xmachine_dir)
    compose_file = machine_dir / "docker-compose.yml"

    logger.info(f"Starting machine {machine_id} from dir: {machine_dir}")

    if not machine_dir.exists():
        raise HTTPException(status_code=404, detail=f"Machine directory not found: {machine_dir}")
    if not compose_file.exists():
        raise HTTPException(status_code=404, detail=f"docker-compose.yml not found in {machine_dir}")

    result = subprocess.run(
        ["docker-compose", "up", "-d"],
        cwd=str(machine_dir),
        capture_output=True, text=True, timeout=120
    )

    if result.returncode != 0:
        logger.error(f"docker-compose up failed for {machine_id}: {result.stderr}")
        raise HTTPException(status_code=500, detail=result.stderr)

    return {"success": True, "action": "start", "machine_id": machine_id}


@router.post("/{machine_id}/docker/stop")
async def stop_machine_container(machine_id: str):
    import subprocess
    row = db.get_generated_machine(machine_id)
    if not row:
        raise HTTPException(status_code=404, detail="Machine not found")

    machine_dir = _resolve_machine_dir(row.get("machine_dir", ""))

    result = subprocess.run(
        ["docker-compose", "stop"],
        cwd=str(machine_dir),
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr)

    return {"success": True, "action": "stop", "machine_id": machine_id}


@router.post("/{machine_id}/docker/restart")
async def restart_machine_container(machine_id: str):
    import subprocess
    row = db.get_generated_machine(machine_id)
    if not row:
        raise HTTPException(status_code=404, detail="Machine not found")

    machine_dir = _resolve_machine_dir(row.get("machine_dir", ""))

    result = subprocess.run(
        ["docker-compose", "restart"],
        cwd=str(machine_dir),
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr)

    return {"success": True, "action": "restart", "machine_id": machine_id}


@router.get("/{machine_id}/docker/status")
async def get_machine_container_status(machine_id: str):
    machine = await get_machine(machine_id)
    container = machine.get("container")
    if not container:
        return {"machine_id": machine_id, "status": "no_container", "is_running": False}
    return {
        "machine_id":   machine_id,
        "container_id": container["container_id"],
        "status":       container["status"],
        "is_running":   container["status"] == "running",
    }


@router.get("/{machine_id}/docker/logs")
async def get_machine_container_logs(machine_id: str, tail: int = 100):
    machine = await get_machine(machine_id)
    cid = (machine.get("container") or {}).get("container_id")
    if not cid:
        raise HTTPException(status_code=404, detail="No container found for this machine")
    client = _get_docker_client()
    if not client:
        raise HTTPException(status_code=503, detail="Docker is not available")
    try:
        container = client.containers.get(cid)
        logs = container.logs(tail=tail).decode("utf-8", errors="replace")
        return {"container_id": cid, "logs": logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
