from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from fastapi import HTTPException, status

from app.models.research_document import ResearchDocument, DocStatus
from app.schemas.research_document import ResearchDocumentCreate, ResearchDocumentUpdate, VectorSearchQuery

# === CRUD ===

def create_document(db: Session, *, owner_id: int, data: ResearchDocumentCreate) -> ResearchDocument:
    doc = ResearchDocument(
        title=data.title.strip(),
        description=(data.description or "").strip() or None,
        source_url=str(data.source_url) if data.source_url else None,
        blob_url=str(data.blob_url) if data.blob_url else None,
        owner_id=owner_id,
        status=DocStatus.pending,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

def get_document(db: Session, *, doc_id: int, owner_id: int | None = None) -> ResearchDocument:
    stmt = select(ResearchDocument).where(ResearchDocument.id == doc_id)
    doc = db.execute(stmt).scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if owner_id is not None and doc.owner_id != owner_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return doc

def list_documents(db: Session, *, owner_id: int, skip: int = 0, limit: int = 50) -> list[ResearchDocument]:
    stmt = (
        select(ResearchDocument)
        .where(ResearchDocument.owner_id == owner_id)
        .offset(skip).limit(limit)
    )
    return list(db.execute(stmt).scalars().all())

def update_document(db: Session, *, doc_id: int, owner_id: int, data: ResearchDocumentUpdate) -> ResearchDocument:
    doc = get_document(db, doc_id=doc_id, owner_id=owner_id)
    if data.title is not None:
        doc.title = data.title.strip()
    if data.description is not None:
        doc.description = data.description.strip() or None
    if data.source_url is not None:
        doc.source_url = str(data.source_url)
    if data.blob_url is not None:
        doc.blob_url = str(data.blob_url)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

def delete_document(db: Session, *, doc_id: int, owner_id: int) -> None:
    _ = get_document(db, doc_id=doc_id, owner_id=owner_id)  # valida ownership/exists
    db.execute(delete(ResearchDocument).where(ResearchDocument.id == doc_id))
    db.commit()

# === Embeddings (placeholder) ===

def trigger_embedding(db: Session, *, doc_id: int, owner_id: int, force: bool = False) -> ResearchDocument:
    doc = get_document(db, doc_id=doc_id, owner_id=owner_id)

    if doc.status == DocStatus.embedded and not force:
        return doc  # ya está

    # Aquí el contenido del doc (p. ej. bajando el blob_url),
    # luego a Azure OpenAI Embeddings y subir el vector a:
    #   - o (temporal) archivo en Blob y guardas el link
    #
    # >>> PSEUDOCÓDIGO real (no ejecutamos aquí):
    # content = download_blob(doc.blob_url) or fetch_url(doc.source_url)
    # vector = openai.embeddings.create(model="text-embedding-3-large", input=content)
    # embedding_ref = upload_to_search_or_blob(vector)
    #
    # Simula resultado para pruebas:
    doc.embedding_ref = f"blob://embeddings/research_docs/{doc.id}.json"
    doc.status = DocStatus.embedded

    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

# === Búsqueda vectorial (stub) ===

def vector_search(db: Session, *, owner_id: int, q: VectorSearchQuery) -> list[ResearchDocument]:
    # En producción:
    # 1) generar embedding de q.query
    # 2) consultar en el índice vectorial (AI Search / pgvector)
    # 3) devolver los IDs ordenados por similitud
    #
    # Aquí devolvemos “algo” para probar flujo: los últimos K del usuario
    docs = list_documents(db, owner_id=owner_id, skip=0, limit=q.top_k)
    return docs
