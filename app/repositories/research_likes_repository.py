from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.research_likes import ResearchLike


class ResearchLikesRepository:
    @staticmethod
    def get_by_user_and_research(db: Session, user_id: int, research_id: int):
        return (
            db.query(ResearchLike)
            .filter(
                ResearchLike.user_id == user_id,
                ResearchLike.research_id == research_id,
            )
            .first()
        )

    @staticmethod
    def like(db: Session, user_id: int, research_id: int):
        existing = ResearchLikesRepository.get_by_user_and_research(
            db,
            user_id=user_id,
            research_id=research_id,
        )
        if existing:
            was_active = bool(existing.is_active)
            existing.is_active = True
            existing.liked_at = datetime.utcnow()
            existing.updated_at = datetime.utcnow()
            db.flush()
            return existing, was_active

        like = ResearchLike(
            user_id=user_id,
            research_id=research_id,
            is_active=True,
            liked_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(like)
        db.flush()
        return like, False

    @staticmethod
    def unlike(db: Session, user_id: int, research_id: int):
        existing = ResearchLikesRepository.get_by_user_and_research(
            db,
            user_id=user_id,
            research_id=research_id,
        )
        if not existing:
            return None, False

        if not existing.is_active:
            return existing, False

        existing.is_active = False
        existing.updated_at = datetime.utcnow()
        db.flush()
        return existing, True

    @staticmethod
    def list_recent_active_by_user(db: Session, user_id: int, limit: int = 5):
        return (
            db.query(ResearchLike)
            .options(joinedload(ResearchLike.research))
            .filter(
                ResearchLike.user_id == user_id,
                ResearchLike.is_active == True,
            )
            .order_by(ResearchLike.liked_at.desc(), ResearchLike.id.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_active_by_research(db: Session, research_id: int) -> int:
        return (
            db.query(func.count(ResearchLike.id))
            .filter(
                ResearchLike.research_id == research_id,
                ResearchLike.is_active == True,
            )
            .scalar()
            or 0
        )

    @staticmethod
    def get_active_counts_by_research_ids(db: Session, research_ids: list[int]) -> dict[int, int]:
        if not research_ids:
            return {}

        rows = (
            db.query(ResearchLike.research_id, func.count(ResearchLike.id))
            .filter(
                ResearchLike.research_id.in_(research_ids),
                ResearchLike.is_active == True,
            )
            .group_by(ResearchLike.research_id)
            .all()
        )

        return {research_id: count for research_id, count in rows}

    @staticmethod
    def list_active_research_ids_by_user(db: Session, user_id: int, research_ids: list[int]) -> set[int]:
        if not research_ids:
            return set()

        rows = (
            db.query(ResearchLike.research_id)
            .filter(
                ResearchLike.user_id == user_id,
                ResearchLike.research_id.in_(research_ids),
                ResearchLike.is_active == True,
            )
            .all()
        )

        return {row[0] for row in rows}
