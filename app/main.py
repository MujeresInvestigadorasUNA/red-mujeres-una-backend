from fastapi import FastAPI
from app.core.config import settings
from app.core.db import Base, engine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.users_routes import router as users_router
from app.routes.user_types_routes import router as user_types_router
from app.routes.forums_routes import router as forums_router
from app.routes.courses_routes import router as courses_router
from app.routes.research_routes import router as research_router

# Do not create tables at import time — run on startup and handle DB errors gracefully

def init_db():
    Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME)

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
app.include_router(forums_router)
app.include_router(courses_router)
app.include_router(research_router)


@app.on_event("startup")
def _on_startup():
    import logging

    logger = logging.getLogger("uvicorn.error")
    try:
        init_db()
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