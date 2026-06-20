from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.controllers.event_controller import EventController
from app.core.db import get_db
from app.core.auth import require_token, require_researcher_or_admin
from app.schemas.event import EventBase, EventByUserBase, EventCreate, EventCreateResponse, EventOut, EventUpdate, EventUpdateResponse

router = APIRouter(prefix="/events", tags=["events"])


# ── Public endpoints ──────────────────────────────────────────────────────────

@router.get("/", response_model=list[EventBase])
def list_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return EventController.list_events(db, skip=skip, limit=limit)


@router.get("/public", response_model=list[EventBase])
def get_public_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return EventController.get_public_events(db, skip=skip, limit=limit)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    return EventController.get_event(db, event_id)


# ── Protected endpoints ───────────────────────────────────────────────────────

@router.get("/user/{user_id}", response_model=list[EventByUserBase])
def get_user_events(
    user_id: int,
    _: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    return EventController.get_user_events(db, user_id)


@router.post("/", response_model=EventCreateResponse, status_code=201)
def create_event(
    payload: EventCreate,
    _: dict = Depends(require_researcher_or_admin),
    db: Session = Depends(get_db),
):
    return EventController.create_event(db, payload)


@router.put("/{event_id}", response_model=EventUpdateResponse)
def update_event(
    event_id: int,
    payload: EventUpdate,
    _: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    return EventController.update_event(db, event_id, payload)


@router.delete("/{event_id}")
def delete_event(
    event_id: int,
    _: dict = Depends(require_token),
    db: Session = Depends(get_db),
):
    return EventController.delete_event(db, event_id)
