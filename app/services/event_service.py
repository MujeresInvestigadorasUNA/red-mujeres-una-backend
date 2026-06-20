from sqlalchemy.orm import Session
from app.models.event import Event
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventCreate, EventUpdate


class EventService:
    @staticmethod
    def list_events(db: Session, skip: int = 0, limit: int = 50) -> list[Event]:
        return EventRepository.list(db, skip=skip, limit=limit)

    @staticmethod
    def get_public_events(db: Session, skip: int = 0, limit: int = 50) -> list[Event]:
        return EventRepository.get_public_events(db, skip=skip, limit=limit)

    @staticmethod
    def get_event(db: Session, event_id: int) -> Event | None:
        return EventRepository.get_by_id(db, event_id)

    @staticmethod
    def get_user_events(db: Session, user_id: int) -> list[Event]:
        return EventRepository.get_by_user_id(db, user_id)

    @staticmethod
    def create_event(db: Session, payload: EventCreate) -> dict:
        event = EventRepository.create(db, payload)
        db.commit()
        db.refresh(event)
        return {"id": event.id}

    @staticmethod
    def update_event(db: Session, event_id: int, payload: EventUpdate) -> Event | None:
        return EventRepository.update(
            db,
            event_id,
            title=payload.title,
            photo=payload.photo,
            description=payload.description,
            modality=payload.modality,
            max_registration_date=payload.max_registration_date,
            initial_date=payload.initial_date,
            final_date=payload.final_date,
            is_public=payload.is_public,
        )

    @staticmethod
    def delete_event(db: Session, event_id: int) -> bool:
        return EventRepository.delete(db, event_id)
