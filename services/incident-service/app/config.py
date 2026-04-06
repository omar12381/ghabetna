from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str
    JWT_SECRET_KEY: str
    SERVICE_SECRET: str
    USER_FOREST_SERVICE_URL: str  # http://user-forest-service:8000
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"


settings = Settings()




#Le fichier config.py (Le Traducteur Intelligent)
#C'est ici que pydantic-settings intervient. Ce fichier lit le .env et le transforme en objets Python utilisables.

#Validation : Si vous oubliez DATABASE_URL dans le .env, Pydantic va bloquer le démarrage de l'application et vous dire : "Hé, il manque une donnée obligatoire !".

#Conversion de type : Dans le .env, tout est du texte. Dans config.py, vous demandez une list[str] pour CORS_ORIGINS. Pydantic va automatiquement transformer votre texte séparé par des virgules en une vraie liste Python.

#Utilisation : Partout dans votre code, vous ferez from .config import settings puis settings.DATABASE_URL. C'est propre et sécurisé.



#Pydantic, une bibliothèque Python surpuissante qui sert à valider les données.