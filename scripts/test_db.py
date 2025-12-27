"""
Simple DB connection test script. It reads settings from app.core.config and tries to connect.
Run: python scripts/test_db.py
"""
from app.core.config import settings
from sqlalchemy import create_engine

print("Using database URL:", settings.database_url)

engine = create_engine(settings.database_url, future=True)
try:
    with engine.connect() as conn:
        r = conn.execute("SELECT 1")
        print("Connection test OK:", r.scalar_one())
except Exception as e:
    print("Connection test FAILED:", e)
