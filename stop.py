#!/usr/bin/env python3
import os
import sys
import time
import signal
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

RED    = "\033[0;31m"
GREEN  = "\033[0;32m"
YELLOW = "\033[1;33m"
NC     = "\033[0m"

def cprint(color, msg):
    print(f"{color}{msg}{NC}")

# ── PID file helpers ──────────────────────────────────────────────────────────

def read_pid_file(filename):
    path = os.path.join(SCRIPT_DIR, filename)
    try:
        return int(open(path).read().strip())
    except Exception:
        return None

def remove_pid_file(filename):
    path = os.path.join(SCRIPT_DIR, filename)
    try:
        os.remove(path)
    except OSError:
        pass

# ── Kill helpers ──────────────────────────────────────────────────────────────

def kill_pid(pid, label="process"):
    if pid <= 0:
        return False
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                           capture_output=True, timeout=10)
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        cprint(GREEN, f"  ✓ {label} stopped (PID {pid})")
        return True
    except ProcessLookupError:
        cprint(YELLOW, f"  – {label} (PID {pid}) already gone")
        return True
    except Exception as e:
        cprint(RED, f"  ✗ Could not kill {label} PID {pid}: {e}")
        return False


def kill_port(port, label=""):
    killed = False
    if IS_WINDOWS:
        try:
            result = subprocess.run(["netstat", "-ano"], capture_output=True,
                                    text=True, timeout=10)
            pids = set()
            for line in result.stdout.splitlines():
                if f":{port} " in line and "LISTENING" in line:
                    try:
                        pids.add(int(line.split()[-1]))
                    except ValueError:
                        pass
            for pid in pids:
                subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                               capture_output=True, timeout=10)
                killed = True
        except Exception:
            pass
    else:
        # fuser is the most reliable on Linux
        try:
            result = subprocess.run(["fuser", "-k", f"{port}/tcp"],
                                    capture_output=True, timeout=10)
            killed = result.returncode == 0
        except FileNotFoundError:
            # fallback: lsof
            try:
                result = subprocess.run(["lsof", "-ti", f"tcp:{port}"],
                                        capture_output=True, text=True, timeout=10)
                for pid_str in result.stdout.split():
                    try:
                        os.kill(int(pid_str), signal.SIGKILL)
                        killed = True
                    except Exception:
                        pass
            except Exception:
                pass

    if killed:
        cprint(GREEN, f"  ✓ {label or f'port {port}'} killed")
    return killed


def pkill(pattern, label=None):
    if IS_WINDOWS:
        try:
            ps = (
                f"Get-WmiObject Win32_Process | "
                f"Where-Object {{ $_.CommandLine -like '*{pattern}*' }} | "
                f"ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, timeout=15)
        except Exception:
            pass
    else:
        try:
            subprocess.run(["pkill", "-9", "-f", pattern],
                           capture_output=True, timeout=10)
        except Exception:
            pass
    if label:
        cprint(GREEN, f"  ✓ {label} killed")


def is_port_in_use(port):
    if IS_WINDOWS:
        try:
            result = subprocess.run(["netstat", "-ano"], capture_output=True,
                                    text=True, timeout=10)
            return any(f":{port} " in l and "LISTENING" in l
                       for l in result.stdout.splitlines())
        except Exception:
            return False
    else:
        try:
            result = subprocess.run(["fuser", f"{port}/tcp"],
                                    capture_output=True, timeout=5)
            return result.returncode == 0
        except FileNotFoundError:
            try:
                result = subprocess.run(["lsof", "-ti", f"tcp:{port}"],
                                        capture_output=True, timeout=5)
                return bool(result.stdout.strip())
            except Exception:
                return False

# ── Service stoppers ──────────────────────────────────────────────────────────

def stop_api():
    cprint(YELLOW, "Stopping API...")
    pid = read_pid_file(".api.pid")
    if pid:
        kill_pid(pid, "API")
    remove_pid_file(".api.pid")
    kill_port(8000, "API port 8000")
    pkill("web.api.main", "uvicorn/api")


def stop_labapp():
    cprint(YELLOW, "Stopping LabApp...")
    pid = read_pid_file(".labapp.pid")
    if pid:
        kill_pid(pid, "LabApp")
    remove_pid_file(".labapp.pid")
    pkill("labapp.py", "LabApp")


def stop_frontend():
    cprint(YELLOW, "Stopping Frontend...")
    pid = read_pid_file(".frontend.pid")
    if pid:
        kill_pid(pid, "Frontend")
    remove_pid_file(".frontend.pid")
    kill_port(3000, "Frontend port 3000")
    pkill("react-scripts", "react-scripts")
    pkill("vite", "vite")

    time.sleep(1)
    if is_port_in_use(3000):
        cprint(RED, "  ⚠️  Port 3000 still in use — kill manually:")
        if IS_WINDOWS:
            print("      netstat -ano | findstr :3000  →  taskkill /PID <pid> /F")
        else:
            print("      fuser -k 3000/tcp   OR   lsof -ti tcp:3000 | xargs kill -9")
    else:
        cprint(GREEN, "  ✓ Frontend stopped")


def stop_docker():
    cprint(YELLOW, "Stopping Docker...")
    orchestrator_py = os.path.join(SCRIPT_DIR, "docker", "orchestrator", "orchestrator.py")
    generated_dir   = os.path.join(SCRIPT_DIR, "core", "generated_machines")

    if os.path.isfile(orchestrator_py):
        try:
            subprocess.run([sys.executable, orchestrator_py, "stop"],
                           cwd=os.path.dirname(orchestrator_py),
                           capture_output=True, timeout=30)
            cprint(GREEN, "  ✓ Docker stopped via orchestrator")
        except Exception as e:
            cprint(RED, f"  orchestrator error: {e}")
    elif os.path.isdir(generated_dir):
        try:
            subprocess.run(["docker-compose", "down"],
                           cwd=generated_dir, capture_output=True, timeout=30)
            cprint(GREEN, "  ✓ Docker stopped via compose")
        except Exception as e:
            cprint(RED, f"  docker-compose error: {e}")
    else:
        cprint(YELLOW, "  No Docker config found, skipping")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║           STOPPING HACKFORGE SERVICES                     ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    stop_api()
    stop_labapp()
    stop_frontend()
    stop_docker()
    print()
    cprint(GREEN, "  ✓ All services stopped")
    print()

if __name__ == "__main__":
    main()
