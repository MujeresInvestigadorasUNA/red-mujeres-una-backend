from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Literal

class ResearchDocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = Field(None, max_length=10_000)
    source_url: Optional[HttpUrl] = None
    # Por ahora el blob lo dejas vacío; cuando subas, lo llenas vía update
    blob_url: Optional[HttpUrl] = None

class ResearchDocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = Field(None, max_length=10_000)
    source_url: Optional[HttpUrl] = None
    blob_url: Optional[HttpUrl] = None

class ResearchDocumentOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    source_url: Optional[str]
    blob_url: Optional[str]
    embedding_ref: Optional[str]
    status: Literal["pending", "embedded", "failed"]
    owner_id: int

    class Config:
        from_attributes = True

class EmbedRequest(BaseModel):
    # Opcional: permitir forzar regeneración
    force: bool = False

class VectorSearchQuery(BaseModel):
    query: str = Field(..., min_length=2, max_length=4000)
    top_k: int = Field(5, ge=1, le=50)
