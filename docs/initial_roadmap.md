# GHABETNA — ROADMAP DÉFINITIF PAR MILESTONES
> Généré : 27 mars 2026 | Deadline MVP : 30 avril 2026 | Phase 2 : 1–20 mai 2026
> Étudiant : Omar Hellel | Entreprise : Smart For Green

---

## CONTEXTE PROJET

### Ce qui est TERMINÉ — MS-1 user-forest-service (FastAPI :8000 / forest_db)

**Backend endpoints actifs :**
- `roles` : 5 endpoints CRUD
- `users` : 6 endpoints CRUD — champs `direction_regionale_id` (agent) / `direction_secondaire_id` (superviseur) / `role_id`
- `forests` : 6 endpoints CRUD + validation GeoJSON PostGIS (ST_Intersects non-chevauchement)
- `parcelles` : 7 endpoints CRUD + ST_Contains containment + ST_Disjoint non-chevauchement
- `directions-regionales` : 5 endpoints CRUD + protection FK
- `directions-secondaires` : 6 endpoints CRUD + filtre by-regionale + protection FK

**Flutter frontend actifs (8 écrans) :**
- `home_screen.dart` — dashboard responsive LayoutBuilder
- `user_management_screen.dart` — CRUD users + attribution rôle + affectation direction (TOUT ici)
- `directions_screen.dart` — hiérarchie DR/DS
- `add_forest_screen.dart` — formulaire + dessin polygone flutter_map
- `edit_forest_screen.dart` — édition forêt + carte
- `forest_list_screen.dart` — liste forêts
- `parcelle_screen.dart` — gestion parcelles sur carte
- ~~`assign_superviseur_screen.dart`~~ — **SUPPRIMÉ** (fonctionnalité intégrée dans user_management_screen)

**Modèle de données MS-1 :**
```
users : id, username, email, hashed_password, role_id, 
        direction_regionale_id (agent=rempli, superviseur=NULL),
        direction_secondaire_id (superviseur=rempli, agent=NULL),
        telephone, actif

forests : id, name, description, geom POLYGON(4326), 
          created_by_id, direction_secondaire_id, direction_regionale_id,
          surface_ha, type_foret

parcelles : id, forest_id, name, description, geom POLYGON(4326),
            surface_ha, created_by_id
```

**Gaps MS-1 à corriger avant intégration :**
- Credentials DB hardcodés (`password:1234`) → migrer vers `.env` + pydantic-settings
- Aucun JWT → ajouter middleware après M1
- CORS `allow_origins=["*"]` → restreindre
- `Session.get()` déprécié → `db.get(Model, id)`

---

## ARCHITECTURE GLOBALE

### 6 Microservices + DB séparées

| Service | Port | DB propre | Statut |
|---|---|---|---|
| user-forest-service | 8000 | forest_db | ✅ TERMINÉ |
| auth-service | 8001 | auth_db | 🔴 M1 |
| incident-service | 8002 | incident_db | 🔴 M3 |
| notification-service | 8003 | notif_db | 🔴 M5 |
| scoring-service | 8004 | scoring_db | 🔴 M6 |
| analytics-service | 8005 | analytics_db (vues matérialisées) | 🔴 M7 |
| Nginx API Gateway | 80 | — | 🔴 M8 (Phase 2) |
| Redis | 6379 | — | 🔴 M0 |

### Redis — 3 rôles distincts

| Rôle | Pattern | Producteur | Consommateur | TTL |
|---|---|---|---|---|
| JWT Blacklist | `SET blacklist:{jti}` | auth-service (logout) | TOUS les services (verify_token) | = durée restante token |
| Event Bus | `PUBLISH incidents.new {payload}` | incident-service | scoring-service + notification-service | Sans TTL (Pub/Sub) |
| Cache scores | `SET score:{agent_id} {json}` | scoring-service | scoring-service (lecture rapide) | 5 min |
| Cache analytics | `SET analytics:{key} {json}` | analytics-service | analytics-service | 5 min |

### Module partagé (copié dans chaque service)

```python
# shared/jwt_utils.py
def verify_token(token) -> payload | HTTPException(401)
def get_current_user() -> Depends
def require_role(role: str) -> Depends  # HTTPException(403) si rôle insuffisant

# shared/redis_client.py  
def publish(channel, payload)
def subscribe(channel, callback)
def get_cache(key) -> value | None
def set_cache(key, value, ttl)
def blacklist_token(jti, ttl)
def is_blacklisted(jti) -> bool
```

### Règles métier d'affectation (cascade hiérarchique)

```
Admin
 └─ Crée : Directions Régionales / Secondaires / Forêts / Parcelles / Users
 └─ Affecte : Superviseur → Direction Secondaire (via user_management_screen)
 └─ Affecte : Agent → Direction Régionale (via user_management_screen)
    → agent.direction_regionale_id = DR.id
    → agent.direction_secondaire_id = NULL

Superviseur (lié à direction_secondaire_id = DS.id, DS.region_id = DR.id)
 └─ Voit : agents WHERE direction_regionale_id = DR.id (agents de SA région)
 └─ Affecte : agent → parcelle (parcelle.forest.direction_secondaire_id = DS.id)
    → INSERT agent_parcelle_assignments (incident_db)
    → Contrainte : agent.direction_regionale_id == DS.region_id

Agent (lié à direction_regionale_id = DR.id)
 └─ Signale : incident dans sa parcelle assignée
 └─ Rattachement auto : ST_Contains(parcelle.geom, POINT(GPS)) → parcelle_id + forest_id
```

### Flux incident complet (bout en bout)

```
[Mobile Agent]
  → POST /api/incidents/ {lat, lng, type, description, photo}
  
[incident-service]
  → GET /geo/parcelle-at?lat=X&lng=Y → user-forest-service (ST_Contains PostGIS)
  → Résout : parcelle_id, forest_id, dir_secondaire_id
  → INSERT incident (incident_db)
  → PUBLISH redis:incidents.new {incident_id, forest_id, dir_secondaire_id, priorite, agent_id}

[notification-service] ← SUBSCRIBE incidents.new
  → Si priorite == CRITIQUE → Telegram Bot → Protection Civile < 10s

[scoring-service] ← SUBSCRIBE incidents.new
  → Recalcule score agent → SET redis:score:{agent_id} TTL 5min

[Flutter Web Superviseur]
  → GET /api/incidents/?dir_secondaire_id=X (polling 15s)
  → Markers sur carte flutter_map (forêts de SA direction)
  → Heatmap DBSCAN visible sur carte
```

### UX affectation agent→parcelle (recommandation)

**Écran dédié dans dashboard superviseur web** :
`team_assignment_screen.dart`
- Carte flutter_map affichant les parcelles de SA direction secondaire
- Panel latéral : liste agents disponibles (direction_regionale = sa région, pas encore affectés)
- Tap sur une parcelle → dropdown agents disponibles → confirmer
- Table `agent_parcelle_assignments` dans `incident_db`

```sql
-- incident_db
CREATE TABLE agent_parcelle_assignments (
  id              SERIAL PRIMARY KEY,
  agent_id        INTEGER NOT NULL,  -- FK logique vers forest_db.users
  parcelle_id     INTEGER NOT NULL,  -- FK logique vers forest_db.parcelles
  forest_id       INTEGER NOT NULL,  -- FK logique vers forest_db.forests
  dir_secondaire_id INTEGER NOT NULL,
  assigned_by     INTEGER NOT NULL,  -- superviseur_id
  assigned_at     TIMESTAMP DEFAULT NOW(),
  actif           BOOLEAN DEFAULT TRUE,
  UNIQUE (agent_id) WHERE actif = TRUE  -- un agent = une seule parcelle active
);
```

> **Note FK logiques** : DB séparées → pas de vraies FK entre DBs. Les IDs sont validés par appels REST au moment de l'affectation.

---

## MILESTONES — VUE D'ENSEMBLE

| # | Milestone | Période | Dépend de | Exit Condition |
|---|---|---|---|---|
| M0 | Socle technique | 27–28 mars | — | `docker-compose up` → 6 DB + Redis UP |
| M1 | Auth Service | 29 mars–2 avril | M0 | Login→token, logout→401, mauvais rôle→403 |
| M2 | MS-1 sécurisé + affectation parcelle | 3–5 avril | M0+M1 | JWT sur MS-1, superviseur affecte agent→parcelle |
| M3 | Incident Service + Mobile Agent | 6–13 avril | M0+M1+M2 | Agent signale→parcelle auto via GPS→ST_Contains→Redis event |
| M4 | Dashboard Superviseur Flutter Web | 14–20 avril | M1+M3 | Carte incidents scopée direction, validation fonctionnelle |
| M5 | Notification Telegram | 21–22 avril | M3 Redis | Feu signalé → Telegram < 10s mesuré |
| M6 | Scoring Agents | 23–26 avril | M3 Redis | Score recalculé, visibilité par rôle correcte |
| M7 | Analytics + Heatmap | 27–30 avril | M3+M6 | Heatmap DBSCAN + dashboard → MVP COMPLET |
| M8 | API Gateway Nginx | 1–3 mai | M0–M7 | Tout via :80, ports directs bloqués |

---

## M0 — SOCLE TECHNIQUE
**Période :** 27–28 mars | **Durée :** 2 jours
**Exit condition :** `docker-compose up` → 6 PostgreSQL + Redis démarrés. `jwt_utils.py` et `redis_client.py` importables. MS-1 lit son `.env`.

### Tâches

| # | Tâche | Détail | Critère validation |
|---|---|---|---|
| T1 | Mono-repo | `mkdir -p ghabetna/{auth,incident,notification,scoring,analytics}-service nginx shared flutter-app` | Arborescence présente |
| T2 | `.env` global | `SECRET_KEY, AUTH_DB_URL, INCIDENT_DB_URL, SCORING_DB_URL, ANALYTICS_DB_URL, NOTIF_DB_URL, FOREST_DB_URL, REDIS_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID` | `.env.example` commité, `.env` dans `.gitignore` |
| T3 | docker-compose.yml | 6 postgres (ports 5432–5437) + redis:6379 + volumes nommés | `docker-compose up` → 7 conteneurs healthy |
| T4 | `shared/jwt_utils.py` | `verify_token()`, `get_current_user()`, `require_role()` | Import depuis un service → fonctionne sans erreur |
| T5 | `shared/redis_client.py` | `publish/subscribe/get_cache/set_cache/blacklist_token/is_blacklisted` | Test publish→subscribe reçoit le message |
| T6 | Migrer MS-1 `.env` | `app/config.py` BaseSettings, supprimer `password:1234` hardcodé, corriger CORS | MS-1 démarre avec `.env`, plus aucun credential en dur |

---

## M1 — AUTH SERVICE
**Période :** 29 mars–2 avril | **Durée :** 5 jours | **Port :** 8001 | **DB :** auth_db
**Exit condition :** Login credentials valides → `access_token` + `refresh_token`. Token expiré → 401. Agent sur endpoint admin → 403. Logout → token blacklisté Redis → 401 immédiat sur tous les services.

### DB auth_db

```sql
refresh_tokens(id, user_id, token_hash, expires_at, revoked)
activation_tokens(id, user_id, token, expires_at, used)
```

### Endpoints

| Endpoint | Auth | Corps / Params | Réponse |
|---|---|---|---|
| `POST /auth/login` | Public | `{email, password}` | `{access_token, refresh_token, role, user_id, direction_secondaire_id, direction_regionale_id}` |
| `POST /auth/refresh` | refresh_token body | `{refresh_token}` | `{access_token}` |
| `POST /auth/logout` | Bearer | — | 204 + blacklist Redis |
| `GET /auth/me` | Bearer | — | `{user_id, email, role, direction_secondaire_id, direction_regionale_id}` |
| `POST /auth/activate/{token}` | Public | — | 200 + PATCH actif=true sur user-forest-service |

### Tâches

| # | Tâche | Détail | Critère validation |
|---|---|---|---|
| T1 | Setup auth-service | `pip install fastapi python-jose[cryptography] redis passlib pydantic-settings` | `/docs` accessible sur :8001 |
| T2 | `POST /auth/login` | GET user via `GET /users/by-email/{email}` → user-forest-service. Vérifie hash. JWT access (exp 30min, payload: user_id+role+dir_ids). Refresh (exp 7j) → hash stocké auth_db + Redis TTL 7j | Token JWT décodable sur jwt.io |
| T3 | `POST /auth/refresh` | Vérifie refresh hash dans Redis (non révoqué) → nouveau access_token | Nouveau token valide retourné |
| T4 | `POST /auth/logout` | `SET redis:blacklist:{jti}` TTL = exp restante. DELETE refresh Redis | Même token → 401 sur tous services |
| T5 | `GET /users/by-email/{email}` dans MS-1 | Nouveau endpoint interne (pas de JWT requis, IP whitelist ou header secret) | auth-service récupère user pour login |
| T6 | `POST /auth/activate/{token}` | Vérifie activation_token en auth_db → PATCH `/users/{id}` actif=true sur MS-1 → marque token used | Compte activé, login possible |
| T7 | JWT sur MS-1 | Copier `shared/jwt_utils.py`. Ajouter `Depends(verify_token)` sur tous endpoints. `require_role('admin')` sur endpoints sensibles. `require_role('superviseur')` sur affectations | Sans token → 401. Agent sur /users/ admin → 403 |
| T8 | `login_screen.dart` Flutter | Formulaire email+password → `POST /auth/login` → stocker tokens `shared_preferences` → routing : agent→mobile, superviseur/admin→web | Login agent → app mobile. Login superviseur → web |
| T9 | `auth_interceptor.dart` | Injecter `Authorization: Bearer` sur tous services. Si 401 → `POST /auth/refresh` → retry automatique | Refresh transparent, session persistante |

---

## M2 — MS-1 SÉCURISÉ + AFFECTATION AGENT→PARCELLE
**Période :** 3–5 avril | **Durée :** 3 jours
**Exit condition :** Superviseur affecte agent→parcelle avec contraintes métier respectées (agent de sa région, parcelle de sa direction secondaire). Entrée vérifiable en incident_db. Endpoint MS-1 sans token → 401.

### Table dans incident_db

```sql
CREATE TABLE agent_parcelle_assignments (
  id                SERIAL PRIMARY KEY,
  agent_id          INTEGER NOT NULL,
  parcelle_id       INTEGER NOT NULL,
  forest_id         INTEGER NOT NULL,
  dir_secondaire_id INTEGER NOT NULL,
  assigned_by       INTEGER NOT NULL,
  assigned_at       TIMESTAMP DEFAULT NOW(),
  actif             BOOLEAN DEFAULT TRUE,
  UNIQUE (agent_id) WHERE actif = TRUE
);
-- FKs logiques validées par appels REST au moment de l'affectation
```

### Tâches

| # | Tâche | Détail | Critère validation |
|---|---|---|---|
| T1 | Migration Alembic incident_db | Créer table `agent_parcelle_assignments` avec contrainte UNIQUE partielle | `alembic upgrade head` → table créée |
| T2 | `POST /assignments/` dans incident-service | JWT superviseur requis. Validations : (1) agent.direction_regionale_id == superviseur_dir_secondaire.region_id (appel REST MS-1), (2) parcelle.forest.direction_secondaire_id == superviseur.direction_secondaire_id (appel REST MS-1). INSERT avec actif=true, désactive ancien si existant | Affectation valide → 201. Violation → 400 explicite |
| T3 | `GET /assignments/available-agents` | Superviseur → agents WHERE direction_regionale_id = sa_region AND pas d'assignment actif | Liste agents disponibles pour affectation |
| T4 | `GET /assignments/my-team` | Superviseur → agents de sa direction_secondaire avec parcelle assignée + forest_name | Liste équipe complète |
| T5 | `GET /assignments/agent/{id}` | Retourne `{parcelle_id, forest_id, dir_secondaire_id}` — utilisé par incident-service pour rattachement GPS | Réponse correcte |
| T6 | `team_assignment_screen.dart` Flutter Web | Carte flutter_map : polygones parcelles de sa direction. Panel gauche : liste agents disponibles. Tap parcelle → bottom sheet avec dropdown agents → confirmer → POST /assignments/ | Affectation visible sur carte, confirmée en DB |

---

## M3 — INCIDENT SERVICE + APP MOBILE AGENT
**Période :** 6–13 avril | **Durée :** 8 jours | **Port :** 8002 | **DB :** incident_db
**Exit condition :** Agent connecté mobile signale un incident avec photo+GPS → parcelle et forêt détectées automatiquement via ST_Contains → incident créé en incident_db → event PUBLISH sur Redis → `GET /incidents/` le retourne avec tous les champs.

### DB incident_db (tables principales)

```sql
incidents(id, agent_id, parcelle_id, forest_id, dir_secondaire_id,
          type_incident, description, latitude, longitude,
          priorite VARCHAR,   -- CRITIQUE | HAUTE | NORMALE
          statut VARCHAR,     -- en_attente | en_cours | traite | rejete
          note_superviseur INTEGER NULL,  -- 1-5
          commentaire_superviseur TEXT NULL,
          created_at, updated_at)

incident_photos(id, incident_id, photo_url, uploaded_at)
incident_comments(id, incident_id, author_id, author_role, content, created_at)
agent_parcelle_assignments(...)  -- défini en M2
```

### Règle priorité automatique

| Type incident | Priorité | Déclenche Telegram |
|---|---|---|
| feu | CRITIQUE | ✅ |
| refuge_suspect, terrorisme | CRITIQUE | ✅ |
| trafic, contrebande | CRITIQUE | ✅ |
| coupe_illegale | HAUTE | ❌ |
| depot_dechets | NORMALE | ❌ |
| maladie_vegetale | NORMALE | ❌ |

### Endpoint dans MS-1 (nouveau, interne)

```
GET /geo/parcelle-at?lat=X&lng=Y
→ SELECT p.id, p.forest_id, f.direction_secondaire_id
  FROM parcelles p JOIN forests f ON p.forest_id = f.id
  WHERE ST_Contains(p.geom, ST_SetSRID(ST_MakePoint(lng, lat), 4326))
  LIMIT 1
→ {parcelle_id, forest_id, dir_secondaire_id} | 404 si hors zone
```

### Tâches backend

| # | Tâche | Détail | Critère validation |
|---|---|---|---|
| T1 | Setup incident-service | FastAPI + SQLAlchemy + GeoAlchemy2 + Alembic + redis + pydantic-settings | :8002 /docs accessible |
| T2 | Endpoint MS-1 `/geo/parcelle-at` | ST_Contains PostGIS, header interne `X-Internal-Key` pour sécuriser | Coordonnées dans parcelle → retourne IDs corrects |
| T3 | `POST /incidents/` multipart | Reçoit `{lat, lng, type, description}` + fichier photo. Appel `/geo/parcelle-at` → résout parcelle_id+forest_id. Calcul priorité. INSERT incident + photo. PUBLISH `incidents.new` | Incident en DB avec tous les champs auto-remplis |
| T4 | Upload photo | Stockage `/media/incidents/{uuid}.ext`. URL publique retournée. Validation type (jpg/png/webp) + taille max 10MB | Photo accessible via URL |
| T5 | Redis PUBLISH | `PUBLISH incidents.new '{"incident_id":X,"agent_id":Y,"forest_id":Z,"dir_secondaire_id":W,"priorite":"CRITIQUE","type":"feu"}'` | `redis-cli SUBSCRIBE incidents.new` reçoit le message |
| T6 | `GET /incidents/` | Filtres : `dir_secondaire_id, forest_id, agent_id, statut, type, priorite, date_debut, date_fin`. RBAC auto : superviseur filtre sur sa direction_secondaire_id (depuis JWT) | Liste filtrée et scopée correctement |
| T7 | `PATCH /incidents/{id}/status` | Superviseur seulement. Vérifie `incident.dir_secondaire_id == jwt.direction_secondaire_id`. Body : `{statut, commentaire, note_superviseur}`. INSERT comment si fourni | Statut mis à jour, hors scope → 403 |
| T8 | `GET /incidents/my` | Agent → ses incidents triés date DESC | Historique correct |
| T9 | `GET /incidents/{id}` | Détail complet + photo_url + commentaires | Toutes les données présentes |

### Tâches Flutter Mobile

| # | Écran | Fonctionnalité | Critère |
|---|---|---|---|
| T10 | `incident_report_screen.dart` | `image_picker` (caméra/galerie) + dropdown type + description + `geolocator` GPS auto + bouton Signaler + loading indicator | Incident créé, photo visible via URL |
| T11 | `my_incidents_screen.dart` | Liste incidents agent, badge statut coloré (rouge=en_attente, orange=en_cours, vert=traité, gris=rejeté) | Historique correct |
| T12 | `incident_detail_screen.dart` | Photo plein écran + mini-carte flutter_map pin GPS + détails + commentaire superviseur si présent | Détail complet lisible |

---

## M4 — DASHBOARD SUPERVISEUR FLUTTER WEB
**Période :** 14–20 avril | **Durée :** 7 jours
**Exit condition :** Superviseur voit sur carte UNIQUEMENT les incidents dans les forêts de SA direction_secondaire. Markers mis à jour toutes les 15s. Validation d'un incident → statut change en DB → marker change de couleur en < 15s.

### Tâches

| # | Écran | Fonctionnalité | Critère |
|---|---|---|---|
| T1 | `supervisor_map_screen.dart` | flutter_map centré sur la région. Polygones forêts de sa direction (GeoJSON MS-1) en vert translucide. Markers incidents : rouge=CRITIQUE, orange=HAUTE, vert=NORMALE | Carte avec forêts bornées et incidents |
| T2 | Polling temps réel | `Timer.periodic(15s)` → `GET /incidents/?dir_secondaire_id={id}&statut=en_attente` → refresh markers | Nouvel incident visible en < 15s |
| T3 | Popup incident | Tap marker → BottomSheet : photo thumbnail, type, agent, heure, priorité, bouton "Valider" | Info rapide sans quitter la carte |
| T4 | `incident_detail_web_screen.dart` | Photo plein écran + métadonnées + mini-carte + formulaire validation (statut + note ★ + commentaire) + bouton Soumettre | Validation complète en un écran |
| T5 | Après validation | PATCH → SnackBar succès → refresh carte → marker change couleur/disparaît | Feedback immédiat |
| T6 | `incidents_list_screen.dart` | Vue liste alternative. Filtres : statut, type, forêt, agent, période. Export futur | Gestion liste |
| T7 | `team_assignment_screen.dart` | Carte parcelles de sa direction + panel agents disponibles + affectation (voir M2 T6) | Affectation opérationnelle |
| T8 | Navigation web | Drawer : Carte / Incidents / Mon Équipe / Analytics (placeholder) / Scoring (placeholder) | Navigation cohérente |
| T9 | `admin_panel_screen.dart` (admin only) | Réutilise écrans MS-1 existants (users, forêts, directions) intégrés dans le nouveau routing | Admin fonctionnel sans réécrire |

---

## M5 — NOTIFICATION TELEGRAM
**Période :** 21–22 avril | **Durée :** 2 jours | **Port :** 8003 | **DB :** notif_db
**Exit condition :** Incident type `feu` signalé sur mobile → message Telegram reçu par Protection Civile EN MOINS DE 10 SECONDES avec photo, type, forêt, agent, coordonnées GPS et lien Google Maps.

### Setup Telegram Bot (5 minutes)
```
Telegram → @BotFather → /newbot → nom → token
→ stocker dans .env : TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
```

### DB notif_db

```sql
notif_logs(id, incident_id, canal, statut, message_id_telegram, sent_at, retry_count)
notif_config(id, type_incident, priorite_min, canal, actif)
```

### Tâches

| # | Tâche | Détail | Critère |
|---|---|---|---|
| T1 | Setup notification-service | `pip install python-telegram-bot redis fastapi` | :8003 démarre |
| T2 | Redis SUBSCRIBE | `asyncio` task au startup → `subscribe('incidents.new', handle_incident)` | Message reçu et callback déclenché |
| T3 | Filtre criticité | `if payload['priorite'] == 'CRITIQUE' and notif_config.actif` → déclencher Telegram | Seuls incidents CRITIQUES → Telegram |
| T4 | Enrichissement | `GET /incidents/{id}` → incident-service. `GET /users/{agent_id}` → user-forest-service | Message complet avec noms |
| T5 | Message Telegram | `🚨 ALERTE CRITIQUE\n🔥 {type}\n🌲 Forêt: {forest_name}\n👤 Agent: {agent_name}\n📍 Maps: https://maps.google.com/?q={lat},{lng}` + photo en pièce jointe | Message lisible avec photo |
| T6 | Retry | 3 tentatives avec backoff 5s→15s→30s. Statut `failed` en notif_logs si échec total | Résilience réseau |
| T7 | Test chronomètre | Signaler feu sur mobile → mesurer délai Telegram. Documenter le délai pour la soutenance | < 10s mesuré et reproductible |

---

## M6 — SCORING AGENTS
**Période :** 23–26 avril | **Durée :** 4 jours | **Port :** 8004 | **DB :** scoring_db
**Exit condition :** Après validation d'un incident par le superviseur → score de l'agent recalculé en < 2s → agent voit son badge mis à jour → superviseur voit uniquement les scores de SA direction secondaire → admin voit tous.

### Formule

```
Score_auto  = 100 × (incidents_traités_30j / total_signalés_30j)   → poids 60%
Score_eval  = 100 × (moyenne(note_superviseur) / 5)                → poids 40%
Score_global = 0.6 × Score_auto + 0.4 × Score_eval
```

### Badges

| Badge | Seuil | Color Flutter |
|---|---|---|
| 🥇 Or | ≥ 90 | Colors.amber |
| 🥈 Argent | 75–89 | Colors.grey.shade400 |
| 🥉 Bronze | 60–74 | Colors.brown.shade300 |
| ⬆️ À améliorer | 40–59 | Colors.orange |
| 📚 Formation requise | < 40 | Colors.red |

### DB scoring_db

```sql
agent_scores(id, agent_id, score_auto, score_eval, score_global, badge,
             periode_debut, periode_fin, calculated_at)
score_history(id, agent_id, score_global, badge, recorded_at)
```

### Tâches

| # | Tâche | Détail | Critère |
|---|---|---|---|
| T1 | Setup scoring-service | FastAPI + pandas + redis + SQLAlchemy | :8004 démarre |
| T2 | Redis SUBSCRIBE incidents.new | Callback `recalculate_agent_score(agent_id)` après chaque validation | Score déclenché par event |
| T3 | `calculate_score(agent_id)` | `GET /incidents/?agent_id={id}&days=30` → incident-service → pandas groupby → Score_auto. Moyenne `note_superviseur` non-NULL → Score_eval. Score_global. Badge auto. | Calcul correct vérifié sur données test |
| T4 | Cache Redis | `SET score:{agent_id} {json} EX 300` après calcul | Lecture Redis < 1ms |
| T5 | `GET /scoring/agent/{id}` | RBAC : agent → son score seulement (jwt.user_id == id). Superviseur → agents de sa `direction_secondaire_id`. Admin → tous. Retourne `{score_global, score_auto, score_eval, badge, history_7j}` | Visibilité correcte selon rôle |
| T6 | `GET /scoring/ranking` | Superviseur → agents de SA direction_secondaire triés score DESC. Admin → tous. | Classement scopé par direction |
| T7 | `agent_score_screen.dart` | `CircularProgressIndicator` animé score global. Barres Score_auto + Score_eval. Badge icône + couleur. Sparkline 7j (fl_chart) | Écran score visuel et lisible |
| T8 | `supervisor_ranking_screen.dart` | Podium top 3. Liste complète équipe avec badge inline. | Classement équipe |

---

## M7 — ANALYTICS + HEATMAP
**Période :** 27–30 avril | **Durée :** 4 jours | **Port :** 8005 | **DB :** analytics_db
**Exit condition :** Dashboard analytics affiche heatmap des zones à risque sur la carte forêts du superviseur. Graphique temporel incidents/jour. Camembert types. KPIs. PDF générable. APPLICATION MVP COMPLÈTE LE 30 AVRIL.

### Stratégie analytics
- analytics-service lit directement via SQLAlchemy les DBs sources (incident_db + forest_db + scoring_db) avec users read-only
- Pas d'appels REST inter-services pour les calculs → plus simple et plus rapide
- Résultats cachés Redis 5min

### Endpoints

| Endpoint | Params | Calcul | Cache |
|---|---|---|---|
| `GET /analytics/heatmap` | `dir_secondaire_id, days=30` | DBSCAN clustering (eps=0.01, min_samples=3) sur (lat,lng) incidents → clusters {center_lat, center_lng, count, radius} | 5 min |
| `GET /analytics/temporal` | `dir_secondaire_id, days=30` | pandas resample('D').count() → [{date, count}] | 5 min |
| `GET /analytics/by-type` | `dir_secondaire_id` | GROUP BY type_incident → [{type, count, pourcentage}] | 5 min |
| `GET /analytics/by-forest` | `dir_secondaire_id` | Stats par forêt : nb incidents, taux validation, agent le + actif | 5 min |
| `GET /analytics/kpis` | `dir_secondaire_id` | Incidents actifs, traités ce mois, taux validation, nb Telegram envoyés | 2 min |
| `POST /analytics/report` | `{dir_secondaire_id, days}` | BackgroundTask → PDF ReportLab (matplotlib PNGs embarqués) → retourne {task_id} | — |
| `GET /analytics/report/{task_id}` | — | Retourne {url} si PDF prêt, {status:'pending'} sinon | — |

### Tâches

| # | Tâche | Détail | Critère |
|---|---|---|---|
| T1 | Setup analytics-service | `pip install pandas numpy scikit-learn matplotlib reportlab fastapi redis` | :8005 démarre |
| T2 | Heatmap DBSCAN (priorité #1) | `from sklearn.cluster import DBSCAN`. Query incidents lat/lng. DBSCAN → labels. Calculer centroïdes + count par cluster → JSON | Clusters retournés, testés sur données réelles |
| T3 | Flutter heatmap sur carte | `supervisor_map_screen.dart` enrichi : `CircleLayer` flutter_map. Cercles rouges semi-transparents, rayon proportionnel au `count`. Opacité = densité | Zones rouges visibles sur carte forêts |
| T4 | Graphique temporel | pandas resample. fl_chart `LineChart` dans Flutter. Sélecteur période 7j/30j/90j | Graphique interactif |
| T5 | Camembert types | `PieChart` fl_chart. Couleurs par type incident | Répartition lisible |
| T6 | Dashboard KPIs | 4 cartes colorées : actifs (rouge), traités (vert), taux validation (bleu), alertes Telegram (orange) | KPIs corrects |
| T7 | Rapport PDF | Couverture + KPIs tableau + graphique temporel PNG + carte heatmap PNG (matplotlib folium-like) + classement agents. ReportLab | PDF téléchargeable complet |
| T8 | `analytics_screen.dart` Flutter Web | Onglets : Heatmap / Temporel / Types / Forêts / PDF. Filtres : direction, période | Dashboard complet |
| T9 | Test démo 30 avril | Scénario 15min complet. Vérifier tous les flux. Corriger bugs UX | APPLICATION DÉMO-READY |

---

## M8 — API GATEWAY NGINX (Phase 2)
**Période :** 1–3 mai | **Durée :** 3 jours
**Exit condition :** `curl http://localhost/api/auth/login` → 200. `curl http://localhost:8001/auth/login` → connexion refusée (port non exposé dans docker-compose).

### nginx.conf (structure)

```nginx
upstream auth_service      { server auth-service:8001; }
upstream incident_service  { server incident-service:8002; }
upstream notif_service     { server notification-service:8003; }
upstream scoring_service   { server scoring-service:8004; }
upstream analytics_service { server analytics-service:8005; }
upstream forest_service    { server user-forest-service:8000; }

server {
  listen 80;
  location /api/auth/      { proxy_pass http://auth_service/; }
  location /api/forests/   { proxy_pass http://forest_service/; }
  location /api/incidents/ { proxy_pass http://incident_service/; }
  location /api/notify/    { proxy_pass http://notif_service/; }
  location /api/scoring/   { proxy_pass http://scoring_service/; }
  location /api/analytics/ { proxy_pass http://analytics_service/; }
  
  # Rate limiting
  limit_req_zone $binary_remote_addr zone=login:10m rate=10r/m;
  location /api/auth/login { limit_req zone=login burst=5; proxy_pass http://auth_service/auth/login; }
}
```

### Tâches

| # | Tâche | Critère |
|---|---|---|
| T1 | nginx.conf complet | Tous les /api/* routés correctement |
| T2 | docker-compose : ports internes seulement | Services FastAPI sans `ports:` exposés (seulement Nginx sur 80) |
| T3 | Rate limiting login | Brute force bloqué après 10 req/min |
| T4 | CORS centralisé Nginx | Supprimer CORS FastAPI de chaque service |
| T5 | Mettre à jour Flutter | `baseUrl = 'http://localhost:80'` uniquement |
| T6 | Dockerfiles tous services | `python:3.11-slim` + `requirements.txt` + `CMD uvicorn` | `docker-compose up --build` → tout fonctionne |

---

## PHASE 2 — MAI : RAPPORT + SOUTENANCE

| Semaine | Dates | Focus | Tâches |
|---|---|---|---|
| Sem. 6 | 1–7 mai | M8 Nginx + Rapport ch.1-3 | Dockerisation complète. Rédiger : Introduction, État de l'art, Architecture microservices |
| Sem. 7 | 8–14 mai | Rapport ch.4-5 + Tests | Réalisation MS-1, Auth, Incidents, Notifications. Tests intégration. Screenshots annotés |
| Sem. 8 | 15–20 mai | Rapport ch.6 + Slides | Scoring, Analytics, Conclusion. 20 slides soutenance. 3× répétition démo chronomètrée |

---

## SCÉNARIO DÉMO — 15 MINUTES CHRONO

| Min | Acteur | Action | Ce que le jury voit |
|---|---|---|---|
| 0:00 | Admin | Login Flutter Web | JWT routing automatique selon rôle |
| 1:00 | Admin | Crée Forêt Kroumirie + polygone carte | MS-1 PostGIS, carte interactive |
| 2:30 | Admin | Crée agents Omar + Sami dans Direction Régionale Nord | CRUD, rôles |
| 3:30 | Superviseur Ali | Login → carte forêts de SA direction secondaire | Dashboard scopé par direction |
| 4:30 | Superviseur Ali | Affecte Omar→Parcelle A, Sami→Parcelle B sur carte | Contrainte métier respectée |
| 5:30 | Agent Omar | (Mobile) Login → signale FEU photo+GPS | App mobile Flutter |
| 6:30 | Système | **Telegram reçu < 10s** | 🚨 Moment fort de la soutenance |
| 7:30 | Superviseur Ali | Voit marker rouge sur carte → valide → note 5★ | Temps réel + validation |
| 9:00 | Système | Score Omar → badge Or 92/100 | Gamification scoring |
| 10:00 | Superviseur Ali | Analytics → heatmap zones rouges | Analyse intelligente |
| 12:00 | Superviseur Ali | Génère rapport PDF → télécharge | PDF automatique |
| 13:30 | Admin | Montre /docs Swagger de chaque service | Architecture microservices |
| 15:00 | — | Questions jury | Application complète et cohérente |

---

## RÈGLES SI RETARD

**Ordre de coupe — toujours livrer dans cet ordre :**

1. ✅ M0 + M1 — Auth JWT (NON négociable)
2. ✅ M2 — Affectation parcelle (NON négociable)
3. ✅ M3 — Signalement mobile (cœur fonctionnel)
4. ✅ M4 — Dashboard superviseur (sans ça le projet n'a pas de valeur)
5. 🟠 M5 — Telegram (innovation forte, garder si possible)
6. 🟠 M6 — Scoring (différenciateur PFE)
7. 🟡 M7 — Analytics/Heatmap (impressive mais coupable si nécessaire)
8. ⏳ M8 — Nginx (Phase 2, non bloquant pour démo)

---

## PACKAGES PAR SERVICE

```
# Tous les services FastAPI
fastapi uvicorn[standard] pydantic-settings sqlalchemy alembic redis

# auth-service
python-jose[cryptography] passlib[bcrypt]

# incident-service  
geoalchemy2 shapely python-multipart

# notification-service
python-telegram-bot

# scoring-service
pandas numpy

# analytics-service
pandas numpy scikit-learn matplotlib reportlab

# Flutter (à ajouter au pubspec.yaml existant)
image_picker: ^1.0.4
geolocator: ^11.0.0
shared_preferences: ^2.2.2
fl_chart: ^0.68.0
```
