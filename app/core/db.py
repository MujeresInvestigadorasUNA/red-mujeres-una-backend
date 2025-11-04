from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "1433")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# ⚙️ Parámetros obligatorios para Azure SQL
# pytds usa validate_host_certificate y use_tls (no "encrypt")
connection_string = (
    f"mssql+pytds://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?use_tls=true&validate_host_certificate=false"
)

# Crear engine
engine = create_engine(connection_string, pool_pre_ping=True)

# Clase base para los modelos ORM
Base = declarative_base()

# Crear sesión
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependencia para FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()