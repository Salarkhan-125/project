# web/api/routes/assignments.py
"""
Enterprise assignment endpoints — allows staff to assign generated machines
to student classes and manage student machine instances.

Protected by require_roles("enterprise_staff").
"""

import os
import json
import uuid
import shutil
import socket
from pathlib import Path
from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from web.api.config import logger, GENERATED_MACHINES_DIR, PROJECT_ROOT
from web.api.dependencies import db   # MySQL DatabaseManager
from web.api.routes.auth import require_roles, get_current_user


router = APIRouter(prefix="/api/enterprise/assignments", tags=["assignments"])

_staff_guard = require_roles("enterprise_staff")


# ══════════════════════════════════════════════════════════════════════════════
#  REQUEST MODELS
# ══════════════════════════════════════════════════════════════════════════════

class AssignMachineRequest(BaseModel):
    machine_id: str
    class_name: str


class SubmitFlagRequest(BaseModel):
    flag: str


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _find_free_port(start: int = 10000, attempts: int = 200) -> int:
    """Find a free TCP port on localhost."""
    port = start
    for _ in range(attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("0.0.0.0", port))
                return port
            except OSError:
                port += 1
    raise RuntimeError(f"Could not find a free port after {attempts} attempts")


def _generate_unique_flag(seed: str) -> str:
    """Generate a unique flag per student."""
    short_id = uuid.uuid4().hex[:8]
    return f"CTFWITHAI{{{seed.upper()}_{short_id}}}"


# ══════════════════════════════════════════════════════════════════════════════
#  LIST ASSIGNMENTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/")
async def list_assignments(user: dict = Depends(_staff_guard)):
    """Return all assignments for the current staff user."""
    org_id = user.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found in token.")
    assignments = db.get_assignments_for_staff(user.get("sub"), org_id)

    # Attach solved count per assignment
    for a in assignments:
        instances = db.get_assignment_instances(a["assignment_id"])
        solved = sum(1 for i in instances if i.get("status") == "solved")
        a["solved_count"] = solved

    return {"assignments": assignments}


# ══════════════════════════════════════════════════════════════════════════════
#  ASSIGN MACHINE TO CLASS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/assign")
async def assign_machine_to_class(
    req: AssignMachineRequest,
    user: dict = Depends(_staff_guard),
):
    """
    Assign a generated machine to a student class.

    For each student in the class:
    1. Generate a unique flag
    2. Copy the machine folder to a student-specific subfolder
    3. Patch docker-compose.yml with unique port and flag
    4. Generate login credentials (account_id=roll_no, password=reversed roll_no)
    5. Save records to DB
    """
    org_id = user.get("organization_id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Organization ID not found in token.")

    # Validate machine exists and is not already assigned
    machine = db.get_generated_machine(req.machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found.")
    if machine.get("assigned"):
        raise HTTPException(status_code=400, detail="Machine is already assigned to a class.")

    # Get students in the class
    students = db.get_class_students(user.get("sub"), org_id, req.class_name)
    if not students:
        raise HTTPException(status_code=400, detail=f"No students found in class '{req.class_name}'.")

    # Resolve the machine directory
    raw_dir = machine.get("machine_dir", "")
    machine_dir = Path(raw_dir)
    if not machine_dir.is_absolute():
        machine_dir = (Path(PROJECT_ROOT) / raw_dir).resolve()
    if not machine_dir.exists():
        raise HTTPException(status_code=404, detail="Machine files not found on server.")

    # Read manifest for machine info
    manifest_path = machine_dir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except Exception:
            pass

    machine_name = manifest.get("cve_id", machine.get("cve_id", "Unknown"))

    # Create assignment record
    assignment_id = f"assign_{uuid.uuid4().hex[:12]}"
    db.create_machine_assignment({
        "assignment_id":   assignment_id,
        "machine_id":      req.machine_id,
        "machine_name":    machine_name,
        "class_name":      req.class_name,
        "staff_user_id":   user.get("sub"),
        "organization_id": org_id,
        "total_students":  len(students),
    })

    # Create per-student instances
    students_dir = machine_dir / "students"
    students_dir.mkdir(parents=True, exist_ok=True)
    port_counter = _find_free_port(start=15000)
    created_instances = []

    for student in students:
        roll_no = student["roll_no"]
        student_name = student["student_name"]
        instance_id = f"inst_{uuid.uuid4().hex[:12]}"

        # 1. Unique flag
        unique_flag = _generate_unique_flag(roll_no)

        # 2. Copy machine folder for this student
        student_folder = students_dir / roll_no.replace(" ", "_")
        if student_folder.exists():
            shutil.rmtree(student_folder)
        shutil.copytree(machine_dir, student_folder, ignore=shutil.ignore_patterns("students"))

        # 3. Write unique flag.txt
        (student_folder / "flag.txt").write_text(unique_flag)

        # 4. Patch docker-compose.yml with unique port
        compose_path = student_folder / "docker-compose.yml"
        main_port = None
        if compose_path.exists():
            import yaml
            try:
                compose_data = yaml.safe_load(compose_path.read_text())
                if compose_data and "services" in compose_data:
                    for svc_name, svc_cfg in compose_data["services"].items():
                        if svc_cfg is None:
                            svc_cfg = {}
                            compose_data["services"][svc_name] = svc_cfg
                        svc_cfg["restart"] = "always"  # Auto-recover from database race conditions or CTF crashes
                        
                        if "ports" in svc_cfg:
                            new_ports = []
                            for p in svc_cfg["ports"]:
                                free_port = _find_free_port(start=port_counter)
                                if main_port is None or (svc_name == "web" or "80" in str(p).split(":")[-1]):
                                    # Prioritize web ports for the main_port shown to students
                                    main_port = free_port
                                parts = str(p).split(":")
                                if len(parts) == 2:
                                    new_ports.append(f"{free_port}:{parts[1]}")
                                else:
                                    new_ports.append(f"{free_port}:{p}")
                                port_counter = free_port + 1
                            svc_cfg["ports"] = new_ports
                    compose_path.write_text(yaml.dump(compose_data, default_flow_style=False))
            except Exception as e:
                logger.warning(f"Failed to patch compose for student {roll_no}: {e}")

        # Fallback if no ports were defined in docker-compose.yml
        if main_port is None:
            main_port = _find_free_port(start=port_counter)
            port_counter = main_port + 1

        # 5. Isolate Docker project name to prevent orphan warnings when assigned multiple machines
        (student_folder / ".env").write_text(f"COMPOSE_PROJECT_NAME=vf_{instance_id}\n")

        # 6. Generate credentials (password = reversed roll_no)
        raw_password = roll_no[::-1]
        hashed_pw = bcrypt.hashpw(raw_password.encode(), bcrypt.gensalt()).decode()

        # 6. Save instance
        instance = db.create_student_instance({
            "instance_id":     instance_id,
            "assignment_id":   assignment_id,
            "machine_id":      req.machine_id,
            "student_roll_no": roll_no,
            "student_name":    student_name,
            "organization_id": org_id,
            "account_id":      roll_no,
            "hashed_password": hashed_pw,
            "unique_flag":     unique_flag,
            "assigned_port":   main_port,
            "instance_folder": str(student_folder),
        })
        created_instances.append(instance)

    # Mark machine as assigned
    db.mark_machine_assigned(req.machine_id)

    logger.info(f"Assigned machine {req.machine_id} to class '{req.class_name}' "
                f"({len(created_instances)} students)")

    return {
        "message": f"Machine assigned to {len(created_instances)} students in '{req.class_name}'.",
        "assignment_id": assignment_id,
        "instances_created": len(created_instances),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  ASSIGNMENT DETAILS (student progress)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{assignment_id}/details")
async def get_assignment_details(
    assignment_id: str,
    user: dict = Depends(get_current_user),
):
    """Return student progress table data for an assignment."""
    assignment = db.get_assignment(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")

    role = user.get("role")
    
    if role == "enterprise_staff":
        if assignment["staff_user_id"] != user.get("sub"):
            raise HTTPException(status_code=403, detail="Access denied.")
        instances = db.get_assignment_instances(assignment_id)
    elif role == "student":
        # Extract instance_id from sub: "student_{instance_id}"
        sub = user.get("sub", "")
        if not sub.startswith("student_"):
            raise HTTPException(status_code=403, detail="Invalid student token.")
        instance_id = sub[len("student_"):]
        
        student_instance = db.get_student_instance(instance_id)
        if not student_instance or student_instance["assignment_id"] != assignment_id:
            raise HTTPException(status_code=403, detail="Access denied.")
        instances = [student_instance]
    else:
        raise HTTPException(status_code=403, detail="Access denied.")

    # Strip sensitive fields
    for inst in instances:
        inst.pop("hashed_password", None)
        inst.pop("unique_flag", None)

    return {"assignment": assignment, "instances": instances}


# ══════════════════════════════════════════════════════════════════════════════
#  STUDENT CREDENTIALS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{assignment_id}/credentials")
async def get_assignment_credentials(
    assignment_id: str,
    user: dict = Depends(_staff_guard),
):
    """Return student login credentials for an assignment."""
    assignment = db.get_assignment(assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    if assignment["staff_user_id"] != user.get("sub"):
        raise HTTPException(status_code=403, detail="Access denied.")

    instances = db.get_assignment_instances(assignment_id)
    credentials = []
    for inst in instances:
        credentials.append({
            "student_name":    inst["student_name"],
            "roll_no":         inst["student_roll_no"],
            "account_id":      inst["account_id"],
            "password":        inst["student_roll_no"][::-1],  # reversed roll_no
            "assigned_port":   inst.get("assigned_port"),
        })

    return {"assignment": assignment, "credentials": credentials}


# ══════════════════════════════════════════════════════════════════════════════
#  STUDENT MACHINE CONTROL (start / stop)
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/{assignment_id}/instances/{instance_id}/start")
async def start_student_machine(
    assignment_id: str,
    instance_id: str,
    user: dict = Depends(get_current_user),
):
    """Start a student's Docker container."""
    import subprocess

    if user.get("role") == "student" and user.get("sub") != f"student_{instance_id}":
        raise HTTPException(status_code=403, detail="You can only control your own machine.")

    instance = db.get_student_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found.")
    if instance["assignment_id"] != assignment_id:
        raise HTTPException(status_code=400, detail="Instance does not belong to this assignment.")

    folder = Path(instance["instance_folder"])
    if not folder.exists():
        raise HTTPException(status_code=404, detail="Instance folder not found.")

    # Retrofit existing instances with isolated project names
    (folder / ".env").write_text(f"COMPOSE_PROJECT_NAME=vf_{instance_id}\n")

    try:
        result = subprocess.run(
            ["docker-compose", "up", "-d", "--remove-orphans"],
            cwd=str(folder),
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.error(f"docker-compose up failed: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"Failed to start container: {result.stderr[:200]}")

        db.update_student_instance(instance_id, {
            "status": "started",
            "started_at": datetime.now(timezone.utc),
        })

        return {"message": "Machine started successfully.", "status": "started"}

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Container start timed out.")


@router.post("/{assignment_id}/instances/{instance_id}/stop")
async def stop_student_machine(
    assignment_id: str,
    instance_id: str,
    user: dict = Depends(get_current_user),
):
    """Stop a student's Docker container."""
    import subprocess

    if user.get("role") == "student" and user.get("sub") != f"student_{instance_id}":
        raise HTTPException(status_code=403, detail="You can only control your own machine.")

    instance = db.get_student_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found.")
    if instance["assignment_id"] != assignment_id:
        raise HTTPException(status_code=400, detail="Instance does not belong to this assignment.")

    folder = Path(instance["instance_folder"])
    if not folder.exists():
        raise HTTPException(status_code=404, detail="Instance folder not found.")

    # Ensure stopped containers use the same isolated project name
    (folder / ".env").write_text(f"COMPOSE_PROJECT_NAME=vf_{instance_id}\n")

    try:
        subprocess.run(
            ["docker-compose", "down"],
            cwd=str(folder),
            capture_output=True, text=True, timeout=60,
        )
        db.update_student_instance(instance_id, {"status": "assigned"})
        return {"message": "Machine stopped.", "status": "assigned"}

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Container stop timed out.")


# ══════════════════════════════════════════════════════════════════════════════
#  STUDENT FLAG SUBMISSION
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/{instance_id}/submit-flag")
async def submit_student_flag(
    instance_id: str,
    req: SubmitFlagRequest,
    user: dict = Depends(get_current_user),
):
    """Submit a flag for a student's machine instance."""
    if user.get("role") == "student" and user.get("sub") != f"student_{instance_id}":
        raise HTTPException(status_code=403, detail="You can only submit flags for your own machine.")

    instance = db.get_student_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found.")

    # Increment attempts
    new_attempts = (instance.get("attempts", 0) or 0) + 1
    db.update_student_instance(instance_id, {"attempts": new_attempts})

    # Compare flags
    submitted = req.flag.strip()
    if submitted == instance["unique_flag"]:
        db.update_student_instance(instance_id, {
            "status": "solved",
            "solved_at": datetime.now(timezone.utc),
        })
        return {"correct": True, "message": "Correct! Flag submitted successfully."}
    else:
        return {"correct": False, "message": "Incorrect flag. Try again."}
