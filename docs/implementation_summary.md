# GHABETNA — IMPLEMENTATION SUMMARY
> Fichier vivant — mis à jour après chaque milestone terminé
> Injecter dans chaque nouvelle session IA avec ghabetna_cdc_summary.md + ghabetna_roadmap.md

---

## HOW TO USE

Après chaque milestone terminé, copier-coller ce template et remplir :

```markdown
## [MX] MILESTONE_NAME — ✅ DONE | DD mois YYYY
> Service : `nom-service` | Port : `XXXX` | DB : `xxx_db`
> Stack : ...

### Implemented
- ...

### DB Schema
```sql
...
```

### Endpoints
| Method | Route | Auth | Description |
|---|---|---|---|

### Flutter Screens
| Screen | Type | Description |

### Rules
- RULE: ...

### Known Issues
- ISSUE: ...

### Refactor Later
- REFACTOR: ...
```

---

## [MS-1] USER & FOREST MANAGEMENT — ✅ DONE | 27 mars 2026

> Service : `user-forest-service` | Port : `8000` | DB : `forest_db`
> Stack backend : FastAPI + SQLAlchemy (future=True) + GeoAlchemy2 + Shapely + passlib + psycopg2-binary + pydantic-settings + pydantic v2
> Stack frontend : Flutter SDK ^3.10.7 + flutter_map ^7.0.2 + latlong2 ^0.9.1 + http ^1.2.2 + Material 3 (useMaterial3: true, seedColor: Colors.green)
> State management : StatefulWidget + setState() natif (pas de Riverpod/Bloc/Provider)

### Implemented

**Backend :**
- CRUD Rôles — 5 endpoints, champ `name` UNIQUE
- CRUD Utilisateurs — 6 endpoints + `GET /users/superviseurs` (filtre role=superviseur)
  - Hachage PBKDF2-SHA256 via passlib — password jamais dans les réponses
  - Flag `setDirectionSecondaireId` dans updateUser pour envoyer null explicitement
  - Champ `actif` présent mais filtre `?actif=true` non implémenté sur GET /users/
- CRUD Forêts — 6 endpoints + `GET /forests/summary` (sans géométrie)
  - Validation GeoJSON : type Polygon, anneaux fermés, min 4 points, coords numériques
  - Gestion GeoJSON Geometry ET Feature wrapper dans `geo_utils.py`
  - Non-chevauchement via `ST_Intersects` PostGIS
  - Validation Shapely `is_valid` (pas d'auto-intersection)
  - Réponses construites manuellement avec `geometry_to_geojson()` (évite lazy-loading GeoAlchemy2)
- CRUD Parcelles — 7 endpoints + `GET /parcelles/by_forest/{id}/summary`
  - Containment strict via `ST_Contains`
  - Non-contact/chevauchement via `NOT ST_Disjoint`
  - Calcul surface : `area_deg × (111320²) / 10000` — APPROXIMATION (distorsion latitude)
- CRUD Directions Régionales — 5 endpoints + protection FK avant DELETE
- CRUD Directions Secondaires — 6 endpoints + `GET /by-regionale/{id}` + protection FK avant DELETE
- Source unique des routes directions : `directions.py` expose `router_regionales` + `router_secondaires`
- Index GIST créés au startup (`CREATE INDEX IF NOT EXISTS`) sur `forests.geom` et `parcelles.geom`
- Migrations artisanales dans `on_startup` via liste `_migrations` de `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`

**`geo_utils.py` (module transverse) :**
- `_extract_and_validate_polygon_geojson(geojson)` — validation structure
- `geojson_to_geometry(geojson)` — parse → Shapely → validation → WKB GeoAlchemy2
- `geometry_to_geojson(geom)` — WKB → Shapely → dict GeoJSON

**Flutter (8 écrans — `user_forest_app/lib/`) :**
- `home_screen.dart` — dashboard responsive LayoutBuilder (Row >800px / Column <800px), `scaffoldBackgroundColor: Color(0xFFF4F5F7)`
- `user_management_screen.dart` — CRUD users + attribution rôle + affectation direction (tout ici, pas d'écran séparé)
- `directions_screen.dart` — hiérarchie DR/DS arborescente
- `add_forest_screen.dart` — formulaire + dessin polygone interactif flutter_map (click to add vertex, supprimer dernier point)
- `edit_forest_screen.dart` — édition forêt + carte
- `forest_list_screen.dart` — liste forêts avec accès édition/parcelles
- `parcelle_screen.dart` — gestion parcelles sur carte
- ~~`assign_superviseur_screen.dart`~~ — **SUPPRIMÉ** (fonctionnalité intégrée dans user_management_screen)

**Services Flutter (`services/`) :**
- `user_service.dart` — CRUD + filtre superviseurs + flag `setDirectionSecondaireId`
- `forest_service.dart` — CRUD forêts
- `parcelle_service.dart` — CRUD parcelles
- `direction_service.dart` — CRUD DR + DS

**Modèles Flutter (`models/`) :**
- `user.dart` (User + Role), `forest.dart`, `parcelle.dart`, `direction_regionale.dart`, `direction_secondaire.dart`
- Pattern : `fromJson()` sur tous les modèles
- Pas de `toJson()` sur les modèles — sérialisation inline dans les services

**Config Flutter :**
- `config/api_config.dart` — `apiBaseUrl` constante (à migrer vers `.env` après M0)
- Pas de token auth dans les headers HTTP (à ajouter après M1)

### DB Schema

```sql
-- forest_db

CREATE TABLE roles (
  id   SERIAL PRIMARY KEY,
  name VARCHAR(50) NOT NULL UNIQUE  -- 'admin','agent_forestier','superviseur'
);

CREATE TABLE direction_regionale (
  id          SERIAL PRIMARY KEY,
  nom         VARCHAR NOT NULL UNIQUE,
  gouvernorat VARCHAR NOT NULL
);

CREATE TABLE direction_secondaire (
  id        SERIAL PRIMARY KEY,
  nom       VARCHAR NOT NULL,
  region_id INTEGER NOT NULL REFERENCES direction_regionale(id)
);
CREATE INDEX ON direction_secondaire(region_id);

CREATE TABLE users (
  id                      SERIAL PRIMARY KEY,
  username                VARCHAR(50)  NOT NULL UNIQUE,
  email                   VARCHAR(255) NOT NULL UNIQUE,
  hashed_password         VARCHAR(255) NOT NULL,
  role_id                 INTEGER NOT NULL REFERENCES roles(id),
  direction_secondaire_id INTEGER REFERENCES direction_secondaire(id),  -- superviseur=rempli, agent=NULL
  direction_regionale_id  INTEGER REFERENCES direction_regionale(id),   -- agent=rempli, superviseur=NULL
  telephone               VARCHAR(50),
  actif                   BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX ON users(username);
CREATE INDEX ON users(email);
CREATE INDEX ON users(direction_secondaire_id);
CREATE INDEX ON users(direction_regionale_id);

CREATE TABLE forests (
  id                      SERIAL PRIMARY KEY,
  name                    VARCHAR(100) NOT NULL,
  description             TEXT,
  geom                    GEOMETRY(POLYGON, 4326) NOT NULL,
  created_by_id           INTEGER REFERENCES users(id),
  direction_secondaire_id INTEGER REFERENCES direction_secondaire(id),
  direction_regionale_id  INTEGER REFERENCES direction_regionale(id),
  surface_ha              FLOAT,
  type_foret              VARCHAR
);
CREATE INDEX ix_forests_geom ON forests USING GIST (geom);

CREATE TABLE parcelles (
  id            SERIAL PRIMARY KEY,
  forest_id     INTEGER NOT NULL REFERENCES forests(id) ON DELETE CASCADE,
  name          VARCHAR(100) NOT NULL,
  description   TEXT,
  geom          GEOMETRY(POLYGON, 4326) NOT NULL,
  surface_ha    FLOAT,
  created_by_id INTEGER REFERENCES users(id)
);
CREATE INDEX ON parcelles(forest_id);
CREATE INDEX ix_parcelles_geom ON parcelles USING GIST (geom);
```

### Endpoints

| Method | Route | Auth | Description |
|---|---|---|---|
| POST | /roles/ | ❌ none | Créer rôle |
| GET | /roles/ | ❌ none | Lister rôles |
| GET | /roles/{id} | ❌ none | Obtenir rôle |
| PUT | /roles/{id} | ❌ none | Modifier rôle |
| DELETE | /roles/{id} | ❌ none | Supprimer rôle |
| POST | /users/ | ❌ none | Créer user |
| GET | /users/ | ❌ none | Lister users |
| GET | /users/superviseurs | ❌ none | Lister superviseurs |
| GET | /users/{id} | ❌ none | Obtenir user |
| PUT | /users/{id} | ❌ none | Modifier user |
| DELETE | /users/{id} | ❌ none | Supprimer user |
| POST | /forests/ | ❌ none | Créer forêt + validation GeoJSON |
| GET | /forests/ | ❌ none | Lister forêts (avec géométrie) |
| GET | /forests/summary | ❌ none | Lister forêts (sans géométrie) |
| GET | /forests/{id} | ❌ none | Obtenir forêt |
| PUT | /forests/{id} | ❌ none | Modifier forêt |
| DELETE | /forests/{id} | ❌ none | Supprimer forêt |
| POST | /parcelles/ | ❌ none | Créer parcelle + ST_Contains |
| GET | /parcelles/ | ❌ none | Lister parcelles |
| GET | /parcelles/by_forest/{id} | ❌ none | Parcelles d'une forêt |
| GET | /parcelles/by_forest/{id}/summary | ❌ none | Parcelles sans géométrie |
| GET | /parcelles/{id} | ❌ none | Obtenir parcelle |
| PUT | /parcelles/{id} | ❌ none | Modifier parcelle |
| DELETE | /parcelles/{id} | ❌ none | Supprimer parcelle |
| POST | /directions-regionales/ | ❌ none | Créer DR |
| GET | /directions-regionales/ | ❌ none | Lister DR |
| GET | /directions-regionales/{id} | ❌ none | Obtenir DR |
| PUT | /directions-regionales/{id} | ❌ none | Modifier DR |
| DELETE | /directions-regionales/{id} | ❌ none | Supprimer DR (protection FK) |
| POST | /directions-secondaires/ | ❌ none | Créer DS |
| GET | /directions-secondaires/ | ❌ none | Lister DS |
| GET | /directions-secondaires/by-regionale/{id} | ❌ none | DS par région |
| GET | /directions-secondaires/{id} | ❌ none | Obtenir DS |
| PUT | /directions-secondaires/{id} | ❌ none | Modifier DS |
| DELETE | /directions-secondaires/{id} | ❌ none | Supprimer DS (protection FK) |

> À ajouter après M1 :
> `GET /users/by-email/{email}` — endpoint interne pour auth-service (login)
> `GET /geo/parcelle-at?lat=X&lng=Y` — ST_Contains pour rattachement GPS (incident-service)

### Flutter Screens

| Screen | Route | Description |
|---|---|---|
| `home_screen.dart` | `/` | Dashboard responsive, navigation vers tous les écrans |
| `user_management_screen.dart` | `/users` | CRUD users + rôle + direction (tout ici) |
| `directions_screen.dart` | `/directions` | Hiérarchie DR/DS |
| `add_forest_screen.dart` | `/forests/add` | Formulaire + dessin polygone carte |
| `forest_list_screen.dart` | `/forests/list` | Liste forêts |
| `edit_forest_screen.dart` | push | Édition forêt + carte |
| `parcelle_screen.dart` | push | Gestion parcelles sur carte |

### Rules

- RULE: Un polygone forêt ne peut pas chevaucher un autre polygone forêt existant (ST_Intersects)
- RULE: Une parcelle doit être totalement contenue dans sa forêt parente (ST_Contains)
- RULE: Une parcelle ne peut pas toucher ni chevaucher une autre parcelle de la même forêt (NOT ST_Disjoint)
- RULE: Impossible de supprimer une Direction Régionale si elle a des Directions Secondaires (protection FK)
- RULE: Impossible de supprimer une Direction Secondaire si elle a des users ou forêts associés (protection FK)
- RULE: email et username sont UNIQUE dans users — vérification avant INSERT avec HTTPException(400)
- RULE: agent.direction_regionale_id = rempli, direction_secondaire_id = NULL
- RULE: superviseur.direction_secondaire_id = rempli, direction_regionale_id = NULL
- RULE: password hashé PBKDF2-SHA256 — jamais retourné dans UserRead

### Known Issues

- ISSUE: Aucune authentification JWT — tous les endpoints sont publics (corrigé en M1)
- ISSUE: DATABASE_URL hardcodée avec password `1234` dans `app/db.py` (corrigé en M0)
- ISSUE: CORS `allow_origins=["*"]` — dangereux en prod (corrigé en M0)
- ISSUE: `db.query(Model).get(id)` déprécié SQLAlchemy 2.0 — utiliser `db.get(Model, id)`
- ISSUE: Calcul surface approximatif (`area_deg × 111320²`) — inexact hors petites zones (low priority)
- ISSUE: Filtre `?actif=true` sur GET /users/ non implémenté — champ présent en DB mais ignoré
- ISSUE: Pas de timeout HTTP côté Flutter (risque freeze sur réseau lent)
- ISSUE: Pas de pagination sur /forests/ et /parcelles/ — `limit=1000` par défaut
- ISSUE: Migrations artisanales dans on_startup — non versionnées, non réversibles (migrer vers Alembic)
- ISSUE: Versions Python non pinnées dans requirements.txt (pas de `==x.y.z`)
- ISSUE: Aucun test (0% couverture)

### Refactor Later

- REFACTOR: Migrer DATABASE_URL vers pydantic-settings BaseSettings + .env (priorité M0)
- REFACTOR: Remplacer migrations on_startup par Alembic (Phase 2)
- REFACTOR: Ajouter `db.get(Model, id)` à la place de `db.query(Model).get(id)` (Phase 2)
- REFACTOR: Ajouter filtre `?actif=true` sur GET /users/ (Phase 2)
- REFACTOR: Remplacer calcul surface approx par `ST_Area(ST_Transform(geom, 3857))` PostGIS (Phase 2)
- REFACTOR: Ajouter pagination `{data, total, skip, limit}` sur /forests/ et /parcelles/ (Phase 2)
- REFACTOR: Migrer state management Flutter vers Riverpod si app grandit (post-soutenance)
- REFACTOR: Ajouter timeout `.timeout(Duration(seconds: 30))` sur tous les appels HTTP Flutter (Phase 2)
- REFACTOR: Remplacer `echo=True` SQLAlchemy par loguru ou structlog (Phase 2)
- REFACTOR: Pincer versions dans requirements.txt avec `pip freeze > requirements.lock` (Phase 2)
- REFACTOR: Ajouter endpoint `/health` pour monitoring et sondes Docker (Phase 2)

---

## [M0] SOCLE TECHNIQUE — ✅ DONE | 31 mars 2026
> Service : N/A (infra only) | Port : N/A | DB : forest_db
> Stack : Docker + docker-compose + PostgreSQL/PostGIS 15-3.3 + pydantic-settings + Flutter String.fromEnvironment

### Implemented
- Monorepo : `ghabetna/services/user_management/` (backend) + `ghabetna/flutter/user_forest_app/` (Flutter)
- `DATABASE_URL` migrée vers pydantic-settings `BaseSettings` + `.env` — hostname `db` (Docker)
- CORS : `allow_origins` lu via `os.getenv("CORS_ORIGINS")` — plus de `["*"]`
- Dockerfile `python:3.11-slim` + `libpq-dev/gcc` + entrypoint `uvicorn app.main:app`
- `docker-compose.yml` racine : `postgis/postgis:15-3.3` + healthcheck `pg_isready` + `depends_on: service_healthy` + volume `postgres_data`
- `.env.example` versionné, `.env` exclu via `.gitignore` (racine + service)
- Flutter `apiBaseUrl` → `String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000')`

### Rules (for future milestones)
- RULE: `DATABASE_URL` toujours via pydantic-settings + `.env` — jamais hardcodée
- RULE: `.env` jamais versionné — seul `.env.example` l'est
- RULE: `allow_origins=["*"]` interdit — toujours via `os.getenv("CORS_ORIGINS")`
- RULE: `depends_on: condition: service_healthy` obligatoire pour tout service qui dépend de `db`
- RULE: URL backend Flutter via `String.fromEnvironment` — jamais hardcodée dans les services
- RULE: Redis absent jusqu'à M5 — aucune dépendance Redis avant
- RULE: Alembic absent jusqu'à Phase 2 — migrations via `_migrations` on_startup

### Refactor Later
- ~~REFACTOR: Renommer `services/user_management/` → `services/user-forest-service/` et aplatir `flutter/user_forest_app/` → `flutter/`~~ — ✅ **FAIT en M1**
- ~~REFACTOR: Pinner les versions `requirements.txt` (ex. `fastapi==0.111.0`)~~ — ✅ **FAIT en M1** (auth-service pinné, user-forest-service à vérifier)
- REFACTOR: Ajouter `version: "3.9"` au `docker-compose.yml` — **M1 (trivial)**
- ~~REFACTOR: Ajouter Redis dans `docker-compose.yml`~~ — ✅ **FAIT en M1**
- REFACTOR: Remplacer migrations artisanales par Alembic — **Phase 2**

## [M1] AUTH SERVICE — ✅ DONE | 03 avril 2026

> Service : `auth-service` | Port : `8001` | DB : Redis (pas PostgreSQL)
> Stack backend : FastAPI + python-jose (HS256) + passlib (pbkdf2_sha256) + redis-py async + httpx + pydantic-settings + email-validator
> Stack frontend : flutter_secure_storage ^9.2.4 + http ^1.2.2 (AuthenticatedClient)
> Inter-service : auth-service → user-forest-service via `X-Service-Secret` header + httpx

### Implemented

**auth-service (nouveau micro-service) :**
- `POST /auth/login` — rate-limited (5 req/min/IP via Redis INCR+EXPIRE), admin-only
  - Appel inter-service `GET /users/by-email/{email}` avec `X-Service-Secret`
  - Vérifie `actif`, `role == "admin"`, puis `verify_password` PBKDF2-SHA256
  - Retourne `TokenResponse(access_token, refresh_token, token_type, role)`
- `POST /auth/refresh` — token rotation : révoque l'ancien jti, crée nouveau access + refresh
- `POST /auth/logout` — idempotent, révoque le refresh token depuis Redis
- `GET /health` — sonde Docker
- `app/utils/jwt.py` — `create_access_token`, `create_refresh_token` (jti=uuid4), `decode_token`
- `app/utils/password.py` — `verify_password` uniquement (auth-service ne crée pas d'users)
- `app/models.py` — `LoginRequest`, `TokenResponse`, `RefreshRequest`, `AccessTokenResponse`, `TokenPayload`
- `app/config.py` — pydantic-settings `BaseSettings` : `JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `REDIS_URL`, `USER_SERVICE_URL`, `SERVICE_SECRET`, `CORS_ORIGINS`

**JWT HS256 — structure des tokens :**
- Access token : `{sub (str), role, type="access", exp=now+15min}`
- Refresh token : `{sub (str), role, type="refresh", jti=uuid4, exp=now+7j}`
- Redis key : `refresh:{jti}` → `user_id`, TTL = `REFRESH_TOKEN_EXPIRE_DAYS × 86400`
- `decode_token` convertit `sub` en `int`; lève `HTTPException(401)` sur expiry/invalid

**Rate limiting :**
- Clé Redis : `rate_limit:login:{ip}` — INCR atomique + EXPIRE 60s au premier hit
- Seuil : 5 req/min → HTTP 429

**user-forest-service — ajouts M1 :**
- `app/utils/jwt_guard.py` — `get_current_user()`, `require_roles(*roles)`, `verify_service_secret()`
  - `OAuth2PasswordBearer(tokenUrl="http://localhost:8001/auth/login")` — URL hardcodée (Swagger uniquement)
  - `require_roles` → `HTTPException(403)` si rôle insuffisant
  - `verify_service_secret` → `Header(alias="X-Service-Secret")` → `HTTPException(403)` si mismatch
- `GET /users/by-email/{email}` — endpoint interne (`include_in_schema=False`), `Depends(verify_service_secret)`
  - Retourne `UserAuthRead` avec `hashed_password` et `role` name — jamais exposé publiquement
- Tous les endpoints CRUD désormais protégés par JWT (`Depends(get_current_user)` ou `require_roles`)

**docker-compose — ajouts M1 :**
- Service `redis` : image `redis:7-alpine`, healthcheck `redis-cli ping`, volume `redis_data`
- Service `auth-service` : port `8001`, `depends_on: redis: condition: service_healthy`
- Note : `auth-service` dépend aussi de `db` dans compose (inutile — auth-service n'utilise pas PostgreSQL)

**Flutter — ajouts M1 (`flutter/lib/`) :**
- `utils/token_storage.dart` — `saveTokens`, `getAccessToken`, `getRefreshToken`, `clearTokens`, `isLoggedIn` via `flutter_secure_storage`
- `utils/http_client.dart` — `AuthenticatedClient extends http.BaseClient`
  - Injecte `Authorization: Bearer {token}` sur chaque requête
  - Sur 401 : refresh automatique + retry une fois
  - Sur double 401 : `clearTokens()` + retourne le 401 original
  - Timeout 30s sur chaque send
- `services/auth_service.dart` — `login()`, `refreshAccessToken()`, `logout()`
  - `login` : `POST /auth/login` avec JSON `{email, password}` + sauvegarde tokens
  - Différencie 403 "Account disabled" vs 403 "Admin only" via `detail` field
- `config/api_config.dart` — `authBaseUrl` pour auth-service (port 8001)
- `screens/login_screen.dart` — formulaire email/password, Material 3, gestion erreurs par code HTTP
- `screens/home_screen.dart` — auth guard dans `initState` (`isLoggedIn` → redirect `/login`), bouton logout dans AppBar
- `main.dart` — `initialRoute: '/login'`, routes `/login` → `LoginScreen`, `/` → `HomeScreen`
- `screens/user_management_screen.dart` — corrigé : `_httpClient = AuthenticatedClient()` (était `http.Client()`)

**Tests M1 :**
- `services/auth-service/tests/test_jwt.py` — unit tests : création access/refresh, decode, expiry, type validation
- `docs/test_scripts/test_f2_auth_flow.sh` — test curl end-to-end : login → refresh → logout
- `docs/test_scripts/test_f3_guards.sh` — test curl : guards JWT (401 sans token, 403 mauvais rôle)

### Endpoints auth-service

| Method | Route | Auth | Description |
|---|---|---|---|
| POST | /auth/login | ❌ none (rate-limited) | Login email+password → access+refresh tokens |
| POST | /auth/refresh | ❌ none | Rotation refresh token → nouveaux tokens |
| POST | /auth/logout | ❌ none | Révocation refresh token (idempotent) |
| GET | /health | ❌ none | Health check Docker |

### Endpoints user-forest-service — ajouts M1

| Method | Route | Auth | Description |
|---|---|---|---|
| GET | /users/by-email/{email} | 🔒 X-Service-Secret | Endpoint interne auth-service (non documenté Swagger) |
| (tous les autres) | /users/, /forests/, /parcelles/, /directions-* | 🔒 JWT Bearer | Protégés depuis M1 |

### Flutter Screens

| Screen | Route | Description |
|---|---|---|
| `login_screen.dart` | `/login` | Formulaire email/password + gestion 401/403/429/5xx |
| `home_screen.dart` | `/` | Auth guard initState + logout AppBar |

### Rules

- RULE: Seuls les users avec `role == "admin"` peuvent se connecter au portail web
- RULE: `actif == false` → HTTP 403 "Account disabled" avant vérification du mot de passe
- RULE: Rate limit 5 req/min par IP sur `/auth/login` — clé Redis atomique `rate_limit:login:{ip}`
- RULE: Token rotation obligatoire au refresh — l'ancien jti est supprimé de Redis avant d'émettre le nouveau
- RULE: Logout est idempotent — token expiré ou invalide est ignoré silencieusement
- RULE: `X-Service-Secret` obligatoire sur les endpoints inter-services — jamais exposés en Swagger
- RULE: `flutter_secure_storage` uniquement pour les tokens — jamais `SharedPreferences`
- RULE: `AuthenticatedClient` obligatoire sur tous les appels HTTP Flutter après M1 — plus de `http.Client()` nu
- RULE: Access token expire en 15min, refresh token en 7 jours — configurable via `.env`

### Known Issues

- ISSUE: `passlib[bcrypt]` dans requirements.txt — bcrypt non utilisé (seul pbkdf2_sha256 est actif)
- ISSUE: `pytest==8.3.5` dans requirements.txt prod — doit être dans `requirements-test.txt` séparé
- ISSUE: `class Config: env_file = ".env"` dans `config.py` — pattern déprécié pydantic-settings v2 (utiliser `model_config = SettingsConfigDict(...)`)
- ISSUE: `OAuth2PasswordBearer(tokenUrl="http://localhost:8001/auth/login")` hardcodé — cassé hors localhost (Swagger uniquement, pas fonctionnel)
- ISSUE: `auth-service` `depends_on: db` dans docker-compose inutile — auth-service n'utilise pas PostgreSQL
- ISSUE: `AuthenticatedClient` ne redirige pas vers `/login` après refresh échoué — `home_screen` gère le redirect passivement via `initState`
- ISSUE: Restriction `role == "admin"` uniquement — les superviseurs n'ont pas accès au portail web (à revoir en M4 selon CDC)

### Refactor Later

- REFACTOR: Séparer `requirements-test.txt` de `requirements.txt` (enlever pytest du prod)
- REFACTOR: Migrer `class Config` vers `model_config = SettingsConfigDict(env_file=".env")` dans `config.py`
- REFACTOR: Remplacer bcrypt par pbkdf2_sha256 dans `passlib[pbkdf2]` (éviter dépendance bcrypt inutile)
- REFACTOR: Rendre `tokenUrl` configurable via env (pour Swagger en staging/prod)
- REFACTOR: Supprimer `depends_on: db` dans auth-service du docker-compose
- REFACTOR: Ajouter redirect `/login` depuis `AuthenticatedClient` quand refresh échoue (nécessite NavigatorKey global)
- REFACTOR: Ouvrir accès portail web aux superviseurs en M4 (restriction admin-only temporaire)

---

## [M2] MS-1 SÉCURISÉ + AFFECTATION PARCELLE — ⬜ TODO

> À remplir après completion

---

## [M3] INCIDENT SERVICE + MOBILE AGENT — ⬜ TODO

> À remplir après completion

---

## [M4] DASHBOARD SUPERVISEUR FLUTTER WEB — ⬜ TODO

> À remplir après completion

---

## [M5] NOTIFICATION TELEGRAM — ⬜ TODO

> À remplir après completion

---

## [M6] SCORING AGENTS — ⬜ TODO

> À remplir après completion

---

## [M7] ANALYTICS + HEATMAP — ⬜ TODO

> À remplir après completion

---

## [M8] API GATEWAY NGINX — ⬜ TODO

> À remplir après completion

