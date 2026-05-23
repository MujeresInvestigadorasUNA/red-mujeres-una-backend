from __future__ import annotations

from sqlalchemy.orm import Session
from app.models.research import Research


class ResearchRepository:
    @staticmethod
    def list(db: Session, skip: int = 0, limit: int = 100):
        return db.query(Research).order_by(Research.id).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_id(db: Session, research_id: int):
        research = db.query(Research).filter(Research.id == research_id).first()
        if not research:
            raise ValueError("Research not found")
        return research

    @staticmethod
    def get_by_user_id(db: Session, user_id: int):
        return db.query(Research).filter(Research.user_id == user_id).all()

    @staticmethod
    def get_by_ids(db: Session, research_ids: list[int]) -> list[Research]:
        if not research_ids:
            return []
        rows = db.query(Research).filter(Research.id.in_(research_ids)).all()
        order_map = {rid: i for i, rid in enumerate(research_ids)}
        return sorted(rows, key=lambda r: order_map.get(r.id, len(research_ids)))

    @staticmethod
    def list_all(db: Session):
        return db.query(Research).all()

    @staticmethod
    def create(
        db: Session,
        user_id: int,
        title: str,
        description: str | None,
        research_link: str,
        vector_link: str,
    ):
        research = Research(
            user_id=user_id,
            title=title,
            description=description,
            research_link=research_link,
            vector_link=vector_link,
        )
        db.add(research)
        db.flush()
        return research

    @staticmethod
    def update(db: Session, research_id: int, updates: dict):
        research = db.query(Research).filter(Research.id == research_id).first()
        if not research:
            raise ValueError("Research not found")
        
        for key, value in updates.items():
            if hasattr(research, key) and key not in ['id', 'research_link', 'vector_link']:
                setattr(research, key, value)
        
        db.flush()
        return research

    @staticmethod
    def delete(db: Session, research_id: int):
        research = db.query(Research).filter(Research.id == research_id).first()
        if not research:
            return False
        db.delete(research)
        db.commit()
        return True
