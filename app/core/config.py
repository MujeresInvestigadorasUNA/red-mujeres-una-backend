from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    APP_NAME: str = Field("backend", validation_alias="APP_NAME")
    ENV: str = Field("dev", validation_alias="ENV")
    DEBUG: bool = Field(True, validation_alias="DEBUG")
    API_V1_PREFIX: str = Field("/api/v1", validation_alias="API_V1_PREFIX")

    JWT_SECRET: str = Field(..., validation_alias="JWT_SECRET")
    JWT_ALG: str = Field("HS256", validation_alias="JWT_ALG")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    DATABASE_URL: str = Field("sqlite:///./app.db", validation_alias="DATABASE_URL")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
