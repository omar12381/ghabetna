# GHABETNA — M2 : MS-1 SÉCURISÉ + AFFECTATION PARCELLE (FINAL)
> Milestone : M2 | Statut : 🔄 EN COURS
> Révision finale : 05 avril 2026
> Décisions actées : affectation = tâche admin | table minimale Proposition B | forest_db

---

## DÉCISIONS ARCHITECTURALES FINALES

| Décision | Choix retenu | Raison |
|---|---|---|
| Qui affecte | Admin uniquement | Décision encadreur |
| Qui voit | Superviseur : lecture seule, sa DS uniquement | Cohérence hiérarchique |
| Où vit la table | `forest_db` (user-forest-service) | Vraies FK PostgreSQL, transactions atomiques |
| Schéma table | Proposition B — minimale | Pas de redondance, source de vérité unique |
| Contrainte géo | agent.direction_regionale_id == parcelle.forest.direction_secondaire.region_id | Cohérence géographique obligatoire |
| Champs redondants | Supprimés (forest_id, dir_secondaire_id, dir_regionale_id) | Résolus par JOIN à la lecture |

---

## RÈGLES MÉTIER FINALES

```
Admin
 └─ Affecte : agent → parcelle (POST /affectations/)
     Validation : agent.direction_regionale_id == parcelle.forest.direction_secondaire.region_id
     → sinon HTTP 403 "Incohérence géographique"
     Un agent = une seule affectation active (UNIQUE agent_id WHERE actif=TRUE)
     Plusieurs agents peuvent partager une même parcelle
     Mise à jour atomique : users.direction_secondaire_id dans la même transaction

Superviseur (direction_secondaire_id = DS.id, DS.region_id = DR.id)
 └─ Voit les agents (lecture seule) :
     (A) agents WHERE direction_secondaire_id = DS.id      ← équipe directe
     (B) agents WHERE direction_regionale_id  = DR.id
         AND pas d'affectation active                      ← libres de sa région
 └─ Voit les affectations de SA direction secondaire uniquement (lecture seule)
 └─ Ne peut PAS créer / modifier / supprimer une affectation
```

---

## DB SCHEMA FINAL — `forest_db`

### Table `agent_parcelle_assignments` — Proposition B (minimale)

```sql
-- forest_db — même DB que user-forest-service
-- Vraies FK PostgreSQL ✅ — pas de redondance ✅

CREATE TABLE agent_parcelle_assignments (
  id          SERIAL PRIMARY KEY,
  agent_id    INTEGER NOT NULL REFERENCES users(id),
  parcelle_id INTEGER NOT NULL REFERENCES parcelles(id),
  assigned_by INTEGER NOT NULL REFERENCES users(id),  -- admin_id
  assigned_at TIMESTAMP NOT NULL DEFAULT NOW(),
  actif       BOOLEAN NOT NULL DEFAULT TRUE
);

-- Un agent = une seule affectation active
CREATE UNIQUE INDEX uq_agent_assignment_actif
  ON agent_parcelle_assignments (agent_id)
  WHERE actif = TRUE;

CREATE INDEX ix_apa_parcelle  ON agent_parcelle_assignments (parcelle_id);
CREATE INDEX ix_apa_assigned  ON agent_parcelle_assignments (assigned_by);
```

### Pourquoi on ne stocke pas forest_id, dir_secondaire_id, dir_regionale_id

Ces champs sont **redondants** — ils sont déjà accessibles via JOIN :
```sql
-- Tout est résolvable depuis parcelle_id uniquement :
SELECT apa.*,
       p.name          AS parcelle_name,
       p.forest_id,
       f.name          AS forest_name,
       f.direction_secondaire_id,
       ds.nom          AS dir_secondaire_nom,
       ds.region_id    AS dir_regionale_id,
       dr.nom          AS dir_regionale_nom
FROM agent_parcelle_assignments apa
JOIN parcelles           p  ON p.id  = apa.parcelle_id
JOIN forests             f  ON f.id  = p.forest_id
JOIN direction_secondaire ds ON ds.id = f.direction_secondaire_id
JOIN direction_regionale  dr ON dr.id = ds.region_id
WHERE apa.actif = TRUE
```

Les stocker en plus créerait un risque d'incohérence si une forêt change de direction.

### Vue d'ensemble `forest_db` après M2

```
direction_regionale
  └── direction_secondaire
        └── forests
              └── parcelles
                    └── agent_parcelle_assignments ← NOUVEAU
                          ├── agent_id    → users
                          ├── parcelle_id → parcelles
                          └── assigned_by → users (admin)

users
  ├── direction_regionale_id  (agent : DR d'appartenance)
  ├── direction_secondaire_id (superviseur : DS / agent après affectation)
  └── role_id → roles
```

---

## NOTE ARCHITECTURE M3 — Cas agent hors parcelle

> Réflexion validée lors de la conception M2.

**Cas :** Agent affecté à parcelle A signale un incident dans parcelle B (il passe par B pour rejoindre A).

**Résolution naturelle :** `incident-service` utilise `ST_Contains(parcelle.geom, GPS)` pour résoudre automatiquement la parcelle de l'incident. Si A et B sont proches géographiquement, elles appartiennent très probablement à la même forêt → même direction secondaire → même superviseur. L'architecture gère ce cas sans code spécial.

**Règle M3 :**
- `incident.parcelle_id` = parcelle résolue par GPS (pas forcément la parcelle de l'agent)
- `incident.agent_id` = agent qui signale
- Score de l'agent : compte normalement — l'agent a bien fait son travail

---

## ARCHITECTURE M2

```
[App Admin Flutter]
  └──→ POST /affectations/        ──→ [user-forest-service :8000] ──→ [forest_db]
       DELETE /affectations/{id}       (vraies FK, transactions atomiques)
       GET /affectations/*

[App Superviseur Flutter]
  ├──→ GET /affectations/         ──→ [user-forest-service :8000] ──→ [forest_db]
  ├──→ GET /users/agents/*        ──→ [user-forest-service :8000]
  ├──→ GET /forests/ /parcelles/  ──→ [user-forest-service :8000]
  └──→ POST /auth/login           ──→ [auth-service :8001]        ──→ [Redis]

[incident-service :8002]          ──→ [incident_db]
  └── Structure conservée, endpoints affectation supprimés, prêt pour M3
```

---

## TÂCHES & SOUS-TÂCHES

---

### ✅ T1 — SETUP INCIDENT-SERVICE
> Déjà implémenté et testé. Garder tel quel.

---

### ✅ T2 — TABLE `agent_parcelle_assignments` (incident_db)
> Implémentée dans incident_db. À MIGRER vers forest_db (voir NT1).

---

### ✅ T3 — CLIENT HTTP INTER-SERVICES (incident-service)
> Implémenté. À SUPPRIMER de incident-service (voir NT4).

---

### ✅ T4 — JWT GUARD (incident-service)
> Implémenté. Garder pour M3.

---

### ✅ T5 — ENDPOINTS AFFECTATION (incident-service)
> Implémentés. À SUPPRIMER de incident-service + RÉÉCRIRE dans user-forest-service (voir NT2).

---

### ✅ T6 — ENDPOINTS AGENTS (user-forest-service)
> Implémentés avec appel HTTP vers incident-service. À ADAPTER (voir NT3).

---

### [X] NT1 — MIGRATION TABLE VERS `forest_db`
**Composant :** Backend — user-forest-service
**Priorité :** 🔴 Critique
**Fichiers :** `app/models.py`, `app/database.py`, `app/schemas.py`

#### Sous-tâches

**NT1.1 — Modèle SQLAlchemy — Proposition B (minimale)**
```python
# user-forest-service/app/models.py — ajouter
from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func

class AgentParcelleAssignment(Base):
    __tablename__ = "agent_parcelle_assignments"

    id          = Column(Integer, primary_key=True, index=True)
    agent_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    parcelle_id = Column(Integer, ForeignKey("parcelles.id"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    actif       = Column(Boolean, nullable=False, default=True)
    # Pas de forest_id, dir_secondaire_id, dir_regionale_id
    # → résolus par JOIN à la lecture
```

**NT1.2 — Migrations artisanales**
```python
# user-forest-service/app/database.py — ajouter dans _migrations
_migrations += [
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_assignment_actif
    ON agent_parcelle_assignments (agent_id)
    WHERE actif = TRUE
    """,
    "CREATE INDEX IF NOT EXISTS ix_apa_parcelle ON agent_parcelle_assignments (parcelle_id)",
    "CREATE INDEX IF NOT EXISTS ix_apa_assigned  ON agent_parcelle_assignments (assigned_by)",
]
```

**NT1.3 — Schémas Pydantic**
```python
# user-forest-service/app/schemas.py — ajouter

class AssignmentCreate(BaseModel):
    agent_id: int
    parcelle_id: int

class AssignmentRead(BaseModel):
    id: int
    agent_id: int
    parcelle_id: int
    assigned_by: int
    assigned_at: datetime
    actif: bool
    # Enrichis via JOIN direct (même DB)
    agent_username: str
    parcelle_name: str
    forest_id: int
    forest_name: str
    dir_secondaire_id: int
    dir_regionale_id: int
    model_config = {"from_attributes": True}

class AssignmentMinimal(BaseModel):
    parcelle_id: int | None = None
    parcelle_name: str | None = None
    forest_id: int | None = None
    forest_name: str | None = None
    dir_secondaire_id: int | None = None
```

**NT1.4 — Supprimer la table de `incident_db`**
- Supprimer `AgentParcelleAssignment` de `incident-service/app/models.py`
- Vider `_migrations` dans `incident-service/app/database.py`
- Si données de test dans `incident_db` → `DROP TABLE agent_parcelle_assignments` manuellement

---

### [X] NT2 — ENDPOINTS AFFECTATION DANS USER-FOREST-SERVICE
**Composant :** Backend — user-forest-service
**Priorité :** 🔴 Critique
**Fichier :** `app/routers/affectations.py` (nouveau fichier)

#### Sous-tâches

**NT2.1 — `POST /affectations/`** — Admin affecte un agent à une parcelle

```python
# Guard : require_roles("admin")
#
# Flux (tout en SQL local — pas d'appel HTTP) :
#
# 1. Charger agent :
#    SELECT u.*, r.name as role_name FROM users u JOIN roles r ON r.id = u.role_id
#    WHERE u.id = agent_id
#    → u.actif == True          → sinon HTTP 403 "Agent inactif"
#    → r.name == "agent_forestier" → sinon HTTP 403 "Utilisateur n'est pas un agent"
#
# 2. Charger parcelle → forêt → direction_secondaire → direction_regionale :
#    SELECT p.*, f.id as forest_id, f.direction_secondaire_id,
#           ds.region_id as dir_regionale_id
#    FROM parcelles p
#    JOIN forests f ON f.id = p.forest_id
#    JOIN direction_secondaire ds ON ds.id = f.direction_secondaire_id
#    WHERE p.id = parcelle_id
#    → sinon HTTP 404 "Parcelle introuvable"
#
# 3. Validation géographique (contrainte obligatoire même pour admin) :
#    agent.direction_regionale_id == parcelle.dir_regionale_id
#    → sinon HTTP 403 "Incohérence géographique : agent et parcelle dans des régions différentes"
#
# 4. Transaction DB (atomique — même DB ✅) :
#    a. UPDATE agent_parcelle_assignments
#       SET actif = False
#       WHERE agent_id = :agent_id AND actif = True
#
#    b. INSERT agent_parcelle_assignments
#       (agent_id, parcelle_id, assigned_by=admin_id, actif=True)
#
#    c. Si agent.direction_secondaire_id IS NULL :
#       UPDATE users
#       SET direction_secondaire_id = parcelle.dir_secondaire_id
#       WHERE id = agent_id
#       (même transaction — atomique ✅)
#
# 5. Retourner AssignmentRead enrichi (JOIN SQL)
```

**NT2.2 — `DELETE /affectations/{agent_id}`** — Admin désaffecte un agent

```python
# Guard : require_roles("admin")
# 1. SELECT WHERE agent_id=? AND actif=True → sinon HTTP 404 "Agent non affecté"
# 2. UPDATE SET actif=False
# 3. HTTP 204
```

**NT2.3 — `GET /affectations/`** — Liste des affectations

```python
# Guard : require_roles("admin", "superviseur")
# Filtre selon rôle :
#   admin       → toutes les affectations actives
#                 + filtre optionnel ?dir_secondaire_id=X
#   superviseur → WHERE ds.id = current_user.direction_secondaire_id uniquement

# Query avec JOIN complet (tout dans forest_db) :
SELECT apa.id, apa.agent_id, apa.parcelle_id, apa.assigned_by, apa.assigned_at, apa.actif,
       u.username      AS agent_username,
       p.name          AS parcelle_name,
       f.id            AS forest_id,
       f.name          AS forest_name,
       f.direction_secondaire_id,
       ds.region_id    AS dir_regionale_id
FROM agent_parcelle_assignments apa
JOIN users               u  ON u.id  = apa.agent_id
JOIN parcelles           p  ON p.id  = apa.parcelle_id
JOIN forests             f  ON f.id  = p.forest_id
JOIN direction_secondaire ds ON ds.id = f.direction_secondaire_id
WHERE apa.actif = True
  AND ds.id = :ds_id   -- uniquement si superviseur
ORDER BY apa.assigned_at DESC
```

**NT2.4 — `GET /affectations/agent/{agent_id}`** — Affectation courante d'un agent

```python
# Guard : require_roles("admin", "superviseur")
# Même JOIN que NT2.3 + WHERE apa.agent_id = ? AND apa.actif = True
# Si aucune → retourner AssignmentMinimal avec tous les champs null
```

**NT2.5 — `GET /affectations/parcelle/{parcelle_id}`** — Agents d'une parcelle

```python
# Guard : require_roles("admin", "superviseur")
# SELECT u.id, u.username, u.email, u.telephone
# FROM agent_parcelle_assignments apa JOIN users u ON u.id = apa.agent_id
# WHERE apa.parcelle_id = ? AND apa.actif = True
```

**NT2.6 — Enregistrer dans `main.py`**
```python
from app.routers import affectations
app.include_router(affectations.router, prefix="/affectations", tags=["Affectations"])
```

---

### NT3 — ADAPTER `GET /users/agents/mon-equipe`
**Composant :** Backend — user-forest-service
**Priorité :** 🔴 Critique
**Fichier :** `app/routers/users.py`

#### Sous-tâches

**NT3.1 — Remplacer l'appel HTTP par un JOIN direct**

L'ancienne version appelait `incident-service` pour récupérer les IDs affectés.
Maintenant `agent_parcelle_assignments` est dans `forest_db` → JOIN direct :

```sql
SELECT u.id, u.username, u.email, u.telephone, u.actif,
       u.direction_secondaire_id, u.direction_regionale_id,
       apa.parcelle_id,
       p.name  AS parcelle_name,
       f.id    AS forest_id,
       f.name  AS forest_name
FROM users u
JOIN roles r ON r.id = u.role_id AND r.name = 'agent_forestier'
LEFT JOIN agent_parcelle_assignments apa
       ON apa.agent_id = u.id AND apa.actif = TRUE
LEFT JOIN parcelles p ON p.id = apa.parcelle_id
LEFT JOIN forests   f ON f.id = p.forest_id
WHERE
  u.direction_secondaire_id = :ds_id       -- équipe directe
  OR (
    u.direction_regionale_id = :dr_id      -- libres de la région
    AND apa.agent_id IS NULL               -- non affectés (LEFT JOIN → NULL)
  )
ORDER BY u.direction_secondaire_id NULLS LAST, u.username
```

Champ `type` dans la réponse :
- `"equipe_directe"` si `u.direction_secondaire_id == ds_id`
- `"libre_region"` sinon

**NT3.2 — `GET /users/agents/disponibles`**
- Sous-ensemble de NT3.1 : uniquement `type == "libre_region"`

---

### NT4 — NETTOYAGE INCIDENT-SERVICE
**Composant :** Backend — incident-service
**Priorité :** 🔴 Critique

#### Sous-tâches

**NT4.1 — Vider `affectations.py`**
```python
# incident-service/app/routers/affectations.py
from fastapi import APIRouter

router = APIRouter()
# Endpoints affectation supprimés — migrés vers user-forest-service
# Fichier réutilisé en M3 pour les incidents
```

**NT4.2 — Vider `models.py`**
```python
# incident-service/app/models.py
from app.database import Base
# AgentParcelleAssignment supprimé — migré vers forest_db
# Modèle Incident ajouté en M3
```

**NT4.3 — Vider `_migrations` dans `database.py`**
```python
# incident-service/app/database.py
_migrations = []
# Index agent_parcelle_assignments supprimés — plus dans incident_db
```

**NT4.4 — Vider `http_client.py`**
```python
# incident-service/app/utils/http_client.py
# Fonctions get_user, get_parcelle, get_forest, patch_user supprimées
# Fichier conservé vide — sera réutilisé en M3 pour appels inter-services incidents
```

**NT4.5 — Désactiver le router affectations dans `main.py`**
```python
# Commenter jusqu'à M3
# app.include_router(affectations.router, prefix="/affectations", tags=["Affectations"])
```

---

### NT5 — AUTH SUPERVISEUR (auth-service)
**Composant :** Backend — auth-service
**Priorité :** 🔴 Critique

#### Sous-tâches

**NT5.1 — Ouvrir login aux superviseurs**
```python
# Avant
if user.role != "admin":
    raise HTTPException(403, "Accès admin uniquement")

# Après
if user.role not in ["admin", "superviseur"]:
    raise HTTPException(403, "Accès réservé aux administrateurs et superviseurs")
```

**NT5.2 — Enrichir `UserAuthRead` dans user-forest-service**
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

**NT5.3 — Injecter direction ids dans le JWT**
```python
payload = {
    "sub": str(user.id),
    "role": user.role,
    "direction_secondaire_id": user.direction_secondaire_id,
    "direction_regionale_id": user.direction_regionale_id,
    "type": "access",
    "exp": ...
}
```

**NT5.4 — Mettre à jour `CurrentUser` dans `jwt_guard.py` de user-forest-service**
```python
@dataclass
class CurrentUser:
    id: int
    role: str
    direction_secondaire_id: int | None
    direction_regionale_id: int | None
```

**NT5.5 — Fixes hardening M1**
- Supprimer `depends_on: db` dans auth-service du `docker-compose.yml`
- Créer `requirements-test.txt` séparé (retirer pytest de `requirements.txt`)
- Migrer `class Config` → `model_config = SettingsConfigDict(...)` dans `config.py`

---

### NT6 — ÉCRAN AFFECTATION DANS APP ADMIN (Flutter)
**Composant :** Flutter — app admin existante (`flutter/`)
**Priorité :** 🔴 Critique

#### Sous-tâches

**NT6.1 — `affectation_service.dart`** → `user-forest-service :8000`
```dart
class AffectationService {
  final _client = AuthenticatedClient();

  // Admin : écriture + lecture
  Future<AssignmentRead> affecter(int agentId, int parcelleId) async
    // POST /affectations/

  Future<void> desaffecter(int agentId) async
    // DELETE /affectations/{agent_id}

  Future<List<AssignmentRead>> getAffectations({int? dirSecondaireId}) async
    // GET /affectations/?dir_secondaire_id=X

  Future<AssignmentMinimal?> getAffectationAgent(int agentId) async
    // GET /affectations/agent/{agent_id}

  Future<List<AgentMinimal>> getAgentsParParcelle(int parcelleId) async
    // GET /affectations/parcelle/{parcelle_id}
}
```

**NT6.2 — Modèles Dart `assignment.dart`**
```dart
class AssignmentRead {
  final int id, agentId, parcelleId, assignedBy;
  final DateTime assignedAt;
  final bool actif;
  final String agentUsername, parcelleName, forestName;
  final int forestId, dirSecondaireId, dirRegionaleId;
  factory AssignmentRead.fromJson(Map<String, dynamic> json) { ... }
}

class AssignmentMinimal {
  final int? parcelleId, forestId, dirSecondaireId;
  final String? parcelleName, forestName;
  factory AssignmentMinimal.fromJson(Map<String, dynamic> json) { ... }
}
```

**NT6.3 — `assign_agent_screen.dart`**
```
Layout (deux panneaux) :

Panneau gauche — Formulaire d'affectation :
  Dropdown Direction Régionale  → filtre les agents disponibles
  Dropdown Direction Secondaire → filtre les forêts
  Dropdown Forêt                → charge les parcelles
  Dropdown Parcelle
  Liste agents disponibles (non affectés dans la DR)
  Bouton "Affecter" → POST /affectations/
  Gestion erreur 403 "Incohérence géographique" → SnackBar rouge

Panneau droit — Tableau affectations actives :
  Filtre par direction secondaire
  Colonnes : Agent | Parcelle | Forêt | Date affectation | Action
  Bouton "Désaffecter" par ligne → DELETE + confirmation dialog
```

**NT6.4 — Ajouter route dans `home_screen.dart` admin**
```dart
// Ajouter carte/bouton "Gestion Affectations" dans dashboard admin
// Route '/affectations' → AssignAgentScreen
```

---

### NT7 — APP FLUTTER SUPERVISEUR
**Composant :** Flutter — nouvelle app (`flutter_superviseur/`)
**Priorité :** 🟠 Haute

#### Sous-tâches

**NT7.1 — Setup**
```bash
flutter create flutter_superviseur --org com.ghabetna
```
```yaml
# pubspec.yaml
dependencies:
  http: ^1.2.2
  flutter_secure_storage: ^9.2.4
  flutter_map: ^7.0.2
  latlong2: ^0.9.1
  fl_chart: ^0.68.0
```

**NT7.2 — `api_config.dart`**
```dart
const String forestServiceBaseUrl = 'http://localhost:8000';
const String authBaseUrl          = 'http://localhost:8001';
// incident-service ajouté en M3
```

**NT7.3 — Utilitaires** : copier `token_storage.dart` + `http_client.dart` depuis app admin

**NT7.4 — `affectation_service.dart`** superviseur → lecture seule
```dart
// Pas de affecter() ni desaffecter()
Future<List<AssignmentRead>> getAffectations()
Future<AssignmentMinimal?> getAffectationAgent(int agentId)
Future<List<AgentMinimal>> getAgentsParParcelle(int parcelleId)
```

**NT7.5 — `agent_service.dart`**
```dart
Future<List<AgentWithStatus>> getMonEquipe()    // GET /users/agents/mon-equipe
Future<List<AgentWithStatus>> getDisponibles()  // GET /users/agents/disponibles
```

**NT7.6 — `forest_service.dart`** + **`parcelle_service.dart`**
```dart
Future<List<Forest>> getForets({int? dirSecondaireId})
Future<List<Parcelle>> getParcellesByForet(int foretId)
```

**NT7.7 — Modèles Dart**
```dart
class AgentWithStatus {
  final int id;
  final String username, email;
  final String? telephone;
  final bool actif;
  final int? directionSecondaireId;
  final AssignmentMinimal? affectation;  // null si libre
  final String type;  // "equipe_directe" | "libre_region"
}
```

**NT7.8 — Login Screen**
- Guard : `role == "superviseur"` uniquement après décodage JWT
- Erreurs HTTP : 401, 403, 429, 5xx

**NT7.9 — Home Screen / Dashboard**
```
NavigationRail (>800px) / BottomNav (<800px) :
  🏠 Tableau de bord   KPIs
  👥 Mon équipe        lecture seule
  🗺️  Carte             parcelles colorées
  📊 Statistiques      [placeholder M7]
  ⭐ Scoring            [placeholder M6]
  🔔 Incidents          [placeholder M3]

KPI Cards :
  Total agents équipe | Agents affectés | Agents libres | Incidents [--]
```

**NT7.10 — Agents Screen**
- Deux sections : "Mon équipe" (vert) / "Disponibles dans la région" (orange)
- Chip statut : affecté (📍 Parcelle X — Forêt Y) / non affecté
- **Pas de bouton Affecter** — lecture seule
- Bouton "Voir détails" → dialog avec infos affectation complètes
- Barre de recherche locale + Pull-to-refresh

**NT7.11 — Carte Parcelles Screen**
- `GET /forests/?direction_secondaire_id={ds_id}` → PolygonLayer forêts vert clair
- `GET /parcelles/by_forest/{id}` → PolygonLayer parcelles
  - Affectée ≥1 agent → vert foncé opaque
  - Libre → orange semi-transparent
- Tap parcelle → BottomSheet : infos + agents affectés (lecture seule)
- Légende + centrage bounding box

---

### NT8 — AJOUT FILTRE FORÊTS PAR DIRECTION SECONDAIRE
**Composant :** Backend — user-forest-service
**Priorité :** 🟡 Moyenne
**Fichier :** `app/routers/forests.py`

```python
# Ajouter paramètre optionnel sur GET /forests/
@router.get("/forests/")
def get_forests(direction_secondaire_id: int | None = Query(None), ...):
    query = db.query(Forest)
    if direction_secondaire_id:
        query = query.filter(Forest.direction_secondaire_id == direction_secondaire_id)
    return query.all()
```

---

## ORDRE D'EXÉCUTION RECOMMANDÉ

```
Jour 1 — Migration Backend :
  NT4  nettoyer incident-service (vider affectations, models, migrations)
  NT1  créer table + modèle + schémas dans user-forest-service (Proposition B)
  NT2  réécrire endpoints affectation dans user-forest-service

Jour 2 — Adapter Backend + Auth :
  NT3  adapter GET /users/agents/mon-equipe (JOIN direct, supprimer appel HTTP)
  NT5  auth superviseur + JWT enrichi + hardening M1
  NT8  filtre forêts par direction secondaire

Jour 3 — Flutter Admin :
  NT6  écran affectation + service + modèles dans app admin

Jour 4 — Flutter Superviseur :
  NT7  app superviseur complète

Jour 5 — Tests end-to-end :
  Admin affecte agent → parcelle → vérifier forest_db
  Contrainte géo : agent hors région → 403
  Superviseur voit son équipe + affectations (lecture seule)
  Superviseur ne peut pas POST /affectations/ → 403
  Carte superviseur : couleurs correctes
```

---

## ENDPOINTS M2 FINAUX

### user-forest-service (port 8000)

| Method | Route | Auth | Description |
|---|---|---|---|
| POST | /affectations/ | 🔒 admin | Affecter agent → parcelle |
| DELETE | /affectations/{agent_id} | 🔒 admin | Désaffecter un agent |
| GET | /affectations/ | 🔒 admin, superviseur | Admin: toutes. Superviseur: sa DS uniquement |
| GET | /affectations/agent/{agent_id} | 🔒 admin, superviseur | Affectation courante d'un agent |
| GET | /affectations/parcelle/{parcelle_id} | 🔒 admin, superviseur | Agents d'une parcelle |
| GET | /users/agents/mon-equipe | 🔒 superviseur | Équipe directe + libres région (JOIN direct) |
| GET | /users/agents/disponibles | 🔒 superviseur | Agents libres uniquement |
| GET | /forests/?direction_secondaire_id= | 🔒 JWT | Forêts filtrées par DS |

### auth-service (port 8001)

| Method | Route | Modification |
|---|---|---|
| POST | /auth/login | Accepte superviseur + JWT enrichi avec direction ids |

### incident-service (port 8002)

| Statut | Description |
|---|---|
| 🗑️ Supprimé | Endpoints /affectations/* |
| ✅ Conservé | Structure, jwt_guard, /health, incident_db |
| ⏳ M3 | Endpoints /incidents/*, table incidents |

---

## EXIT CONDITIONS M2

| Critère | Vérification |
|---|---|
| Table `agent_parcelle_assignments` dans `forest_db` avec vraies FK | `\d agent_parcelle_assignments` psql ✅ |
| Table minimale : seulement agent_id, parcelle_id, assigned_by, assigned_at, actif | Pas de forest_id ni dir_*_id ✅ |
| `incident-service` démarre proprement (nettoyé) | `GET /health` → 200 ✅ |
| Admin affecte agent → parcelle | POST /affectations/ → 200 ✅ |
| Validation géographique | Agent hors région → 403 ✅ |
| Mise à jour `direction_secondaire_id` atomique | Même transaction vérifiée ✅ |
| Admin désaffecte | DELETE → 204 ✅ |
| Superviseur login avec JWT direction ids | Token décodé correct ✅ |
| Superviseur voit équipe + libres (JOIN direct, pas HTTP) | 2 sections AgentsScreen ✅ |
| Superviseur voit affectations sa DS uniquement | GET /affectations/ scopé ✅ |
| Superviseur ne peut pas affecter | POST /affectations/ → 403 ✅ |
| Carte superviseur couleurs correctes | Vert/orange selon statut ✅ |

---

## NOTE SOUTENANCE — ARGUMENT ARCHITECTURAL

> À mentionner lors de la présentation :

**"Le choix de migrer `agent_parcelle_assignments` vers `forest_db` nous a permis d'éliminer 3 appels HTTP inter-services par requête d'affectation, de remplacer des FK logiques par de vraies contraintes PostgreSQL, et de rendre la mise à jour de `direction_secondaire_id` atomique dans la même transaction. C'est un exemple concret du compromis microservices : on a choisi la cohérence des données sur la séparation stricte des services quand les deux entités sont fonctionnellement liées."**

---

## KNOWN ISSUES

- ISSUE: Vérifier qu'il n'y a pas de données de test à conserver dans `incident_db.agent_parcelle_assignments` avant suppression
- ISSUE: `flutter_map` requiert `List<LatLng>` — conversion GeoJSON dans `parcelle.dart`
- ISSUE: Si superviseur sans `direction_secondaire_id` en DB → valider en `initState` + message explicite
- ISSUE: L'app admin existante doit utiliser `AuthenticatedClient` sur le nouvel écran affectation

## REFACTOR LATER

- REFACTOR: Package Flutter partagé `AuthenticatedClient` + `TokenStorage` (admin + superviseur) — Phase 2
- REFACTOR: Pagination `GET /users/agents/mon-equipe` si > 50 agents
- REFACTOR: Alembic pour les migrations — Phase 2
- REFACTOR: `incident-service/http_client.py` — réutiliser en M3 pour vérifier affectation agent lors d'un signalement d'incident
