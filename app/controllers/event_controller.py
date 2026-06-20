from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.schemas.event import EventCreate, EventUpdate
from app.services.event_service import EventService


class EventController:
    @staticmethod
    def list_events(db: Session, skip: int = 0, limit: int = 100):
        return EventService.list_events(db, skip, limit)

    @staticmethod
    def get_public_events(db: Session, skip: int = 0, limit: int = 100):
        return EventService.get_public_events(db, skip=skip, limit=limit)

    @staticmethod
    def get_event(db: Session, event_id: int):
        try:
            return EventService.get_event(db, event_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def get_user_events(db: Session, user_id: int):
        try:
            return EventService.get_user_events(db, user_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @staticmethod
    def create_event(db: Session, event: EventCreate):
        try:
            return EventService.create_event(db, event)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail="Internal Server Error" + str(e))

    @staticmethod
    def update_event(db: Session, event_id: int, event: EventUpdate):
        try:
            EventService.update_event(db, event_id, event)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    def delete_event(db: Session, event_id: int):
        if not EventService.delete_event(db, event_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
        return {"status": "ok"}
