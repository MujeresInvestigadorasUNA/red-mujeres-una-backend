from sqlalchemy.orm import Session
from app.schemas.course import (
    CourseCreate, CourseUpdate, CourseOut, CourseSessionCreate,
    EnrollResponse, EnrollmentListItem
)
from app.services import course_service as svc

def create(db: Session, *, creator_id: int, payload: CourseCreate) -> CourseOut:
    course = svc.create_course(db, creator_id=creator_id, data=payload)
    return _to_out(db, course)

def update(db: Session, *, course_id: int, editor_id: int, payload: CourseUpdate) -> CourseOut:
    course = svc.update_course(db, course_id=course_id, editor_id=editor_id, data=payload)
    return _to_out(db, course)

def get_one(db: Session, *, course_id: int) -> CourseOut:
    course = svc.get_course(db, course_id=course_id)
    return _to_out(db, course)

def list_many(db: Session, *, skip: int, limit: int) -> list[CourseOut]:
    courses = svc.list_courses(db, skip=skip, limit=limit)
    return [_to_out(db, c) for c in courses]

def add_session(db: Session, *, course_id: int, editor_id: int, payload: CourseSessionCreate) -> CourseOut:
    course = svc.add_session(db, course_id=course_id, editor_id=editor_id, s=payload)
    return _to_out(db, course)

def remove_session(db: Session, *, course_id: int, session_id: int, editor_id: int) -> CourseOut:
    course = svc.remove_session(db, course_id=course_id, session_id=session_id, editor_id=editor_id)
    return _to_out(db, course)

def enroll(db: Session, *, course_id: int, user_id: int) -> EnrollResponse:
    en = svc.enroll(db, course_id=course_id, user_id=user_id)
    return EnrollResponse(course_id=en.course_id, user_id=en.user_id, waitlisted=en.waitlisted)

def unenroll(db: Session, *, course_id: int, user_id: int) -> None:
    svc.unenroll(db, course_id=course_id, user_id=user_id)

def list_enrollments(db: Session, *, course_id: int) -> list[EnrollmentListItem]:
    rows = svc.list_enrollments(db, course_id=course_id)
    return [EnrollmentListItem(user_id=r[0], first_name=r[1], last_name=r[2], email=r[3]) for r in rows]

# ----- mapeo a CourseOut -----
def _to_out(db: Session, course) -> CourseOut:
    enrolled = svc._enrolled_count(db, course.id)  # type: ignore
    return CourseOut.model_validate({
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "instructor_name": course.instructor_name,
        "created_by": course.created_by,
        "capacity": course.capacity,
        "status": course.status.value,
        "sessions": course.sessions,
        "enrolled_count": enrolled,
    })
