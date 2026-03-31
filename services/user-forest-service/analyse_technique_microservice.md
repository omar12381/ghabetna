# Analyse Technique Approfondie — Microservice « User & Forest Management »

> **Date d'analyse :** 27 mars 2026  
> **Codebase :** `d:\user_management`  
> **Analyst :** Antigravity (Google DeepMind Advanced Agentic Coding)

---

## 1. VUE D'ENSEMBLE DU MICROSERVICE

### Nom et rôle fonctionnel

**Nom :** `user_forest_app` / API `User & Forest Management`

Ce microservice est une **application full-stack autonome** gérant le cycle de vie complet des **utilisateurs**, des **forêts géospatiales**, des **parcelles forestières** et de la **hiérarchie administrative** (Directions Régionales → Directions Secondaires) d'un organisme de gestion forestière (vraisemblablement tunisien, au vu des noms de champs `gouvernorat`, `superviseur`, etc.).

### Responsabilités principales (domaine métier)

| Domaine | Responsabilité |
|---|---|
| **Gestion des utilisateurs** | CRUD complet, attribution de rôles, affectation aux directions |
| **Cartographie forestière** | Création et gestion de polygones GeoJSON, validation de non-chevauchement |
| **Gestion des parcelles** | Sous-division des forêts en parcelles avec contrôle topologique strict |
| **Administration organisationnelle** | Hiérarchie Directions Régionales / Directions Secondaires |
| **Sécurité de base** | Hachage des mots de passe, contrôle de doublons |

### Position dans l'architecture globale

Ce service est **auto-contenu et standalone**. Il expose une API REST et est consommé directement par le frontend Flutter. Il n'existe aucune dépendance documentée vers d'autres microservices.

```
┌─────────────────────────────────────┐
│   Flutter App (user_forest_app)     │  ← Frontend (Multi-platform)
│   Port: N/A (client)                │
└──────────────┬──────────────────────┘
               │ HTTP REST (JSON)
               │ http://localhost:8000
┌──────────────▼──────────────────────┐
│   FastAPI Backend (app/)            │  ← Backend Python
│   Port: 8000                        │
└──────────────┬──────────────────────┘
               │ SQLAlchemy + psycopg2
┌──────────────▼──────────────────────┐
│   PostgreSQL + PostGIS extension    │  ← Base de données spatiale
│   Port: 5432 / DB: forest_db        │
└─────────────────────────────────────┘
```

---

## 2. ANALYSE DU FRONTEND

### Stack technique

| Composant | Outil | Version |
|---|---|---|
| Framework UI | Flutter (Dart) | SDK ^3.10.7 |
| Client HTTP | `http` | ^1.2.2 |
| Carte interactive | `flutter_map` | ^7.0.2 |
| Helpers géographiques | `latlong2` | ^0.9.1 |
| Icônes | `cupertino_icons` | ^1.0.8 |
| Design System | Material 3 | intégré |
| Linting | `flutter_lints` | ^6.0.0 |

### Structure des composants et arborescence

```
user_forest_app/lib/
├── main.dart                        # Point d'entrée, routing, ThemeData global
├── config/
│   └── api_config.dart              # URL de base de l'API (constante)
├── models/                          # Modèles de données (DTO côté Flutter)
│   ├── user.dart                    # User + Role
│   ├── forest.dart                  # Forest
│   ├── parcelle.dart                # Parcelle
│   ├── direction_regionale.dart     # DirectionRegionale
│   └── direction_secondaire.dart    # DirectionSecondaire
├── services/                        # Couche d'accès API (Repository pattern)
│   ├── user_service.dart            # CRUD Utilisateurs + filtre superviseurs
│   ├── forest_service.dart          # CRUD Forêts
│   ├── parcelle_service.dart        # CRUD Parcelles
│   └── direction_service.dart       # CRUD Directions Régionales + Secondaires
└── screens/                         # Vues UI (Stateful/Stateless widgets)
    ├── home_screen.dart             # Dashboard d'accueil responsive
    ├── user_management_screen.dart  # CRUD Utilisateurs complet (25K)
    ├── directions_screen.dart       # Gestion hiérarchie directions (21K)
    ├── add_forest_screen.dart       # Ajout forêt + dessin carte (21K)
    ├── edit_forest_screen.dart      # Édition forêt + carte (10K)
    ├── forest_list_screen.dart      # Liste des forêts (9.5K)
    ├── parcelle_screen.dart         # Gestion parcelles / carte (27K)
    └── assign_superviseur_screen.dart # Affectation superviseur (5.5K)
```

### Pages et vues disponibles

| Route | Widget | Description |
|---|---|---|
| `/` | `HomeScreen` | Dashboard d'accueil avec navigation responsive |
| `/users` | `UserManagementScreen` | Liste CRUD des utilisateurs, formulaires inline |
| `/directions` | `DirectionsScreen` | Gestion arborescente Dirs. Régionales/Secondaires |
| `/forests/add` | `AddForestScreen` | Formulaire + `flutter_map` pour dessiner un polygone |
| `/forests/list` | `ForestListScreen` | Liste des forêts avec accès édition/parcelles |
| *(push)* | `EditForestScreen` | Édition d'une forêt existante avec carte |
| *(push)* | `ParcelleScreen` | Visualisation et gestion des parcelles d'une forêt |
| *(push)* | `AssignSuperviseurScreen` | Assignation d'un superviseur à une direction secondaire |

### Gestion de l'état (State Management)

> **Pattern utilisé :** `StatefulWidget` natif Flutter + `setState()`.

Il n'existe aucune bibliothèque de state management (pas de `Riverpod`, `Bloc`, `Provider`, `GetX`, etc.). Chaque écran est un `StatefulWidget` autonome qui :
1. Charge les données depuis le service correspondant dans `initState()`
2. Stocke l'état dans des variables locales (`List<User> _users`, `bool _isLoading`, etc.)
3. Rafraîchit l'UI via `setState()`

C'est adapté pour une application de taille modeste mais représente une limite en cas de montée en complexité.

### Communication avec le backend

Toutes les communications HTTP passent par les classes de la couche `services/`. Le pattern est homogène dans tous les services :

```dart
// Exemple de pattern uniforme (ForestService)
Future<List<Forest>> fetchForests() async {
  final uri = Uri.parse('$apiBaseUrl/forests/');
  final response = await _client.get(uri);           // GET sans auth header

  if (response.statusCode != 200) {
    throw Exception('Erreur: ${response.statusCode}');
  }
  final List<dynamic> data = jsonDecode(response.body);
  return data.map((json) => Forest.fromJson(json)).toList();
}
```

**Format des requêtes :**
- `Content-Type: application/json` sur les POST/PUT
- Body : objet JSON sérialisé via `jsonEncode()`
- Pas de token/header d'authentification

**Format des réponses :**
- JSON désérialisé via `jsonDecode()` puis mappé sur les modèles via `fromJson()`
- Les erreurs sont propagées comme des exceptions Flutter standard

**Particularité notable dans `UserService` :**
```dart
// Mécanisme de désaffectation explicite du champ nullable
Future<User> updateUser({
  bool setDirectionSecondaireId = false,   // flag pour forcer null
  int? directionSecondaireId,
}) async {
  if (setDirectionSecondaireId) {
    body['direction_secondaire_id'] = directionSecondaireId; // peut être null
  }
}
```
Ce pattern permet d'envoyer `null` explicitement pour vider une association.

### Gestion des erreurs côté UI

- Les erreurs sont capturées dans des blocs `try/catch` dans les screens
- Affichage via `ScaffoldMessenger.of(context).showSnackBar()`
- Aucune page d'erreur dédiée ni retry automatique
- Pas de gestion offline / cache local

### Aspects UX/UI notables

- **Material Design 3** avec `useMaterial3: true` et `ColorScheme.fromSeed(seedColor: Colors.green)`
- `HomeScreen` **responsive** : détection de `LayoutBuilder` → disposition `Row` (>800px) ou `Column` (<800px)
- `scaffoldBackgroundColor: Color(0xFFF4F5F7)` — fond gris very light pour contraste
- `flutter_map` pour le **dessin interactif de polygones** sur fond OpenStreetMap
- Cartes avec drawers et mode édition (click to add vertex, supprimer le dernier point)

---

## 3. ANALYSE DU BACKEND

### Stack technique

| Composant | Outil | Version |
|---|---|---|
| Langage | Python | 3.10+ |
| Framework web | FastAPI | latest (non pinné) |
| Serveur ASGI | Uvicorn | latest (standard extras) |
| ORM | SQLAlchemy | latest (future=True) |
| Driver PostgreSQL | psycopg2-binary | latest |
| ORM spatial | GeoAlchemy2 | latest |
| Géométrie vecteur | Shapely | latest |
| Validation | Pydantic v2 | latest |
| Hachage MDP | passlib | latest |
| Forms multipart | python-multipart | latest |

### Architecture interne

L'architecture est de type **MVC simplifié / Layered Architecture** :

```
┌─────────────────────────────────────────────────────────┐
│                    FastAPI Application                    │
│   (app/main.py — CORS, startup hooks, router mounting)   │
├──────────────┬──────────────────────────────────────────┤
│   Routers    │  app/routers/*.py (Controllers)           │
│              │  Validation Pydantic (schemas.py)         │
├──────────────┼──────────────────────────────────────────┤
│  Business    │  Logique métier inline dans les routers   │
│  Logic       │  geo_utils.py (services transverses)      │
├──────────────┼──────────────────────────────────────────┤
│   Models     │  app/models.py (SQLAlchemy ORM)           │
├──────────────┼──────────────────────────────────────────┤
│  Data Layer  │  app/db.py (engine, session, Base)        │
│              │  PostgreSQL + PostGIS via GeoAlchemy2      │
└──────────────┴──────────────────────────────────────────┘
```

**Remarque :** Il n'y a pas de couche Service/Repository distincte côté backend. La logique métier est directement dans les fonctions de routeur (pattern "fat controller").

### Liste complète des endpoints exposés

#### `/roles` — Gestion des Rôles

| Méthode | Route | Description | Corps / Params | Réponse |
|---|---|---|---|---|
| `POST` | `/roles/` | Créer un rôle | `{ "name": str }` | `201 RoleRead` |
| `GET` | `/roles/` | Lister tous les rôles | — | `200 [RoleRead]` |
| `GET` | `/roles/{role_id}` | Obtenir un rôle | path: `role_id` | `200 RoleRead` \| `404` |
| `PUT` | `/roles/{role_id}` | Mettre à jour un rôle | `{ "name": str }` | `200 RoleRead` \| `404` |
| `DELETE` | `/roles/{role_id}` | Supprimer un rôle | path: `role_id` | `204` \| `404` |

#### `/users` — Gestion des Utilisateurs

| Méthode | Route | Description | Corps / Params | Réponse |
|---|---|---|---|---|
| `POST` | `/users/` | Créer un utilisateur | `UserCreate` | `201 UserRead` \| `400` |
| `GET` | `/users/` | Lister tous les utilisateurs | — | `200 [UserRead]` |
| `GET` | `/users/superviseurs` | Lister les superviseurs | — | `200 [UserRead]` |
| `GET` | `/users/{user_id}` | Obtenir un utilisateur | path: `user_id` | `200 UserRead` \| `404` |
| `PUT` | `/users/{user_id}` | Mettre à jour un utilisateur | `UserUpdate` (partiel) | `200 UserRead` \| `404` |
| `DELETE` | `/users/{user_id}` | Supprimer un utilisateur | path: `user_id` | `204` \| `404` |

**Body `UserCreate` :**
```json
{
  "username": "string",
  "email": "user@example.com",
  "password": "string",
  "role_id": 1,
  "direction_secondaire_id": null,
  "direction_regionale_id": null,
  "telephone": null,
  "actif": true
}
```

#### `/forests` — Gestion des Forêts

| Méthode | Route | Description | Params | Réponse |
|---|---|---|---|---|
| `POST` | `/forests/` | Créer une forêt | `ForestCreate` | `201 ForestRead` \| `400` |
| `GET` | `/forests/` | Lister toutes les forêts (avec géométrie) | `?skip=0&limit=1000` | `200 [ForestRead]` |
| `GET` | `/forests/summary` | Lister forêts sans géométrie | `?skip=0&limit=1000` | `200 [ForestSummaryRead]` |
| `GET` | `/forests/{forest_id}` | Obtenir une forêt | path: `forest_id` | `200 ForestRead` \| `404` |
| `PUT` | `/forests/{forest_id}` | Mettre à jour une forêt | `ForestUpdate` (partiel) | `200 ForestRead` \| `400/404` |
| `DELETE` | `/forests/{forest_id}` | Supprimer une forêt | path: `forest_id` | `204` \| `404` |

**Body `ForestCreate` :**
```json
{
  "name": "Forêt X",
  "description": "...",
  "geometry": { "type": "Polygon", "coordinates": [[[lng,lat], ...]] },
  "created_by_id": 1,
  "direction_secondaire_id": 2,
  "direction_regionale_id": 1,
  "surface_ha": 120.5,
  "type_foret": "naturelle"
}
```

#### `/parcelles` — Gestion des Parcelles

| Méthode | Route | Description | Params | Réponse |
|---|---|---|---|---|
| `POST` | `/parcelles/` | Créer une parcelle | `ParcelleCreate` | `201 ParcelleRead` \| `400/404` |
| `GET` | `/parcelles/` | Lister toutes les parcelles | `?skip&limit` | `200 [ParcelleRead]` |
| `GET` | `/parcelles/by_forest/{forest_id}` | Parcelles d'une forêt (avec géométrie) | path+`?skip&limit` | `200 [ParcelleRead]` |
| `GET` | `/parcelles/by_forest/{forest_id}/summary` | Parcelles d'une forêt (sans géométrie) | path+`?skip&limit` | `200 [ParcelleSummaryRead]` |
| `GET` | `/parcelles/{parcelle_id}` | Obtenir une parcelle | path | `200 ParcelleRead` \| `404` |
| `PUT` | `/parcelles/{parcelle_id}` | Mettre à jour une parcelle | `ParcelleUpdate` | `200 ParcelleRead` \| `400/404` |
| `DELETE` | `/parcelles/{parcelle_id}` | Supprimer une parcelle | path | `204` \| `404` |

#### `/directions-regionales` — Directions Régionales

| Méthode | Route | Description | Réponse |
|---|---|---|---|
| `POST` | `/directions-regionales/` | Créer | `201 DirectionRegionaleRead` |
| `GET` | `/directions-regionales/` | Lister | `200 [DirectionRegionaleRead]` |
| `GET` | `/directions-regionales/{region_id}` | Obtenir | `200` \| `404` |
| `PUT` | `/directions-regionales/{region_id}` | Mettre à jour | `200` \| `404` |
| `DELETE` | `/directions-regionales/{region_id}` | Supprimer (avec protection FK) | `204` \| `400/404` |

#### `/directions-secondaires` — Directions Secondaires

| Méthode | Route | Description | Réponse |
|---|---|---|---|
| `POST` | `/directions-secondaires/` | Créer (vérifie existence parent) | `201` |
| `GET` | `/directions-secondaires/` | Lister toutes | `200 [DirectionSecondaireRead]` |
| `GET` | `/directions-secondaires/by-regionale/{id}` | Filtrer par régionale | `200 [...]` |
| `GET` | `/directions-secondaires/{secondaire_id}` | Obtenir | `200` \| `404` |
| `PUT` | `/directions-secondaires/{secondaire_id}` | Mettre à jour | `200` \| `404` |
| `DELETE` | `/directions-secondaires/{secondaire_id}` | Supprimer (avec protection FK) | `204` \| `400/404` |

> **✅ Source unique des routes directions :** L'unique implémentation active est `directions.py`, qui expose les deux routers (`router_regionales` et `router_secondaires`) montés dans `main.py`. Les fichiers redondants `directions_regionales.py` et `directions_secondaires.py` ont été **supprimés** — la base de code est propre et sans dead code.

### Logique métier principale

#### 1. Validation géospatiale (geo_utils.py)
- `_extract_and_validate_polygon_geojson()` : valide la structure GeoJSON (type Polygon, anneaux fermés, coordonnées numériques, min 4 points)
- `geojson_to_geometry()` : pipeline complet → parse → shape Shapely → validation validité (pas d'auto-intersection) → conversion GeoAlchemy2 WKB
- `geometry_to_geojson()` : pipeline inverse → WKB → shape Shapely → GeoJSON dict (pour la sérialisation vers Flutter)

#### 2. Non-chevauchement des forêts (`forests.py`)
```python
# Utilise PostGIS ST_Intersects via GeoAlchemy2
overlapping_forests = db.query(models.Forest).filter(
    models.Forest.geom.ST_Intersects(geom)
).all()
if overlapping_forests:
    raise HTTPException(400, detail=f"La forêt chevauche : {names}")
```

#### 3. Containment + non-chevauchement des parcelles (`parcelles.py`)
```python
# 1) La parcelle doit être TOTALEMENT dans la forêt parente
is_within = db.query(models.Forest).filter(
    models.Forest.id == forest_id,
    models.Forest.geom.ST_Contains(geom)
).first()

# 2) Pas de contact ni chevauchement avec les autres parcelles
touching = db.query(models.Parcelle).filter(
    ~models.Parcelle.geom.ST_Disjoint(geom)
).all()
```

#### 4. Calcul de surface approximatif (`parcelles.py`)
```python
# Approximation en degrés → hectares (valide pour petites zones)
area_deg = shape(geojson).area
surface_ha = area_deg * (111320 * 111320) / 10000
```
> **Note :** Cette formule suppose une projection plane et introduit des erreurs croissantes avec la latitude. Ce n'est qu'une approximation.

#### 5. Migrations incrementales au démarrage (`main.py`)
```python
_migrations = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS direction_secondaire_id ...",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS telephone ...",
    # ...
]
for sql in _migrations:
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
    except Exception:
        pass  # non-bloquant
```

### Modèles de données / Entités

Voir section 4 pour le schéma complet.

### Validations et règles métier

| Règle | Couche | Implémentation |
|---|---|---|
| Email unique | Backend | Query avant INSERT + `HTTPException(400)` |
| Username unique | Backend | Query avant INSERT + `HTTPException(400)` |
| Polygon GeoJSON valide | Backend | `geo_utils.geojson_to_geometry()` |
| Polygon non auto-intersectant | Backend | `shapely.is_valid` |
| Forêt sans chevauchement | Backend | PostGIS `ST_Intersects` |
| Parcelle dans la forêt parent | Backend | PostGIS `ST_Contains` |
| Parcelle sans contact/chevauchement | Backend | PostGIS `NOT ST_Disjoint` |
| Suppression protégée (Dir. Régionale) | Backend | Query FK avant DELETE |
| Suppression protégée (Dir. Secondaire) | Backend | Query FK avant DELETE |
| Mot de passe haché | Backend | `passlib` pbkdf2_sha256 |

---

## 4. BASE DE DONNÉES & PERSISTANCE

### Type

**PostgreSQL** avec extension **PostGIS** (géospatial).  
Driver : `psycopg2-binary`. ORM : `SQLAlchemy` + `GeoAlchemy2`.

### Schéma des tables

```sql
-- Table: roles
CREATE TABLE roles (
    id      SERIAL PRIMARY KEY,
    name    VARCHAR(50) NOT NULL UNIQUE    -- 'admin','agent_forestier','superviseur'
);

-- Table: direction_regionale
CREATE TABLE direction_regionale (
    id          SERIAL PRIMARY KEY,
    nom         VARCHAR NOT NULL UNIQUE,
    gouvernorat VARCHAR NOT NULL
);

-- Table: direction_secondaire
CREATE TABLE direction_secondaire (
    id          SERIAL PRIMARY KEY,
    nom         VARCHAR NOT NULL,
    region_id   INTEGER NOT NULL REFERENCES direction_regionale(id)
);
CREATE INDEX ON direction_secondaire(region_id);

-- Table: users
CREATE TABLE users (
    id                      SERIAL PRIMARY KEY,
    username                VARCHAR(50) NOT NULL UNIQUE,
    email                   VARCHAR(255) NOT NULL UNIQUE,
    hashed_password         VARCHAR(255) NOT NULL,
    role_id                 INTEGER NOT NULL REFERENCES roles(id),
    direction_secondaire_id INTEGER REFERENCES direction_secondaire(id),
    direction_regionale_id  INTEGER REFERENCES direction_regionale(id),
    telephone               VARCHAR(50),
    actif                   BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX ON users(username);
CREATE INDEX ON users(email);
CREATE INDEX ON users(direction_secondaire_id);
CREATE INDEX ON users(direction_regionale_id);

-- Table: forests
CREATE TABLE forests (
    id                      SERIAL PRIMARY KEY,
    name                    VARCHAR(100) NOT NULL,
    description             TEXT,
    geom                    GEOMETRY(POLYGON, 4326) NOT NULL,   -- WGS84
    created_by_id           INTEGER REFERENCES users(id),
    direction_secondaire_id INTEGER REFERENCES direction_secondaire(id),
    direction_regionale_id  INTEGER REFERENCES direction_regionale(id),
    surface_ha              FLOAT,
    type_foret              VARCHAR
);
CREATE INDEX ix_forests_geom ON forests USING GIST (geom);

-- Table: parcelles
CREATE TABLE parcelles (
    id              SERIAL PRIMARY KEY,
    forest_id       INTEGER NOT NULL REFERENCES forests(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    geom            GEOMETRY(POLYGON, 4326) NOT NULL,
    surface_ha      FLOAT,
    created_by_id   INTEGER REFERENCES users(id)
);
CREATE INDEX ON parcelles(forest_id);
CREATE INDEX ix_parcelles_geom ON parcelles USING GIST (geom);
```

### Stratégie de migration

Il n'y a **pas d'outil de migration dédié** (Alembic, Flyway, etc.). La stratégie adoptée est un **système de migration artisanal** dans l'événement `on_startup` de FastAPI :

```python
_migrations = ["ALTER TABLE ... ADD COLUMN IF NOT EXISTS ..."]
for sql in _migrations:
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
    except Exception:
        pass  # Non-bloquant
```

`Base.metadata.create_all(bind=engine)` gère la création initiale des tables.

### Indexation et optimisations

| Index | Table | Colonne | Type | Usage |
|---|---|---|---|---|
| `ix_forests_geom` | `forests` | `geom` | GIST | Requêtes spatiales PostGIS |
| `ix_parcelles_geom` | `parcelles` | `geom` | GIST | Requêtes spatiales PostGIS |
| `ix_users_username` | `users` | `username` | B-Tree | Recherche unicité |
| `ix_users_email` | `users` | `email` | B-Tree | Recherche unicité |
| `ix_users_direction_*` | `users` | FK directions | B-Tree | Joins/filtres |
| `ix_parcelles_forest_id` | `parcelles` | `forest_id` | B-Tree | Filtre par forêt |

Les index GIST accélèrent les opérations `ST_Intersects`, `ST_Contains`, `ST_Disjoint` utilisées dans la validation topologique.

---

## 5. COMMUNICATION INTER-MICROSERVICES

### Protocoles utilisés

**Exclusivement REST/HTTP synchrone.** Il n'existe :
- ❌ Aucun message broker (RabbitMQ, Kafka, etc.)
- ❌ Aucun bus d'événements
- ❌ Aucune communication gRPC
- ❌ Aucun service discovery

Le seul flux est : `Flutter App → HTTP → FastAPI Backend → SQL → PostgreSQL`.

### Événements publiés/consommés

Aucun. L'architecture est entièrement synchrone requête/réponse.

### Contrats d'interface

Les contrats sont définis par les schémas Pydantic dans `app/schemas.py`. Il n'existe pas de fichier OpenAPI/Swagger exporté ni de contrat formel (AsyncAPI, Protobuf).

FastAPI génère automatiquement la documentation interactive à `http://localhost:8000/docs` (Swagger UI) et `http://localhost:8000/redoc`.

### Gestion de la résilience

- ❌ Aucun retry automatique côté client Flutter
- ❌ Aucun circuit breaker
- ❌ Aucun timeout configuré côté Flutter (`http.Client` default)
- ❌ Aucun mécanisme de fallback

---

## 6. SÉCURITÉ

### Mécanisme d'authentification/autorisation

> [!WARNING]
> **Aucun système d'authentification n'est implémenté.** Tous les endpoints sont publics et accessibles sans token ni session.

L'API accepte n'importe quelle requête sans vérification d'identité. Il n'y a pas de :
- JWT / OAuth2 / API Key
- Session middleware
- Dependency FastAPI `Security()`

### Gestion des rôles et permissions

Les rôles (`admin`, `agent_forestier`, `superviseur`) sont stockés en base et associés aux utilisateurs, mais **ils ne sont pas vérifiés côté API**. N'importe quel appelant peut créer/supprimer/modifier n'importe quelle ressource.

### Hachage des mots de passe

```python
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
def hash_password(password: str) -> str:
    return pwd_context.hash(password)
```

L'algorithme **PBKDF2-SHA256** est utilisé — c'est un bon choix. Les mots de passe ne sont jamais retournés dans les réponses API.

### Protection contre les vulnérabilités

| Vecteur | État | Détail |
|---|---|---|
| **CORS** | ⚠️ Ouvert | `allow_origins=["*"]` — acceptable en dev, **dangereux en prod** |
| **Injection SQL** | ✅ Protégé | SQLAlchemy ORM + requêtes paramétrées |
| **Injection GeoJSON** | ✅ Protégé | Validation stricte via `geo_utils.py` + Shapely |
| **XSS** | N/A | API JSON pure, pas de rendu HTML |
| **CSRF** | N/A | API stateless sans cookies |
| **Exposition MDP** | ✅ OK | Jamais retourné dans `UserRead` |

### Secrets et variables d'environnement

> [!CAUTION]
> **La chaîne de connexion PostgreSQL est hardcodée dans `app/db.py` :**  
> `DATABASE_URL = "postgresql+psycopg2://forest_user:1234@localhost:5432/forest_db"`  
> Mot de passe `1234` en clair dans le code source. **Critique en production.**

Il n'existe aucun système de gestion de secrets (`.env`, `pydantic-settings`, HashiCorp Vault, etc.).

---

## 7. CONFIGURATION & DÉPLOIEMENT

### Variables d'environnement requises

Aucune. Tout est en dur dans le code.

### Fichiers de configuration

| Fichier | Rôle |
|---|---|
| `app/db.py` | URL de connexion PostgreSQL (hardcodée) |
| `user_forest_app/lib/config/api_config.dart` | URL de base de l'API Flutter (constante Dart) |
| `requirements.txt` | Dépendances Python (sans versions pinnées) |
| `user_forest_app/pubspec.yaml` | Dépendances Flutter avec ranges de versions |

Il n'existe **aucun fichier** :
- `Dockerfile` / `docker-compose.yml`
- Configuration Kubernetes
- `.env` / `.env.example`
- Fichier CI/CD (GitHub Actions, GitLab CI, etc.)

### Démarrage manuel

```bash
# Backend
cd d:\user_management
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

# Frontend
cd user_forest_app
flutter run -d chrome   # ou -d windows / android
```

### Arborescence backend actuelle (après nettoyage)

```
app/
├── __init__.py
├── main.py                  # Entrée ASGI, CORS, startup, mounting des routers
├── db.py                    # Engine SQLAlchemy, SessionLocal, get_db()
├── models.py                # Entités ORM (Role, User, Forest, Parcelle, Directions)
├── schemas.py               # Schémas Pydantic (Create / Update / Read)
├── geo_utils.py             # Validation GeoJSON, conversions Shapely ↔ PostGIS
└── routers/
    ├── __init__.py
    ├── roles.py             # CRUD /roles
    ├── users.py             # CRUD /users + /users/superviseurs
    ├── forests.py           # CRUD /forests + /forests/summary
    ├── parcelles.py         # CRUD /parcelles + filtres by_forest
    └── directions.py        # CRUD /directions-regionales + /directions-secondaires
                             # (fichiers directions_regionales.py et
                             #  directions_secondaires.py supprimés)
```

### Ports exposés

| Composant | Port |
|---|---|
| FastAPI Backend | `8000` |
| PostgreSQL | `5432` |
| Flutter (dev web) | Variable (Chrome) |

---

## 8. GESTION DES ERREURS & LOGS

### Stratégie de gestion des erreurs

**Backend FastAPI :**

| Code HTTP | Cas d'usage |
|---|---|
| `201 Created` | Création réussie |
| `204 No Content` | Suppression réussie |
| `400 Bad Request` | Doublon email/username, chevauchement géométrique, GeoJSON invalide |
| `404 Not Found` | Ressource introuvable |
| `500 Internal Server Error` | Exception non anticipée (wrappée dans `HTTPException`) |

Les détails des erreurs sont retournés dans le champ `detail` du JSON de réponse FastAPI :
```json
{"detail": "La forêt chevauche les forêts existantes : Forêt A, Forêt B"}
```

**Frontend Flutter :**
```dart
try {
  await _service.createForest(...);
} catch (e) {
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(content: Text('Erreur: $e'))
  );
}
```

### Système de logging

- **Backend :** Aucun système de logging structuré. SQLAlchemy est configuré avec `echo=True` (log de toutes les requêtes SQL en console). Pas de `logging.getLogger()`, pas de fichier de log, pas de niveau de log configurable.
- **Frontend :** Uniquement `print()` pour les erreurs de calcul de surface (`print(f"Erreur calcul surface: {e}")`).

### Monitoring et observabilité

❌ Aucun. Pas de :
- Prometheus / Grafana
- Sentry / DataDog
- Health check endpoint (`/health`, `/readiness`)
- Traces distribuées (OpenTelemetry)
- Métriques d'utilisation

---

## 9. TESTS

### Types de tests présents

| Type | État |
|---|---|
| Tests unitaires | ❌ Absents |
| Tests d'intégration | ❌ Absents |
| Tests E2E | ❌ Absents |
| Tests widget Flutter | ⚠️ Fichier vide généré par défaut |

### Détail

Le seul fichier de test présent est `user_forest_app/test/widget_test.dart`, généré automatiquement par `flutter create`. Il contient un test sur le widget par défaut `MyApp`, mais celui-ci a été remplacé par le vrai contenu applicatif — le test n'est donc plus valide.

Côté backend Python, il n'existe aucun fichier `test_*.py`, aucun dossier `tests/`.

### Outils de test disponibles (mais non utilisés)

- **Python :** `pytest`, `pytest-asyncio`, `httpx` (TestClient FastAPI)
- **Flutter :** `flutter_test` (déjà en dev_dependency dans `pubspec.yaml`)

### Couverture estimée : **0%**

### Commandes pour exécuter les tests

```bash
# Backend (si des tests existaient)
pytest tests/ -v

# Frontend
flutter test
```

---

## 10. DÉPENDANCES & PACKAGES

### Backend Python (`requirements.txt`)

| Package | Rôle |
|---|---|
| `fastapi` | Framework web async, routing, DI, validation |
| `uvicorn[standard]` | Serveur ASGI (+ websockets, watchfiles pour --reload) |
| `SQLAlchemy` | ORM relationnel, gestionnaire de sessions |
| `psycopg2-binary` | Driver PostgreSQL pour Python |
| `geoalchemy2` | Extension SQLAlchemy pour types géométriques PostGIS |
| `shapely` | Manipulation de géométries vectorielles (validation, calcul d'aire) |
| `pydantic-settings` | (Présent mais non utilisé — prévu pour `.env`) |
| `python-multipart` | Support des form-data HTTP (utile pour upload futur) |
| `passlib` | Hachage et vérification de mots de passe (pbkdf2_sha256) |

> **⚠️ Aucune version n'est fixée** (`==x.y.z`). Cela peut provoquer des ruptures de compatibilité lors d'un `pip install` futur.

### Frontend Flutter (`pubspec.yaml`)

| Package | Rôle |
|---|---|
| `flutter` SDK | Framework UI multi-platform |
| `http: ^1.2.2` | Client HTTP pour appels REST |
| `flutter_map: ^7.0.2` | Widget de carte interactive (OpenStreetMap) |
| `latlong2: ^0.9.1` | Types LatLng pour flutter_map |
| `cupertino_icons: ^1.0.8` | Icônes style iOS |
| `flutter_test` (dev) | Framework de tests widget |
| `flutter_lints: ^6.0.0` (dev) | Règles de linting Dart recommandées |

---

## 11. POINTS FORTS & BONNES PRATIQUES DÉTECTÉES

### ✅ Validation géospatiale robuste (`geo_utils.py`)
Le module `geo_utils.py` est bien conçu : il valide exhaustivement le GeoJSON (structure, fermeture des anneaux, types numériques, validité Shapely), distingue GeoJSON Geometry et Feature wrapper, et génère des messages d'erreur précis et localisés.

### ✅ Schémas Pydantic séparés (Create / Update / Read)
Le pattern `Base → Create → Update → Read` est appliqué correctement pour chaque entité. L'`Update` utilise `Optional` pour le patch partiel, et les mots de passe ne figurent jamais dans `Read`.

### ✅ Validation topologique PostGIS
L'utilisation de `ST_Intersects`, `ST_Contains` et `ST_Disjoint` directement dans les requêtes SQLAlchemy délègue les calculs géospatiaux complexes à PostGIS (C/C++ natif), ce qui est la bonne approche — beaucoup plus efficace que du calcul Python.

### ✅ Index GIST créés au démarrage
Les index `USING GIST` sur les colonnes géométriques sont créés à la fois via `Index()` dans `models.py` et via `CREATE INDEX IF NOT EXISTS` dans le startup hook — garantissant la présence même sur des bases existantes.

### ✅ Endpoint `/forests/summary` et `/parcelles/by_forest/{id}/summary`
La présence de variantes "résumé" (sans géométrie) est une excellente optimisation : les payloads GeoJSON peuvent être très volumineux, et les listes n'ont pas besoin des géométries.

### ✅ Service Layer Flutter (`services/`)
La séparation claire entre l'UI (`screens/`) et la couche d'accès données (`services/`) est bien respectée. Chaque service est injectable (accepte un `http.Client` en paramètre), ce qui facilite les tests unitaires.

### ✅ Pattern de désaffectation explicite (`UserService.updateUser`)
Le flag `setDirectionSecondaireId` permet d'envoyer explicitement `null` pour désaffecter un superviseur — un cas typiquement mal géré dans les APIs REST.

### ✅ Réponses construites manuellement après persistance géospatiale
Dans `forests.py` et `parcelles.py`, les réponses sont construites avec `geometry_to_geojson(db_obj.geom)` plutôt que de s'appuyer sur `from_attributes=True`, ce qui évite les problèmes de lazy-loading des colonnes GeoAlchemy2.

### ✅ HomeScreen responsive
La gestion `LayoutBuilder` pour basculer entre Row/Column selon la largeur disponible est une bonne pratique Flutter pour le support multi-plateforme.

### ✅ Protection de suppression par FK
Les endpoints DELETE des Directions Régionales/Secondaires vérifient l'existence de dépendances avant suppression, avec des messages d'erreur explicites.

---

## 12. POINTS D'AMÉLIORATION & RECOMMANDATIONS

### 🔴 Critique

#### 1. Absence totale d'authentification/autorisation
**Problème :** Tous les endpoints sont publics.  
**Solution :** Implémenter JWT avec FastAPI OAuth2 :
```python
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    # valider JWT, retourner l'utilisateur
```
Ajouter un endpoint `POST /auth/login` retournant un access_token.

#### 2. URL de base de données hardcodée avec mot de passe en clair
**Problème :** `"postgresql+...://forest_user:1234@localhost:5432/forest_db"` dans le code source.  
**Solution :** Utiliser `pydantic-settings` (déjà installé !) :
```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    class Config:
        env_file = ".env"

settings = Settings()
```

#### 3. Zéro test
**Problème :** Aucune couverture de test sur un code avec de la logique métier complexe (géospatiale notamment).  
**Solution minimale :** Tests d'intégration FastAPI avec `TestClient` et une base de test SQLite ou PostgreSQL de test :
```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_forest_overlap():
    # ...
```

### 🟠 Majeur

#### 4. ~~Duplication des routers Direction~~ ✅ Résolu
~~`directions.py`, `directions_regionales.py` et `directions_secondaires.py` implémentaient des logiques similaires avec seul `directions.py` monté.~~  
**Action effectuée :** `directions_regionales.py` et `directions_secondaires.py` ont été **supprimés**. Il ne reste plus qu'un seul fichier source `directions.py`, propre et sans dead code.

#### 5. Absence de système de migration (Alembic)
**Problème :** Les migrations artisanales dans `on_startup` sont fragiles, non versionnées, et non réversibles.  
**Solution :**
```bash
pip install alembic
alembic init alembic
alembic revision --autogenerate -m "initial"
alembic upgrade head
```

#### 6. CORS `allow_origins=["*"]` en production
**Réduire à la liste blanche des origines connues :**
```python
allow_origins=["https://mon-app.com", "http://localhost:3000"]
```

#### 7. Calcul de surface approximatif
**Problème :** `area_deg * (111320²) / 10000` est inexact au-delà des petites zones et ne corrige pas la distorsion en latitude.  
**Solution :** Utiliser PostGIS `ST_Area(ST_Transform(geom, 3857))` ou pyproj pour un calcul correct.

#### 8. Versions Python non pinnées dans `requirements.txt`
**Problème :** `pip install` peut installer des versions incompatibles futures.  
**Solution :** `pip freeze > requirements.lock` ou utiliser `poetry` / `uv` avec lockfile.

### 🟡 Mineur

#### 9. State management minimal (StatefulWidget + setState)
**Recommandation :** Pour une évolution future, migrer vers `Riverpod` (le choix le plus adapté à ce type d'app Flutter avec appels asynchrones multiples).

#### 10. Pas de timeout sur le client HTTP Flutter
```dart
// Ajouter un timeout
final response = await _client.get(uri)
    .timeout(const Duration(seconds: 30));
```

#### 11. Logging non structuré
**Recommandation :** Remplacer `echo=True` SQLAlchemy par `structlog` ou `loguru` avec niveaux et format JSON :
```python
import structlog
logger = structlog.get_logger()
logger.info("forest.created", forest_id=db_forest.id, name=forest.name)
```

#### 12. Pas de pagination sur la liste des forêts et parcelles
`limit=1000` par défaut peut surcharger le système avec un grand nombre de forêts. Implémenter une pagination correcte avec métadonnées :
```json
{ "data": [...], "total": 500, "skip": 0, "limit": 20 }
```

#### 13. `actif` non utilisé comme filtre
Le flag `actif` sur les utilisateurs est prévu mais les endpoints ne filtrent pas dessus. Ajouter `?actif=true` comme query parameter optionnel sur `GET /users/`.

#### 14. `db.query(Model).get(id)` déprécié
SQLAlchemy 2.0 a déprécié `Session.get()` via `.query()`. Utiliser :
```python
user = db.get(models.User, user_id)  # SQLAlchemy 2.0
```

---

## 13. RÉSUMÉ EXÉCUTIF

**User & Forest Management** est un microservice full-stack fonctionnel et bien délimité, développé avec **FastAPI (Python)** côté backend et **Flutter (Dart)** côté frontend. Son domaine métier est la gestion d'un patrimoine forestier géospatial avec une hiérarchie organisationnelle.

**Points remarquables :**
Le code présente une **maturité technique notable sur la partie géospatiale** — la validation topologique via PostGIS (non-chevauchement des forêts, containment des parcelles) est correctement implémentée et efficacement déléguée à la base de données. La structure de code est claire, modulaire et cohérente.

**Risques majeurs identifiés :**
1. **Sécurité nulle** — Aucune authentification, tous les endpoints sont publics, les credentials DB sont en dur. Ce service ne peut pas être exposé en dehors d'un réseau local fermé en l'état.
2. **Zéro test** — La logique métier complexe (calculs géospatiaux, règles topologiques) n'est couverte par aucun test automatisé, rendant toute modification risquée.
3. **Pas de Dockerfile ni CI/CD** — Le déploiement est entièrement manuel.

**Recommandation prioritaire pour un tech lead :**  
Avant tout passage en production, implémenter dans cet ordre : (1) authentification JWT, (2) variables d'environnement via `.env` + `pydantic-settings`, (3) migration vers Alembic, (4) tests d'intégration sur les règles géospatiales. Ces quatre actions réduiraient 80% du risque opérationnel actuel.

Le service est une **bonne base de développement** avec une architecture claire, mais est actuellement au stade **prototype/MVP** et nécessite un renforcement significatif avant industrialisation.
