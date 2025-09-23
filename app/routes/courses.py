from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import Annotated

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.course import (
    CourseCreate, CourseUpdate, CourseOut, CourseSessionCreate,
    EnrollResponse, EnrollmentListItem
)
from app.controllers import course_controller as ctl

router = APIRouter(prefix="/courses", tags=["courses"])

DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[dict, Depends(get_current_user)]

@router.post("/", response_model=CourseOut, status_code=status.HTTP_201_CREATED)
def create_course(payload: CourseCreate, db: DbDep, current_user: UserDep):
    return ctl.create(db, creator_id=current_user.id, payload=payload)

@router.get("/", response_model=list[CourseOut])
def list_courses(skip: int = 0, limit: int = 50, db: DbDep = None, current_user: UserDep = None):
    return ctl.list_many(db, skip=skip, limit=limit)

@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: int, db: DbDep, current_user: UserDep):
    return ctl.get_one(db, course_id=course_id)

@router.patch("/{course_id}", response_model=CourseOut)
def update_course(course_id: int, payload: CourseUpdate, db: DbDep, current_user: UserDep):
    return ctl.update(db, course_id=course_id, editor_id=current_user.id, payload=payload)

@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int, db: DbDep, current_user: UserDep):
    from app.services import course_service as svc
    svc.delete_course(db, course_id=course_id, editor_id=current_user.id)
    return

# ---- Sesiones ----
@router.post("/{course_id}/sessions", response_model=CourseOut)
def add_session(course_id: int, payload: CourseSessionCreate, db: DbDep, current_user: UserDep):
    return ctl.add_session(db, course_id=course_id, editor_id=current_user.id, payload=payload)

@router.delete("/{course_id}/sessions/{session_id}", response_model=CourseOut)
def remove_session(course_id: int, session_id: int, db: DbDep, current_user: UserDep):
    return ctl.remove_session(db, course_id=course_id, session_id=session_id, editor_id=current_user.id)

# ---- Inscripciones ----
@router.post("/{course_id}/enroll", response_model=EnrollResponse)
def enroll(course_id: int, db: DbDep, current_user: UserDep):
    return ctl.enroll(db, course_id=course_id, user_id=current_user.id)

@router.post("/{course_id}/unenroll", status_code=status.HTTP_204_NO_CONTENT)
def unenroll(course_id: int, db: DbDep, current_user: UserDep):
    ctl.unenroll(db, course_id=course_id, user_id=current_user.id)
    return

@router.get("/{course_id}/enrollments", response_model=list[EnrollmentListItem])
def list_enrollments(course_id: int, db: DbDep, current_user: UserDep):
    return ctl.list_enrollments(db, course_id=course_id)
