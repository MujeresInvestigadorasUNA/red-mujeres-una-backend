from fastapi import HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from app.services.users_service import UsersService
from app.schemas.users import UserCreate, UserUpdate
from typing import Optional


class UserController:
    @staticmethod
    def list_users(db: Session, skip: int = 0, limit: int | None = None):
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
    async def register_with_photo(
        db: Session,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        user_type_id: int,
        photo: Optional[UploadFile] = None,
        user_profession: Optional[str] = None,
        user_description: Optional[str] = None,
        is_public: bool = False
    ):
        """
        Registra un usuario CON imagen de perfil.
        """
        try:
            return await UsersService.register_user_with_image(
                db=db,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                user_type_id=user_type_id,
                photo=photo,
                user_profession=user_profession,
                user_description=user_description,
                is_public=is_public
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @staticmethod
    def cleanup_firebase_user(db: Session, email: str):
        try:
            return UsersService.cleanup_firebase_user(db, email)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_profile_picture_url(db: Session, user_id: int, expires_minutes: int = 60):
        try:
            return UsersService.get_profile_picture_url(db, user_id, expires_minutes)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    async def update_profile_picture(
        db: Session,
        user_id: int,
        photo: UploadFile = File(...)
    ):
        """
        Actualiza la foto de perfil de un usuario.
        """
        try:
            return await UsersService.update_user_profile_picture(db, user_id, photo)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

    @staticmethod
    def update_user(db: Session, user_id: int, user: UserUpdate):
        try:
            UsersService.update_user(db, user_id, user)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def update_user_type(db: Session, user_id: int, user_type_id: int):
        try:
            UsersService.update_user_type(db, user_id, user_type_id)
            return {"success": True}
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def delete_user(db: Session, user_id: int):
        if not UsersService.delete_user(db, user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return {"status": "ok"}

    @staticmethod
    def get_researchers(db: Session, is_public_only: bool = False, skip: int = 0, limit: int | None = None):
        """Get researchers (user_type_id = 2). Optionally filter by is_public = True."""
        return UsersService.get_researchers(db, is_public_only, skip, limit)
    
    @staticmethod
    def login(db: Session, user_login):
        try:
            return UsersService.login(db, user_login)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")

    @staticmethod
    def exists(db: Session, email: str):
        try:
            existing = UsersService.get_by_email(db, email)
            return {"exists": existing is not None}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))