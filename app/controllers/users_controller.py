from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.services.users_service import UsersService
from app.schemas.users import UserCreate, UserUpdate

class UserController:
    @staticmethod
    def list_users(db: Session, skip: int = 0, limit: int = 100):
        return UsersService.list_users(db, skip, limit)

    @staticmethod
    def get_user(db: Session, user_id: int):
        try:
            return UsersService.get_user(db, user_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        
    @staticmethod
    def create_user(db: Session, user: UserCreate):
        try:
            return UsersService.create_user(db, user)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail="Internal Server Error" + str(e))

    @staticmethod
    def update_user(db: Session, user_id: int, user: UserUpdate):
        try:
            UsersService.update_user(db, user_id, user)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def delete_user(db: Session, user_id: int):
        if not UsersService.delete_user(db, user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return {"status": "ok"}
    
    @staticmethod
    def login(db: Session, user_login):
        try:
            return UsersService.login(db, user_login)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")