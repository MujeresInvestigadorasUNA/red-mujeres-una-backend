from pydantic_settings import BaseSettings
from pydantic import Field
from urllib.parse import quote_plus

class Settings(BaseSettings):
    # App
    APP_NAME: str = Field("backend", validation_alias="APP_NAME")
    ENV: str = Field("dev", validation_alias="ENV")
    DEBUG: bool = Field(True, validation_alias="DEBUG")
    API_V1_PREFIX: str = Field("/api/v1", validation_alias="API_V1_PREFIX")

    # Legacy single DATABASE_URL (optional)
    DATABASE_URL: str = Field("sqlite:///./app.db", validation_alias="DATABASE_URL")

    # Granular SQL Server config (if provided, used to compose a mssql+pyodbc URL)
    SQLSERVER_HOST: str | None = Field(None, validation_alias="SQLSERVER_HOST")
    SQLSERVER_PORT: int | None = Field(1433, validation_alias="SQLSERVER_PORT")
    SQLSERVER_DB: str | None = Field(None, validation_alias="SQLSERVER_DB")
    SQLSERVER_USER: str | None = Field(None, validation_alias="SQLSERVER_USER")
    SQLSERVER_PASSWORD: str | None = Field(None, validation_alias="SQLSERVER_PASSWORD")
    SQLSERVER_DRIVER: str = Field("ODBC Driver 18 for SQL Server", validation_alias="SQLSERVER_DRIVER")
    SQLSERVER_TIMEOUT: int | None = Field(None, validation_alias="SQLSERVER_TIMEOUT")

    # Azure Blob Storage
    AZURE_STORAGE_CONNECTION_STRING: str | None = Field(None, validation_alias="AZURE_STORAGE_CONNECTION_STRING")
    AZURE_STORAGE_ACCOUNT_NAME: str | None = Field(None, validation_alias="AZURE_STORAGE_ACCOUNT_NAME")
    AZURE_STORAGE_ACCOUNT_KEY: str | None = Field(None, validation_alias="AZURE_STORAGE_ACCOUNT_KEY")
    AZURE_BLOB_CONTAINER_DOCUMENTS: str = Field("documents", validation_alias="AZURE_BLOB_CONTAINER_DOCUMENTS")
    AZURE_BLOB_CONTAINER_IMAGES: str = Field("images", validation_alias="AZURE_BLOB_CONTAINER_IMAGES")
    AZURE_BLOB_CONTAINER_VECTORIZED: str = Field("vectorized-documents", validation_alias="AZURE_BLOB_CONTAINER_VECTORIZED")
    MAX_UPLOAD_SIZE_MB: int = Field(50, validation_alias="MAX_UPLOAD_SIZE_MB")

    # Azure OpenAI (Embeddings)
    AZURE_OPENAI_ENDPOINT: str | None = Field(None, validation_alias="AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_KEY: str | None = Field(None, validation_alias="AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_API_VERSION: str = Field("2024-02-01", validation_alias="AZURE_OPENAI_API_VERSION")
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT: str | None = Field(None, validation_alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
    AZURE_OPENAI_EMBEDDING_BATCH_SIZE: int = Field(10, validation_alias="AZURE_OPENAI_EMBEDDING_BATCH_SIZE")

    # Azure OpenAI (Chat / RAG)
    AZURE_OPENAI_CHAT_DEPLOYMENT: str | None = Field(None, validation_alias="AZURE_OPENAI_CHAT_DEPLOYMENT")
    AZURE_OPENAI_CHAT_ENDPOINT: str | None = Field(None, validation_alias="AZURE_OPENAI_CHAT_ENDPOINT")
    AZURE_OPENAI_CHAT_API_KEY: str | None = Field(None, validation_alias="AZURE_OPENAI_CHAT_API_KEY")

    # Firebase Admin
    FIREBASE_SERVICE_ACCOUNT_PATH: str | None = Field(None, validation_alias="FIREBASE_SERVICE_ACCOUNT_PATH")
    FIREBASE_SERVICE_ACCOUNT_JSON: str | None = Field(None, validation_alias="FIREBASE_SERVICE_ACCOUNT_JSON")

    # Qdrant
    QDRANT_ENDPOINT: str | None = Field(None, validation_alias="QDRANT_ENDPOINT")
    QDRANT_API_KEY: str | None = Field(None, validation_alias="QDRANT_API_KEY")
    QDRANT_RESEARCH_COLLECTION: str = Field("research-embeddings", validation_alias="QDRANT_RESEARCH_COLLECTION")
    QDRANT_TIMEOUT_SECONDS: int = Field(30, validation_alias="QDRANT_TIMEOUT_SECONDS")

    # CORS
    ALLOW_ORIGINS: str | None = Field(None, validation_alias="ALLOW_ORIGINS")

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

def _compose_database_url(s: Settings) -> str:
    """Compose a SQLAlchemy URL for SQL Server when SQLSERVER_* vars are present.

    Uses url-encoding for user/password and adds sensible defaults.
    """
    if s.SQLSERVER_HOST and s.SQLSERVER_USER and s.SQLSERVER_DB:
        user = quote_plus(s.SQLSERVER_USER)
        pwd = quote_plus(s.SQLSERVER_PASSWORD or "")
        driver = quote_plus(s.SQLSERVER_DRIVER)
        host = s.SQLSERVER_HOST
        port = s.SQLSERVER_PORT or 1433
        timeout = f"&Connection+Timeout={s.SQLSERVER_TIMEOUT}" if s.SQLSERVER_TIMEOUT else ""
        # Use TrustServerCertificate=no by default; change in .env if needed
        # Use MARS_Connection=No (ODBC expects Yes/No)
        return (
            f"mssql+pyodbc://{user}:{pwd}@{host}:{port}/{s.SQLSERVER_DB}"
            f"?driver={driver}&Encrypt=yes&TrustServerCertificate=no&MARS_Connection=No{timeout}"
        )
    return s.DATABASE_URL


# Backwards-compatible attribute name used by other modules
Settings.database_url = property(lambda self: _compose_database_url(self))