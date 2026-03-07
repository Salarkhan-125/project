"""
Docker Orchestrator
Manages deployment and lifecycle of Hackforge vulnerable machines
"""

import subprocess
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
import time


class DockerOrchestrator:
    """
    Orchestrates Docker container deployment and management
    """
    
    def __init__(self, machines_dir: str = None):
        if machines_dir:
            self.machines_dir = Path(machines_dir)
        else:
            # Default to generated_machines in core
            self.machines_dir = Path(__file__).parent.parent.parent / "core" / "generated_machines"
        
        self.compose_file = self.machines_dir / "docker-compose.yml"
    
    def _run_command(self, command: List[str], cwd: str = None) -> tuple:
        """
        Run shell command and return output
        
        Returns:
            (success: bool, output: str, error: str)
        """
        try:
            result = subprocess.run(
                command,
                cwd=cwd or str(self.machines_dir),
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            return (result.returncode == 0, result.stdout, result.stderr)
        except subprocess.TimeoutExpired:
            return (False, "", "Command timeout after 5 minutes")
        except Exception as e:
            return (False, "", str(e))
    
    def check_docker_installed(self) -> bool:
        """Check if Docker and Docker Compose are installed"""
        
        print("🔍 Checking Docker installation...")
        
        # Check Docker
        success, _, _ = self._run_command(["docker", "--version"])
        if not success:
            print("❌ Docker is not installed or not in PATH")
            return False
        
        print("✓ Docker is installed")
        
        # Check Docker Compose
        success, _, _ = self._run_command(["docker-compose", "--version"])
        if not success:
            print("❌ Docker Compose is not installed or not in PATH")
            return False
        
        print("✓ Docker Compose is installed")
        return True
    
    def check_machines_exist(self) -> bool:
        """Check if generated machines exist"""
        
        if not self.machines_dir.exists():
            print(f"❌ Machines directory not found: {self.machines_dir}")
            print("   Run template engine first: python3 core/template_engine.py")
            return False
        
        if not self.compose_file.exists():
            print(f"❌ docker-compose.yml not found in {self.machines_dir}")
            print("   Run template engine first: python3 core/template_engine.py")
            return False
        
        return True
    
    def list_machines(self) -> List[Dict]:
        """List all available machines"""
        
        machines = []
        
        if not self.machines_dir.exists():
            return machines
        
        # Find all machine directories
        for machine_dir in self.machines_dir.iterdir():
            if machine_dir.is_dir() and not machine_dir.name.startswith('.'):
                config_file = machine_dir / "config.json"
                
                if config_file.exists():
                    try:
                        with open(config_file, 'r') as f:
                            config = json.load(f)
                        
                        machines.append({
                            'machine_id': config['machine_id'],
                            'variant': config['variant'],
                            'difficulty': config['difficulty'],
                            'blueprint_id': config['blueprint_id'],
                            'flag': config['flag']['content'],
                            'directory': str(machine_dir)
                        })
                    except Exception as e:
                        print(f"⚠️ Error reading config for {machine_dir.name}: {e}")
        
        return machines
    
    def build_machines(self, no_cache: bool = False) -> bool:
        """Build all machine Docker images"""
        
        print("\n" + "="*60)
        print("🔨 Building Docker Images")
        print("="*60)
        
        if not self.check_machines_exist():
            return False
        
        command = ["docker-compose", "build"]
        if no_cache:
            command.append("--no-cache")
        
        print(f"\nRunning: {' '.join(command)}")
        print("This may take a few minutes...\n")
        
        success, stdout, stderr = self._run_command(command)
        
        if stdout:
            print(stdout)
        if stderr:
            print(stderr)
        
        if success:
            print("\n✅ All images built successfully!")
            return True
        else:
            print("\n❌ Build failed!")
            return False
    
    def start_machines(self, build: bool = True, detached: bool = True) -> bool:
        """Start all machines"""
        
        print("\n" + "="*60)
        print("🚀 Starting Machines")
        print("="*60)
        
        if not self.check_machines_exist():
            return False
        
        command = ["docker-compose", "up"]
        
        if detached:
            command.append("-d")
        
        if build:
            command.append("--build")
        
        print(f"\nRunning: {' '.join(command)}")
        print("Starting containers...\n")
        
        success, stdout, stderr = self._run_command(command)
        
        if stdout:
            print(stdout)
        if stderr and "WARNING" not in stderr:
            print(stderr)
        
        if success:
            print("\n✅ All machines started successfully!")
            
            # Show running machines
            time.sleep(2)
            self.status_machines()
            return True
        else:
            print("\n❌ Failed to start machines!")
            return False
    
    def stop_machines(self) -> bool:
        """Stop all machines"""
        
        print("\n" + "="*60)
        print("🛑 Stopping Machines")
        print("="*60)
        
        if not self.compose_file.exists():
            print("❌ No docker-compose.yml found")
            return False
        
        command = ["docker-compose", "stop"]
        
        print(f"\nRunning: {' '.join(command)}\n")
        
        success, stdout, stderr = self._run_command(command)
        
        if stdout:
            print(stdout)
        if stderr and "WARNING" not in stderr:
            print(stderr)
        
        if success:
            print("\n✅ All machines stopped!")
            return True
        else:
            print("\n❌ Failed to stop machines!")
            return False
    
    def destroy_machines(self, remove_volumes: bool = False) -> bool:
        """Destroy all machines and clean up"""
        
        print("\n" + "="*60)
        print("💥 Destroying Machines")
        print("="*60)
        
        if not self.compose_file.exists():
            print("❌ No docker-compose.yml found")
            return False
        
        command = ["docker-compose", "down"]
        
        if remove_volumes:
            command.append("-v")
        
        print(f"\nRunning: {' '.join(command)}\n")
        
        success, stdout, stderr = self._run_command(command)
        
        if stdout:
            print(stdout)
        if stderr and "WARNING" not in stderr:
            print(stderr)
        
        if success:
            print("\n✅ All machines destroyed and cleaned up!")
            return True
        else:
            print("\n❌ Failed to destroy machines!")
            return False
    
    def status_machines(self) -> List[Dict]:
        """Get status of all machines"""
        
        print("\n" + "="*60)
        print("📊 Machine Status")
        print("="*60 + "\n")
        
        if not self.compose_file.exists():
            print("❌ No docker-compose.yml found")
            return []
        
        command = ["docker-compose", "ps", "--format", "json"]
        
        success, stdout, stderr = self._run_command(command)
        
        if not success:
            # Fallback to regular ps
            command = ["docker-compose", "ps"]
            success, stdout, stderr = self._run_command(command)
            print(stdout)
            return []
        
        # Parse JSON output
        containers = []
        try:
            for line in stdout.strip().split('\n'):
                if line:
                    container = json.loads(line)
                    containers.append(container)
        except:
            # If JSON parsing fails, just show raw output
            print(stdout)
            return []
        
        # Display formatted status
        if containers:
            for i, container in enumerate(containers, 1):
                name = container.get('Name', 'Unknown')
                state = container.get('State', 'Unknown')
                ports = container.get('Publishers', [])
                
                # Extract port mapping
                port_str = "No ports"
                if ports:
                    port_mappings = []
                    for port in ports:
                        published = port.get('PublishedPort', '')
                        target = port.get('TargetPort', '')
                        if published and target:
                            port_mappings.append(f"{published}→{target}")
                    if port_mappings:
                        port_str = ", ".join(port_mappings)
                
                # Color code status
                status_icon = "🟢" if state == "running" else "🔴"
                
                print(f"Machine {i}: {name}")
                print(f"  Status: {status_icon} {state}")
                print(f"  Ports: {port_str}")
                
                if state == "running" and ports:
                    for port in ports:
                        published = port.get('PublishedPort', '')
                        if published:
                            print(f"  URL: http://0.0.0.0:{published}")
                
                print()
        else:
            print("No containers running")
        
        return containers
    
    def logs_machines(self, follow: bool = False, tail: int = 50) -> bool:
        """Show logs from all machines"""
        
        print("\n" + "="*60)
        print("📜 Machine Logs")
        print("="*60 + "\n")
        
        if not self.compose_file.exists():
            print("❌ No docker-compose.yml found")
            return False
        
        command = ["docker-compose", "logs", f"--tail={tail}"]
        
        if follow:
            command.append("-f")
        
        print(f"Running: {' '.join(command)}\n")
        
        if follow:
            # Stream logs in real-time
            try:
                subprocess.run(command, cwd=str(self.machines_dir))
                return True
            except KeyboardInterrupt:
                print("\n\n✓ Stopped following logs")
                return True
        else:
            success, stdout, stderr = self._run_command(command)
            
            if stdout:
                print(stdout)
            if stderr and "WARNING" not in stderr:
                print(stderr)
            
            return success
    
    def restart_machines(self) -> bool:
        """Restart all machines"""
        
        print("\n" + "="*60)
        print("🔄 Restarting Machines")
        print("="*60)
        
        if not self.compose_file.exists():
            print("❌ No docker-compose.yml found")
            return False
        
        command = ["docker-compose", "restart"]
        
        print(f"\nRunning: {' '.join(command)}\n")
        
        success, stdout, stderr = self._run_command(command)
        
        if stdout:
            print(stdout)
        if stderr and "WARNING" not in stderr:
            print(stderr)
        
        if success:
            print("\n✅ All machines restarted!")
            time.sleep(2)
            self.status_machines()
            return True
        else:
            print("\n❌ Failed to restart machines!")
            return False


def main():
    """CLI interface for orchestrator"""
    
    orchestrator = DockerOrchestrator()
    
    if len(sys.argv) < 2:
        print("""
╔═══════════════════════════════════════════════════════════╗
║             HACKFORGE DOCKER ORCHESTRATOR                 ║
╚═══════════════════════════════════════════════════════════╝

Usage: python3 orchestrator.py <command>

Commands:
  start       - Build and start all machines
  stop        - Stop all machines
  restart     - Restart all machines
  destroy     - Stop and remove all containers
  status      - Show status of all machines
  logs        - Show logs (add -f to follow)
  build       - Build Docker images only
  list        - List all available machines

Examples:
  python3 orchestrator.py start
  python3 orchestrator.py status
  python3 orchestrator.py logs -f
  python3 orchestrator.py destroy
""")
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    # Check Docker installation
    if not orchestrator.check_docker_installed():
        sys.exit(1)
    
    if command == "start":
        success = orchestrator.start_machines()
        sys.exit(0 if success else 1)
    
    elif command == "stop":
        success = orchestrator.stop_machines()
        sys.exit(0 if success else 1)
    
    elif command == "restart":
        success = orchestrator.restart_machines()
        sys.exit(0 if success else 1)
    
    elif command == "destroy":
        print("\n⚠️  WARNING: This will stop and remove all containers!")
        confirm = input("Are you sure? (yes/no): ")
        if confirm.lower() == "yes":
            success = orchestrator.destroy_machines(remove_volumes=True)
            sys.exit(0 if success else 1)
        else:
            print("Cancelled")
            sys.exit(0)
    
    elif command == "status":
        orchestrator.status_machines()
        sys.exit(0)
    
    elif command == "logs":
        follow = "-f" in sys.argv or "--follow" in sys.argv
        success = orchestrator.logs_machines(follow=follow)
        sys.exit(0 if success else 1)
    
    elif command == "build":
        no_cache = "--no-cache" in sys.argv
        success = orchestrator.build_machines(no_cache=no_cache)
        sys.exit(0 if success else 1)
    
    elif command == "list":
        machines = orchestrator.list_machines()
        
        print("\n" + "="*60)
        print("📋 Available Machines")
        print("="*60 + "\n")
        
        if machines:
            for i, machine in enumerate(machines, 1):
                print(f"Machine {i}:")
                print(f"  ID: {machine['machine_id']}")
                print(f"  Variant: {machine['variant']}")
                print(f"  Difficulty: {machine['difficulty']}/5")
                print(f"  Flag: {machine['flag']}")
                print()
        else:
            print("No machines found. Run template engine first!")
        
        sys.exit(0)
    
    else:
        print(f"❌ Unknown command: {command}")
        print("Run without arguments to see usage")
        sys.exit(1)


if __name__ == "__main__":
    main()
