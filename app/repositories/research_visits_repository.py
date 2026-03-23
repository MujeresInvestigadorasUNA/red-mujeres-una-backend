from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models.research_visits import ResearchVisit


class ResearchVisitsRepository:
    @staticmethod
    def get_by_user_and_research(db: Session, user_id: int, research_id: int):
        return (
            db.query(ResearchVisit)
            .filter(
                ResearchVisit.user_id == user_id,
                ResearchVisit.research_id == research_id,
            )
            .first()
        )

    @staticmethod
    def create_or_refresh(db: Session, user_id: int, research_id: int):
        visit = ResearchVisitsRepository.get_by_user_and_research(db, user_id=user_id, research_id=research_id)
        if visit:
            visit.visited_at = datetime.utcnow()
            db.flush()
            return visit

        visit = ResearchVisit(
            user_id=user_id,
            research_id=research_id,
            visited_at=datetime.utcnow(),
        )
        db.add(visit)
        db.flush()
        return visit

    @staticmethod
    def list_recent_by_user(db: Session, user_id: int, limit: int = 5):
        return (
            db.query(ResearchVisit)
            .options(joinedload(ResearchVisit.research))
            .filter(ResearchVisit.user_id == user_id)
            .order_by(ResearchVisit.visited_at.desc(), ResearchVisit.id.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def delete_older_than_limit(db: Session, user_id: int, keep_limit: int = 5):
        old_visits = (
            db.query(ResearchVisit)
            .filter(ResearchVisit.user_id == user_id)
            .order_by(ResearchVisit.visited_at.desc(), ResearchVisit.id.desc())
            .offset(keep_limit)
            .all()
        )

        for visit in old_visits:
            db.delete(visit)

        return len(old_visits)
