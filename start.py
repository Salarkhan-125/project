#!/usr/bin/env python3
"""
ctfWithAi Platform Startup Script (Cross-Platform, Linux-first)
Starts: MySQL → API Server → LabApp
"""

import os
import sys
import time
import subprocess
import urllib.request
import io
from pathlib import Path

# Force UTF-8 stdout/stderr for Windows cmd/powershell
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# ── Config ────────────────────────────────────────────────────────────────────

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
IS_WINDOWS    = sys.platform == "win32"
SERVER_HOST   = os.environ.get("SERVER_HOST", "http://localhost").rstrip("/")
API_PORT      = int(os.environ.get("APP_PORT", 8000))
MYSQL_SERVICE = None  # None = auto-detect

# ── Colors ────────────────────────────────────────────────────────────────────

if IS_WINDOWS:
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

RED    = "\033[0;31m"
GREEN  = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE   = "\033[0;34m"
CYAN   = "\033[0;36m"
NC     = "\033[0m"

def cprint(color, msg):
    print(f"{color}{msg}{NC}")

# ── Process helpers ───────────────────────────────────────────────────────────

def kill_port(port):
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
        except Exception:
            pass
    else:
        try:
            subprocess.run(["fuser", "-k", f"{port}/tcp"],
                           capture_output=True, timeout=10)
        except FileNotFoundError:
            try:
                r = subprocess.run(["lsof", "-ti", f"tcp:{port}"],
                                   capture_output=True, text=True, timeout=10)
                for pid in r.stdout.split():
                    try:
                        subprocess.run(["kill", "-9", pid], capture_output=True)
                    except Exception:
                        pass
            except Exception:
                pass


def pkill(pattern):
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
            subprocess.run(["pkill", "-9", "-f", pattern], capture_output=True, timeout=10)
        except Exception:
            pass


def write_pid(filename, pid):
    with open(os.path.join(SCRIPT_DIR, filename), "w") as f:
        f.write(str(pid))


def popen(cmd, cwd, logfile, env=None):
    kwargs = dict(
        cwd=cwd,
        stdout=logfile,
        stderr=subprocess.STDOUT,
        env=env,
    )
    if IS_WINDOWS:
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    if isinstance(cmd, str):
        kwargs["shell"] = True
    return subprocess.Popen(cmd, **kwargs)


def open_log(name):
    path = os.path.join(SCRIPT_DIR, "logs", name)
    return open(path, "w"), path


# ── [1/3] MySQL ───────────────────────────────────────────────────────────────

def detect_mysql_service():
    if MYSQL_SERVICE:
        return MYSQL_SERVICE
    if not IS_WINDOWS:
        return "mysql"
    candidates = ["MySQL80", "MySQL", "MySQL57", "MySQL84", "MySQL90", "MariaDB"]
    try:
        result = subprocess.run(
            ["sc", "query", "type=", "service", "state=", "all"],
            capture_output=True, text=True, timeout=15
        )
        for name in candidates:
            if name.lower() in result.stdout.lower():
                return name
    except Exception:
        pass
    return "MySQL80"


def check_mysql():
    cprint(YELLOW, "[1/3] Checking MySQL...")
    svc = detect_mysql_service()

    if IS_WINDOWS:
        active = "RUNNING" in subprocess.run(
            ["sc", "query", svc], capture_output=True, text=True, timeout=10
        ).stdout
        start_cmd = ["net", "start", svc]
        check_cmd = ["sc", "query", svc]
        check_key = "RUNNING"
    else:
        active = subprocess.run(
            ["systemctl", "is-active", svc],
            capture_output=True, text=True, timeout=10
        ).stdout.strip() == "active"
        start_cmd = ["sudo", "systemctl", "start", svc]
        check_cmd = ["systemctl", "is-active", svc]
        check_key = "active"

    if active:
        cprint(GREEN, f"  ✓ MySQL is running (service: {svc})")
        print()
        return

    cprint(YELLOW, f"  Starting MySQL service '{svc}'...")
    try:
        subprocess.run(start_cmd, capture_output=True, text=True, timeout=30)
        time.sleep(2)
        check = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
        if check_key in check.stdout:
            cprint(GREEN, "  ✓ MySQL started")
            print()
            return
    except Exception as e:
        cprint(RED, f"  ❌ Error starting MySQL: {e}")

    cprint(RED, f"  ❌ Could not start MySQL (service: {svc})")
    if IS_WINDOWS:
        print(f"  Run as Administrator: net start {svc}")
    else:
        print(f"  Run: sudo systemctl start {svc}")
    sys.exit(1)


# ── [2/3] API ─────────────────────────────────────────────────────────────────

def start_api():
    cprint(YELLOW, "[2/3] Starting API Server...")
    kill_port(API_PORT)
    pkill("web.api.main")
    time.sleep(1)

    log_file, log_path = open_log("api.log")
    proc = popen(
        [sys.executable, "-m", "uvicorn", "web.api.main:app",
         "--host", "0.0.0.0", "--port", str(API_PORT)],
        cwd=SCRIPT_DIR, logfile=log_file
    )
    write_pid(".api.pid", proc.pid)
    time.sleep(4)

    if proc.poll() is not None:
        cprint(RED, f"  ❌ API failed to start. Check logs/api.log")
        _tail_log(log_path)
        sys.exit(1)

    cprint(GREEN, f"  ✓ API started (PID: {proc.pid})")
    print(f"    URL:  {SERVER_HOST}:{API_PORT}")
    print(f"    Docs: {SERVER_HOST}:{API_PORT}/docs")

    try:
        urllib.request.urlopen(f"http://localhost:{API_PORT}/api/lab/status", timeout=5)
        cprint(GREEN, "    ✓ Lab API responding")
    except Exception:
        cprint(YELLOW, "    ⚠️  Lab API not responding yet (may still be initializing)")

    print()
    return proc


# ── [3/3] LabApp ──────────────────────────────────────────────────────────────

def start_labapp():
    cprint(YELLOW, "[3/3] Starting LabApp (VulnForge Bridge)...")
    pkill("labapp.py")
    time.sleep(1)

    venv_win  = os.path.join(SCRIPT_DIR, "core", "env", "Scripts", "python.exe")
    venv_unix = os.path.join(SCRIPT_DIR, "core", "env", "bin", "python")
    if os.path.exists(venv_win):
        python_exe = venv_win
    elif os.path.exists(venv_unix):
        python_exe = venv_unix
    else:
        python_exe = sys.executable

    labapp = os.path.join(SCRIPT_DIR, "core", "labapp.py")
    log_file, log_path = open_log("labapp.log")
    proc = popen([python_exe, labapp], cwd=SCRIPT_DIR, logfile=log_file)
    write_pid(".labapp.pid", proc.pid)
    time.sleep(3)

    if proc.poll() is not None:
        cprint(RED, "  ❌ LabApp failed to start. Check logs/labapp.log")
        _tail_log(log_path)
        sys.exit(1)

    cprint(GREEN, f"  ✓ LabApp started (PID: {proc.pid})")
    print()
    return proc


# ── Summary ───────────────────────────────────────────────────────────────────

def show_summary():
    host = SERVER_HOST
    print()
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║              CTFWITHAI IS NOW RUNNING                     ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    cprint(GREEN, "  🌐 Services:")
    print(f"    • API:       {host}:{API_PORT}")
    print(f"    • API Docs:  {host}:{API_PORT}/docs")
    print(f"    • MySQL:     localhost:3306")
    print()
    cprint(YELLOW, "  📋 Logs: logs/api.log  |  logs/labapp.log")
    print()
    cprint(YELLOW, "  🛠️  Stop all: python stop.py")
    print()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tail_log(path, lines=20):
    try:
        with open(path) as f:
            for line in f.readlines()[-lines:]:
                print(f"    {line.rstrip()}")
    except Exception:
        pass


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print()
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║         CTFWITHAI PLATFORM STARTUP (VulnForge)            ║")
    print(f"║              Server: {SERVER_HOST:<38}║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()

    os.makedirs(os.path.join(SCRIPT_DIR, "logs"), exist_ok=True)
    os.makedirs(os.path.join(SCRIPT_DIR, "core", "generated_machines"), exist_ok=True)

    try:
        check_mysql()
        start_api()
        start_labapp()
        show_summary()
    except KeyboardInterrupt:
        print()
        cprint(YELLOW, "  Interrupted. Run 'python stop.py' to stop all services.")
        sys.exit(0)


if __name__ == "__main__":
    main()
