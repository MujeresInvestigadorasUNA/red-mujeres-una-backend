"""
Ejemplo de cómo registrar un usuario CON imagen usando Blob Storage.

Este archivo muestra cómo integrar el upload de imagen en el flujo de registro.
"""

# ============================================================================
# OPCIÓN 1: REGISTRO CON IMAGEN (TODO EN UN ENDPOINT)
# ============================================================================

from fastapi import UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from app.services.blob_storage_service import blob_storage_service
from app.models.users import Users
from app.repositories.users_repository import UsersRepository
from app.schemas.users import UserCreate
from app.core.auth import hash_password
from typing import Optional
import io


async def register_user_with_image(
    db: Session,
    email: str = Form(...),
    password: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    user_type_id: int = Form(...),
    photo: Optional[UploadFile] = File(None)  # IMAGEN OPCIONAL
) -> dict:
    """
    Registra un usuario CON imagen.
    
    El frontend envía un multipart/form-data con:
    - email, password, first_name, last_name, user_type_id (texto)
    - photo (archivo binario - opcional)
    """
    try:
        # 1. Validar que el email no exista
        existing = UsersRepository.get_by_email(db, email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # 2. Si hay imagen, validar y subir a Blob Storage
        photo_url = None
        photo_blob_name = None
        
        if photo:
            # Validar tipo de archivo
            allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
            if photo.content_type not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid image type. Allowed: {', '.join(allowed_types)}"
                )

            # Validar tamaño (máximo 5MB para fotos de perfil)
            max_size = 5 * 1024 * 1024  # 5MB
            photo_content = await photo.read()
            if len(photo_content) > max_size:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Image too large. Max 5MB"
                )

            # Subir a Blob Storage
            photo_file = io.BytesIO(photo_content)
            upload_result = blob_storage_service.upload_file(
                file_content=photo_file,
                file_name=photo.filename,
                container_type="images",
                metadata={"type": "profile", "email": email},
                subfolder=f"users/profile-pictures"
            )
            
            photo_url = upload_result["url"]
            photo_blob_name = upload_result["blob_name"]

        # 3. Crear usuario en BD
        user = Users(
            email=email,
            password=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            user_type_id=user_type_id,
            photo=photo_url  # ← Guardamos la URL del blob
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)

        # 4. Si es investigadora, crear registro en forums
        if user_type_id == 2:
            from app.repositories.forums_repository import ForumsRepository
            ForumsRepository.create(
                db,
                user_id=user.id,
                user_profession=None,
                user_description=None
            )

        # 5. Generar token JWT
        from app.core.auth import create_access_token
        from datetime import timedelta
        from app.core.config import settings

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
                "photo_url": user.photo,  # ← URL de Blob Storage
                "user_type_id": user.user_type_id
            },
            "access_token": access_token
        }

    except HTTPException as e:
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
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error registering user: {str(e)}"
        )


# ============================================================================
# OPCIÓN 2: ACTUALIZAR FOTO DE USUARIO DESPUÉS DEL REGISTRO
# ============================================================================

async def update_user_profile_picture(
    db: Session,
    user_id: int,
    photo: UploadFile = File(...)
) -> dict:
    """
    Actualiza SOLO la foto de perfil de un usuario existente.
    
    Endpoint separado para cambiar/actualizar la foto.
    """
    try:
        # 1. Obtener usuario
        user = UsersRepository.get_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # 2. Validar imagen
        allowed_types = {"image/jpeg", "image/png", "image/webp"}
        if photo.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid image type"
            )

        max_size = 5 * 1024 * 1024
        photo_content = await photo.read()
        if len(photo_content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Image too large. Max 5MB"
            )

        # 3. Eliminar foto anterior si existe
        if user.photo:
            try:
                # Extraer blob_name de la URL (último segmento)
                blob_name = user.photo.split("/")[-1]
                blob_storage_service.delete_file(
                    blob_name=blob_name,
                    container_type="images"
                )
            except:
                pass

        # 4. Subir nueva foto
        photo_file = io.BytesIO(photo_content)
        upload_result = blob_storage_service.upload_file(
            file_content=photo_file,
            file_name=photo.filename,
            container_type="images",
            metadata={"type": "profile", "user_id": str(user_id)},
            subfolder=f"users/{user_id}"
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

    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# VALIDACIONES RECOMENDADAS
# ============================================================================

from PIL import Image

def validate_image_file(file_content: bytes, max_size_mb: int = 5) -> bool:
    """
    Valida que un archivo sea una imagen válida.
    """
    max_bytes = max_size_mb * 1024 * 1024
    
    if len(file_content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image too large. Max {max_size_mb}MB"
        )
    
    try:
        # Intenta abrir como imagen (valida que sea imagen real)
        img = Image.open(io.BytesIO(file_content))
        img.verify()
        
        # Validar dimensiones (ej: máximo 5000x5000)
        if img.width > 5000 or img.height > 5000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image dimensions too large. Max 5000x5000 pixels"
            )
        
        return True
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or corrupted image file"
        )
