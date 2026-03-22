from fastapi import APIRouter, Depends, Query, File, UploadFile, Form
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.controllers.research_controller import ResearchController
from app.schemas.research import (
    ResearchDetailsOut,
    ResearchCreateResponse,
    RelatedResearchOut,
    ResearchVisitRegisterOut,
    ResearchRecentVisitOut,
)

router = APIRouter(prefix="/research", tags=["research"])


@router.get("/", response_model=list[ResearchDetailsOut])
def list_research(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return ResearchController.list_research(db, skip=skip, limit=limit)


@router.get("/user/{user_id}", response_model=list[ResearchDetailsOut])
def list_user_research(user_id: int, db: Session = Depends(get_db)):
    return ResearchController.get_user_research(db, user_id)


@router.get("/{research_id}", response_model=ResearchDetailsOut)
def get_research(research_id: int, db: Session = Depends(get_db)):
    return ResearchController.get_research(db, research_id)


@router.get("/{research_id}/related", response_model=list[RelatedResearchOut])
def get_related_research(
    research_id: int,
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    return ResearchController.get_related_research(db, research_id=research_id, limit=limit)


@router.post("/user/{user_id}/visits/{research_id}", response_model=ResearchVisitRegisterOut)
def register_research_visit(
    user_id: int,
    research_id: int,
    db: Session = Depends(get_db),
):
    return ResearchController.register_research_visit(db, user_id=user_id, research_id=research_id)


@router.get("/user/{user_id}/visits", response_model=list[ResearchRecentVisitOut])
def list_recent_research_visits(
    user_id: int,
    limit: int = Query(5, ge=1, le=5),
    db: Session = Depends(get_db),
):
    return ResearchController.get_recent_research_visits(db, user_id=user_id, limit=limit)


@router.get("/user/{user_id}/related-from-visits", response_model=list[RelatedResearchOut])
def get_related_research_from_recent_visits(
    user_id: int,
    limit: int = Query(4, ge=1, le=20),
    db: Session = Depends(get_db),
):
    return ResearchController.get_related_research_from_recent_visits(db, user_id=user_id, limit=limit)


@router.post("/", response_model=ResearchCreateResponse)
async def create_research(
    user_id: int = Form(...),
    title: str = Form(...),
    document: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    # Lee el archivo en async context
    pdf_bytes = await document.read()
    
    # Llama al controller de forma síncrona
    return ResearchController.create_research_sync(
        db=db,
        user_id=user_id,
        title=title,
        document_bytes=pdf_bytes,
        document_filename=document.filename,
        document_content_type=document.content_type,
    )


@router.delete("/{research_id}")
def delete_research(research_id: int, db: Session = Depends(get_db)):
    return ResearchController.delete_research(db, research_id)
