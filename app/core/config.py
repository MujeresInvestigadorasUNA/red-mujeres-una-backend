from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str
    DB_ENCRYPT: bool
    DB_TRUST_CERT: bool

    class Config:
        env_file = ".env"  # optional, if you add one

settings = Settings()