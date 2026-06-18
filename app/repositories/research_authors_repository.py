from __future__ import annotations

from sqlalchemy.orm import Session
from app.models.research_authors import ResearchAuthor


class ResearchAuthorsRepository:
    @staticmethod
    def get_by_research(db: Session, research_id: int) -> list[ResearchAuthor]:
        return db.query(ResearchAuthor).filter(ResearchAuthor.research_id == research_id).all()

    @staticmethod
    def get_by_research_and_user(db: Session, research_id: int, user_id: int) -> ResearchAuthor | None:
        return (
            db.query(ResearchAuthor)
            .filter(ResearchAuthor.research_id == research_id, ResearchAuthor.user_id == user_id)
            .first()
        )

    @staticmethod
    def add(db: Session, research_id: int, user_id: int) -> ResearchAuthor:
        author = ResearchAuthor(research_id=research_id, user_id=user_id)
        db.add(author)
        db.flush()
        return author

    @staticmethod
    def remove(db: Session, research_id: int, user_id: int) -> bool:
        author = (
            db.query(ResearchAuthor)
            .filter(ResearchAuthor.research_id == research_id, ResearchAuthor.user_id == user_id)
            .first()
        )
        if not author:
            return False
        db.delete(author)
        db.flush()
        return True
