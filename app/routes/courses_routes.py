from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.controllers.courses_controller import CourseController
from app.core.db import get_db
from app.schemas.courses import CourseBase, CourseByUserBase, CourseCreate, CourseCreateResponse, CourseOut, CourseUpdate, CourseUpdateResponse

router = APIRouter(prefix="/courses", tags=["courses"])

@router.get("/", response_model=list[CourseBase])
def list_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return CourseController.list_courses(db, skip=skip, limit=limit)

@router.get("/public", response_model=list[CourseBase])
def get_public_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    return CourseController.get_public_courses(db, skip=skip, limit=limit)

@router.get("/{course_id}", response_model=CourseOut)
def get_course(course_id: int, db: Session = Depends(get_db)):
    return CourseController.get_course(db, course_id)

@router.get("/user/{user_id}", response_model=list[CourseByUserBase])
def get_user_courses(user_id: int, db: Session = Depends(get_db)):
    return CourseController.get_user_courses(db, user_id)

@router.post("/", response_model=CourseCreateResponse, status_code=201)
def create_course(payload: CourseCreate, db: Session = Depends(get_db)):
    return CourseController.create_course(db, payload)

@router.put("/{course_id}", response_model=CourseUpdateResponse)
def update_course(course_id: int, payload: CourseUpdate, db: Session = Depends(get_db)):
    return CourseController.update_course(db, course_id, payload)

@router.delete("/{course_id}")
def delete_course(course_id: int, db: Session = Depends(get_db)):
    return CourseController.delete_course(db, course_id)