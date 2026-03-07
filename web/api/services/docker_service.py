# forge/web/api/services/docker_service.py
"""
Docker-related helper functions and services
"""
import os
from pathlib import Path
import subprocess
import socket
from web.api.config import logger, CORE_PATH

# Public host used for container access URLs (no trailing slash)
_SERVER_HOST = os.environ.get("SERVER_HOST", "http://localhost").rstrip("/")

def start_campaign_containers(campaign_path: Path) -> bool:
    """
    Start Docker containers for a campaign
    
    Args:
        campaign_path: Path to campaign directory
        
    Returns:
        bool: True if containers started successfully, False otherwise
    """
    try:
        compose_file = campaign_path / "docker-compose.yml"

        if not compose_file.exists():
            logger.warning(f"No docker-compose.yml found in {campaign_path}")
            return False

        logger.info(f"Starting containers for {campaign_path.name}...")

        # Run docker-compose up -d --build
        result = subprocess.run(
            ["docker-compose", "up", "-d", "--build"],
            cwd=str(campaign_path),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            logger.info(f"✓ Containers started successfully")
            return True
        else:
            logger.error(f"✗ Failed to start containers: {result.stderr}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout starting containers for {campaign_path.name}")
        return False
    except Exception as e:
        logger.error(f"Error starting containers: {e}")
        return False


def find_machine_directory(machine_id: str) -> Path:
    """
    Find machine directory in either generated_machines or campaigns
    
    Args:
        machine_id: Machine ID to search for
        
    Returns:
        Path: Path to machine directory
        
    Raises:
        FileNotFoundError: If machine directory not found
    """
    # Try generated_machines first
    machine_dir = CORE_PATH / "generated_machines" / machine_id
    
    if machine_dir.exists():
        return machine_dir
    
    # Try campaigns directory
    campaigns_dir = CORE_PATH / "campaigns"
    
    if campaigns_dir.exists():
        for campaign_dir in campaigns_dir.glob("campaign_*"):
            test_dir = campaign_dir / machine_id
            if test_dir.exists():
                return test_dir
    
    # Not found anywhere
    raise FileNotFoundError(f"Machine directory not found: {machine_id}")


def get_port_from_compose(compose_file: Path) -> str:
    """
    Extract port number from docker-compose.yml file
    
    Args:
        compose_file: Path to docker-compose.yml
        
    Returns:
        str: Port number or None if not found
    """
    try:
        with open(compose_file, 'r') as f:
            for line in f:
                if 'ports:' in line:
                    continue
                if '"' in line and ':80"' in line:
                    port = line.split('"')[1].split(':')[0]
                    return port
        return None
    except Exception as e:
        logger.error(f"Error reading compose file: {e}")
        return None


def find_available_port(start_port: int = 8080, max_attempts: int = 100) -> int:
    """
    Find an available port starting from start_port
    
    Args:
        start_port: Port to start searching from
        max_attempts: Maximum number of ports to try
        
    Returns:
        int: Available port number
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                logger.info(f"Found available port: {port}")
                return port
        except OSError:
            continue
    
    logger.warning(f"No available port found in range {start_port}-{start_port + max_attempts}, using {start_port}")
    return start_port


def start_machine_docker_compose(machine_id: str) -> dict:
    """
    Start docker-compose for a specific machine
    
    Args:
        machine_id: Machine ID
        
    Returns:
        dict: Result with success status, message, and optional URL
    """
    try:
        # Find machine directory
        try:
            machine_dir = find_machine_directory(machine_id)
        except FileNotFoundError as e:
            return {
                "success": False,
                "message": str(e),
                "machine_id": machine_id
            }
        
        compose_file = machine_dir / "docker-compose.yml"
        if not compose_file.exists():
            return {
                "success": False,
                "message": "docker-compose.yml not found",
                "machine_id": machine_id
            }

        logger.info(f"Starting container for {machine_id} in {machine_dir}")

        # Run docker-compose up
        result = subprocess.run(
            ["docker-compose", "up", "-d", "--build"],
            cwd=str(machine_dir),
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            logger.info(f"✓ Container started: {machine_id}")

            # Get port from docker-compose.yml
            port = get_port_from_compose(compose_file)

            return {
                "success": True,
                "message": "Container started successfully",
                "machine_id": machine_id,
                "url": f"{_SERVER_HOST}:{port}" if port else None,
                "logs": result.stdout
            }
        else:
            logger.error(f"Failed to start {machine_id}: {result.stderr}")
            return {
                "success": False,
                "message": "Failed to start container",
                "error": result.stderr,
                "machine_id": machine_id
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Container start timeout",
            "machine_id": machine_id
        }
    except Exception as e:
        logger.error(f"Error starting {machine_id}: {e}")
        return {
            "success": False,
            "message": str(e),
            "machine_id": machine_id
        }


def stop_machine_docker_compose(machine_id: str) -> dict:
    """
    Stop docker-compose for a specific machine
    
    Args:
        machine_id: Machine ID
        
    Returns:
        dict: Result with success status and message
    """
    try:
        # Find machine directory
        try:
            machine_dir = find_machine_directory(machine_id)
        except FileNotFoundError as e:
            return {
                "success": False,
                "message": str(e),
                "machine_id": machine_id
            }

        compose_file = machine_dir / "docker-compose.yml"
        if not compose_file.exists():
            return {
                "success": False,
                "message": "docker-compose.yml not found",
                "machine_id": machine_id
            }

        logger.info(f"Stopping container for {machine_id}")

        result = subprocess.run(
            ["docker-compose", "down"],
            cwd=str(machine_dir),
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            logger.info(f"✓ Container stopped: {machine_id}")
            return {
                "success": True,
                "message": "Container stopped successfully",
                "machine_id": machine_id
            }
        else:
            return {
                "success": False,
                "message": "Failed to stop container",
                "error": result.stderr,
                "machine_id": machine_id
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Container stop timeout",
            "machine_id": machine_id
        }
    except Exception as e:
        logger.error(f"Error stopping {machine_id}: {e}")
        return {
            "success": False,
            "message": str(e),
            "machine_id": machine_id
        }


def restart_machine_docker_compose(machine_id: str) -> dict:
    """
    Restart docker-compose for a specific machine
    
    Args:
        machine_id: Machine ID
        
    Returns:
        dict: Result with success status and message
    """
    try:
        # Find machine directory
        try:
            machine_dir = find_machine_directory(machine_id)
        except FileNotFoundError as e:
            return {
                "success": False,
                "message": str(e),
                "machine_id": machine_id
            }

        logger.info(f"Restarting container for {machine_id}")

        # Stop
        subprocess.run(
            ["docker-compose", "down"],
            cwd=str(machine_dir),
            capture_output=True,
            timeout=60
        )

        # Start
        result = subprocess.run(
            ["docker-compose", "up", "-d", "--build"],
            cwd=str(machine_dir),
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            logger.info(f"✓ Container restarted: {machine_id}")
            return {
                "success": True,
                "message": "Container restarted successfully",
                "machine_id": machine_id
            }
        else:
            return {
                "success": False,
                "message": "Failed to restart container",
                "error": result.stderr,
                "machine_id": machine_id
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Container restart timeout",
            "machine_id": machine_id
        }
    except Exception as e:
        logger.error(f"Error restarting {machine_id}: {e}")
        return {
            "success": False,
            "message": str(e),
            "machine_id": machine_id
        }


def get_machine_docker_status(machine_id: str) -> dict:
    """
    Get docker status for a specific machine
    
    Args:
        machine_id: Machine ID
        
    Returns:
        dict: Status information with containers and running state
    """
    import json
    
    try:
        # Find machine directory
        try:
            machine_dir = find_machine_directory(machine_id)
        except FileNotFoundError:
            return {
                "machine_id": machine_id,
                "containers": [],
                "running": False,
                "error": "Machine directory not found"
            }

        result = subprocess.run(
            ["docker-compose", "ps", "--format", "json"],
            cwd=str(machine_dir),
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0 and result.stdout.strip():
            containers = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        containers.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

            return {
                "machine_id": machine_id,
                "containers": containers,
                "running": any(c.get('State') == 'running' for c in containers)
            }
        else:
            return {
                "machine_id": machine_id,
                "containers": [],
                "running": False
            }

    except subprocess.TimeoutExpired:
        return {
            "machine_id": machine_id,
            "containers": [],
            "running": False,
            "error": "Status check timeout"
        }
    except Exception as e:
        logger.error(f"Error getting status for {machine_id}: {e}")
        return {
            "machine_id": machine_id,
            "containers": [],
            "running": False,
            "error": str(e)
        }


def get_machine_docker_logs(machine_id: str, tail: int = 100) -> dict:
    """
    Get docker logs for a specific machine
    
    Args:
        machine_id: Machine ID
        tail: Number of log lines to retrieve
        
    Returns:
        dict: Logs and machine ID
    """
    try:
        # Find machine directory
        try:
            machine_dir = find_machine_directory(machine_id)
        except FileNotFoundError:
            return {
                "machine_id": machine_id,
                "logs": "",
                "error": "Machine directory not found"
            }

        result = subprocess.run(
            ["docker-compose", "logs", f"--tail={tail}"],
            cwd=str(machine_dir),
            capture_output=True,
            text=True,
            timeout=30
        )

        return {
            "machine_id": machine_id,
            "logs": result.stdout
        }

    except subprocess.TimeoutExpired:
        return {
            "machine_id": machine_id,
            "logs": "",
            "error": "Log retrieval timeout"
        }
    except Exception as e:
        logger.error(f"Error getting logs for {machine_id}: {e}")
        return {
            "machine_id": machine_id,
            "logs": "",
            "error": str(e)
        }
