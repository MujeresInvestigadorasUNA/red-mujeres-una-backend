"""
Azure Blob Storage service para gestionar documentos, imágenes y contenido vectorizado.
Se usa internamente dentro de otros servicios (users_service, event_service, etc).
"""

import io
import os
import re
import unicodedata
from datetime import datetime, timedelta
from typing import BinaryIO, Optional
from azure.storage.blob import BlobServiceClient, ContainerClient, BlobSasPermissions, generate_blob_sas
from azure.core.exceptions import AzureError, ResourceNotFoundError
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class BlobStorageService:
    """Servicio para gestionar operaciones de Azure Blob Storage."""

    def __init__(self):
        """Inicializa el cliente de BlobServiceClient basado en configuración."""
        self.connection_string = settings.AZURE_STORAGE_CONNECTION_STRING
        self.account_name = settings.AZURE_STORAGE_ACCOUNT_NAME
        self.account_key = settings.AZURE_STORAGE_ACCOUNT_KEY

        # Inicializa el cliente basado en credenciales disponibles
        if self.connection_string:
            try:
                self.client = BlobServiceClient.from_connection_string(self.connection_string)
                logger.info("Blob Storage client initialized with connection string")
            except Exception as e:
                logger.warning(f"Failed to initialize Blob Storage: {e}")
                self.client = None
        elif self.account_name and self.account_key:
            try:
                account_url = f"https://{self.account_name}.blob.core.windows.net"
                self.client = BlobServiceClient(
                    account_url=account_url,
                    credential=self.account_key
                )
                logger.info("Blob Storage client initialized with account name/key")
            except Exception as e:
                logger.warning(f"Failed to initialize Blob Storage: {e}")
                self.client = None
        else:
            self.client = None
            logger.warning("Azure Blob Storage no configurado")

    def _get_container_client(self, container_name: str) -> Optional[ContainerClient]:
        """Obtiene o crea un cliente de contenedor."""
        if not self.client:
            raise ValueError("Blob Storage client no inicializado")

        try:
            container_client = self.client.get_container_client(container_name)
            try:
                container_client.get_container_properties()
            except AzureError:
                container_client = self.client.create_container(name=container_name)
                logger.info(f"Contenedor creado: {container_name}")
            return container_client
        except AzureError as e:
            logger.error(f"Error accediendo contenedor {container_name}: {e}")
            raise

    @staticmethod
    def _sanitize_metadata_key(key: str) -> str:
        """Normaliza claves de metadata para Azure Blob (ASCII + [a-z0-9_])."""
        normalized = unicodedata.normalize("NFKD", str(key)).encode("ascii", "ignore").decode("ascii")
        normalized = normalized.lower().strip().replace("-", "_").replace(" ", "_")
        normalized = re.sub(r"[^a-z0-9_]", "", normalized)
        if not normalized:
            normalized = "meta"
        if not (normalized[0].isalpha() or normalized[0] == "_"):
            normalized = f"m_{normalized}"
        return normalized[:128]

    @staticmethod
    def _sanitize_metadata_value(value: object) -> str:
        """Convierte valores de metadata a ASCII seguro para headers HTTP de Azure."""
        normalized = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
        normalized = normalized.replace("\r", " ").replace("\n", " ").strip()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized[:1024]

    def _sanitize_metadata(self, metadata: Optional[dict]) -> dict:
        """Sanitiza metadata y evita colisiones de claves tras normalizacion."""
        if not metadata:
            return {}

        sanitized = {}
        collisions = {}
        for raw_key, raw_value in metadata.items():
            key = self._sanitize_metadata_key(raw_key)
            if key in sanitized:
                collisions[key] = collisions.get(key, 0) + 1
                key = f"{key}_{collisions[key]}"
            sanitized[key] = self._sanitize_metadata_value(raw_value)

        return sanitized

    def upload_file(
        self,
        file_content: BinaryIO,
        file_name: str,
        container_type: str = "documents",
        metadata: Optional[dict] = None,
        subfolder: str = "",
        fixed_blob_name: Optional[str] = None,
    ) -> dict:
        """
        Sube un archivo al blob storage.

        Args:
            file_content: Objeto con método read()
            file_name: Nombre del archivo
            container_type: Tipo de contenedor ('documents', 'images', 'vectorized')
            metadata: Dict opcional con metadata
            subfolder: Subcarpeta dentro del contenedor (ej: 'user_123/', 'course_456/')

        Returns:
            Dict con detalles del upload (url, blob_name, timestamp)
        """
        try:
            # Mapea el tipo de contenedor al nombre real
            container_map = {
                "documents": settings.AZURE_BLOB_CONTAINER_DOCUMENTS,
                "images": settings.AZURE_BLOB_CONTAINER_IMAGES,
                "vectorized": settings.AZURE_BLOB_CONTAINER_VECTORIZED,
            }
            container_name = container_map.get(container_type, settings.AZURE_BLOB_CONTAINER_DOCUMENTS)
            container_client = self._get_container_client(container_name)

            # Timestamp siempre disponible para metadata
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

            # Genera nombre del blob; usa nombre fijo si se provee
            if subfolder:
                subfolder = subfolder.rstrip('/') + '/'

            if fixed_blob_name:
                blob_name = f"{subfolder}{fixed_blob_name}"
            else:
                base_name = os.path.splitext(file_name)[0]
                ext = os.path.splitext(file_name)[1]
                blob_name = f"{subfolder}{base_name}_{timestamp}{ext}"

            # Prepara metadata
            blob_metadata = self._sanitize_metadata(metadata)
            blob_metadata.update({
                "original_name": self._sanitize_metadata_value(file_name),
                "uploaded_at": self._sanitize_metadata_value(timestamp),
            })

            # Sube el blob
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.upload_blob(file_content, overwrite=True, metadata=blob_metadata)

            logger.info(f"Archivo subido: {blob_name}")
            return {
                "blob_name": blob_name,
                "url": blob_client.url,
                "container": container_name,
                "timestamp": timestamp,
                "file_name": file_name,
            }
        except AzureError as e:
            logger.error(f"Error subiendo archivo: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado subiendo archivo: {e}")
            raise

    def download_file(self, blob_name: str, container_type: str = "documents") -> bytes:
        """
        Descarga un archivo del blob storage.

        Args:
            blob_name: Nombre del blob
            container_type: Tipo de contenedor

        Returns:
            Contenido como bytes
        """
        try:
            container_map = {
                "documents": settings.AZURE_BLOB_CONTAINER_DOCUMENTS,
                "images": settings.AZURE_BLOB_CONTAINER_IMAGES,
                "vectorized": settings.AZURE_BLOB_CONTAINER_VECTORIZED,
            }
            container_name = container_map.get(container_type, settings.AZURE_BLOB_CONTAINER_DOCUMENTS)
            container_client = self._get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)
            download_stream = blob_client.download_blob()
            return download_stream.readall()
        except AzureError as e:
            logger.error(f"Error descargando {blob_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado descargando archivo: {e}")
            raise

    def delete_file(self, blob_name: str, container_type: str = "documents") -> bool:
        """
        Elimina un archivo del blob storage.

        Args:
            blob_name: Nombre del blob
            container_type: Tipo de contenedor

        Returns:
            True si se eliminó exitosamente
        """
        try:
            container_map = {
                "documents": settings.AZURE_BLOB_CONTAINER_DOCUMENTS,
                "images": settings.AZURE_BLOB_CONTAINER_IMAGES,
                "vectorized": settings.AZURE_BLOB_CONTAINER_VECTORIZED,
            }
            container_name = container_map.get(container_type, settings.AZURE_BLOB_CONTAINER_DOCUMENTS)
            container_client = self._get_container_client(container_name)
            container_client.delete_blob(blob_name)
            logger.info(f"Archivo eliminado: {blob_name}")
            return True
        except ResourceNotFoundError:
            # Si el blob no existe, no es un error; devolvemos False sin log de error
            logger.debug(f"Blob no encontrado al eliminar: {blob_name}")
            return False
        except AzureError as e:
            logger.error(f"Error eliminando {blob_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado eliminando archivo: {e}")
            raise

    def list_files(self, container_type: str = "documents", prefix: str = "") -> list:
        """
        Lista archivos en un contenedor.

        Args:
            container_type: Tipo de contenedor
            prefix: Prefijo para filtrar

        Returns:
            Lista de propiedades de blobs
        """
        try:
            container_map = {
                "documents": settings.AZURE_BLOB_CONTAINER_DOCUMENTS,
                "images": settings.AZURE_BLOB_CONTAINER_IMAGES,
                "vectorized": settings.AZURE_BLOB_CONTAINER_VECTORIZED,
            }
            container_name = container_map.get(container_type, settings.AZURE_BLOB_CONTAINER_DOCUMENTS)
            container_client = self._get_container_client(container_name)
            blobs = container_client.list_blobs(name_starts_with=prefix)
            return [
                {
                    "name": blob.name,
                    "size": blob.size,
                    "created": blob.creation_time.isoformat() if blob.creation_time else None,
                    "modified": blob.last_modified.isoformat() if blob.last_modified else None,
                    "metadata": blob.metadata or {},
                }
                for blob in blobs
            ]
        except AzureError as e:
            logger.error(f"Error listando archivos: {e}")
            raise
        except Exception as e:
            logger.error(f"Error inesperado listando archivos: {e}")
            raise

    def generate_blob_sas_url(
        self,
        blob_name: str,
        container_type: str = "documents",
        expires_minutes: int = 30,
        content_disposition: str | None = None,
        content_type: str | None = None,
    ) -> dict:
        """
        Genera una URL SAS temporal de solo lectura para un blob.

        Args:
            blob_name: Nombre del blob dentro del contenedor
            container_type: Tipo de contenedor ('documents', 'images', 'vectorized')
            expires_minutes: Tiempo de expiracion del SAS en minutos
            content_disposition: Content-Disposition de respuesta (inline/attachment)
            content_type: Content-Type de respuesta

        Returns:
            Dict con url y expires_at
        """
        if not self.account_name or not self.account_key:
            raise ValueError("Azure Blob Storage credentials missing for SAS generation")

        try:
            container_map = {
                "documents": settings.AZURE_BLOB_CONTAINER_DOCUMENTS,
                "images": settings.AZURE_BLOB_CONTAINER_IMAGES,
                "vectorized": settings.AZURE_BLOB_CONTAINER_VECTORIZED,
            }
            container_name = container_map.get(container_type, settings.AZURE_BLOB_CONTAINER_DOCUMENTS)
            container_client = self._get_container_client(container_name)

            # Validate blob existence to avoid issuing SAS for missing blobs
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.get_blob_properties()

            expires_at = datetime.utcnow() + timedelta(minutes=max(1, expires_minutes))
            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=container_name,
                blob_name=blob_name,
                account_key=self.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=expires_at,
                content_disposition=content_disposition,
                content_type=content_type,
            )

            url = f"https://{self.account_name}.blob.core.windows.net/{container_name}/{blob_name}?{sas_token}"
            return {"url": url, "expires_at": expires_at}
        except AzureError as e:
            logger.error(f"Error generating SAS for {blob_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error generating SAS: {e}")
            raise

    def generate_blob_sas_urls(
        self,
        blob_name: str,
        container_type: str = "documents",
        expires_minutes: int = 30,
        content_type: str | None = None,
    ) -> dict:
        """Genera URLs SAS para visualizacion inline y descarga."""
        inline = self.generate_blob_sas_url(
            blob_name=blob_name,
            container_type=container_type,
            expires_minutes=expires_minutes,
            content_disposition="inline",
            content_type=content_type,
        )
        download = self.generate_blob_sas_url(
            blob_name=blob_name,
            container_type=container_type,
            expires_minutes=expires_minutes,
            content_disposition="attachment",
            content_type=content_type,
        )
        return {
            "inline_url": inline["url"],
            "download_url": download["url"],
            "expires_at": inline["expires_at"],
        }


# Instancia singleton para usar en toda la app
blob_storage_service = BlobStorageService()
