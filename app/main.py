from fastapi import FastAPI
from app.core.config import settings
from app.core.db import Base, engine, SessionLocal
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.models.user_types import UserType
from app.models.research_authors import ResearchAuthor  # noqa: F401 — ensures table is created

from app.routes.users_routes import router as users_router
from app.routes.user_types_routes import router as user_types_router
from app.routes.courses_routes import router as courses_router
from app.routes.research_routes import router as research_router

# Do not create tables at import time — run on startup and handle DB errors gracefully

def init_db():
    Base.metadata.create_all(bind=engine)


def seed_default_user_types():
    db = SessionLocal()
    try:
        if db.query(UserType).count() == 0:
            db.add_all(
                [
                    UserType(description="Usuario"),
                    UserType(description="Investigadora"),
                ]
            )
            db.commit()
    finally:
        db.close()


def ensure_research_status_column():
    """Ensure research.status column exists in database for processing tracking."""
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("research")}
    if "status" in columns:
        return

    if engine.dialect.name == "sqlite":
        ddl = "ALTER TABLE research ADD COLUMN status TEXT DEFAULT 'ready'"
    else:
        ddl = "ALTER TABLE research ADD status NVARCHAR(20) DEFAULT 'ready' NOT NULL"

    with engine.begin() as conn:
        conn.execute(text(ddl))

is_dev_environment = (settings.ENV or "").strip().lower() == "dev"

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs" if is_dev_environment else None,
    redoc_url="/redoc" if is_dev_environment else None,
    openapi_url="/openapi.json" if is_dev_environment else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:8000"],  # Update this if your frontend runs on a different port
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods, including OPTIONS
    allow_headers=["*"],  # Allow all headers
)

# Mount routes
app.include_router(users_router)
app.include_router(user_types_router)
app.include_router(courses_router)
app.include_router(research_router)


@app.on_event("startup")
def _on_startup():
    import logging

    logger = logging.getLogger("uvicorn.error")
    try:
        init_db()
        ensure_research_status_column()
        seed_default_user_types()
        app.state.db_connected = True
        app.state.db_error = None
        logger.info("Database initialized successfully on startup.")
    except Exception as e:
        app.state.db_connected = False
        app.state.db_error = str(e)
        logger.error("Database initialization failed on startup: %s", e, exc_info=True)

@app.get("/")
def health():
    return {"status": "ok", "app": settings.APP_NAME}