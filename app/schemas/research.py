from pydantic import BaseModel
from typing import Optional


class ResearchBase(BaseModel):
    user_id: int
    title: str
    research_link: str
    vector_link: str


class ResearchCreate(BaseModel):
    user_id: int
    title: str


class ResearchUpdate(BaseModel):
    title: Optional[str] = None


class ResearchCreateResponse(BaseModel):
    success: bool
    id: int
    research_link: str
    vector_link: str


class ResearchDetailsOut(ResearchBase):
    id: int

    class Config:
        from_attributes = True


class RelatedResearchOut(BaseModel):
    id: Optional[int] = None
    title: str
    user_id: Optional[int] = None
    research_link: Optional[str] = None
    vector_blob_name: str
    similarity_score: float
