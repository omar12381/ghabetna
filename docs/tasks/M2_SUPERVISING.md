# GHABETNA — M2 : MS-1 SÉCURISÉ + AFFECTATION PARCELLE
> Milestone : M2 | Statut : ⬜ TODO
> Période : ~4 avril → ~8 avril 2026 | Durée estimée : 5 jours
> Dépend de : MS-1 ✅ + M1 ✅
> Exit condition : Superviseur se connecte sur son portail, voit les agents de sa direction secondaire + les agents libres de sa direction régionale, affecte un agent à une parcelle de SA direction secondaire. L'affectation est persistée dans `incident_db` (incident-service) et visible.

---

## RÈGLES MÉTIER FIGÉES

```
Superviseur (users.direction_secondaire_id = DS.id, DS.region_id = DR.id)
 └─ Voit les agents :
     (A) Agents WHERE direction_secondaire_id = DS.id          ← son équipe directe
     (B) Agents WHERE direction_regionale_id  = DR.id
         AND id NOT IN (agent_ids actifs dans incident_db)     ← agents libres de sa région

 └─ Peut affecter un agent vers :
     parcelles WHERE forest.direction_secondaire_id = DS.id    ← parcelles de SA direction secondaire uniquement

 └─ Contraintes affectation :
     agent.direction_regionale_id == DS.region_id              ← même région obligatoire
     Un agent = une seule affectation active (UNIQUE agent_id WHERE actif=TRUE)
     Plusieurs agents peuvent partager une même parcelle (pas de UNIQUE sur parcelle_id)

 └─ Après affectation d'un agent libre (type B) :
     → PATCH http://user-forest-service:8000/users/{agent_id}
     agent.direction_secondaire_id mis à jour → DS.id du superviseur
     (l'agent rejoint officiellement la direction secondaire du superviseur)
```

---

## ARCHITECTURE M2

```
[Flutter Superviseur Web]
        │
        ├──→ POST/GET/DELETE /affectations/*  ──→ [incident-service :8002] ──→ [incident_db PostgreSQL]
        │                                               │
        │                                               ├──→ GET /users/{id}              ──→ [user-forest-service :8000]
        │                                               ├──→ GET /parcelles/{id}          ──→ [user-forest-service :8000]
        │                                               ├──→ GET /forests/{id}            ──→ [user-forest-service :8000]
        │                                               └──→ PATCH /users/{agent_id}      ──→ [user-forest-service :8000]
        │
        ├──→ GET /users/agents/mon-equipe      ──→ [user-forest-service :8000] ──→ [forest_db PostgreSQL]
        │       (appelle incident-service en interne pour savoir qui est affecté)
        ├──→ GET /forests/ + /parcelles/       ──→ [user-forest-service :8000]
        └──→ POST /auth/login                  ──→ [auth-service :8001]        ──→ [Redis]
```

### Microservices M2

| Service | Port | DB | Rôle en M2 |
|---|---|---|---|
| user-forest-service | 8000 | forest_db | Source de vérité : users, parcelles, forêts, directions |
| auth-service | 8001 | Redis | Login superviseur + JWT avec direction ids |
| **incident-service** | **8002** | **incident_db** | **NOUVEAU — affectations agents/parcelles (M3 y ajoutera les incidents)** |

### Règle inter-services
- `incident-service` ne possède **aucune donnée** sur les users, parcelles ou forêts
- Il les **récupère à la demande** via HTTP vers `user-forest-service` avec le header `X-Service-Secret`
- Toutes les validations métier se font dans `incident-service` après récupération des données
- Les IDs dans `incident_db` sont des **FK logiques** — pas de vraies FK PostgreSQL inter-DB

---

## TÂCHES & SOUS-TÂCHES

---

### [X] T1 — SETUP INCIDENT-SERVICE
**Composant :** Backend — nouveau microservice
**Priorité :** 🔴 Critique
**Dossier :** `services/incident-service/`

#### Sous-tâches

**T1.1 — Structure du projet**
```
services/incident-service/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── utils/
│   │   ├── jwt_guard.py        ← copié + adapté depuis user-forest-service
│   │   └── http_client.py      ← client httpx pour appels inter-services
│   └── routers/
│       └── affectations.py
├── requirements.txt
├── Dockerfile
└── .env
```

**T1.2 — `requirements.txt`**
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
psycopg2-binary==2.9.9
pydantic-settings==2.2.1
httpx==0.27.0
python-jose[cryptography]==3.3.0
passlib==1.7.4
```

**T1.3 — `config.py`**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str
    JWT_SECRET_KEY: str
    SERVICE_SECRET: str
    USER_FOREST_SERVICE_URL: str   # http://user-forest-service:8000
    CORS_ORIGINS: list[str] = ["*"]

settings = Settings()
```

**T1.4 — `.env`**
```
DATABASE_URL=postgresql://postgres:postgres@db:5432/incident_db
JWT_SECRET_KEY=same_secret_as_auth_service
SERVICE_SECRET=same_secret_as_other_services
USER_FOREST_SERVICE_URL=http://user-forest-service:8000
```

**T1.5 — `database.py`**
```python
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

engine = create_engine(settings.DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

_migrations = []  # rempli dans T2.2
```

**T1.6 — `main.py`**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, engine, _migrations
from app.routers import affectations
from sqlalchemy import text

app = FastAPI(title="Ghabetna — Incident Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def on_startup():
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        for sql in _migrations:
            conn.execute(text(sql))
        conn.commit()

app.include_router(affectations.router, prefix="/affectations", tags=["Affectations"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "incident-service"}
```

**T1.7 — `Dockerfile`**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
```

**T1.8 — Ajouter dans `docker-compose.yml`**
```yaml
incident-service:
  build: ./services/incident-service
  ports:
    - "8002:8002"
  env_file: ./services/incident-service/.env
  depends_on:
    db:
      condition: service_healthy
    user-forest-service:
      condition: service_started
  networks:
    - ghabetna-network
```
> Ajouter `incident_db` dans le script `docker/init-multiple-dbs.sh` s'il existe, sinon créer manuellement via `CREATE DATABASE incident_db`.

---

### [X] T2 — TABLE `agent_parcelle_assignments` + MIGRATION (incident_db)
**Composant :** Backend — incident-service
**Priorité :** 🔴 Critique
**Fichiers :** `app/models.py`, `app/schemas.py`, `app/database.py`

#### Sous-tâches

**T2.1 — Modèle SQLAlchemy**
```python
# app/models.py
from sqlalchemy import Column, Integer, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base

class AgentParcelleAssignment(Base):
    __tablename__ = "agent_parcelle_assignments"

    id                = Column(Integer, primary_key=True, index=True)
    agent_id          = Column(Integer, nullable=False)   # FK logique → forest_db.users.id
    parcelle_id       = Column(Integer, nullable=False)   # FK logique → forest_db.parcelles.id
    forest_id         = Column(Integer, nullable=False)   # FK logique → forest_db.forests.id
    dir_secondaire_id = Column(Integer, nullable=False)   # FK logique → forest_db.direction_secondaire.id
    dir_regionale_id  = Column(Integer, nullable=False)   # FK logique → forest_db.direction_regionale.id
    assigned_by       = Column(Integer, nullable=False)   # FK logique → forest_db.users.id (superviseur)
    assigned_at       = Column(DateTime(timezone=True), server_default=func.now())
    actif             = Column(Boolean, nullable=False, default=True)
```

**T2.2 — Migrations artisanales**
```python
# app/database.py — liste _migrations
_migrations = [
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_assignment_actif
    ON agent_parcelle_assignments (agent_id)
    WHERE actif = TRUE
    """,
    "CREATE INDEX IF NOT EXISTS ix_apa_parcelle ON agent_parcelle_assignments (parcelle_id)",
    "CREATE INDEX IF NOT EXISTS ix_apa_ds       ON agent_parcelle_assignments (dir_secondaire_id)",
    "CREATE INDEX IF NOT EXISTS ix_apa_dr       ON agent_parcelle_assignments (dir_regionale_id)",
    "CREATE INDEX IF NOT EXISTS ix_apa_assigned ON agent_parcelle_assignments (assigned_by)",
]
```

**T2.3 — Schémas Pydantic**
```python
# app/schemas.py
from pydantic import BaseModel
from datetime import datetime

class AssignmentCreate(BaseModel):
    agent_id: int
    parcelle_id: int

class AssignmentRead(BaseModel):
    id: int
    agent_id: int
    parcelle_id: int
    forest_id: int
    dir_secondaire_id: int
    dir_regionale_id: int
    assigned_by: int
    assigned_at: datetime
    actif: bool
    # Données enrichies récupérées depuis user-forest-service
    agent_username: str
    parcelle_name: str
    forest_name: str
    model_config = {"from_attributes": True}

class AssignmentMinimal(BaseModel):
    parcelle_id: int | None = None
    parcelle_name: str | None = None
    forest_id: int | None = None
    forest_name: str | None = None

class AgentIdsResponse(BaseModel):
    agent_ids: list[int]
```

---

### [X] T3 — CLIENT HTTP INTER-SERVICES
**Composant :** Backend — incident-service
**Priorité :** 🔴 Critique
**Fichier :** `app/utils/http_client.py`

#### Sous-tâches

**T3.1 — Fonctions httpx avec X-Service-Secret**
```python
import httpx
from fastapi import HTTPException
from app.config import settings

HEADERS = {"X-Service-Secret": settings.SERVICE_SECRET}
BASE = settings.USER_FOREST_SERVICE_URL

async def get_user(user_id: int) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE}/users/{user_id}", headers=HEADERS, timeout=5.0)
    if r.status_code == 404:
        raise HTTPException(404, f"Agent {user_id} introuvable")
    if r.status_code != 200:
        raise HTTPException(502, "Erreur communication user-forest-service")
    return r.json()

async def get_parcelle(parcelle_id: int) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE}/parcelles/{parcelle_id}", headers=HEADERS, timeout=5.0)
    if r.status_code == 404:
        raise HTTPException(404, f"Parcelle {parcelle_id} introuvable")
    if r.status_code != 200:
        raise HTTPException(502, "Erreur communication user-forest-service")
    return r.json()

async def get_forest(forest_id: int) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE}/forests/{forest_id}", headers=HEADERS, timeout=5.0)
    if r.status_code == 404:
        raise HTTPException(404, f"Forêt {forest_id} introuvable")
    if r.status_code != 200:
        raise HTTPException(502, "Erreur communication user-forest-service")
    return r.json()

async def patch_user_direction_secondaire(agent_id: int, dir_secondaire_id: int) -> None:
    async with httpx.AsyncClient() as client:
        r = await client.patch(
            f"{BASE}/users/{agent_id}",
            headers=HEADERS,
            json={"direction_secondaire_id": dir_secondaire_id},
            timeout=5.0
        )
    if r.status_code not in (200, 204):
        raise HTTPException(502, "Impossible de mettre à jour la direction de l'agent")
```

**T3.2 — Ajouter `PATCH /users/{id}` interne dans user-forest-service**
- `include_in_schema=False`, protégé par `verify_service_secret`
- Body : `{"direction_secondaire_id": int}`
- Met à jour uniquement ce champ → retourne HTTP 204

---

### [X] T4 — JWT GUARD DANS INCIDENT-SERVICE
**Composant :** Backend — incident-service
**Priorité :** 🔴 Critique
**Fichier :** `app/utils/jwt_guard.py`

#### Sous-tâches

**T4.1 — `CurrentUser` dataclass + `get_current_user` + `require_roles`**
```python
from dataclasses import dataclass
from fastapi import Depends, HTTPException, Header
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8001/auth/login")

@dataclass
class CurrentUser:
    id: int
    role: str
    direction_secondaire_id: int | None
    direction_regionale_id: int | None

def get_current_user(token: str = Depends(oauth2_scheme)) -> CurrentUser:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        if payload.get("type") != "access":
            raise HTTPException(401, "Token invalide")
        return CurrentUser(
            id=int(payload["sub"]),
            role=payload["role"],
            direction_secondaire_id=payload.get("direction_secondaire_id"),
            direction_regionale_id=payload.get("direction_regionale_id"),
        )
    except JWTError:
        raise HTTPException(401, "Token invalide ou expiré")

def require_roles(*roles: str):
    def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles:
            raise HTTPException(403, f"Accès réservé aux rôles : {', '.join(roles)}")
        return user
    return checker

def verify_service_secret(x_service_secret: str = Header(alias="X-Service-Secret")):
    if x_service_secret != settings.SERVICE_SECRET:
        raise HTTPException(403, "Secret inter-service invalide")
```

---

### [X] T5 — ENDPOINTS AFFECTATION (incident-service)
**Composant :** Backend — incident-service
**Priorité :** 🔴 Critique
**Fichier :** `app/routers/affectations.py`

#### Sous-tâches

**T5.1 — `POST /affectations/`** — Affecter un agent à une parcelle
```
Flux complet :
1. require_roles("superviseur") → CurrentUser superviseur
2. Vérifier superviseur.direction_secondaire_id is not None → sinon HTTP 400

3. GET user-forest-service /users/{agent_id}
   → agent.actif == True          → sinon HTTP 403 "Agent inactif"
   → agent.role == "agent_forestier" → sinon HTTP 403
   → agent.direction_regionale_id == superviseur.direction_regionale_id
                                   → sinon HTTP 403 "Agent hors de votre région"

4. GET user-forest-service /parcelles/{parcelle_id}
   → récupérer forest_id

5. GET user-forest-service /forests/{forest_id}
   → forest.direction_secondaire_id == superviseur.direction_secondaire_id
                                   → sinon HTTP 403 "Parcelle hors de votre périmètre"
   → récupérer dir_regionale_id

6. Transaction DB :
   a. UPDATE SET actif=False WHERE agent_id=? AND actif=True  ← désactiver ancienne
   b. INSERT agent_parcelle_assignments (tous les champs, actif=True)

7. Si agent.direction_secondaire_id IS NULL :
   → PATCH user-forest-service /users/{agent_id} {"direction_secondaire_id": superviseur.direction_secondaire_id}

8. Retourner AssignmentRead enrichi
```

**T5.2 — `DELETE /affectations/{agent_id}`** — Désaffecter
```
1. require_roles("superviseur")
2. SELECT affectation active WHERE agent_id=? AND actif=True → sinon HTTP 404
3. affectation.dir_secondaire_id == superviseur.direction_secondaire_id → sinon HTTP 403
4. UPDATE SET actif=False
5. HTTP 204
```

**T5.3 — `GET /affectations/`** — Liste affectations actives de la direction secondaire
```
1. require_roles("superviseur", "admin")
2. SELECT * WHERE dir_secondaire_id = superviseur.direction_secondaire_id AND actif=True
3. Enrichir en parallèle (asyncio.gather) : get_user + get_parcelle + get_forest pour chaque ligne
4. Retourner List[AssignmentRead]
```

**T5.4 — `GET /affectations/agent/{agent_id}`** — Affectation courante
```
1. require_roles("superviseur", "admin")
2. SELECT WHERE agent_id=? AND actif=True
3. Si aucune → AssignmentMinimal avec tous les champs null
4. Enrichir → retourner AssignmentMinimal
```

**T5.5 — `GET /affectations/parcelle/{parcelle_id}`** — Agents d'une parcelle
```
1. require_roles("superviseur", "admin")
2. SELECT agent_id WHERE parcelle_id=? AND actif=True
3. get_user(agent_id) pour chaque → retourner liste {id, username, email}
```

**T5.6 — `GET /affectations/agents-ids`** — Endpoint interne pour user-forest-service
```python
# include_in_schema=False — non visible dans Swagger
# Depends(verify_service_secret)
# Query param : ?dir_regionale_id=X
# SELECT agent_id FROM agent_parcelle_assignments WHERE dir_regionale_id=? AND actif=True
# Retourne : {"agent_ids": [1, 5, 12]}
```

---

### [X] T6 — ENDPOINTS AGENTS DANS USER-FOREST-SERVICE
**Composant :** Backend — user-forest-service
**Priorité :** 🔴 Critique
**Fichier :** `app/routers/users.py`

#### Sous-tâches

**T6.1 — `GET /users/agents/mon-equipe`**
- Guard : `require_roles("superviseur")`
- Extraire `direction_secondaire_id` (DS) et `direction_regionale_id` (DR) depuis JWT
- Appel interne : `GET http://incident-service:8002/affectations/agents-ids?dir_regionale_id={DR}` avec `X-Service-Secret` → liste `ids_affectes`
- Query SQL :
  ```sql
  SELECT u.id, u.username, u.email, u.telephone, u.actif,
         u.direction_secondaire_id, u.direction_regionale_id
  FROM users u
  JOIN roles r ON r.id = u.role_id AND r.name = 'agent_forestier'
  WHERE
    u.direction_secondaire_id = :ds_id
    OR (
      u.direction_regionale_id = :dr_id
      AND u.id NOT IN :ids_affectes
    )
  ORDER BY u.direction_secondaire_id NULLS LAST, u.username
  ```
- Champ `type` : `"equipe_directe"` si `direction_secondaire_id == DS`, sinon `"libre_region"`

**T6.2 — `GET /users/agents/disponibles`**
- Sous-ensemble de T6.1 — uniquement les agents `libre_region`

**T6.3 — Ajouter `?direction_secondaire_id=` sur `GET /forests/`**
- Paramètre optionnel query
- `WHERE direction_secondaire_id = ?` si présent — rétrocompatible

---

### [X] T7 — AUTH SUPERVISEUR (auth-service)
**Composant :** Backend — auth-service
**Priorité :** 🔴 Critique
**Fichier :** `app/routers/auth.py`

#### Sous-tâches

**T7.1 — Ouvrir le login aux superviseurs**
```python
# Avant
if user.role != "admin":
    raise HTTPException(403, "Accès admin uniquement")
# Après
if user.role not in ["admin", "superviseur"]:
    raise HTTPException(403, "Accès réservé aux administrateurs et superviseurs")
```

**T7.2 — Enrichir `UserAuthRead` dans user-forest-service**
```python
class UserAuthRead(BaseModel):
    id: int
    email: str
    hashed_password: str
    role: str
    actif: bool
    direction_secondaire_id: int | None   # NOUVEAU
    direction_regionale_id: int | None    # NOUVEAU
```

**T7.3 — Injecter direction ids dans le JWT**
```python
# Payload access token
{
  "sub": str(user.id),
  "role": user.role,
  "direction_secondaire_id": user.direction_secondaire_id,
  "direction_regionale_id": user.direction_regionale_id,
  "type": "access",
  "exp": ...
}
```

**T7.4 — Fixes hardening M1**
- Supprimer `depends_on: db` dans auth-service du `docker-compose.yml`
- Créer `requirements-test.txt` (retirer pytest de `requirements.txt`)
- Migrer `class Config` → `model_config = SettingsConfigDict(...)` dans `config.py`

---

### T8 — SETUP APP FLUTTER SUPERVISEUR
**Composant :** Flutter — nouvelle app
**Priorité :** 🔴 Critique
**Dossier :** `flutter_superviseur/`

#### Sous-tâches

**T8.1 — Créer le projet**
```bash
flutter create flutter_superviseur --org com.ghabetna
```

**T8.2 — `pubspec.yaml`**
```yaml
dependencies:
  flutter:
    sdk: flutter
  http: ^1.2.2
  flutter_secure_storage: ^9.2.4
  flutter_map: ^7.0.2
  latlong2: ^0.9.1
  fl_chart: ^0.68.0
dev_dependencies:
  flutter_lints: ^3.0.0
```

**T8.3 — Copier utilitaires depuis app admin**
- `lib/utils/token_storage.dart` — identique
- `lib/utils/http_client.dart` — AuthenticatedClient identique
- `lib/config/api_config.dart` :
```dart
const String forestServiceBaseUrl   = 'http://localhost:8000';
const String authBaseUrl            = 'http://localhost:8001';
const String incidentServiceBaseUrl = 'http://localhost:8002';
```

**T8.4 — Theme + `main.dart`**
```dart
// Theme
ColorScheme.fromSeed(seedColor: Colors.green, brightness: Brightness.light)
scaffoldBackgroundColor: const Color(0xFFF4F5F7)

// Routes
initialRoute: '/login',
routes: {
  '/login': (_) => const LoginScreen(),
  '/':      (_) => const HomeScreen(),
  '/agents':(_) => const AgentsScreen(),
  '/carte': (_) => const CarteParcellesScreen(),
}
```

---

### T9 — LOGIN SCREEN SUPERVISEUR
**Composant :** Flutter
**Priorité :** 🔴 Critique
**Fichier :** `lib/screens/login_screen.dart`

#### Sous-tâches

**T9.1 — Formulaire email + password avec validation client**

**T9.2 — Gestion erreurs HTTP**
- 401 → "Email ou mot de passe incorrect"
- 403 "Account disabled" → "Compte désactivé"
- 403 rôle → "Accès réservé aux superviseurs"
- 429 → "Trop de tentatives, réessayez dans 1 minute"
- 5xx → "Erreur serveur"

**T9.3 — Guard rôle côté Flutter**
```dart
// Décoder JWT (base64 payload) après login réussi
// Si role != "superviseur" → SnackBar "Interface réservée aux superviseurs" → ne pas naviguer
```

**T9.4 — Redirect vers HomeScreen si succès**

---

### T10 — HOME SCREEN / DASHBOARD SUPERVISEUR
**Composant :** Flutter
**Priorité :** 🟠 Haute
**Fichier :** `lib/screens/home_screen.dart`

#### Sous-tâches

**T10.1 — NavigationRail (>800px) / BottomNav (<800px)**
```
🏠 Tableau de bord
👥 Mon équipe
🗺️  Carte
📊 Statistiques   [placeholder M7]
⭐ Scoring         [placeholder M6]
🔔 Incidents       [placeholder M3]
```

**T10.2 — KPI Cards**
- "Agents dans mon équipe" — count total `mon-equipe`
- "Agents affectés" — count avec parcelle_affectee != null
- "Agents disponibles" — count libre_region
- "Incidents ouverts" — placeholder `--`

**T10.3 — Auth guard `initState`** + bouton logout AppBar

**T10.4 — `ComingSoonCard` widget** pour les sections placeholder (icône grise + "Disponible prochainement")

---

### T11 — AGENTS SCREEN
**Composant :** Flutter
**Priorité :** 🟠 Haute
**Fichier :** `lib/screens/agents_screen.dart`

#### Sous-tâches

**T11.1 — Charger via `GET /users/agents/mon-equipe` (user-forest-service :8000)**

**T11.2 — Deux sections visuelles**
- "Mon équipe" (equipe_directe) — header vert
- "Agents disponibles dans la région" (libre_region) — header orange

**T11.3 — `ListTile` par agent** : avatar initiales, username, email, téléphone, chip statut

**T11.4 — Actions**
- Libre → "Affecter" → `AffectationSheet`
- Affecté → "Modifier" → `AffectationSheet`
- Affecté → "Désaffecter" → confirmation → `DELETE /affectations/{agent_id}` (incident-service :8002)

**T11.5 — Barre de recherche locale + Pull-to-refresh**

---

### T12 — AFFECTATION BOTTOM SHEET
**Composant :** Flutter
**Priorité :** 🟠 Haute
**Fichier :** `lib/screens/affectation_sheet.dart`

#### Sous-tâches

**T12.1 — Header** : info agent + avertissement si déjà affecté "⚠️ Remplacera l'affectation actuelle"

**T12.2 — Dropdown Forêt** : `GET /forests/?direction_secondaire_id={ds_id}` (forest-service :8000)

**T12.3 — Dropdown Parcelle** (activé après forêt) : `GET /parcelles/by_forest/{id}` (forest-service :8000)

**T12.4 — Mini carte flutter_map** : polygone parcelle sélectionnée en vert semi-transparent

**T12.5 — Bouton "Confirmer"**
- `POST /affectations/` → **incident-service :8002**
- Loading → succès (SnackBar vert + refresh) ou erreur (SnackBar rouge + message serveur)

---

### T13 — CARTE PARCELLES SCREEN
**Composant :** Flutter
**Priorité :** 🟠 Haute
**Fichier :** `lib/screens/carte_parcelles_screen.dart`

#### Sous-tâches

**T13.1 — Charger forêts** `GET /forests/?direction_secondaire_id={ds_id}` → PolygonLayer vert clair

**T13.2 — Charger parcelles + statut affectation**
- `GET /parcelles/by_forest/{id}` pour chaque forêt (forest-service :8000)
- `GET /affectations/` (incident-service :8002) → IDs des parcelles affectées
- Parcelle affectée → vert foncé | Libre → orange semi-transparent

**T13.3 — Tap sur parcelle → BottomSheet**
- Infos parcelle + liste agents via `GET /affectations/parcelle/{id}` (incident-service :8002)
- Bouton "Affecter un agent" → `AffectationSheet` pré-sélectionné

**T13.4 — Légende + centrage automatique sur bounding box parcelles**

---

### T14 — SERVICES & MODÈLES FLUTTER
**Composant :** Flutter
**Priorité :** 🔴 Critique
**Dossier :** `lib/services/` + `lib/models/`

#### Sous-tâches

**T14.1 — `auth_service.dart`** — copié depuis app admin

**T14.2 — `agent_service.dart`** → user-forest-service :8000
```dart
Future<List<AgentWithStatus>> getMonEquipe()
Future<List<AgentWithStatus>> getDisponibles()
```

**T14.3 — `affectation_service.dart`** → incident-service :8002
```dart
Future<AssignmentRead> affecter(int agentId, int parcelleId)
Future<void> desaffecter(int agentId)
Future<List<AssignmentRead>> getAffectations()
Future<AssignmentMinimal?> getAffectationAgent(int agentId)
Future<List<AgentMinimal>> getAgentsParParcelle(int parcelleId)
```

**T14.4 — `forest_service.dart`** + **`parcelle_service.dart`** → user-forest-service :8000

**T14.5 — Modèles Dart**
```dart
class AgentWithStatus {
  final int id;
  final String username, email;
  final String? telephone;
  final bool actif;
  final int? directionSecondaireId;
  final ParcelleMinimal? parcelleAffectee;  // null si libre
  final String type;  // "equipe_directe" | "libre_region"
  factory AgentWithStatus.fromJson(Map<String, dynamic> json) { ... }
}

class AssignmentRead {
  final int id, agentId, parcelleId, forestId, dirSecondaireId, assignedBy;
  final DateTime assignedAt;
  final bool actif;
  final String agentUsername, parcelleName, forestName;
  factory AssignmentRead.fromJson(Map<String, dynamic> json) { ... }
}

class AssignmentMinimal {
  final int? parcelleId, forestId;
  final String? parcelleName, forestName;
  factory AssignmentMinimal.fromJson(Map<String, dynamic> json) { ... }
}
```

---

## ORDRE D'EXÉCUTION RECOMMANDÉ

```
Jour 1 — Backend fondations :
  T1  setup incident-service (structure, config, docker)
  T2  table agent_parcelle_assignments + migrations
  T7  auth superviseur + JWT enrichi (direction ids)

Jour 2 — Backend logique métier :
  T3  client HTTP inter-services (http_client.py)
  T4  JWT guard incident-service
  T5  endpoints affectation (5 endpoints + 1 interne)
  T6  endpoints agents user-forest-service + PATCH interne

Jour 3 — Flutter setup + auth + dashboard :
  T8  setup app superviseur
  T14 services + modèles
  T9  login screen
  T10 home/dashboard

Jour 4 — Flutter features :
  T11 agents screen
  T12 affectation sheet
  T13 carte parcelles

Jour 5 — Tests end-to-end + polish :
  Test flux complet superviseur bout en bout
  Edge cases (agent hors région, parcelle hors périmètre, agent déjà affecté)
  Bugs UX
```

---

## EXIT CONDITIONS M2

| Critère | Vérification |
|---|---|
| `incident-service` démarre sur port 8002 | `GET /health` → 200 ✅ |
| `incident_db` créée + table `agent_parcelle_assignments` présente | `\dt` psql ✅ |
| Superviseur se connecte sur son portail Flutter | Login → HomeScreen ✅ |
| JWT contient `direction_secondaire_id` + `direction_regionale_id` | Decode JWT vérifié ✅ |
| Voit équipe directe + agents libres de sa direction régionale | AgentsScreen 2 sections ✅ |
| Affectation persistée dans `incident_db` | POST /affectations/ → 200, row en DB ✅ |
| Agent d'une autre région → refusé | POST /affectations/ → 403 "Agent hors de votre région" ✅ |
| Parcelle hors direction secondaire → refusée | POST /affectations/ → 403 "Parcelle hors de votre périmètre" ✅ |
| Agent libre affecté → `direction_secondaire_id` mis à jour dans `forest_db` | PATCH vérifié ✅ |
| Désaffectation fonctionne | DELETE /affectations/{agent_id} → 204 ✅ |
| Carte parcelles avec statut coloré | CarteParcellesScreen vert/orange ✅ |
| Fixes hardening M1 appliqués | docker-compose.yml + config.py ✅ |

---

## ENDPOINTS M2 — RÉCAPITULATIF

### incident-service (port 8002) — NOUVEAU

| Method | Route | Auth | Description |
|---|---|---|---|
| POST | /affectations/ | 🔒 superviseur | Affecter agent → parcelle (validations inter-services) |
| DELETE | /affectations/{agent_id} | 🔒 superviseur | Désaffecter un agent |
| GET | /affectations/ | 🔒 superviseur, admin | Liste affectations actives de la direction secondaire |
| GET | /affectations/agent/{agent_id} | 🔒 superviseur, admin | Affectation courante d'un agent |
| GET | /affectations/parcelle/{parcelle_id} | 🔒 superviseur, admin | Agents affectés à une parcelle |
| GET | /affectations/agents-ids | 🔒 X-Service-Secret | Interne — IDs agents affectés (pour user-forest-service) |
| GET | /health | ❌ none | Health check Docker |

### user-forest-service (port 8000) — ajouts M2

| Method | Route | Auth | Description |
|---|---|---|---|
| GET | /users/agents/mon-equipe | 🔒 superviseur | Agents visibles (équipe directe + libres région) |
| GET | /users/agents/disponibles | 🔒 superviseur | Agents libres uniquement |
| PATCH | /users/{id} | 🔒 X-Service-Secret | Interne — mise à jour direction_secondaire_id |
| GET | /forests/?direction_secondaire_id= | 🔒 JWT | Forêts filtrées par direction secondaire (nouveau param) |

### auth-service (port 8001) — modification M2

| Method | Route | Modification |
|---|---|---|
| POST | /auth/login | Accepte `role == "superviseur"` + JWT enrichi avec direction ids |

---

## DB SCHEMA — AJOUTS M2

```sql
-- incident_db (NOUVELLE DB SÉPARÉE — microservice incident-service)
-- Pas de vraies FK PostgreSQL inter-DB — IDs validés par appels REST

CREATE TABLE agent_parcelle_assignments (
  id                SERIAL PRIMARY KEY,
  agent_id          INTEGER NOT NULL,        -- FK logique → forest_db.users.id
  parcelle_id       INTEGER NOT NULL,        -- FK logique → forest_db.parcelles.id
  forest_id         INTEGER NOT NULL,        -- FK logique → forest_db.forests.id
  dir_secondaire_id INTEGER NOT NULL,        -- FK logique → forest_db.direction_secondaire.id
  dir_regionale_id  INTEGER NOT NULL,        -- FK logique → forest_db.direction_regionale.id
  assigned_by       INTEGER NOT NULL,        -- FK logique → forest_db.users.id (superviseur)
  assigned_at       TIMESTAMP NOT NULL DEFAULT NOW(),
  actif             BOOLEAN NOT NULL DEFAULT TRUE
);

-- Un agent = une seule affectation active à la fois
CREATE UNIQUE INDEX uq_agent_assignment_actif
  ON agent_parcelle_assignments (agent_id)
  WHERE actif = TRUE;

-- Indexes
CREATE INDEX ix_apa_parcelle ON agent_parcelle_assignments (parcelle_id);
CREATE INDEX ix_apa_ds       ON agent_parcelle_assignments (dir_secondaire_id);
CREATE INDEX ix_apa_dr       ON agent_parcelle_assignments (dir_regionale_id);
CREATE INDEX ix_apa_assigned ON agent_parcelle_assignments (assigned_by);
```

---

## FLUTTER SCREENS — RÉCAPITULATIF

| Screen | Fichier | Service(s) appelé(s) | Description |
|---|---|---|---|
| Login | `login_screen.dart` | auth-service :8001 | Auth superviseur + guard rôle Flutter |
| Home / Dashboard | `home_screen.dart` | user-forest-service :8000 | KPIs + NavRail + placeholders M3/M6/M7 |
| Agents | `agents_screen.dart` | user-forest-service :8000 | Équipe directe + agents libres région |
| Affectation Sheet | `affectation_sheet.dart` | forest-service :8000 + incident-service :8002 | Forêt→Parcelle→Confirmer |
| Carte Parcelles | `carte_parcelles_screen.dart` | forest-service :8000 + incident-service :8002 | Carte statut affectation coloré |

---

## KNOWN ISSUES ANTICIPÉS

- ISSUE: `GET /affectations/` enrichit chaque ligne avec 3 appels HTTP (user + parcelle + forêt) → utiliser `asyncio.gather` pour paralléliser, sinon lent sur grande équipe
- ISSUE: `flutter_map` requiert `List<LatLng>` — prévoir conversion GeoJSON coordinates dans `parcelle.dart`
- ISSUE: Si superviseur n'a pas de `direction_secondaire_id` en DB → valider en `initState` HomeScreen avant tout appel API, afficher message explicite
- ISSUE: La mise à jour `direction_secondaire_id` (PATCH vers user-forest-service) est hors transaction `incident_db` → si PATCH échoue, l'affectation est créée mais l'agent non mis à jour → logger l'erreur sans bloquer (non critique pour M2, corriger en M3)
- ISSUE: `GET /users/agents/mon-equipe` appelle incident-service pour récupérer les IDs affectés — crée une dépendance circulaire potentielle au démarrage si les deux services démarrent en même temps → gérer avec retry ou `depends_on: service_started` dans docker-compose

---

## REFACTOR LATER

- REFACTOR: Extraire `AuthenticatedClient` et `TokenStorage` dans un package Flutter partagé (admin + superviseur) — Phase 2
- REFACTOR: Pagination sur `GET /users/agents/mon-equipe` si > 50 agents
- REFACTOR: Remplacer migrations artisanales par Alembic dans incident-service dès M3
- REFACTOR: Mettre en cache Redis les réponses user/parcelle/forêt dans incident-service pour éviter appels HTTP répétés à user-forest-service
- REFACTOR: Supprimer `depends_on: db` dans auth-service docker-compose (fait en T7.4)
