from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class ResearchBase(BaseModel):
    user_id: int
    title: str
    description: Optional[str] = None
    research_link: str
    vector_link: Optional[str] = None  # nullable during processing


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


class ResearchAuthorOut(BaseModel):
    user_id: int
    first_name: str
    last_name: str
    email: str

    class Config:
        from_attributes = True


class ResearchDetailsOut(ResearchBase):
    id: int
    status: str = "ready"
    likes_count: int = 0
    visits_count: int = 0
    is_liked: Optional[bool] = None
    authors: list[ResearchAuthorOut] = []

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


class ResearchPdfUrlOut(BaseModel):
    inline_url: str
    download_url: str
    expires_at: datetime


class ResearchGraphNodeOut(BaseModel):
    id: str
    label: str
    type: str
    research_id: Optional[int] = None
    user_id: Optional[int] = None
    research_link: Optional[str] = None
    vector_link: Optional[str] = None
    status: Optional[str] = None
    likes_count: Optional[int] = None
    is_liked: Optional[bool] = None


class ResearchGraphEdgeOut(BaseModel):
    source: str
    target: str
    weight: float
    relation: Optional[str] = None


class ResearchGraphOut(BaseModel):
    meta: dict[str, Any]
    nodes: list[ResearchGraphNodeOut]
    edges: list[ResearchGraphEdgeOut]


class ResearchEmbeddingPointOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    user_id: int
    research_link: str
    x: float
    y: float
    z: Optional[float] = None


class ResearchEmbeddingEdgeOut(BaseModel):
    source: int
    target: int
    weight: float
    relation: str = "similarity"


class ResearchEmbeddingMapOut(BaseModel):
    meta: dict[str, Any]
    points: list[ResearchEmbeddingPointOut]
    edges: list[ResearchEmbeddingEdgeOut] = []


class ResearchAuthorsListOut(BaseModel):
    research_id: int
    authors: list[ResearchAuthorOut]


class ResearchAuthorsActionOut(BaseModel):
    success: bool
    research_id: int
    added: list[int] = []
    skipped: list[int] = []
    removed: list[int] = []
    not_found: list[int] = []


class ResearchAuthorsBulkRequest(BaseModel):
    user_ids: list[int]


class RAGMessageHistory(BaseModel):
    role: str
    content: str


class RAGQuestionRequest(BaseModel):
    question: str
    user_id: Optional[int] = None
    history: list[RAGMessageHistory] = []


class RAGSourceOut(BaseModel):
    research_id: int
    title: str
    user_id: Optional[int] = None
    score: float


class RAGAnswerOut(BaseModel):
    answer: str
    sources: list[RAGSourceOut]
