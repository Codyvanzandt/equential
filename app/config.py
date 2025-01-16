from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from dotenv import find_dotenv
import uuid

class Settings(BaseSettings):
    mongodb_url: str
    database_name: str = "equential"
    users_collection: str = "users"
    base_url: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=find_dotenv(),
        env_file_encoding='utf-8',
        extra='ignore'
    )

@lru_cache()
def get_settings() -> Settings:
    return Settings()