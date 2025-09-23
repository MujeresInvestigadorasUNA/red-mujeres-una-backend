from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base 

class DocStatus(str, enum.Enum):
    pending = "pending"        # creado, aún sin embedding
    embedded = "embedded"      # embedding listo
    failed = "failed"          # error al generar embedding

class ResearchDocument(Base):
    __tablename__ = "research_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)

    # Link “original” de la investigación (p.ej. artículo, PDF público)
    source_url = Column(String(2048), nullable=True)

    # Link al blob en Azure (cuando lo subas). Por ahora opcional.
    blob_url = Column(String(2048), nullable=True)

    # Dónde quedó el embedding (id de índice/search, o URL en blob/archivo)
    embedding_ref = Column(String(1024), nullable=True)

    status = Column(Enum(DocStatus), default=DocStatus.pending, nullable=False)

    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    owner = relationship("User", lazy="joined")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
