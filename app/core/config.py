from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Using SQLite file by default; swap to Postgres later if you want
    DATABASE_URL: str = "sqlite:///./app.db"
    APP_NAME: str = "FastAPI Clean Example"
    SECRET_KEY: str = "123456789abcdef1234567890abcdef"  # Change this in production!

    class Config:
        env_file = ".env"  # optional, if you add one
        extra = "ignore"

settings = Settings()