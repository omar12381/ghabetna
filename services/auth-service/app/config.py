from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    JWT_SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    REDIS_URL: str
    USER_SERVICE_URL: str
    SERVICE_SECRET: str
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"


settings = Settings()
