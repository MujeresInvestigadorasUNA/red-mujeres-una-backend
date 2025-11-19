from sqlalchemy import desc
from sqlalchemy.orm import Session
from app.models.courses import Courses
from app.schemas.courses import CourseCreate

class CoursesRepository:
    @staticmethod
    def list(db: Session, skip: int = 0, limit: int = 100):
        return db.query(Courses).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_public_courses(db: Session, skip: int = 0, limit: int = 100):
        return db.query(Courses).filter(Courses.is_public == True).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_id(db: Session, course_id: int):
        course = db.query(Courses).filter(Courses.id == course_id).first()
        if not course:
            raise ValueError("Course not found")
        return course

    @staticmethod
    def get_by_user_id(db: Session, user_id: int):
        return db.query(Courses)\
                .filter(Courses.user_id == user_id)\
                .order_by(desc(Courses.id))\
                .all()

    @staticmethod
    def create(db: Session, payload: CourseCreate):
        course = Courses(
            user_id=payload.user_id
        )
        db.add(course)
        db.flush()
        return course

    @staticmethod
    def update(
        db : Session,
            course_id : int,
            title : str,
            photo : str,
            description : str,
            modality : str,
            max_registration_date : str,
            initial_date : str,
            final_date : str,
            max_quotas : int,
            is_public : bool
        ):
        course = db.query(Courses).filter(Courses.id == course_id).first()
        if not course:
            raise ValueError("Course not found")

        course.title = title
        course.photo = photo
        course.description = description
        course.modality = modality
        course.max_registration_date = max_registration_date
        course.initial_date = initial_date
        course.final_date = final_date
        course.max_quotas = max_quotas
        course.is_public = is_public

        db.commit()
        db.refresh(course)
        return True

    @staticmethod
    def delete(db: Session, course_id: int):
        course = db.query(Courses).filter(Courses.id == course_id).first()
        if not course:
            return False
        db.delete(course)
        db.commit()
        return True