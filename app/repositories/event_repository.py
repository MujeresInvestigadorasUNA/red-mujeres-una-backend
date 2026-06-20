from sqlalchemy import asc, case
from sqlalchemy.orm import Session
from app.models.event import Event
from app.schemas.event import EventCreate

_event_order = (
    case((Event.initial_date.is_(None), 1), else_=0),
    asc(Event.initial_date),
)


class EventRepository:
    @staticmethod
    def list(db: Session, skip: int = 0, limit: int = 100):
        return db.query(Event).order_by(*_event_order).offset(skip).limit(limit).all()

    @staticmethod
    def get_public_events(db: Session, skip: int = 0, limit: int = 100):
        return db.query(Event).filter(Event.is_public == True).order_by(*_event_order).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_id(db: Session, event_id: int):
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise ValueError("Event not found")
        return event

    @staticmethod
    def get_by_user_id(db: Session, user_id: int):
        return db.query(Event)\
                .filter(Event.user_id == user_id)\
                .order_by(*_event_order)\
                .all()

    @staticmethod
    def create(db: Session, payload: EventCreate):
        event = Event(
            user_id=payload.user_id
        )
        db.add(event)
        db.flush()
        return event

    @staticmethod
    def update(
        db: Session,
        event_id: int,
        title: str,
        photo: str,
        description: str,
        modality: str,
        max_registration_date: str,
        initial_date: str,
        final_date: str,
        is_public: bool,
    ):
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise ValueError("Event not found")

        event.title = title
        event.photo = photo
        event.description = description
        event.modality = modality
        event.max_registration_date = max_registration_date
        event.initial_date = initial_date
        event.final_date = final_date
        event.is_public = is_public

        db.commit()
        db.refresh(event)
        return True

    @staticmethod
    def delete(db: Session, event_id: int):
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            return False
        db.delete(event)
        db.commit()
        return True
