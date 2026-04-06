from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Base de données dédiée incident_db
    INCIDENT_DB_URL: str

    # JWT (clé partagée avec auth-service)
    SECRET_KEY: str

    # Clé inter-services (X-Internal-Key)
    INTERNAL_API_KEY: str

    # URL du user-forest-service pour /geo/parcelle-at
    FOREST_SERVICE_URL: str

    # Redis pour PUBLISH incidents.new
    REDIS_URL: str

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"


settings = Settings()
