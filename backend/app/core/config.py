# .env 읽기 (DB 주소, API 키)  [채원]
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")  # backend/ 에서 실행

    database_url: str
    jwt_secret: str
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5-5"


settings = Settings()
