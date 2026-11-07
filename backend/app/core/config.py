from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://transporte:transporte_demo@db:5432/transporte"
    session_secret: str = "transporte-demo-cambiar-antes-de-compartir"
    session_cookie_secure: bool = False
    session_hours: int = 12
    max_upload_bytes: int = 10 * 1024 * 1024
    max_import_rows: int = 20_000
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
