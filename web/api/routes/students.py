# web/api/routes/students.py
"""
Student Management API — Enterprise Staff only.

Endpoints for managing student classes:
  GET    /api/enterprise/students/classes          → list all classes
  POST   /api/enterprise/students/class            → create a new class
  PUT    /api/enterprise/students/class/:className  → update a class
  DELETE /api/enterprise/students/class/:className  → delete a class
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

from web.api.dependencies import db
from web.api.config import logger
from web.api.routes.auth import require_roles

router = APIRouter(
    prefix="/api/enterprise/students",
    tags=["students"],
)


# ─── Request / Response Models ────────────────────────────────────────────────

class StudentEntry(BaseModel):
    """One student row."""
    roll_no:      str
    student_name: str
    father_name:  Optional[str] = None
    section:      Optional[str] = None


class CreateClassRequest(BaseModel):
    """Create a new class with its students."""
    class_name: str
    students:   List[StudentEntry]


class UpdateClassRequest(BaseModel):
    """Update class name and/or its students."""
    class_name: str                   # new (or unchanged) class name
    students:   List[StudentEntry]


# ─── GET /classes ─────────────────────────────────────────────────────────────

@router.get("/classes")
async def get_classes(
    caller: dict = Depends(require_roles("enterprise_staff")),
    class_name: Optional[str] = None,
):
    """
    Return all classes for the logged-in staff user.
    If ?class_name=X is provided, return the student list for that class instead.
    """
    staff_user_id = caller.get("sub")
    enterprise_id = caller.get("organization_id")

    if not enterprise_id:
        raise HTTPException(status_code=400, detail="No organization linked to this account.")

    # If class_name query param is given, return students for that class
    if class_name:
        students = db.get_class_students(staff_user_id, enterprise_id, class_name.strip())
        return {"students": students, "class_name": class_name.strip()}

    classes = db.get_classes_for_staff(staff_user_id, enterprise_id)
    return {"classes": classes}


# ─── POST /class ──────────────────────────────────────────────────────────────

@router.post("/class")
async def create_class(
    body: CreateClassRequest,
    caller: dict = Depends(require_roles("enterprise_staff")),
):
    """Create a new class with its student list."""
    staff_user_id = caller.get("sub")
    enterprise_id = caller.get("organization_id")

    if not enterprise_id:
        raise HTTPException(status_code=400, detail="No organization linked to this account.")

    class_name = body.class_name.strip()
    if not class_name:
        raise HTTPException(status_code=400, detail="Class name is required.")

    if not body.students or len(body.students) == 0:
        raise HTTPException(status_code=400, detail="At least one student is required.")

    # Validate each student entry
    for i, s in enumerate(body.students):
        if not s.roll_no.strip():
            raise HTTPException(status_code=400, detail=f"Row {i+1}: Roll No is required.")
        if not s.student_name.strip():
            raise HTTPException(status_code=400, detail=f"Row {i+1}: Student Name is required.")

    # Check for duplicate class name for this staff user
    if db.class_name_exists(staff_user_id, enterprise_id, class_name):
        raise HTTPException(status_code=400, detail=f"A class named '{class_name}' already exists.")

    # Convert Pydantic models to dicts
    students_data = [s.model_dump() for s in body.students]

    try:
        db.create_class(staff_user_id, enterprise_id, class_name, students_data)
        logger.info(f"Class '{class_name}' created by {staff_user_id} with {len(students_data)} students")
    except Exception as e:
        logger.error(f"Failed to create class '{class_name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to create class. Please try again.")

    return {
        "message":       "Class created successfully.",
        "class_name":    class_name,
        "student_count": len(students_data),
    }


# ─── PUT /class/:className ────────────────────────────────────────────────────

@router.put("/class/{class_name:path}")
async def update_class(
    class_name: str,
    body: UpdateClassRequest,
    caller: dict = Depends(require_roles("enterprise_staff")),
):
    """Update a class — replace its name and/or student list."""
    staff_user_id = caller.get("sub")
    enterprise_id = caller.get("organization_id")

    if not enterprise_id:
        raise HTTPException(status_code=400, detail="No organization linked to this account.")

    old_class_name = class_name.strip()
    new_class_name = body.class_name.strip()

    if not new_class_name:
        raise HTTPException(status_code=400, detail="Class name is required.")

    # Verify the old class exists and belongs to this staff
    existing_students = db.get_class_students(staff_user_id, enterprise_id, old_class_name)
    if not existing_students:
        raise HTTPException(status_code=404, detail="Class not found.")

    # If renaming, check new name isn't already taken
    if new_class_name != old_class_name:
        if db.class_name_exists(staff_user_id, enterprise_id, new_class_name):
            raise HTTPException(status_code=400, detail=f"A class named '{new_class_name}' already exists.")

    if not body.students or len(body.students) == 0:
        raise HTTPException(status_code=400, detail="At least one student is required.")

    # Validate each student entry
    for i, s in enumerate(body.students):
        if not s.roll_no.strip():
            raise HTTPException(status_code=400, detail=f"Row {i+1}: Roll No is required.")
        if not s.student_name.strip():
            raise HTTPException(status_code=400, detail=f"Row {i+1}: Student Name is required.")

    students_data = [s.model_dump() for s in body.students]

    try:
        db.update_class(staff_user_id, enterprise_id, old_class_name, new_class_name, students_data)
        logger.info(f"Class '{old_class_name}' -> '{new_class_name}' updated by {staff_user_id}")
    except Exception as e:
        logger.error(f"Failed to update class '{old_class_name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to update class. Please try again.")

    return {
        "message":       "Class updated successfully.",
        "class_name":    new_class_name,
        "student_count": len(students_data),
    }


# ─── DELETE /class/:className ─────────────────────────────────────────────────

@router.delete("/class/{class_name:path}")
async def delete_class(
    class_name: str,
    caller: dict = Depends(require_roles("enterprise_staff")),
):
    """Delete a class and all its students."""
    staff_user_id = caller.get("sub")
    enterprise_id = caller.get("organization_id")

    if not enterprise_id:
        raise HTTPException(status_code=400, detail="No organization linked to this account.")

    class_name = class_name.strip()

    # Verify the class exists and belongs to this staff
    existing = db.get_class_students(staff_user_id, enterprise_id, class_name)
    if not existing:
        raise HTTPException(status_code=404, detail="Class not found.")

    try:
        count = db.delete_class(staff_user_id, enterprise_id, class_name)
        logger.info(f"Class '{class_name}' deleted by {staff_user_id} ({count} students removed)")
    except Exception as e:
        logger.error(f"Failed to delete class '{class_name}': {e}")
        raise HTTPException(status_code=500, detail="Failed to delete class. Please try again.")

    return {
        "message":         "Class deleted successfully.",
        "class_name":      class_name,
        "students_removed": count,
    }
