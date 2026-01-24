"""
Ejemplos de cómo usar el BlobStorageService internamente en la aplicación.
Estos ejemplos muestran integración con usuarios, cursos y otros servicios.
"""

# ============================================================================
# EJEMPLO 1: Guardar foto de perfil de usuario
# ============================================================================

from fastapi import UploadFile
from sqlalchemy.orm import Session
from app.services.blob_storage_service import blob_storage_service
from app.models.users import Users
from app.repositories.users_repository import UsersRepository


def update_user_profile_picture(
    db: Session,
    user_id: int,
    profile_picture: UploadFile
) -> dict:
    """
    Sube la foto de perfil de un usuario a Blob Storage
    y guarda la URL en la base de datos.
    """
    try:
        # Sube la imagen a Azure Blob Storage
        upload_result = blob_storage_service.upload_file(
            file_content=profile_picture.file,
            file_name=profile_picture.filename,
            container_type="images",
            metadata={"user_id": str(user_id), "type": "profile"},
            subfolder=f"users/{user_id}"  # Organiza por usuario
        )

        # Actualiza el usuario con la URL de la imagen
        user = UsersRepository.get_by_id(db, user_id)
        if user:
            user.profile_picture_url = upload_result["url"]
            user.profile_picture_blob_name = upload_result["blob_name"]
            db.commit()
            db.refresh(user)

        return {
            "success": True,
            "user_id": user_id,
            "image_url": upload_result["url"],
            "blob_name": upload_result["blob_name"]
        }
    except Exception as e:
        db.rollback()
        raise Exception(f"Error updating profile picture: {str(e)}")


# ============================================================================
# EJEMPLO 2: Guardar documento de curso
# ============================================================================

def upload_course_document(
    db: Session,
    course_id: int,
    document: UploadFile,
    document_type: str = "lecture_material"
) -> dict:
    """
    Sube un documento (PDF, Word, etc) para un curso.
    Organiza los archivos por curso.
    """
    try:
        # Sube el documento
        upload_result = blob_storage_service.upload_file(
            file_content=document.file,
            file_name=document.filename,
            container_type="documents",
            metadata={
                "course_id": str(course_id),
                "document_type": document_type,
                "content_type": document.content_type
            },
            subfolder=f"courses/{course_id}/{document_type}"
        )

        # Opcionalmente: guarda la referencia en la BD
        # course.documents.append(DocumentModel(
        #     blob_name=upload_result["blob_name"],
        #     url=upload_result["url"],
        #     filename=document.filename
        # ))
        # db.commit()

        return upload_result
    except Exception as e:
        raise Exception(f"Error uploading course document: {str(e)}")


# ============================================================================
# EJEMPLO 3: Guardar imagen de portada de curso
# ============================================================================

def upload_course_cover_image(
    db: Session,
    course_id: int,
    cover_image: UploadFile
) -> dict:
    """
    Sube la imagen de portada/banner de un curso.
    """
    try:
        upload_result = blob_storage_service.upload_file(
            file_content=cover_image.file,
            file_name=cover_image.filename,
            container_type="images",
            metadata={"course_id": str(course_id), "type": "cover"},
            subfolder=f"courses/{course_id}"
        )

        # Actualizar course.cover_image_url en BD
        # course.cover_image_url = upload_result["url"]
        # db.commit()

        return upload_result
    except Exception as e:
        raise Exception(f"Error uploading course cover: {str(e)}")


# ============================================================================
# EJEMPLO 4: Guardar documentos vectorizados (para búsqueda semántica)
# ============================================================================

import json
import io
from datetime import datetime


def save_vectorized_document(
    document_id: int,
    document_text: str,
    embeddings: list,
    embedding_model: str = "text-embedding-3-small"
) -> dict:
    """
    Guarda un documento vectorizado (embeddings) para búsqueda semántica.
    Los embeddings se guardan como JSON en el contenedor 'vectorized'.
    
    Args:
        document_id: ID del documento original
        document_text: Texto original del documento
        embeddings: Lista/array de embeddings generados
        embedding_model: Modelo usado para generar embeddings
    """
    try:
        # Crea estructura JSON con los embeddings
        vectorized_data = {
            "document_id": document_id,
            "text_sample": document_text[:500],  # Primeros 500 chars como referencia
            "embeddings": embeddings,
            "embedding_model": embedding_model,
            "created_at": datetime.utcnow().isoformat(),
            "text_length": len(document_text)
        }

        # Convierte a JSON bytes
        json_content = json.dumps(vectorized_data)
        file_content = io.BytesIO(json_content.encode('utf-8'))

        # Sube el archivo vectorizado
        upload_result = blob_storage_service.upload_file(
            file_content=file_content,
            file_name=f"doc_{document_id}_vectors.json",
            container_type="vectorized",
            metadata={
                "document_id": str(document_id),
                "embedding_model": embedding_model
            },
            subfolder="documents"
        )

        # Opcionalmente: guarda referencia en BD
        # document.vectorized_blob_name = upload_result["blob_name"]
        # db.commit()

        return {
            "success": True,
            "blob_name": upload_result["blob_name"],
            "url": upload_result["url"],
            "embedding_count": len(embeddings)
        }
    except Exception as e:
        raise Exception(f"Error saving vectorized document: {str(e)}")


# ============================================================================
# EJEMPLO 5: Recuperar documento (descarga desde blob storage)
# ============================================================================

def get_course_document(blob_name: str) -> bytes:
    """
    Descarga un documento del blob storage.
    Útil para servir archivos a usuarios.
    """
    try:
        content = blob_storage_service.download_file(
            blob_name=blob_name,
            container_type="documents"
        )
        return content
    except Exception as e:
        raise Exception(f"Error downloading document: {str(e)}")


# ============================================================================
# EJEMPLO 6: Eliminar imagen de usuario (limpieza)
# ============================================================================

def delete_user_profile_picture(db: Session, user_id: int) -> bool:
    """
    Elimina la foto de perfil de un usuario tanto de Blob Storage
    como de la base de datos.
    """
    try:
        user = UsersRepository.get_by_id(db, user_id)
        if user and user.profile_picture_blob_name:
            # Elimina del blob storage
            blob_storage_service.delete_file(
                blob_name=user.profile_picture_blob_name,
                container_type="images"
            )

            # Limpia la referencia en BD
            user.profile_picture_url = None
            user.profile_picture_blob_name = None
            db.commit()

        return True
    except Exception as e:
        db.rollback()
        raise Exception(f"Error deleting profile picture: {str(e)}")


# ============================================================================
# EJEMPLO 7: Listar documentos de un curso
# ============================================================================

def list_course_documents(course_id: int) -> list:
    """
    Lista todos los documentos de un curso.
    """
    try:
        # Filtra por prefijo (carpeta de curso)
        documents = blob_storage_service.list_files(
            container_type="documents",
            prefix=f"courses/{course_id}"
        )
        return documents
    except Exception as e:
        raise Exception(f"Error listing course documents: {str(e)}")


# ============================================================================
# INTEGRACIÓN COMPLETA EN UN CONTROLADOR
# ============================================================================

class UsersController:
    """Ejemplo de controlador que usa Blob Storage internamente."""

    @staticmethod
    def update_user_with_image(
        db: Session,
        user_id: int,
        profile_picture: UploadFile
    ) -> dict:
        """
        Actualiza el perfil del usuario incluyendo foto.
        """
        try:
            # Primero, sube la imagen
            upload_result = blob_storage_service.upload_file(
                file_content=profile_picture.file,
                file_name=profile_picture.filename,
                container_type="images",
                metadata={"user_id": str(user_id)},
                subfolder=f"users/{user_id}"
            )

            # Actualiza el usuario en BD
            user = UsersRepository.get_by_id(db, user_id)
            user.profile_picture_url = upload_result["url"]
            db.commit()
            db.refresh(user)

            return {
                "user_id": user.id,
                "email": user.email,
                "profile_picture_url": user.profile_picture_url
            }
        except Exception as e:
            db.rollback()
            raise ValueError(f"Error updating user: {str(e)}")
