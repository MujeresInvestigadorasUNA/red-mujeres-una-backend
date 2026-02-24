from fastapi import APIRouter, Depends, Query, File, UploadFile, Form
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.controllers.research_controller import ResearchController
from app.schemas.research import ResearchDetailsOut, ResearchCreateResponse

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


@router.post("/", response_model=ResearchCreateResponse)
async def create_research(
    user_id: int = Form(...),
    title: str = Form(...),
    document: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    return await ResearchController.create_research(
        db=db,
        user_id=user_id,
        title=title,
        document=document,
    )


@router.delete("/{research_id}")
def delete_research(research_id: int, db: Session = Depends(get_db)):
    return ResearchController.delete_research(db, research_id)
