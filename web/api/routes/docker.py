# forge/web/api/routes/docker.py
"""
Docker container management endpoints.
Uses the Docker SDK directly — the legacy Orchestrator class no longer exists.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
import docker
from web.api.dependencies import db
from web.api.config import logger
from web.api.routes.auth import get_current_user, require_roles

router = APIRouter(prefix="/api/docker", tags=["docker"])


# ── Module-level Docker singleton — created once, reused on every request ──
_docker_singleton = None

def _docker_client():
    """
    Returns a cached Docker client. Creates it on first call only.
    Raises HTTP 503 if Docker is unavailable.
    """
    global _docker_singleton
    if _docker_singleton is None:
        try:
            _docker_singleton = docker.from_env()
            _docker_singleton.ping()  # verify once at startup only
        except Exception as e:
            _docker_singleton = None
            raise HTTPException(status_code=503, detail=f"Docker is not available: {e}")
    return _docker_singleton


# ============================================================================
# BULK OPERATIONS
# ============================================================================

@router.post("/start")
async def start_containers(background_tasks: BackgroundTasks, current_user: dict = Depends(require_roles("enterprise_staff", "enterprise_admin"))):
    """Start all stopped ctfWithAi Docker containers in the background."""
    def _start_all():
        try:
            client = docker.from_env()
            stopped = client.containers.list(all=True, filters={"status": "exited"})
            for c in stopped:
                c.start()
                logger.info(f"Started container: {c.name}")
        except Exception as e:
            logger.error(f"Background start-all failed: {e}")

    background_tasks.add_task(_start_all)
    return {"message": "Starting containers in background", "status": "building"}


@router.post("/stop")
async def stop_containers(current_user: dict = Depends(require_roles("enterprise_staff", "enterprise_admin"))):
    """Stop all running Docker containers."""
    client = _docker_client()
    try:
        running = client.containers.list()
        for c in running:
            c.stop(timeout=10)
            logger.info(f"Stopped container: {c.name}")
        return {"message": f"Stopped {len(running)} container(s) successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop containers: {e}")


@router.post("/restart")
async def restart_containers(current_user: dict = Depends(require_roles("enterprise_staff", "enterprise_admin"))):
    """Restart all running Docker containers."""
    client = _docker_client()
    try:
        running = client.containers.list()
        for c in running:
            c.restart(timeout=10)
            logger.info(f"Restarted container: {c.name}")
        return {"message": f"Restarted {len(running)} container(s) successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart containers: {e}")


@router.get("/status")
async def docker_status(current_user: dict = Depends(require_roles("enterprise_staff", "enterprise_admin"))):
    """Get status of all Docker containers."""
    client = _docker_client()
    try:
        all_containers = client.containers.list(all=True)
        containers = [
            {
                "Id":     c.id[:12],
                "Name":   c.name,
                "State":  c.status,
                "Status": c.status,
                "Image":  c.image.tags[0] if c.image.tags else "unknown",
            }
            for c in all_containers
        ]
        return {
            "containers": containers,
            "total":      len(containers),
            "running":    sum(1 for c in containers if c["State"] == "running"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Docker status: {e}")


@router.delete("/destroy")
async def destroy_containers(current_user: dict = Depends(require_roles("enterprise_staff", "enterprise_admin"))):
    """Force-remove all Docker containers (running or stopped)."""
    client = _docker_client()
    try:
        all_containers = client.containers.list(all=True)
        for c in all_containers:
            c.remove(force=True)
            logger.info(f"Destroyed container: {c.name}")
        return {"message": f"Destroyed {len(all_containers)} container(s) successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to destroy containers: {e}")




# ============================================================================
# INDIVIDUAL CONTAINER MANAGEMENT
# ============================================================================

@router.post("/container/{container_id}/start")
async def start_container(container_id: str, current_user: dict = Depends(get_current_user)):
    """Start a specific container"""
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)

        if container.status == 'running':
            return {"message": "Container is already running", "status": "running"}

        container.start()
        return {"message": f"Container {container.name} started successfully", "status": "started"}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start container: {str(e)}")


@router.post("/container/{container_id}/stop")
async def stop_container(container_id: str, current_user: dict = Depends(get_current_user)):
    """Stop a specific container"""
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)

        if container.status != 'running':
            return {"message": "Container is already stopped", "status": "stopped"}

        container.stop(timeout=10)
        return {"message": f"Container {container.name} stopped successfully", "status": "stopped"}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop container: {str(e)}")


@router.post("/container/{container_id}/restart")
async def restart_container(container_id: str, current_user: dict = Depends(get_current_user)):
    """Restart a specific container"""
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        container.restart(timeout=10)
        return {"message": f"Container {container.name} restarted successfully", "status": "restarted"}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restart container: {str(e)}")


@router.delete("/container/{container_id}")
async def remove_container(container_id: str, current_user: dict = Depends(get_current_user)):
    """Remove a specific container"""
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        container.remove(force=True)
        return {"message": f"Container removed successfully", "status": "removed"}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove container: {str(e)}")


@router.get("/container/{container_id}/logs")
async def get_container_logs(container_id: str, tail: int = 100, current_user: dict = Depends(get_current_user)):
    """Get logs from a specific container"""
    try:
        client = docker.from_env()
        container = client.containers.get(container_id)
        logs = container.logs(tail=tail, timestamps=True).decode('utf-8')
        return {"logs": logs, "container_id": container_id}
    except docker.errors.NotFound:
        raise HTTPException(status_code=404, detail=f"Container {container_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")


@router.get("/campaign/{campaign_id}/containers")
async def get_campaign_containers(campaign_id: str, current_user: dict = Depends(get_current_user)):
    """Get all Docker containers for a specific campaign"""
    try:
        client = docker.from_env()

        campaign = db.get_campaign(campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        all_containers = client.containers.list(all=True)
        campaign_machine_ids = [m['machine_id'] for m in campaign.get('machines', [])]

        campaign_containers = []
        for container in all_containers:
            container_name = container.name
            for machine_id in campaign_machine_ids:
                if machine_id[:12] in container_name or machine_id in container_name:
                    campaign_containers.append({
                        'Id': container.id,
                        'Name': container.name,
                        'State': container.status,
                        'Status': container.status,
                        'Image': container.image.tags[0] if container.image.tags else 'unknown',
                        'machine_id': machine_id
                    })
                    break

        return {
            'campaign_id': campaign_id,
            'campaign_name': campaign.get('campaign_name', 'Unknown'),
            'containers': campaign_containers,
            'total': len(campaign_containers),
            'running': sum(1 for c in campaign_containers if c['State'] == 'running')
        }
    except docker.errors.DockerException as e:
        raise HTTPException(status_code=500, detail=f"Docker error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
