# [M0] SOCLE TECHNIQUE — TASK LIST
> Projet : GHABETNA | Milestone : M0
> Objectif : Mettre en place le socle technique — structure monorepo, containerisation Docker,
> correction de la dette MS-1, et garantir que `docker-compose up` démarre tout.

---

## DECISIONS PRISES POUR CE MILESTONE

| Sujet | Décision |
|---|---|
| Structure projet | Monorepo : `services/user-forest-service/` + `flutter/` à la racine |
| Docker | `docker-compose` : PostgreSQL/PostGIS + user-forest-service uniquement |
| Redis | **Pas dans M0** — ajouté en M5 quand réellement utilisé |
| Alembic | **Pas dans M0** — migrations artisanales conservées, Alembic en Phase 2 |
| CI/CD | **Pas dans M0** — hors scope roadmap |
| Objectif final | `docker-compose up` démarre tout et les endpoints MS-1 fonctionnent |
| Flutter | Déplacé dans `flutter/` + correction des 2 hardcodes (URL + CORS) |

---

## TÂCHE 1 — RESTRUCTURATION MONOREPO

> Objectif : Créer la nouvelle arborescence racine propre avant toute autre modification.

- [ ] **1.1** Créer le dossier racine du projet `ghabetna/` (si pas déjà fait)
- [ ] **1.2** Créer le dossier `ghabetna/services/`
- [ ] **1.3** Déplacer le dossier `user_forest_app/` (backend FastAPI) vers `ghabetna/services/user-forest-service/`
  - Vérifier que tous les fichiers sont présents : `app/`, `requirements.txt`, `main.py` (ou équivalent)
- [ ] **1.4** Créer le dossier `ghabetna/flutter/`
- [ ] **1.5** Déplacer le dossier Flutter (le projet Dart) vers `ghabetna/flutter/`
  - Vérifier que `pubspec.yaml` est présent à la racine de `ghabetna/flutter/`
- [ ] **1.6** Vérifier l'arborescence finale attendue :
  ```
  ghabetna/
  ├── services/
  │   └── user-forest-service/
  │       ├── app/
  │       │   ├── main.py
  │       │   ├── db.py
  │       │   ├── models.py
  │       │   ├── routers/
  │       │   └── ...
  │       └── requirements.txt
  ├── flutter/
  │   ├── pubspec.yaml
  │   └── lib/
  ├── docker-compose.yml        ← créé en Tâche 3
  └── .gitignore                ← créé en Tâche 5
  ```

---

## TÂCHE 2 — CORRECTION DETTE MS-1 (BACKEND)

> Objectif : Corriger les 3 issues critiques listées dans l'implementation summary avant de containeriser.
> Ne pas toucher à la logique métier — corrections d'infra uniquement.

### 2.1 — Migrer DATABASE_URL vers `.env` + pydantic-settings

- [X] **2.1.1** Dans `services/user-forest-service/`, créer le fichier `.env` :
  ```env
  DATABASE_URL=postgresql://ghabetna_user:ghabetna_pass@db:5432/forest_db
  ```
  > ⚠️ Le hostname sera `db` (nom du service Docker) — pas `localhost`

- [X] **2.1.2** Créer le fichier `.env.example` (versionné dans git) :
  ```env
  DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/forest_db
  ```

- [X] **2.1.3** Modifier `app/db.py` — remplacer la `DATABASE_URL` hardcodée par :
  ```python
  from pydantic_settings import BaseSettings

  class Settings(BaseSettings):
      DATABASE_URL: str

      class Config:
          env_file = ".env"

  settings = Settings()
  DATABASE_URL = settings.DATABASE_URL
  ```
  > `pydantic-settings` est déjà dans le stack (confirmé dans implementation summary)

- [X] **2.1.4** Vérifier que `pydantic-settings` est bien dans `requirements.txt` (déjà listé — juste confirmer)

### 2.2 — Corriger CORS

- [X] **2.2.1** Dans `app/main.py`, remplacer `allow_origins=["*"]` par :
  ```python
  import os
  allow_origins = os.getenv("CORS_ORIGINS", "http://localhost").split(",")
  ```
- [X] **2.2.2** Ajouter `CORS_ORIGINS=http://localhost:3000,http://localhost:8080` dans `.env`
- [X] **2.2.3** Ajouter `CORS_ORIGINS=http://localhost:3000,http://localhost:8080` dans `.env.example`

### 2.3 — Ajouter `.env` au `.gitignore`

- [X] **2.3.1** Dans `services/user-forest-service/`, créer ou vérifier `.gitignore` contient :
  ```
  .env
  __pycache__/
  *.pyc
  .pytest_cache/
  ```

---

## TÂCHE 3 — DOCKERFILE POUR USER-FOREST-SERVICE

> Objectif : Containeriser le service FastAPI existant sans modifier sa logique.

- [X] **3.1** Créer `services/user-forest-service/Dockerfile` :
  ```dockerfile
  FROM python:3.11-slim

  WORKDIR /app

  # Dépendances système pour psycopg2 et GeoAlchemy2
  RUN apt-get update && apt-get install -y \
      libpq-dev \
      gcc \
      && rm -rf /var/lib/apt/lists/*

  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt

  COPY . .

  EXPOSE 8000

  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```
  > Utiliser `python:3.11-slim` — léger, compatible avec toutes les dépendances du projet

- [X] **3.2** Vérifier que le point d'entrée `app.main:app` correspond bien à l'emplacement réel du `FastAPI()` dans le projet

- [X] **3.3** Créer `services/user-forest-service/.dockerignore` :
  ```
  .env
  __pycache__/
  *.pyc
  .git/
  .pytest_cache/
  ```

---

## TÂCHE 4 — DOCKER-COMPOSE À LA RACINE

> Objectif : Un seul fichier à la racine qui orchestre PostgreSQL/PostGIS + user-forest-service.
> `docker-compose up` doit tout démarrer et les endpoints doivent répondre.

- [X] **4.1** Créer `ghabetna/docker-compose.yml` :
  ```yaml
  version: "3.9"

  services:

    db:
      image: postgis/postgis:15-3.3
      container_name: ghabetna_db
      environment:
        POSTGRES_USER: ghabetna_user
        POSTGRES_PASSWORD: ghabetna_pass
        POSTGRES_DB: forest_db
      volumes:
        - postgres_data:/var/lib/postgresql/data
      ports:
        - "5432:5432"
      healthcheck:
        test: ["CMD-SHELL", "pg_isready -U ghabetna_user -d forest_db"]
        interval: 10s
        timeout: 5s
        retries: 5

    user-forest-service:
      build: ./services/user-forest-service
      container_name: ghabetna_user_forest
      env_file:
        - ./services/user-forest-service/.env
      ports:
        - "8000:8000"
      depends_on:
        db:
          condition: service_healthy
      restart: on-failure

  volumes:
    postgres_data:
  ```
  > **Pourquoi `service_healthy` ?** Le service FastAPI doit attendre que PostgreSQL soit prêt avant de démarrer — sinon les migrations `on_startup` échouent.

- [X] **4.2** Vérifier que les credentials dans `.env` (`ghabetna_user`, `ghabetna_pass`, `forest_db`) correspondent exactement aux variables `POSTGRES_USER/PASSWORD/DB` du docker-compose

- [X] **4.3** S'assurer que la `DATABASE_URL` dans `.env` pointe vers `db:5432` (hostname Docker) et non `localhost`

---

## TÂCHE 5 — .GITIGNORE RACINE

> Objectif : Un `.gitignore` propre à la racine du monorepo.

- [X] **5.1** Créer `ghabetna/.gitignore` :
  ```
  # Environnements
  .env
  *.env

  # Python
  __pycache__/
  *.pyc
  *.pyo
  .pytest_cache/
  *.egg-info/
  dist/
  build/

  # Docker
  postgres_data/

  # Flutter / Dart
  flutter/.dart_tool/
  flutter/build/
  flutter/.flutter-plugins
  flutter/.flutter-plugins-dependencies
  flutter/.packages

  # IDE
  .idea/
  .vscode/
  *.iml
  ```

---

## TÂCHE 6 — CORRECTION DETTE MS-1 (FLUTTER)

> Objectif : Corriger le hardcode `apiBaseUrl` dans le projet Flutter déplacé.
> Ne pas toucher aux écrans ni à la logique — uniquement la config réseau.

- [X] **6.1** Ouvrir `flutter/lib/config/api_config.dart`
- [X] **6.2** Remplacer la valeur hardcodée par une constante configurable :
  ```dart
  class ApiConfig {
    // Modifier cette valeur selon l'environnement :
    // - Dev local (sans Docker) : http://localhost:8000
    // - Dev avec Docker        : http://localhost:8000  (port mappé)
    // - Prod (futur)           : https://api.ghabetna.tn
    static const String apiBaseUrl = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://localhost:8000',
    );
  }
  ```
  > `String.fromEnvironment` permet de passer l'URL via `flutter run --dart-define=API_BASE_URL=...` sans modifier le code

- [X] **6.3** Vérifier que tous les services Flutter (`user_service.dart`, `forest_service.dart`, `parcelle_service.dart`, `direction_service.dart`) utilisent bien `ApiConfig.apiBaseUrl` et non une URL hardcodée directement

---

## TÂCHE 7 — VALIDATION FINALE

> Objectif : Vérifier que tout fonctionne ensemble avant de clore M0.

### 7.1 — Build Docker

- [X] **7.1.1** Depuis `ghabetna/`, exécuter :
  ```bash
  docker-compose build
  ```
  Résultat attendu : build sans erreur pour `user-forest-service`

### 7.2 — Démarrage complet

- [X] **7.2.1** Exécuter :
  ```bash
  docker-compose up
  ```
- [X] **7.2.2** Vérifier dans les logs que `db` passe en `healthy` avant que `user-forest-service` démarre
- [X] **7.2.3** Vérifier dans les logs de `user-forest-service` que les migrations `on_startup` s'exécutent sans erreur

### 7.3 — Tests endpoints

- [X] **7.3.1** Ouvrir `http://localhost:8000/docs` — la page Swagger doit s'afficher
- [X] **7.3.2** Tester `GET /roles/` — doit retourner `[]` (liste vide, pas une erreur 500)
- [X] **7.3.3** Tester `POST /roles/` avec `{"name": "admin"}` — doit retourner le rôle créé avec un `id`
- [X] **7.3.4** Tester `GET /forests/` — doit retourner `[]`
- [X] **7.3.5** Tester `GET /users/` — doit retourner `[]`

### 7.4 — Arrêt et redémarrage (persistance)

-[X].4.1** Exécuter `docker-compose down` (sans `--volumes`)
-[X]7.4.2** Exécuter `docker-compose up` à nouveau
- [X] **7.4.3** Vérifier que le rôle `admin` créé en 7.3.3 est toujours présent — confirme que le volume `postgres_data` persiste

### 7.5 — Vérification Flutter

- [X] **7.5.1** Depuis `ghabetna/flutter/`, exécuter `flutter pub get` — doit réussir sans erreur
- [X] **7.5.2** Lancer l'app Flutter (`flutter run`) et vérifier que la home screen s'affiche et communique avec le backend Docker sur `localhost:8000`

---

## RÉSUMÉ DES FICHIERS CRÉÉS / MODIFIÉS

| Fichier | Action |
|---|---|
| `ghabetna/docker-compose.yml` | ✨ Créé |
| `ghabetna/.gitignore` | ✨ Créé |
| `services/user-forest-service/Dockerfile` | ✨ Créé |
| `services/user-forest-service/.dockerignore` | ✨ Créé |
| `services/user-forest-service/.env` | ✨ Créé (non versionné) |
| `services/user-forest-service/.env.example` | ✨ Créé (versionné) |
| `services/user-forest-service/.gitignore` | ✨ Créé |
| `services/user-forest-service/app/db.py` | ✏️ Modifié (DATABASE_URL → pydantic-settings) |
| `services/user-forest-service/app/main.py` | ✏️ Modifié (CORS allow_origins) |
| `flutter/lib/config/api_config.dart` | ✏️ Modifié (apiBaseUrl → String.fromEnvironment) |

---

## CE QUI N'EST PAS DANS M0 (pour éviter toute dérive)

| Item | Milestone cible |
|---|---|
| Redis | M5 (notifications) |
| Alembic | Phase 2 |
| Auth JWT | M1 |
| Service auth-service | M1 |
| CI/CD GitHub Actions | Hors scope |
| Tests unitaires | Hors scope M0 |
| API Gateway NGINX | M8 |
| Pagination endpoints | Phase 2 |
