from sqlalchemy.orm import Session
from app.models.courses import Courses
from app.repositories.courses_repository import CoursesRepository
from app.schemas.courses import CourseCreate, CourseUpdate

class CoursesService:
    @staticmethod
    def list_courses(db: Session, skip: int = 0, limit: int = 50) -> list[Courses]:
        return CoursesRepository.list(db, skip=skip, limit=limit)

    @staticmethod
    def get_public_courses(db: Session, skip: int = 0, limit: int = 50) -> list[Courses]:
        return CoursesRepository.get_public_courses(db, skip=skip, limit=limit)

    @staticmethod
    def get_course(db: Session, course_id: int) -> Courses | None:
        return CoursesRepository.get_by_id(db, course_id)
    
    @staticmethod
    def get_user_courses(db: Session, user_id: int) -> list[Courses]:
        return CoursesRepository.get_by_user_id(db, user_id)

    @staticmethod
    def create_course(db: Session, payload: CourseCreate) -> dict:
        course = CoursesRepository.create(db, payload)

        # Persist the course to ensure the generated id is available
        db.commit()
        db.refresh(course)

        return { "id": course.id }

    @staticmethod
    def update_course(db: Session, course_id: int, payload: CourseUpdate) -> Courses | None:
        return CoursesRepository.update(
            db,
            course_id,
            title=payload.title,
            photo=payload.photo,
            description=payload.description,
            modality=payload.modality,
            max_registration_date=payload.max_registration_date,
            initial_date=payload.initial_date,
            final_date=payload.final_date,
            max_quotas=payload.max_quotas,
            is_public=payload.is_public
        )

    @staticmethod
    def delete_course(db: Session, course_id: int) -> bool:
        return CoursesRepository.delete(db, course_id)