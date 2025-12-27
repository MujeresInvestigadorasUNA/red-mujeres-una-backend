from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Use the computed database_url (can be sqlite or mssql+pyodbc built from parts)
DATABASE_URL = settings.database_url

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=connect_args,
    pool_pre_ping=True,  # help avoid stale/closed connection errors
)

# If using pyodbc via executemany, enabling fast_executemany can improve bulk insert performance
if "pyodbc" in DATABASE_URL:
    @event.listens_for(engine, "before_cursor_execute")
    def _enable_fast_executemany(conn, cursor, statement, parameters, context, executemany):
        if executemany and hasattr(cursor, "fast_executemany"):
            try:
                cursor.fast_executemany = True
            except Exception:
                # don't fail startup if setting this attribute is not supported
                pass

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()