from pydantic_settings import BaseSettings
from pydantic import Field
from urllib.parse import quote_plus


class Settings(BaseSettings):
    # App
    APP_NAME: str = Field("backend", validation_alias="APP_NAME")
    ENV: str = Field("dev", validation_alias="ENV")
    DEBUG: bool = Field(True, validation_alias="DEBUG")
    API_V1_PREFIX: str = Field("/api/v1", validation_alias="API_V1_PREFIX")

    # Security / JWT
    JWT_SECRET: str = Field(..., validation_alias="JWT_SECRET")
    JWT_ALG: str = Field("HS256", validation_alias="JWT_ALG")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")

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