from sqlalchemy.orm import Session
from app.schemas.research_document import (
    ResearchDocumentCreate, ResearchDocumentUpdate, ResearchDocumentOut,
    VectorSearchQuery
)
from app.services import research_document_service as svc

def create(db: Session, *, owner_id: int, payload: ResearchDocumentCreate) -> ResearchDocumentOut:
    doc = svc.create_document(db, owner_id=owner_id, data=payload)
    return ResearchDocumentOut.model_validate(doc)

def get_one(db: Session, *, owner_id: int, doc_id: int) -> ResearchDocumentOut:
    doc = svc.get_document(db, doc_id=doc_id, owner_id=owner_id)
    return ResearchDocumentOut.model_validate(doc)

def list_mine(db: Session, *, owner_id: int, skip: int = 0, limit: int = 50) -> list[ResearchDocumentOut]:
    docs = svc.list_documents(db, owner_id=owner_id, skip=skip, limit=limit)
    return [ResearchDocumentOut.model_validate(d) for d in docs]

def update_one(db: Session, *, owner_id: int, doc_id: int, payload: ResearchDocumentUpdate) -> ResearchDocumentOut:
    doc = svc.update_document(db, doc_id=doc_id, owner_id=owner_id, data=payload)
    return ResearchDocumentOut.model_validate(doc)

def delete_one(db: Session, *, owner_id: int, doc_id: int) -> None:
    svc.delete_document(db, doc_id=doc_id, owner_id=owner_id)

def embed_now(db: Session, *, owner_id: int, doc_id: int, force: bool) -> ResearchDocumentOut:
    doc = svc.trigger_embedding(db, doc_id=doc_id, owner_id=owner_id, force=force)
    return ResearchDocumentOut.model_validate(doc)

def search_vectors(db: Session, *, owner_id: int, q: VectorSearchQuery) -> list[ResearchDocumentOut]:
    docs = svc.vector_search(db, owner_id=owner_id, q=q)
    return [ResearchDocumentOut.model_validate(d) for d in docs]
