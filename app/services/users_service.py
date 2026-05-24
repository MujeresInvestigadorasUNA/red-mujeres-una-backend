from sqlalchemy.orm import Session
from app.repositories.users_repository import UsersRepository
from app.repositories.user_types_repository import UserTypeRepository
from app.schemas.users import UserCreate, UserUpdate
from app.models.users import Users
from datetime import timedelta
from app.core.auth import create_access_token, hash_password, verify_password
from app.core.config import settings
from app.services.blob_storage_service import blob_storage_service
from fastapi import UploadFile, HTTPException, status
from typing import Optional
import io
import os
import logging
from azure.core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)

class UsersService:
    @staticmethod
    def list_users(db: Session, skip: int = 0, limit: int = 50) -> list[Users]:
        return UsersRepository.list(db, skip=skip, limit=limit)

    @staticmethod
    def get_user(db: Session, user_id: int) -> Users | None:
        user = UsersRepository.get_by_id(db, user_id)
        return user
    
    @staticmethod
    def get_by_email(db: Session, email: str) -> Users | None:
        return UsersRepository.get_by_email(db, email)

    @staticmethod
    def get_researchers(db: Session, is_public_only: bool = False, skip: int = 0, limit: int = 50) -> list[Users]:
        """Get all researchers or only those that are public."""
        return UsersRepository.get_researchers(db, is_public_only, skip, limit)

    @staticmethod
    async def register_user_with_image(
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
    ) -> dict:
        """
        Registra un usuario CON imagen de perfil.
        La imagen se sube a Blob Storage y se guarda la URL en BD.
        """
        try:
            # 1. Validar que el email no exista
            existing = UsersRepository.get_by_email(db, email)
            if existing:
                raise ValueError("Email already registered")

            # 1.1 Validar que el tipo de usuario exista antes de intentar insertar
            user_type = UserTypeRepository.get_by_id(db, user_type_id)
            if not user_type:
                raise ValueError(f"User type {user_type_id} does not exist")

            # 2. Validar imagen (sin subir aún)
            photo_blob_name = None
            photo_content = None
            photo_ext = ".jpg"

            if photo:
                allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
                if photo.content_type not in allowed_types:
                    raise ValueError(f"Invalid image type. Allowed: {', '.join(allowed_types)}")

                max_size = 5 * 1024 * 1024  # 5MB
                photo_content = await photo.read()
                if len(photo_content) > max_size:
                    raise ValueError("Image too large. Max 5MB")

                photo_ext = os.path.splitext(photo.filename)[1] or ".jpg"

            # 3. Crear usuario en BD (aún sin foto) para obtener el ID
            user = Users(
                email=email,
                password=hash_password(password),
                first_name=first_name,
                last_name=last_name,
                user_type_id=user_type_id,
                photo=None,
                user_profession=user_profession,
                user_description=user_description,
                is_public=is_public
            )

            db.add(user)
            db.flush()  # obtiene user.id sin commit

            # 4. Subir la foto (si se envió) con nombre determinístico
            if photo_content:
                subfolder = f"users/{user.id}/"
                fixed_blob_name = f"profile_picture{photo_ext}"
                photo_file = io.BytesIO(photo_content)

                upload_result = blob_storage_service.upload_file(
                    file_content=photo_file,
                    file_name=photo.filename,
                    container_type="images",
                    metadata={"type": "profile", "user_id": str(user.id)},
                    subfolder=subfolder,
                    fixed_blob_name=fixed_blob_name,
                )

                photo_blob_name = upload_result["blob_name"]
                user.photo = upload_result["url"]

            # 5. Confirmar transacción
            db.commit()
            db.refresh(user)

            # 6. Generar token JWT
            access_token = create_access_token(
                data={"sub": user.email},
                expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            )

            return {
                "success": True,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "photo_url": user.photo,
                    "user_type_id": user.user_type_id
                },
                "access_token": access_token
            }

        except ValueError as e:
            db.rollback()
            raise e
        except Exception as e:
            db.rollback()
            # Si falló el registro, eliminar la imagen si se subió
            if photo_blob_name:
                try:
                    blob_storage_service.delete_file(
                        blob_name=photo_blob_name,
                        container_type="images"
                    )
                except:
                    pass  # Ignorar si no se puede eliminar
            
            raise Exception(f"Error registering user: {str(e)}")

    @staticmethod
    def get_profile_picture_url(db: Session, user_id: int, expires_minutes: int = 60) -> dict:
        from urllib.parse import urlparse
        user = UsersRepository.get_by_id(db, user_id)
        if not user.photo:
            raise ValueError("User has no profile picture")

        parsed = urlparse(user.photo)
        path = parsed.path.lstrip("/")
        parts = path.split("/", 1)
        if len(parts) != 2:
            raise ValueError("Invalid photo URL")

        container_name, blob_name = parts
        container_map = {
            settings.AZURE_BLOB_CONTAINER_IMAGES: "images",
            settings.AZURE_BLOB_CONTAINER_DOCUMENTS: "documents",
        }
        container_type = container_map.get(container_name)
        if container_type != "images":
            raise ValueError("Photo is not stored in the images container")

        result = blob_storage_service.generate_blob_sas_url(
            blob_name=blob_name,
            container_type="images",
            expires_minutes=expires_minutes,
            content_type="image/jpeg",
        )
        return {"url": result["url"], "expires_at": result["expires_at"]}

    @staticmethod
    async def update_user_profile_picture(
        db: Session,
        user_id: int,
        photo: UploadFile
    ) -> dict:
        """
        Actualiza SOLO la foto de perfil de un usuario existente.
        Elimina la foto anterior si existe para evitar acumular imágenes sin usar.
        """
        try:
            # 1. Obtener usuario
            user = UsersRepository.get_by_id(db, user_id)
            if not user:
                raise ValueError("User not found")

            # 2. Validar imagen
            allowed_types = {"image/jpeg", "image/png", "image/webp"}
            if photo.content_type not in allowed_types:
                raise ValueError("Invalid image type")

            max_size = 5 * 1024 * 1024
            photo_content = await photo.read()
            if len(photo_content) > max_size:
                raise ValueError("Image too large. Max 5MB")

            # Nombre de blob determinístico para esta foto de perfil
            ext = os.path.splitext(photo.filename)[1] or ".jpg"
            subfolder = f"users/{user_id}/"
            fixed_blob_name = f"profile_picture{ext}"
            full_blob_name = f"{subfolder.rstrip('/')}/{fixed_blob_name}"

            # 3. Eliminar foto anterior determinísticamente (mismo nombre)
            try:
                blob_storage_service.delete_file(
                    blob_name=full_blob_name,
                    container_type="images"
                )
                logger.info(f"Foto anterior de usuario {user_id} eliminada: {full_blob_name}")
            except ResourceNotFoundError:
                # Si no existe, no es un error; se continuará con la subida nueva
                logger.debug(f"Foto anterior no encontrada para usuario {user_id}, se continuará con la nueva carga")
            except Exception as e:
                logger.warning(f"No se pudo eliminar foto anterior de usuario {user_id}: {str(e)}")

            # 4. Subir nueva foto
            photo_file = io.BytesIO(photo_content)
            upload_result = blob_storage_service.upload_file(
                file_content=photo_file,
                file_name=photo.filename,
                container_type="images",
                metadata={"type": "profile", "user_id": str(user_id)},
                subfolder=subfolder,
                fixed_blob_name=fixed_blob_name,
            )

            # 5. Actualizar usuario
            user.photo = upload_result["url"]
            db.commit()
            db.refresh(user)

            return {
                "success": True,
                "user_id": user.id,
                "photo_url": user.photo,
                "message": "Profile picture updated successfully"
            }

        except ValueError as e:
            db.rollback()
            raise e
        except Exception as e:
            db.rollback()
            raise Exception(f"Error updating profile picture: {str(e)}")

    @staticmethod
    def create_user(db: Session, payload: UserCreate) -> dict:
        # Business rule example: unique email
        existing = UsersRepository.get_by_email(db, payload.email)
        if existing:
            raise ValueError("Email already registered")

        user_type = UserTypeRepository.get_by_id(db, payload.user_type_id)
        if not user_type:
            raise ValueError(f"User type {payload.user_type_id} does not exist")
    
        # Hash password before creating user
        payload.password = hash_password(payload.password)
        user = UsersRepository.create(db, payload)

        # Persist the user to ensure the generated id is available
        db.commit()
        db.refresh(user)

        # Create the JWT token
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )

        return { "id": user.id, "access_token": access_token }

    @staticmethod
    def update_user(db: Session, user_id: int, payload: UserUpdate) -> Users | None:

        # If email change is requested, check uniqueness
        if payload.email:
            other = UsersRepository.get_by_email(db, payload.email)
            if other and other.id != user_id:
                raise ValueError("Email already registered to another user")
        
        # Hash password if being updated
        password_to_save = hash_password(payload.password) if payload.password else None

        return UsersRepository.update(
            db,
            user_id,
            email=payload.email,
            first_name=payload.first_name,
            last_name=payload.last_name,
            password=password_to_save,
            photo=payload.photo,
            user_profession=payload.user_profession,
            user_description=payload.user_description,
            is_public=payload.is_public,
            user_type_id=payload.user_type_id
        )

    @staticmethod
    def delete_user(db: Session, user_id: int) -> bool:
        user = UsersRepository.get_by_id(db, user_id)
        if not user:
            return False
        UsersRepository.delete(db, user)
        return True

    @staticmethod
    def login(db: Session, user_login) -> dict:
        # Check if the user exists
        user = UsersService.get_by_email(db, user_login.email)
        
        # Verify password (using bcrypt)
        if user is None or not verify_password(user_login.password, user.password):
            raise ValueError("Invalid credentials")

        # Create the JWT token
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        
        # Return user and token
        return {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "user_type_id": user.user_type_id,
            "access_token": access_token,
        }