from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models.research_like_events import ResearchLikeEvent


class ResearchLikeEventsRepository:
    @staticmethod
    def create(db: Session, user_id: int, research_id: int, action: str):
        event = ResearchLikeEvent(
            user_id=user_id,
            research_id=research_id,
            action=action,
            created_at=datetime.utcnow(),
        )
        db.add(event)
        db.flush()
        return event

    @staticmethod
    def list_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 50):
        return (
            db.query(ResearchLikeEvent)
            .options(joinedload(ResearchLikeEvent.research))
            .filter(ResearchLikeEvent.user_id == user_id)
            .order_by(ResearchLikeEvent.created_at.desc(), ResearchLikeEvent.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
