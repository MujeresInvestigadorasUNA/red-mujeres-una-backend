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
    ResearchLikeActionOut,
    ResearchRecentLikeOut,
    ResearchLikeEventOut,
    ResearchUpdate,
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


@router.post("/user/{user_id}/likes/{research_id}", response_model=ResearchLikeActionOut)
def like_research(
    user_id: int,
    research_id: int,
    db: Session = Depends(get_db),
):
    return ResearchController.like_research(db, user_id=user_id, research_id=research_id)


@router.delete("/user/{user_id}/likes/{research_id}", response_model=ResearchLikeActionOut)
def unlike_research(
    user_id: int,
    research_id: int,
    db: Session = Depends(get_db),
):
    return ResearchController.unlike_research(db, user_id=user_id, research_id=research_id)


@router.get("/user/{user_id}/likes", response_model=list[ResearchRecentLikeOut])
def list_recent_research_likes(
    user_id: int,
    limit: int = Query(5, ge=1, le=5),
    db: Session = Depends(get_db),
):
    return ResearchController.get_recent_research_likes(db, user_id=user_id, limit=limit)


@router.get("/user/{user_id}/likes/history", response_model=list[ResearchLikeEventOut])
def list_research_like_history(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return ResearchController.get_research_like_history(db, user_id=user_id, skip=skip, limit=limit)


@router.get("/user/{user_id}/related-from-interactions", response_model=list[RelatedResearchOut])
def get_related_research_from_recent_interactions(
    user_id: int,
    limit: int = Query(4, ge=1, le=20),
    db: Session = Depends(get_db),
):
    return ResearchController.get_related_research_from_recent_interactions(db, user_id=user_id, limit=limit)


@router.post("/", response_model=ResearchCreateResponse)
async def create_research(
    user_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(None),
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
        description=description,
        document_bytes=pdf_bytes,
        document_filename=document.filename,
        document_content_type=document.content_type,
    )


@router.put("/{research_id}", response_model=dict)
def update_research(
    research_id: int,
    research_update: ResearchUpdate,
    db: Session = Depends(get_db),
):
    return ResearchController.update_research(db, research_id, research_update.model_dump(exclude_unset=True))


@router.delete("/{research_id}")
def delete_research(research_id: int, db: Session = Depends(get_db)):
    return ResearchController.delete_research(db, research_id)
