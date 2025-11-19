from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.controllers.forums_controller import ForumsController
from app.schemas.forums import ForumCreate, ForumUpdate, ForumDetailsOut, ForumCreateResponse, ForumUpdateResponse

router = APIRouter(prefix="/forums", tags=["forums"])

@router.get("/", response_model=list[ForumDetailsOut])
def list_forums(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return ForumsController.list_forums(db, skip=skip, limit=limit)

@router.get("/{forum_id}", response_model=ForumDetailsOut)
def get_forum(forum_id: int, db: Session = Depends(get_db)):
    return ForumsController.get_forum(db, forum_id)

@router.post("/", response_model=ForumCreateResponse)
def create_forum(payload: ForumCreate, db: Session = Depends(get_db)):
    return ForumsController.create_forum(db, payload)

@router.put("/{forum_id}", response_model=ForumUpdateResponse)
def update_forum(forum_id: int, payload: ForumUpdate, db: Session = Depends(get_db)):
    return ForumsController.update_forum(db, forum_id, payload)

@router.delete("/{forum_id}")
def delete_forum(forum_id: int, db: Session = Depends(get_db)):
    return ForumsController.delete_forum(db, forum_id)