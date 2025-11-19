from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.schemas.courses import CourseBase, CourseCreate, CourseUpdate
from app.services.courses_service import CoursesService

class CourseController:
    @staticmethod
    def list_courses(db: Session, skip: int = 0, limit: int = 100):
        return CoursesService.list_courses(db, skip, limit)

    @staticmethod
    def get_public_courses(db: Session, skip: int = 0, limit: int = 100):
        return CoursesService.get_public_courses(db, skip=skip, limit=limit)

    @staticmethod
    def get_course(db: Session, course_id: int):
        try:
            return CoursesService.get_course(db, course_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
    @staticmethod
    def get_user_courses(db: Session, user_id: int):
        try:
            return CoursesService.get_user_courses(db, user_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
    @staticmethod
    def create_course(db: Session, course: CourseCreate):
        try:
            return CoursesService.create_course(db, course)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail="Internal Server Error" + str(e))

    @staticmethod
    def update_course(db: Session, course_id: int, course: CourseUpdate):
        try:
            CoursesService.update_course(db, course_id, course)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def delete_course(db: Session, course_id: int):
        if not CoursesService.delete_course(db, course_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
        return {"status": "ok"}