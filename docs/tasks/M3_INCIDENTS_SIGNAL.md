# M3 — INCIDENT SERVICE + APP MOBILE AGENT
> Milestone 3 / 9 | Projet : GHABETNA | Étudiant : Omar Hellel
> Période : 6–13 avril 2026 | Durée : 8 jours
> Service : `incident-service` | Port : `8002` | DB : `incident_db`
> App mobile : `flutter_agent/` (nouvelle app Flutter séparée)

---

## EXIT CONDITIONS

- [ ] Agent connecté sur mobile signale un incident avec photo + GPS
- [ ] Parcelle détectée automatiquement via `ST_Contains` (exact) ou `ST_Distance` (nearest)
- [ ] Incident créé en `incident_db` avec tous les champs auto-remplis
- [ ] Event `PUBLISH incidents.new` sur Redis après création
- [ ] `GET /incidents/` retourne l'incident avec tous les champs
- [ ] Agent peut signaler dans n'importe quelle parcelle de la même forêt

---

## DÉCISIONS ARCHITECTURALES

| Décision | Choix retenu | Raison |
|---|---|---|
| App mobile | Nouvelle app `flutter_agent/` séparée | Cohérent avec pattern admin/superviseur/agent |
| Détection parcelle | GPS auto au moment de la photo — non modifiable | UX simple, fiabilité maximale |
| GPS exact | `ST_Contains` → `gps_match_type = 'exact'` | Cas normal |
| GPS hors parcelle | `ST_Distance` → parcelle la plus proche → `gps_match_type = 'nearest'` | Superviseur toujours résolu |
| Périmètre signalement | Toute parcelle de la même forêt | Agent passe physiquement par d'autres parcelles |
| Upload photos | Filesystem conteneur `/media/incidents/{uuid}.ext` | Simple, suffisant MVP |
| Sécurité inter-services | Header `X-Internal-Key` depuis `.env` | Cohérent avec auth-service |
| Types incidents | Table `incident_types` seedée au démarrage (Option B) | Normalisation sans surcharge CRUD admin |
| Priorités | Table `priorites` seedée au démarrage (Option B) | Même raison |
| Statuts | Table `statuts` seedée au démarrage | Cohérence, évite VARCHAR libres |
| Soft delete | `deleted_at TIMESTAMPTZ NULL` sur `incidents` | Auditabilité, traçabilité |
| Historique statuts | Table `incident_status_history` | Argument fort PFE — auditabilité complète |
| Citoyens | Hors scope M3 — sprint séparé ultérieur | Pas de flag source pour l'instant |
| FK inter-services | FK logiques uniquement — validation par appel REST | Chaque microservice a sa propre DB |

---

## ARCHITECTURE M3

```
[flutter_agent]
    │
    └── POST /incidents/ (multipart: photo + champs)
            │
            ▼
    [incident-service :8002]
            │
            ├── 1. GET /geo/parcelle-at?lat=X&lng=Y ──► [user-forest-service :8000]
            │        Header: X-Internal-Key              ST_Contains → exact
            │        Réponse: parcelle_id,               ST_Distance → nearest
            │                 forest_id,
            │                 dir_secondaire_id,
            │                 gps_match_type
            │
            ├── 2. Résoudre priorite via incident_types.priorite_id (DB locale)
            │
            ├── 3. Transaction atomique :
            │        INSERT incidents
            │        INSERT incident_photos
            │        INSERT incident_status_history (premier statut)
            │
            └── 4. PUBLISH redis:incidents.new {payload}
                     ├── notification-service (M5) ← SUBSCRIBE
                     └── scoring-service     (M6) ← SUBSCRIBE
```

---

## DB SCHEMA — incident_db

### Tables de référence (seedées au démarrage)

```sql
-- Priorités
CREATE TABLE priorites (
  id                  SERIAL PRIMARY KEY,
  code                VARCHAR(20)  NOT NULL UNIQUE,
  label               VARCHAR(50)  NOT NULL,
  declenche_telegram  BOOLEAN      NOT NULL DEFAULT FALSE
);

-- Types d'incidents
CREATE TABLE incident_types (
  id          SERIAL PRIMARY KEY,
  code        VARCHAR(50)  NOT NULL UNIQUE,
  label       VARCHAR(100) NOT NULL,
  priorite_id INTEGER      NOT NULL REFERENCES priorites(id),
  description TEXT
);

-- Statuts
CREATE TABLE statuts (
  id      SERIAL PRIMARY KEY,
  code    VARCHAR(30) NOT NULL UNIQUE,
  label   VARCHAR(50) NOT NULL,
  couleur VARCHAR(7)  NOT NULL   -- ex: '#E53935'
);
```

### Seed au démarrage (ON CONFLICT DO NOTHING)

```sql
INSERT INTO priorites (code, label, declenche_telegram) VALUES
  ('CRITIQUE', 'Critique', TRUE),
  ('HAUTE',    'Haute',    FALSE),
  ('NORMALE',  'Normale',  FALSE)
ON CONFLICT (code) DO NOTHING;

INSERT INTO incident_types (code, label, priorite_id) VALUES
  ('feu',              'Incendie',           1),
  ('refuge_suspect',   'Refuge suspect',     1),
  ('terrorisme',       'Terrorisme',         1),
  ('trafic',           'Trafic',             1),
  ('contrebande',      'Contrebande',        1),
  ('coupe_illegale',   'Coupe illégale',     2),
  ('depot_dechets',    'Dépôt de déchets',   3),
  ('maladie_vegetale', 'Maladie végétale',   3)
ON CONFLICT (code) DO NOTHING;

INSERT INTO statuts (code, label, couleur) VALUES
  ('en_attente', 'En attente', '#E53935'),
  ('en_cours',   'En cours',   '#FB8C00'),
  ('traite',     'Traité',     '#43A047'),
  ('rejete',     'Rejeté',     '#757575')
ON CONFLICT (code) DO NOTHING;
```

### Table principale incidents

```sql
CREATE TABLE incidents (
  id                       SERIAL PRIMARY KEY,

  -- Acteur (FK logique → forest_db.users)
  agent_id                 INTEGER      NOT NULL,

  -- Géographie résolue par GPS (FK logiques → forest_db)
  parcelle_id              INTEGER      NOT NULL,
  forest_id                INTEGER      NOT NULL,
  dir_secondaire_id        INTEGER      NOT NULL,

  -- GPS
  latitude                 FLOAT        NOT NULL,
  longitude                FLOAT        NOT NULL,
  gps_match_type           VARCHAR(10)  NOT NULL DEFAULT 'exact',

  -- Classification (FK réelles → tables locales)
  incident_type_id         INTEGER      NOT NULL REFERENCES incident_types(id),
  statut_id                INTEGER      NOT NULL REFERENCES statuts(id) DEFAULT 1,

  -- Description
  description              TEXT,

  -- Évaluation superviseur
  note_superviseur         INTEGER      CHECK (note_superviseur BETWEEN 1 AND 5),
  commentaire_superviseur  TEXT,

  -- Traçabilité
  updated_by               INTEGER,     -- FK logique → forest_db.users
  deleted_at               TIMESTAMPTZ, -- NULL = actif, rempli = soft deleted

  -- Timestamps
  created_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_inc_agent      ON incidents (agent_id);
CREATE INDEX ix_inc_forest     ON incidents (forest_id);
CREATE INDEX ix_inc_type       ON incidents (incident_type_id);
CREATE INDEX ix_inc_created    ON incidents (created_at DESC);
CREATE INDEX ix_inc_deleted    ON incidents (deleted_at) WHERE deleted_at IS NULL;
-- Index composite (requête superviseur la plus fréquente)
CREATE INDEX ix_inc_dir_statut ON incidents (dir_secondaire_id, statut_id, created_at DESC);
```

### Table photos

```sql
CREATE TABLE incident_photos (
  id           SERIAL PRIMARY KEY,
  incident_id  INTEGER      NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
  photo_url    VARCHAR(500) NOT NULL,
  uploaded_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_photos_incident ON incident_photos (incident_id);
```

### Table commentaires

```sql
CREATE TABLE incident_comments (
  id           SERIAL PRIMARY KEY,
  incident_id  INTEGER     NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
  author_id    INTEGER     NOT NULL,   -- FK logique → forest_db.users
  author_role  VARCHAR(20) NOT NULL,   -- 'superviseur' | 'admin'
  content      TEXT        NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_comments_incident ON incident_comments (incident_id);
```

### Table historique des statuts

```sql
CREATE TABLE incident_status_history (
  id             SERIAL PRIMARY KEY,
  incident_id    INTEGER     NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
  old_statut_id  INTEGER     REFERENCES statuts(id),  -- NULL pour le premier statut
  new_statut_id  INTEGER     NOT NULL REFERENCES statuts(id),
  changed_by     INTEGER     NOT NULL,  -- FK logique → forest_db.users
  changed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  commentaire    TEXT
);

CREATE INDEX ix_history_incident ON incident_status_history (incident_id);
CREATE INDEX ix_history_changed  ON incident_status_history (changed_at DESC);
```

---

## ENDPOINT INTERNE — user-forest-service (:8000)

```
GET /geo/parcelle-at?lat={lat}&lng={lng}
Header: X-Internal-Key: {INTERNAL_API_KEY}

Étape 1 — ST_Contains (exact match) :
  SELECT p.id, p.forest_id, f.direction_secondaire_id, 'exact' AS gps_match_type
  FROM parcelles p
  JOIN forests f ON p.forest_id = f.id
  WHERE ST_Contains(p.geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
  LIMIT 1;

Étape 2 — ST_Distance fallback (si étape 1 = 0 résultats) :
  SELECT p.id, p.forest_id, f.direction_secondaire_id, 'nearest' AS gps_match_type
  FROM parcelles p
  JOIN forests f ON p.forest_id = f.id
  ORDER BY ST_Distance(p.geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326))
  LIMIT 1;

Réponse 200 :
  { "parcelle_id": int, "forest_id": int, "dir_secondaire_id": int, "gps_match_type": "exact"|"nearest" }

Réponse 404 : aucune parcelle dans la DB
Réponse 403 : X-Internal-Key absent ou invalide
```

---

## ENDPOINTS — incident-service (:8002)

| Method | Route | Auth | RBAC | Description |
|---|---|---|---|---|
| GET | `/health` | Public | — | Health check |
| GET | `/incidents/types` | 🔒 JWT | tous | Liste types + priorités (dropdown Flutter) |
| GET | `/incidents/statuts` | 🔒 JWT | tous | Liste statuts + couleurs (badges Flutter) |
| POST | `/incidents/` | 🔒 JWT | agent | Créer incident multipart |
| GET | `/incidents/` | 🔒 JWT | scopé rôle | Liste incidents avec filtres |
| GET | `/incidents/my` | 🔒 JWT | agent | Mes incidents triés date DESC |
| GET | `/incidents/{id}` | 🔒 JWT | scopé rôle | Détail complet + photos + commentaires + historique |
| PATCH | `/incidents/{id}/status` | 🔒 JWT | superviseur | Mise à jour statut + note + commentaire |
| DELETE | `/incidents/{id}` | 🔒 JWT | admin | Soft delete |

### RBAC automatique sur `GET /incidents/`

| Rôle | Filtre forcé |
|---|---|
| `agent_forestier` | `agent_id = jwt.user_id` ET `deleted_at IS NULL` |
| `superviseur` | `dir_secondaire_id = jwt.direction_secondaire_id` ET `deleted_at IS NULL` |
| `admin` | `deleted_at IS NULL` uniquement |

---

## REDIS EVENT

```json
// PUBLISH incidents.new
{
  "incident_id": 42,
  "agent_id": 7,
  "forest_id": 3,
  "dir_secondaire_id": 2,
  "priorite_code": "CRITIQUE",
  "declenche_telegram": true,
  "type_code": "feu",
  "type_label": "Incendie",
  "latitude": 36.8065,
  "longitude": 10.1815
}
```

---

## TÂCHES DÉTAILLÉES

---

### BLOC 1 — SOCLE INCIDENT-SERVICE (Jour 1)

#### T1 — Setup incident-service
- [X] Créer dossier `incident-service/`
- [X] `requirements.txt` : `fastapi uvicorn[standard] sqlalchemy alembic python-multipart httpx redis pydantic-settings psycopg2-binary python-jose[cryptography]`
- [X] `app/config.py` — `BaseSettings` lit `.env` : `INCIDENT_DB_URL, FOREST_SERVICE_URL, INTERNAL_API_KEY, REDIS_URL, SECRET_KEY`
- [X] `app/db.py` — engine SQLAlchemy + `get_db()` dependency
- [X] `app/main.py` — app FastAPI + CORS restrictif + routers + startup event
- [X] Copier `shared/jwt_utils.py` → `app/utils/jwt_utils.py`
- [X] Copier `shared/redis_client.py` → `app/utils/redis_client.py`
- [X] `GET /health` → `{"status": "ok", "service": "incident-service"}`
- [X] Vérifier `:8002/docs` accessible

#### T2 — Alembic + migrations incident_db
- [X] `alembic init alembic` + configurer `env.py` avec `INCIDENT_DB_URL`
- [X] Migration 001 : tables `priorites`, `incident_types`, `statuts`
- [X] Migration 002 : table `incidents` + tous les indexes
- [X] Migration 003 : tables `incident_photos`, `incident_comments`
- [X] Migration 004 : table `incident_status_history`
- [X] `alembic upgrade head` → toutes les tables créées sans erreur

#### T3 — Seed au démarrage
- [X] `app/utils/seed.py` — fonction `run_seed(db)`
- [X] INSERT priorites avec `ON CONFLICT (code) DO NOTHING`
- [X] INSERT incident_types avec `ON CONFLICT (code) DO NOTHING`
- [X] INSERT statuts avec `ON CONFLICT (code) DO NOTHING`
- [X] Appeler `run_seed()` dans l'événement `startup` de `main.py`
- [X] Vérifier idempotence : 2 démarrages successifs → pas d'erreur, pas de doublons

---

### BLOC 2 — ENDPOINT INTERNE GPS (Jour 2)

#### T4 — `/geo/parcelle-at` dans user-forest-service
- [X] Créer `user-forest-service/app/routers/geo.py`
- [X] Dependency `verify_internal_key(request)` : header absent ou invalide → 403
- [X] Ajouter `INTERNAL_API_KEY` dans `.env` et `config.py` de user-forest-service
- [X] Query ST_Contains (exact match)
- [X] Query ST_Distance fallback si exact = 0 résultats
- [X] Réponse `{parcelle_id, forest_id, dir_secondaire_id, gps_match_type}`
- [X] 404 si aucune parcelle dans la DB
- [X] Inclure le router dans `user-forest-service/app/main.py`
- [X] Tester avec coordonnées dans une parcelle connue → `gps_match_type = 'exact'`
- [X] Tester avec coordonnées hors parcelle → `gps_match_type = 'nearest'`

#### T5 — Client HTTP interne dans incident-service
- [X] Créer `app/utils/forest_client.py`
- [X] `async def get_parcelle_at(lat, lng) → dict`
- [X] Header `X-Internal-Key` injecté automatiquement depuis `settings`
- [X] Timeout 5s max
- [X] 404 → lever `HTTPException(422, "Position hors zone surveillée")`
- [X] Timeout/connexion échouée → lever `HTTPException(503, "Service indisponible")`

---

### BLOC 3 — BACKEND INCIDENTS (Jours 3–4)

#### T6 — Modèles SQLAlchemy
- [X] `app/models/priorite.py` — classe `Priorite`
- [X] `app/models/incident_type.py` — classe `IncidentType` avec relation `priorite`
- [X] `app/models/statut.py` — classe `Statut`
- [X] `app/models/incident.py` — classe `Incident` avec relations `type`, `statut`
- [X] `app/models/photo.py` — classe `IncidentPhoto`
- [X] `app/models/comment.py` — classe `IncidentComment`
- [X] `app/models/history.py` — classe `IncidentStatusHistory`

#### T7 — Schémas Pydantic
- [X] `IncidentCreate` : `{incident_type_code, description}` — lat/lng comme Form fields séparés
- [X] `IncidentRead` : tous champs + `type_label`, `priorite_code`, `statut_code`, `statut_couleur`, `photo_urls: list[str]`, `comments: list`, `history: list`
- [X] `IncidentListItem` : version allégée sans commentaires ni historique
- [X] `IncidentStatusUpdate` : `{statut_code, note_superviseur?, commentaire?}`
- [X] `TypeIncidentRead` : `{code, label, priorite_code, priorite_label, declenche_telegram}`
- [X] `StatutRead` : `{code, label, couleur}`

#### T8 — `GET /incidents/types` et `GET /incidents/statuts`
- [X] Retourner liste complète depuis DB seedée
- [X] Utilisés par Flutter pour dropdowns et badges
- [X] Pas de filtre — toujours retourner toutes les entrées

#### T9 — `POST /incidents/` multipart
- [X] Accepter `Form(incident_type_code)`, `Form(description)`, `Form(latitude)`, `Form(longitude)`, `File(photo)`
- [X] Valider `incident_type_code` existe en DB → sinon 422
- [X] Valider type fichier : `jpg/jpeg/png/webp` uniquement → 422 sinon
- [X] Valider taille fichier : max 10MB → 422 sinon
- [X] Appeler `forest_client.get_parcelle_at(lat, lng)`
- [X] Résoudre `incident_type_id`, `priorite_id`, `declenche_telegram` via JOIN local
- [X] Résoudre `statut_id` initial = statut `en_attente`
- [X] Sauvegarder photo : `uuid4().hex + extension` → `/media/incidents/{filename}`
- [X] Transaction atomique :
  - [X] INSERT `incidents`
  - [X] INSERT `incident_photos`
  - [X] INSERT `incident_status_history` (`old_statut_id = NULL`, `changed_by = agent_id`)
- [X] Retourner `IncidentRead` avec 201
- [X] Après commit : `redis.publish('incidents.new', json.dumps(payload))` dans try/except
  - [X] Payload : `incident_id, agent_id, forest_id, dir_secondaire_id, priorite_code, declenche_telegram, type_code, type_label, latitude, longitude`
  - [X] Si Redis down → `logger.warning(...)` uniquement, NE PAS faire échouer le POST

#### T10 — `GET /incidents/` avec RBAC
- [X] Filtre `deleted_at IS NULL` toujours appliqué
- [X] `agent_forestier` → forcer `agent_id = jwt.user_id`
- [X] `superviseur` → forcer `dir_secondaire_id = jwt.direction_secondaire_id`
- [X] `admin` → pas de filtre forcé
- [X] Filtres optionnels : `forest_id, statut_code, type_code, priorite_code, date_debut, date_fin`
- [X] JOIN `incident_types`, `statuts`, `priorites` pour enrichir la réponse
- [X] Trier `created_at DESC`, pagination `skip=0&limit=50`

#### T11 — `GET /incidents/my`
- [X] `agent_id = jwt.user_id` ET `deleted_at IS NULL`
- [X] Trier `created_at DESC`
- [X] Inclure `photo_urls` et `statut_couleur`

#### T12 — `GET /incidents/{id}`
- [X] Vérifier accès selon rôle (agent → ses incidents, superviseur → sa direction, admin → tous)
- [X] Vérifier `deleted_at IS NULL` sauf admin
- [X] JOIN photos + commentaires + historique statuts
- [X] Retourner `IncidentRead` complet

#### T13 — `PATCH /incidents/{id}/status`
- [X] Vérifier `role == 'superviseur'` → sinon 403
- [X] Vérifier `incident.dir_secondaire_id == jwt.direction_secondaire_id` → sinon 403
- [X] Valider `statut_code` existe en DB → sinon 422
- [X] Valider `note_superviseur` entre 1 et 5 si fournie → sinon 422
- [X] Transaction atomique :
  - [X] UPDATE `incidents` : `statut_id`, `note_superviseur`, `commentaire_superviseur`, `updated_by`, `updated_at`
  - [X] INSERT `incident_status_history`
  - [X] INSERT `incident_comments` si commentaire fourni
- [X] Retourner incident mis à jour

#### T14 — `DELETE /incidents/{id}` (soft delete)
- [X] Vérifier `role == 'admin'` → sinon 403
- [X] UPDATE `incidents` : `deleted_at = NOW()`, `updated_by = jwt. nbuser_id`
- [X] Retourner 204

#### T15 — Servir les fichiers media
- [X] `app.mount("/media", StaticFiles(directory="/media/incidents"), name="media")`
- [X] Créer `/media/incidents/` au startup si inexistant
- [X] Tester URL : `http://localhost:8002/media/incidents/{uuid}.jpg`

---

### BLOC 4 — APP MOBILE FLUTTER AGENT (Jours 5–7)

#### T16 — Setup `flutter_agent/`
- [X] `flutter create flutter_agent`
- [X] `pubspec.yaml` dépendances :
  ```yaml
  http: ^1.2.2
  shared_preferences: ^2.2.2
  image_picker: ^1.0.4
  geolocator: ^11.0.0
  flutter_map: ^7.0.2
  latlong2: ^0.9.1
  ```
- [X] `AndroidManifest.xml` : permissions `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `CAMERA`, `READ_EXTERNAL_STORAGE`
- [X] `Info.plist` : clés `NSLocationWhenInUseUsageDescription`, `NSCameraUsageDescription`, `NSPhotoLibraryUsageDescription`
- [X] `config/api_config.dart` : `incidentServiceBaseUrl`, `authBaseUrl`
- [X] Copier `token_storage.dart` + `http_client.dart` depuis `flutter_superviseur/`
- [X] `main.dart` routing + theme Material 3 seedColor: Colors.green

#### T17 — Auth agent mobile
- [X] `services/auth_service.dart` — `login(email, password)`
- [X] Décoder JWT → vérifier `role == 'agent_forestier'` → sinon "Compte non autorisé"
- [X] Stocker `access_token`, `refresh_token`, `user_id`, `username`
- [X] `screens/login_screen.dart` : formulaire + loading + messages erreur en français

#### T18 — Services et modèles Flutter
- [X] `services/incident_service.dart` :
  - [X] `getTypes()` → `GET /incidents/types`
  - [X] `getStatuts()` → `GET /incidents/statuts`
  - [X] `createIncident(type_code, description, lat, lng, photo)` → multipart POST
  - [X] `getMyIncidents()` → `GET /incidents/my`
  - [X] `getIncidentDetail(id)` → `GET /incidents/{id}`
- [X] `models/incident.dart` : `IncidentType`, `Statut`, `IncidentListItem`, `IncidentDetail` avec `fromJson()`

#### T19 — `incident_report_screen.dart`
- [X] **Capture photo :**
  - [X] Bouton "Prendre une photo" → `ImagePicker(source: camera)`
  - [X] Bouton "Galerie" → `ImagePicker(source: gallery)`
  - [X] Preview photo (Container 200px hauteur)
  - [X] Photo obligatoire → validation avant soumission
- [X] **GPS automatique :**
  - [X] `initState` → `Geolocator.getCurrentPosition()` automatiquement
  - [X] Indicateur "📍 Localisation en cours..."
  - [X] Coordonnées affichées en petit texte une fois obtenues
  - [X] Permission refusée → dialog explicatif en français
  - [X] GPS désactivé → dialog demande activation
  - [X] GPS obligatoire → validation avant soumission
- [X] **Formulaire :**
  - [X] Dropdown `type_incident` chargé depuis `GET /incidents/types`
  - [X] Badge priorité auto affiché selon type (Rouge=CRITIQUE, Orange=HAUTE, Vert=NORMALE)
  - [X] Champ `description` optionnel, multiline, max 500 chars
- [X] **Soumission :**
  - [X] Valider photo + type + GPS → SnackBar rouge si manquant
  - [X] Loading indicator + bouton désactivé pendant upload
  - [X] Succès → SnackBar vert "Incident signalé avec succès ✅" + `Navigator.pop()`
  - [X] Erreur 422 hors zone → "Votre position est hors zone surveillée"
  - [X] Erreur 503 → "Service indisponible, réessayez"

#### T20 — `my_incidents_screen.dart`
- [X] `GET /incidents/my` → `ListView` incidents
- [X] `ListTile` : icône type + `type_label` + date + badge statut coloré + badge priorité
- [X] Pull-to-refresh (`RefreshIndicator`)
- [X] Tap → `IncidentDetailScreen`
- [X] État vide : icône + "Aucun incident signalé pour le moment"
- [X] État erreur : icône + message + bouton "Réessayer"

#### T21 — `incident_detail_screen.dart`
- [X] Photo plein largeur, tap → plein écran
- [X] Row badges : type + priorité + statut (couleurs depuis `statut.couleur`)
- [X] Date/heure signalement formatée
- [X] Mini-carte `flutter_map` : marker PIN sur coordonnées GPS, zoom 15, non interactive
- [X] Indicateur GPS : "📍 Position exacte" ou "📍 Position approximative (parcelle la plus proche)"
- [X] Section "Retour superviseur" si `note_superviseur != null` : étoiles + commentaire
- [X] Historique statuts : liste changements avec date et auteur

#### T22 — `home_screen.dart` agent
- [X] AppBar "GHABETNA" + bouton déconnexion
- [X] Sous-titre "Bonjour, {username}"
- [X] 2 cards principales : "Signaler un incident" (rouge/orange) + "Mes signalements" (verte)
- [X] Badge compteur incidents `en_attente` sur la card "Mes signalements"
- [X] Placeholder score badge gris "Score: --" → sera rempli en M6

---

### BLOC 5 — REDIS + INTÉGRATION (Jour 8)

#### T23 — PUBLISH Redis
- [ ] Après commit transaction → construire payload enrichi avec `declenche_telegram`
- [ ] `redis_client.publish('incidents.new', json.dumps(payload))`
- [ ] Try/except : Redis down → `logger.warning(...)` uniquement, pas d'exception levée
- [ ] Tester : `redis-cli SUBSCRIBE incidents.new` → message reçu après signalement

#### T24 — Tests d'intégration bout en bout
- [ ] Login agent → token valide stocké
- [ ] Signaler feu avec photo + GPS dans parcelle → `gps_match_type = 'exact'`
- [ ] Signaler avec GPS hors parcelle → `gps_match_type = 'nearest'`
- [ ] Vérifier incident en DB avec tous les champs auto-remplis
- [ ] Vérifier `incident_status_history` créé avec premier statut (`old_statut_id = NULL`)
- [ ] Vérifier photo accessible via URL `/media/incidents/{uuid}.jpg`
- [ ] Vérifier Redis reçoit l'event avec payload complet
- [ ] `GET /incidents/my` → retourne l'incident créé
- [ ] `GET /incidents/{id}` → détail complet avec photos + historique
- [ ] RBAC : superviseur voit uniquement sa direction
- [ ] RBAC : agent ne voit que ses incidents
- [ ] `PATCH /incidents/{id}/status` → statut mis à jour + historique créé
- [ ] Superviseur hors scope → 403
- [ ] `note_superviseur = 6` → 422 (contrainte CHECK)
- [ ] Seed idempotent : redémarrer service → pas de doublons en DB

---

## STRUCTURE FICHIERS

```
incident-service/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── priorite.py
│   │   ├── incident_type.py
│   │   ├── statut.py
│   │   ├── incident.py
│   │   ├── photo.py
│   │   ├── comment.py
│   │   └── history.py
│   ├── schemas/
│   │   └── incident.py
│   ├── routers/
│   │   └── incidents.py
│   └── utils/
│       ├── jwt_utils.py        ← copié depuis shared/
│       ├── redis_client.py     ← copié depuis shared/
│       ├── forest_client.py    ← nouveau
│       └── seed.py             ← nouveau
├── alembic/
├── alembic.ini
└── requirements.txt

user-forest-service/            ← MODIFICATION
└── app/
    └── routers/
        └── geo.py              ← NOUVEAU

flutter_agent/                  ← NOUVELLE APP
├── lib/
│   ├── main.dart
│   ├── config/
│   │   └── api_config.dart
│   ├── models/
│   │   └── incident.dart
│   ├── services/
│   │   ├── auth_service.dart
│   │   └── incident_service.dart
│   ├── utils/
│   │   ├── token_storage.dart
│   │   └── http_client.dart
│   └── screens/
│       ├── login_screen.dart
│       ├── home_screen.dart
│       ├── incident_report_screen.dart
│       ├── my_incidents_screen.dart
│       └── incident_detail_screen.dart
└── pubspec.yaml
```

---

## PLANNING JOUR PAR JOUR

| Jour | Date | Tâches | Livrable |
|---|---|---|---|
| J1 | 6 avril | T1 + T2 + T3 | incident-service démarre, tables créées, seed ok |
| J2 | 7 avril | T4 + T5 | `/geo/parcelle-at` opérationnel + client HTTP |
| J3 | 8 avril | T6 + T7 + T8 + T9 | `POST /incidents/` fonctionnel |
| J4 | 9 avril | T10 + T11 + T12 + T13 + T14 + T15 | Tous les endpoints backend |
| J5 | 10 avril | T16 + T17 + T18 | Flutter setup + auth + services |
| J6 | 11 avril | T19 | `incident_report_screen` complet |
| J7 | 12 avril | T20 + T21 + T22 | Tous les écrans Flutter |
| J8 | 13 avril | T23 + T24 | Redis PUBLISH + tests bout en bout |

---

## RÈGLES MÉTIER

- RULE: Un agent peut signaler dans toute parcelle de la même forêt — pas seulement sa parcelle assignée
- RULE: La parcelle est détectée automatiquement par GPS — l'agent ne la choisit jamais manuellement
- RULE: `gps_match_type = 'exact'` si ST_Contains, `'nearest'` si ST_Distance fallback
- RULE: La priorité est calculée via `incident_types.priorite_id` — non modifiable par l'agent
- RULE: `statut_id` initial toujours = `en_attente` à la création
- RULE: Tout changement de statut → INSERT obligatoire dans `incident_status_history`
- RULE: `POST /incidents/` ne doit jamais échouer à cause de Redis — PUBLISH dans try/except
- RULE: Photos stockées sur filesystem `/media/incidents/` — jamais en DB
- RULE: `PATCH /incidents/{id}/status` → superviseur limité à sa `direction_secondaire_id`
- RULE: `note_superviseur` contrainte DB : `CHECK (note_superviseur BETWEEN 1 AND 5)`
- RULE: Soft delete uniquement — jamais de DELETE physique sur `incidents`
- RULE: Endpoint `/geo/parcelle-at` protégé par `X-Internal-Key` — jamais exposé publiquement
- RULE: Chaque microservice a sa propre DB — pas de FK PostgreSQL inter-services — validation par appel REST
- RULE: `deleted_at IS NULL` toujours filtré dans les requêtes sauf admin explicitement

---

## KNOWN ISSUES ANTICIPÉS

- ISSUE: `geolocator` sur émulateur Android retourne (0,0) — tester sur device réel ou configurer coordonnées GPS de l'émulateur
- ISSUE: `image_picker` iOS crash si les 3 clés `Info.plist` absentes
- ISSUE: Photos dans `/media/incidents/` perdues si conteneur Docker recréé — volume Docker à ajouter en Phase 2
- ISSUE: ST_Distance retourne la parcelle la plus proche globalement — si elle appartient à une autre forêt le rattachement sera incorrect — à filtrer par forêt en Phase 2

---

## REFACTOR LATER

- REFACTOR: Filtrer ST_Distance par `forest_id` pour rester dans la même forêt — Phase 2
- REFACTOR: Pagination curseur sur `GET /incidents/` pour > 1000 incidents — Phase 2
- REFACTOR: Volume Docker pour `/media/incidents/` — Phase 2
- REFACTOR: WebSocket temps réel au lieu de polling 15s (M4) — Phase 2
- REFACTOR: Citoyens — inscription libre + rôle `citoyen` — sprint dédié
- REFACTOR: Package Flutter partagé `AuthenticatedClient` + `TokenStorage` — Phase 2
- REFACTOR: Endpoint admin pour gérer `incident_types` dynamiquement — Phase 2

---

## DÉPENDANCES

| Dépend de | Ce qui est requis |
|---|---|
| M0 ✅ | Redis UP, `.env` configuré, `shared/jwt_utils.py` + `shared/redis_client.py` disponibles |
| M1 ✅ | JWT valide, login agent fonctionnel sur `auth-service :8001` |
| M2 ✅ | `agent_parcelle_assignments` dans `forest_db`, parcelles créées avec géométrie PostGIS |

## PRÉPARE POUR

| Milestone | Ce que M3 fournit |
|---|---|
| M4 | `GET /incidents/?dir_secondaire_id=X&statut_code=en_attente` pour dashboard superviseur |
| M5 | Event Redis `incidents.new` avec `declenche_telegram: true` pour Telegram |
| M6 | Event Redis `incidents.new` + `PATCH /status` avec `note_superviseur` pour scoring |
| M7 | Table `incidents` avec `created_at`, `incident_type_id`, `dir_secondaire_id` pour analytics |
