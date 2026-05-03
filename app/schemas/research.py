from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ResearchBase(BaseModel):
    user_id: int
    title: str
    description: Optional[str] = None
    research_link: str
    vector_link: str


class ResearchCreate(BaseModel):
    user_id: int
    title: str
    description: Optional[str] = None


class ResearchUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class ResearchCreateResponse(BaseModel):
    success: bool
    id: int
    research_link: str
    vector_link: Optional[str] = None
    description: Optional[str] = None
    status: str = "processing"  # processing, ready, failed


class ResearchDetailsOut(ResearchBase):
    id: int
    status: str = "ready"

    class Config:
        from_attributes = True


class RelatedResearchOut(BaseModel):
    id: Optional[int] = None
    title: str
    user_id: Optional[int] = None
    research_link: Optional[str] = None
    vector_blob_name: str
    similarity_score: float


class ResearchVisitRegisterOut(BaseModel):
    success: bool
    user_id: int
    research_id: int
    visited_at: datetime
    removed_old_visits: int


class ResearchRecentVisitOut(BaseModel):
    research_id: int
    title: str
    user_id: int
    research_link: str
    visited_at: datetime


class ResearchLikeActionOut(BaseModel):
    success: bool
    user_id: int
    research_id: int
    is_liked: bool
    liked_at: Optional[datetime] = None


class ResearchRecentLikeOut(BaseModel):
    research_id: int
    title: str
    user_id: int
    research_link: str
    liked_at: datetime


class ResearchLikeEventOut(BaseModel):
    research_id: int
    title: str
    user_id: int
    research_link: str
    action: str
    created_at: datetime
