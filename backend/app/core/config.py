# .env 읽기 (DB 주소, API 키)  [채원]
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")  # backend/ 에서 실행

    database_url: str
    jwt_secret: str
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5-5"
    refine_enabled: bool = True  # False 면 학부모 메시지를 Claude 로 정제하지 않고 failed 로 둔다 (시험용)
    dev_tools: bool = False  # True 면 /dev/refine (정제 켜고 끄기) 를 연다. dev.py 가 켠다
    cors_origins: str = "http://localhost:5173"  # 쉼표로 구분. 단일 출처로 서비스하는 시연에서는 바꿀 필요 없다


settings = Settings()
