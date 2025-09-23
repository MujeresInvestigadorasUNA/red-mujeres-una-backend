from sqlalchemy.orm import Session
from sqlalchemy import select, func, delete
from fastapi import HTTPException, status

from app.models.course import Course, CourseSession, CourseEnrollment, CourseStatus
from app.schemas.course import CourseCreate, CourseUpdate, CourseSessionCreate

# ---- Helpers ----
def _enrolled_count(db: Session, course_id: int) -> int:
    stmt = select(func.count(CourseEnrollment.id)).where(CourseEnrollment.course_id == course_id, CourseEnrollment.waitlisted == False)
    return db.execute(stmt).scalar_one()

def _course_by_id(db: Session, course_id: int) -> Course | None:
    stmt = select(Course).where(Course.id == course_id)
    return db.execute(stmt).scalar_one_or_none()

# ---- CRUD Curso ----
def create_course(db: Session, *, creator_id: int, data: CourseCreate) -> Course:
    course = Course(
        title=data.title.strip(),
        description=(data.description or "").strip() or None,
        instructor_name=data.instructor_name.strip(),
        created_by=creator_id,
        capacity=data.capacity,
        status=CourseStatus.published,
    )
    db.add(course)
    db.flush()  # para tener course.id

    # sesiones opcionales
    for s in data.sessions:
        _add_session(db, course.id, s)

    db.commit()
    db.refresh(course)
    return course

def get_course(db: Session, *, course_id: int) -> Course:
    course = _course_by_id(db, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course

def list_courses(db: Session, *, skip: int = 0, limit: int = 50, status_filter: CourseStatus | None = None) -> list[Course]:
    stmt = select(Course)
    if status_filter:
        stmt = stmt.where(Course.status == status_filter)
    stmt = stmt.offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())

def update_course(db: Session, *, course_id: int, editor_id: int, data: CourseUpdate) -> Course:
    course = get_course(db, course_id=course_id)
    if course.created_by != editor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only creator can edit the course")

    if data.title is not None:
        course.title = data.title.strip()
    if data.description is not None:
        course.description = data.description.strip() or None
    if data.instructor_name is not None:
        course.instructor_name = data.instructor_name.strip()
    if data.capacity is not None:
        # no permitir bajar por debajo de inscritos actuales
        enrolled_now = _enrolled_count(db, course.id)
        if data.capacity < enrolled_now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Capacity cannot be lower than current enrollment ({enrolled_now})")
        course.capacity = data.capacity
    if data.status is not None:
        course.status = CourseStatus(data.status)

    db.add(course)
    db.commit()
    db.refresh(course)
    return course

def delete_course(db: Session, *, course_id: int, editor_id: int) -> None:
    course = get_course(db, course_id=course_id)
    if course.created_by != editor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only creator can delete the course")
    db.execute(delete(Course).where(Course.id == course_id))
    db.commit()

# ---- Sesiones ----
def _add_session(db: Session, course_id: int, s: CourseSessionCreate) -> CourseSession:
    session = CourseSession(
        course_id=course_id,
        date=s.date,
        start_time=s.start_time,
        end_time=s.end_time,
        timezone=s.timezone,
        location=s.location,
    )
    db.add(session)
    return session

def add_session(db: Session, *, course_id: int, editor_id: int, s: CourseSessionCreate) -> Course:
    course = get_course(db, course_id=course_id)
    if course.created_by != editor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only creator can manage sessions")
    _add_session(db, course.id, s)
    db.commit()
    db.refresh(course)
    return course

def remove_session(db: Session, *, course_id: int, session_id: int, editor_id: int) -> Course:
    course = get_course(db, course_id=course_id)
    if course.created_by != editor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only creator can manage sessions")
    db.execute(delete(CourseSession).where(CourseSession.id == session_id, CourseSession.course_id == course_id))
    db.commit()
    db.refresh(course)
    return course

# ---- Inscripciones ----
def enroll(db: Session, *, course_id: int, user_id: int):
    course = get_course(db, course_id=course_id)
    # ya inscrito?
    existing = db.execute(
        select(CourseEnrollment).where(CourseEnrollment.course_id == course_id, CourseEnrollment.user_id == user_id)
    ).scalar_one_or_none()
    if existing:
        return existing  # idempotente

    enrolled_now = _enrolled_count(db, course_id)
    waitlisted = enrolled_now >= course.capacity

    enrollment = CourseEnrollment(course_id=course_id, user_id=user_id, waitlisted=waitlisted)
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return enrollment

def unenroll(db: Session, *, course_id: int, user_id: int):
    # elimina inscripción
    db.execute(delete(CourseEnrollment).where(CourseEnrollment.course_id == course_id, CourseEnrollment.user_id == user_id))
    db.commit()

def list_enrollments(db: Session, *, course_id: int):
    from app.models.user import User
    stmt = (
        select(User.id, User.first_name, User.last_name, User.email)
        .join(CourseEnrollment, CourseEnrollment.user_id == User.id)
        .where(CourseEnrollment.course_id == course_id, CourseEnrollment.waitlisted == False)
        .order_by(User.first_name, User.last_name)
    )
    return db.execute(stmt).all()
