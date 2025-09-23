from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import Annotated

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.research_document import (
    ResearchDocumentCreate, ResearchDocumentUpdate, ResearchDocumentOut, EmbedRequest, VectorSearchQuery
)
from app.controllers import research_document_controller as ctl

router = APIRouter(prefix="/files", tags=["files"])

UserDep = Annotated[dict, Depends(get_current_user)]
DbDep = Annotated[Session, Depends(get_db)]

@router.post("/", response_model=ResearchDocumentOut, status_code=status.HTTP_201_CREATED)
def create_file(payload: ResearchDocumentCreate, db: DbDep, current_user: UserDep):
    return ctl.create(db, owner_id=current_user.id, payload=payload)

@router.get("/", response_model=list[ResearchDocumentOut])
def list_files(skip: int = 0, limit: int = 50, db: DbDep = None, current_user: UserDep = None):
    return ctl.list_mine(db, owner_id=current_user.id, skip=skip, limit=limit)

@router.get("/{doc_id}", response_model=ResearchDocumentOut)
def get_file(doc_id: int, db: DbDep, current_user: UserDep):
    return ctl.get_one(db, owner_id=current_user.id, doc_id=doc_id)

@router.patch("/{doc_id}", response_model=ResearchDocumentOut)
def update_file(doc_id: int, payload: ResearchDocumentUpdate, db: DbDep, current_user: UserDep):
    return ctl.update_one(db, owner_id=current_user.id, doc_id=doc_id, payload=payload)

@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(doc_id: int, db: DbDep, current_user: UserDep):
    ctl.delete_one(db, owner_id=current_user.id, doc_id=doc_id)
    return

@router.post("/{doc_id}/embed", response_model=ResearchDocumentOut)
def embed_file(doc_id: int, payload: EmbedRequest, db: DbDep, current_user: UserDep):
    return ctl.embed_now(db, owner_id=current_user.id, doc_id=doc_id, force=payload.force)

@router.post("/search", response_model=list[ResearchDocumentOut])
def search_files(q: VectorSearchQuery, db: DbDep, current_user: UserDep):
    return ctl.search_vectors(db, owner_id=current_user.id, q=q)
