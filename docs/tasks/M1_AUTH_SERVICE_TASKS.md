# GHABETNA — Milestone 1 : Auth Service
> Plan de tâches & sous-tâches — version définitive
> Étudiant : Omar Hellel | Entreprise : Smart For Green

| Champ | Valeur |
|---|---|
| Milestone | M1 — Auth Service |
| Milestone précédent | MS-1 (User & Forest Management) + M0 (Socle technique) |
| Statut | ⬜ À faire |
| Services impactés | auth-service (nouveau) + user-forest-service (sécurisation) |
| Ports | auth-service: 8001 \| user-forest-service: 8000 |
| Bases de données | auth_db (Redis) nouveau + forest_db (existant, lecture seule pour auth) |

---

## 0. Décisions architecturales figées

> Ces décisions sont FIGÉES pour ce milestone et tous les suivants. Ne pas dévier.

| Décision | Choix | Raison |
|---|---|---|
| Architecture | auth-service séparé — nouveau container Docker, port 8001 | Chaque service possède son propre domaine. auth-service gère uniquement les tokens. |
| Tokens JWT | Access token (15 min) + Refresh token (7 jours) | Conforme CDC. Access court = surface d'attaque réduite. Refresh long = UX fluide. |
| Stockage Flutter | flutter_secure_storage (keychain iOS / keystore Android) | Tokens JWT = credentials sensibles. SharedPreferences = plaintext non chiffré, inacceptable. |
| Redis (backend) | Stockage refresh tokens dans Redis (auth_db = Redis uniquement) | Révocation instantanée : compte désactivé → refresh token supprimé de Redis → bloqué en max 15 min. |
| Accès credentials | auth-service appelle user-forest-service via HTTP interne (GET /users/by-email) | Chaque service possède sa propre DB. auth-service ne touche PAS forest_db directement. Vrai pattern microservices. |
| Validation JWT | Chaque service valide le JWT indépendamment via JWT_SECRET_KEY partagé dans .env | Appeler /verify à chaque requête = auth-service devient SPOF. Shared secret = stateless, O(1), aucune dépendance réseau. |
| Protection RBAC | Role-based : admin / superviseur / tout JWT valide selon la ressource | "All protected" trop blunt. "Only writes" trop permissif. Mapping précis conforme au CDC. |
| Refactors M0 | Inclus dans M1 : renommage dossiers + pinning requirements + version docker-compose | Triviaux (< 30 min), notés dans impl summary comme "à faire en M1". |
| Endpoints manquants MS-1 | GET /users/by-email/{email} + GET /geo/parcelle-at inclus en M1 | /users/by-email indispensable pour le flow login. /geo/parcelle-at nécessaire en M3. |

---

## 1. Carte RBAC — protection endpoints MS-1

| Endpoint | Méthode | Rôle requis |
|---|---|---|
| /roles/* | POST / PUT / DELETE | `admin` |
| /users/ — liste tous | GET | `admin`, `superviseur` |
| /users/{id} | GET | `admin`, `superviseur` |
| /users/superviseurs | GET | `admin` |
| /users/* | POST / PUT / DELETE | `admin` |
| /users/by-email/{email} | GET | internal (`X-Service-Secret`) |
| /forests/* | GET | tout JWT valide |
| /forests/* | POST / PUT / DELETE | `admin`, `superviseur` |
| /parcelles/* | GET | tout JWT valide |
| /parcelles/* | POST / PUT / DELETE | `admin`, `superviseur` |
| /directions-* | GET | tout JWT valide |
| /directions-* | POST / PUT / DELETE | `admin` |
| /geo/parcelle-at | GET | tout JWT valide |
| /health | GET | public (no auth) |

---

## 2. Structure des fichiers cibles

### 2.1 auth-service (nouveau)

| Fichier | Rôle |
|---|---|
| `ghabetna/services/auth-service/` | Nouveau dossier service |
| `app/main.py` | FastAPI app, CORS, startup Redis ping |
| `app/config.py` | BaseSettings : JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MIN, REFRESH_TOKEN_EXPIRE_DAYS, REDIS_URL, USER_SERVICE_URL, SERVICE_SECRET |
| `app/db.py` | Connexion Redis (redis-py asyncio) |
| `app/models.py` | Pydantic schemas : LoginRequest, TokenResponse, RefreshRequest |
| `app/routers/auth.py` | POST /auth/login, POST /auth/refresh, POST /auth/logout |
| `app/services/auth_service.py` | Logique : appel user-service, vérif password, création tokens, Redis ops |
| `app/utils/jwt.py` | create_access_token(), create_refresh_token(), decode_token() |
| `app/utils/password.py` | verify_password() via passlib (même lib que MS-1) |
| `Dockerfile` | python:3.11-slim, port 8001 |
| `requirements.txt` | fastapi, uvicorn, python-jose[cryptography], passlib, redis, httpx, pydantic-settings (versions pinnées) |
| `.env.example` | Template variables d'environnement |

### 2.2 user-forest-service (fichiers modifiés uniquement)

- `app/utils/jwt_guard.py` → nouveau — get_current_user() + require_roles()
- `app/routers/users.py` → modifié — ajout /users/by-email/{email} avec X-Service-Secret
- `app/routers/geo.py` → nouveau — GET /geo/parcelle-at?lat=X&lng=Y
- `app/config.py` → modifié — ajout JWT_SECRET_KEY + SERVICE_SECRET
- `requirements.txt` → modifié — ajout python-jose[cryptography], versions pinnées

### 2.3 Flutter (user_forest_app — fichiers modifiés)

- `lib/services/auth_service.dart` → nouveau — login(), refreshToken(), logout(), isLoggedIn()
- `lib/screens/login_screen.dart` → nouveau — formulaire login email + password
- `lib/utils/token_storage.dart` → nouveau — wrapper flutter_secure_storage
- `lib/utils/http_client.dart` → nouveau — client HTTP avec auto-refresh Authorization header
- `lib/screens/home_screen.dart` → modifié — redirect vers login si pas de token
- `pubspec.yaml` → modifié — ajout flutter_secure_storage: ^9.0.0

### 2.4 Infra (docker-compose.yml racine — modifié)

- Ajout service auth-service (port 8001, depends_on: db + redis)
- Ajout service redis (redis:7-alpine, port 6379, volume redis_data)
- Renommage services/user_management/ → services/user-forest-service/
- Ajout `version: "3.9"`

---

## 3. Tâches & sous-tâches

> ☐ = à faire | Tâche parent cochée = toutes les sous-tâches complètes
> Ordre d'implémentation obligatoire : A → B → C → D → E → F

---

### Groupe A — Refactors M0 (à faire en premier)

#### A1 — Renommage dossiers monorepo `REFACTOR`
- [X] Renommer `ghabetna/services/user_management/` → `ghabetna/services/user-forest-service/`
- [X] Renommer `ghabetna/flutter/user_forest_app/` → `ghabetna/flutter/` (aplatir)
- [X] Mettre à jour tous les chemins dans docker-compose.yml (context, volumes)
- [X] Mettre à jour le README si présent
- [X] Vérifier que `docker-compose up --build` démarre correctement après renommage

> ⚠ Faire avant toute autre modification pour éviter les conflits de chemins.

#### A2 — Pinning versions requirements.txt user-forest-service `REFACTOR`
- [X] Lancer `pip freeze` dans le container user-forest-service en cours d'exécution
- [X] Copier les versions exactes dans requirements.txt (`fastapi==X.Y.Z`, `sqlalchemy==X.Y.Z`, etc.)
- [X] Vérifier que `docker build` réussit avec les versions pinnées

#### A3 — Version docker-compose + bloc Redis `REFACTOR`
- [X] Ajouter `version: "3.9"` en tête du docker-compose.yml (obsolète avec Docker Compose v2 — intentionnellement omis)
- [X] Préparer le bloc redis dans docker-compose.yml (image, port, volume) — sera activé en B1

---

### Groupe B — Infrastructure

#### B1 — Redis dans docker-compose.yml `INFRA`
- [X] Définir service redis : `image: redis:7-alpine`, port 6379:6379, volume redis_data
- [X] Ajouter healthcheck redis : `redis-cli ping`
- [X] Ajouter `depends_on: redis: condition: service_healthy` dans auth-service
- [X] Ajouter `redis_data` dans la section volumes racine
- [X] Tester : `docker-compose up redis` → ping PONG

#### B2 — Scaffold auth-service + Dockerfile `INFRA`
- [X] Créer `ghabetna/services/auth-service/` avec sous-dossiers `app/routers/`, `app/utils/`
- [X] Créer Dockerfile : python:3.11-slim, COPY requirements.txt, pip install, CMD uvicorn port 8001
- [X] Créer requirements.txt avec versions pinnées : fastapi, uvicorn[standard], python-jose[cryptography], passlib[bcrypt], redis, httpx, pydantic-settings
- [X] Créer .env.example : JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, REDIS_URL, USER_SERVICE_URL, SERVICE_SECRET, CORS_ORIGINS
- [X] Ajouter auth-service dans docker-compose.yml : build, port 8001:8001, env_file, depends_on db + redis (service_healthy)
- [X] Vérifier que `docker-compose build auth-service` réussit sans erreur

#### B3 — Config pydantic-settings auth-service `CONFIG`
- [X] Créer `app/config.py` avec BaseSettings
- [X] Champs : JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES (default 15), REFRESH_TOKEN_EXPIRE_DAYS (default 7), REDIS_URL, USER_SERVICE_URL, SERVICE_SECRET, CORS_ORIGINS
- [X] Instancier `settings = Settings()` — import unique dans toute l'app
- [X] Vérifier que l'app démarre et loggue les settings au startup (sans afficher les secrets)

---

### Groupe C — auth-service backend

#### C1 — Connexion Redis + ping startup `BACKEND`
- [X] Créer `app/db.py` : client redis asyncio (`redis.asyncio.from_url(settings.REDIS_URL)`)
- [X] Dans `app/main.py` : on_startup → `await redis.ping()` — lever exception claire si Redis inaccessible
- [X] Exposer `get_redis()` comme dependency FastAPI
- [X] Tester : container up → log confirme "Redis connected"

#### C2 — JWT utils — création et décodage `BACKEND`
- [X] Créer `app/utils/jwt.py`
- [X] `create_access_token(data)` → JWT signé HS256, exp = now + ACCESS_TOKEN_EXPIRE_MINUTES, champs : sub (user_id), role, type="access"
- [X] `create_refresh_token(data)` → JWT signé HS256, exp = now + REFRESH_TOKEN_EXPIRE_DAYS*24h, champs : sub, type="refresh", jti (UUID4)
- [X] `decode_token(token)` → dict payload, raise HTTPException(401) si expiré ou invalide
- [X] Utiliser python-jose : `jose.jwt.encode / decode`, algorithme HS256
- [X] Écrire 3 tests unitaires : token valide, token expiré, token falsifié

#### C3 — Password utils — vérification `BACKEND`
- [X] Créer `app/utils/password.py`
- [X] `verify_password(plain, hashed)` → bool via passlib `CryptContext(schemes=["pbkdf2_sha256"])` — même algo que MS-1
- [X] Ne PAS créer `hash_password()` — auth-service ne crée pas de users

#### C4 — Schemas Pydantic auth `BACKEND`
- [X] Créer `app/models.py`
- [X] `LoginRequest` : email (EmailStr), password (str)
- [X] `TokenResponse` : access_token, refresh_token, token_type="bearer", role (str)
- [X] `RefreshRequest` : refresh_token (str)
- [X] `AccessTokenResponse` : access_token, token_type="bearer"
- [X] `TokenPayload` : sub (int), role (str), type (str), jti (str | None), exp (int)

#### C5 — Service métier — logique auth complète `BACKEND`
- [X] Créer `app/services/auth_service.py`
- [X] `get_user_by_email(email)` → appel httpx vers USER_SERVICE_URL/users/by-email/{email} avec header X-Service-Secret. Retourner {id, hashed_password, role, actif} ou None si 404
- [X] `login(email, password, redis)` → (1) get_user_by_email (2) vérifier actif=True sinon 403 (3) verify_password sinon 401 (4) créer tokens (5) stocker refresh dans Redis clé "refresh:{jti}" TTL=REFRESH_TOKEN_EXPIRE_DAYS*86400 (6) retourner TokenResponse
- [X] `refresh(refresh_token, redis)` → (1) decode_token (2) vérifier type=="refresh" (3) vérifier jti dans Redis sinon 401 (4) supprimer ancien jti (5) créer nouveaux tokens (6) stocker nouveau jti (7) retourner nouveaux tokens
- [X] `logout(refresh_token, redis)` → (1) decode_token silencieusement (2) supprimer jti de Redis si présent (3) retourner 200
- [X] Gérer erreurs httpx (timeout, connexion refused) → HTTPException(503)

#### C6 — Router auth — 3 endpoints `BACKEND`
- [X] Créer `app/routers/auth.py`
- [X] `POST /auth/login` : body LoginRequest → TokenResponse. Rate limit : 5 tentatives/min/IP
- [X] `POST /auth/refresh` : body RefreshRequest → AccessTokenResponse + nouveau refresh_token
- [X] `POST /auth/logout` : body RefreshRequest → {message}. Toujours 200 (idempotent)
- [X] Inclure router dans `app/main.py` avec prefix="/auth"
- [] Tester les 3 endpoints via Swagger /docs

#### C7 — main.py auth-service `BACKEND`
- [X] Créer `app/main.py` : `FastAPI(title="GHABETNA Auth Service", version="1.0")`
- [X] CORS : allow_origins depuis `settings.CORS_ORIGINS.split(",")`, allow_methods=["POST"]
- [X] `GET /health` → `{"status": "ok", "service": "auth-service"}` — public, no auth
- [X] Inclure router auth
- [X] Startup : ping Redis, log confirmation

---

### Groupe D — Sécurisation user-forest-service (MS-1)

#### D1 — JWT_SECRET_KEY + SERVICE_SECRET dans config MS-1 `CONFIG`
- [ ] Modifier `app/config.py` : ajouter JWT_SECRET_KEY (str) et SERVICE_SECRET (str)
- [ ] Ajouter ces variables dans .env.example et docker-compose.yml env_file
- [ ] JWT_SECRET_KEY IDENTIQUE à celui de auth-service — même valeur dans le .env racine
- [ ] Vérifier que l'app redémarre correctement

#### D2 — jwt_guard.py — dépendances FastAPI `BACKEND`
- [ ] Créer `app/utils/jwt_guard.py`
- [ ] `get_current_user(token = Depends(OAuth2PasswordBearer))` → décoder JWT, vérifier type=="access", retourner TokenPayload
- [ ] `require_roles(*roles)` → dépendance FastAPI qui vérifie payload.role dans roles, sinon HTTPException(403)
- [ ] `verify_service_secret(x_service_secret: str = Header())` → vérifier contre settings.SERVICE_SECRET, sinon 403
- [ ] Ajouter python-jose[cryptography] dans requirements.txt avec version pinnée

#### D3 — Guards RBAC sur tous les routers MS-1 `BACKEND`
- [ ] `routers/roles.py` : POST/PUT/DELETE → `Depends(require_roles("admin"))`
- [ ] `routers/users.py` : GET /users/ + GET /users/{id} → `require_roles("admin","superviseur")` | GET /superviseurs → `require_roles("admin")` | POST/PUT/DELETE → `require_roles("admin")`
- [ ] `routers/forests.py` : GET → `Depends(get_current_user)` | POST/PUT/DELETE → `require_roles("admin","superviseur")`
- [ ] `routers/parcelles.py` : GET → `Depends(get_current_user)` | POST/PUT/DELETE → `require_roles("admin","superviseur")`
- [ ] `routers/directions.py` : GET → `Depends(get_current_user)` | POST/PUT/DELETE → `require_roles("admin")`
- [ ] Ajouter `GET /health` → public dans main.py
- [ ] Tester chaque endpoint : sans token (401), mauvais rôle (403), bon rôle (200)

#### D4 — GET /users/by-email/{email} `BACKEND`
- [ ] Ajouter dans `routers/users.py` : `GET /users/by-email/{email}`
- [ ] Protection : `Depends(verify_service_secret)` uniquement
- [ ] Retourner : {id, email, hashed_password, role (nom string), actif} — PAS d'autres champs
- [ ] Si user non trouvé : HTTPException(404)
- [ ] `include_in_schema=False` — ne pas exposer dans Swagger public

#### D5 — GET /geo/parcelle-at `BACKEND`
- [ ] Créer `app/routers/geo.py`
- [ ] `GET /geo/parcelle-at?lat=float&lng=float` → Protection : `Depends(get_current_user)`
- [ ] Query PostGIS : `SELECT p.id, p.name, p.forest_id FROM parcelles p WHERE ST_Contains(p.geom, ST_SetSRID(ST_Point(lng, lat), 4326))`
- [ ] Retourner : {parcelle_id, parcelle_name, forest_id} ou HTTPException(404)
- [ ] Inclure router geo dans main.py
- [ ] Tester avec coordonnées GPS dans une parcelle existante → retourne la parcelle

---

### Groupe E — Flutter : Login UI + gestion tokens

#### E1 — flutter_secure_storage dans pubspec `FLUTTER`
- [ ] Ajouter `flutter_secure_storage: ^9.0.0` dans pubspec.yaml
- [ ] Lancer `flutter pub get`
- [ ] Android : vérifier `minSdkVersion >= 18` dans android/app/build.gradle
- [ ] iOS : rien de requis pour iOS 12+

#### E2 — token_storage.dart `FLUTTER`
- [ ] Créer `lib/utils/token_storage.dart`
- [ ] `saveTokens(accessToken, refreshToken)` → écriture sécurisée des deux tokens
- [ ] `getAccessToken()` → String?
- [ ] `getRefreshToken()` → String?
- [ ] `clearTokens()` → suppression des deux tokens
- [ ] `isLoggedIn()` → bool : getAccessToken() != null
- [ ] Clés de stockage : constantes `"access_token"` et `"refresh_token"`

#### E3 — auth_service.dart `FLUTTER`
- [ ] Créer `lib/services/auth_service.dart`
- [ ] `login(email, password)` → POST /auth/login, stocker tokens via TokenStorage, retourner le role
- [ ] `refreshAccessToken()` → POST /auth/refresh, mettre à jour access_token dans TokenStorage
- [ ] `logout()` → POST /auth/logout (best effort), puis TokenStorage.clearTokens()
- [ ] URL auth-service : `String.fromEnvironment("AUTH_BASE_URL", defaultValue: "http://localhost:8001")`
- [ ] Gérer erreurs : 401 (mauvais credentials), 403 (compte inactif), 503 (service down) — messages en français

#### E4 — http_client.dart avec auto-refresh `FLUTTER`
- [ ] Créer `lib/utils/http_client.dart`
- [ ] Classe `AuthenticatedClient` wrappant http.Client
- [ ] Injecter `"Authorization: Bearer {access_token}"` automatiquement sur chaque requête
- [ ] Si réponse 401 → tenter refreshAccessToken() → rejouer la requête originale une seule fois
- [ ] Si refresh échoue → appeler logout() → rediriger vers login_screen
- [ ] Remplacer http.Client dans user_service, forest_service, parcelle_service, direction_service par AuthenticatedClient
- [ ] Ajouter `.timeout(Duration(seconds: 30))` sur toutes les requêtes

#### E5 — login_screen.dart `FLUTTER`
- [ ] Créer `lib/screens/login_screen.dart`
- [ ] UI : logo GHABETNA + champ email + champ password (obscureText avec toggle) + bouton "Se connecter"
- [ ] Validation : email format valide, password non vide
- [ ] Sur submit : AuthService.login() → succès → Navigator.pushReplacement vers home_screen
- [ ] Afficher CircularProgressIndicator pendant l'appel
- [ ] Afficher SnackBar rouge avec message d'erreur en français si échec
- [ ] Style Material 3 cohérent (seedColor: Colors.green)

#### E6 — Modifier home_screen.dart `FLUTTER`
- [ ] Dans initState : vérifier `TokenStorage.isLoggedIn()`
- [ ] Si non connecté → `Navigator.pushReplacement` vers login_screen via `addPostFrameCallback`
- [ ] Ajouter bouton "Déconnexion" dans AppBar → AuthService.logout() → retour login_screen
- [ ] Afficher le rôle de l'utilisateur connecté sur le home

#### E7 — Mettre à jour main.dart `FLUTTER`
- [ ] Route initiale = login_screen (pas home_screen)
- [ ] home_screen accessible uniquement après login réussi
- [ ] Vérifier que le bouton retour Android ne peut pas revenir au login depuis home (pushReplacement partout)

---

### Groupe F — Tests & validation end-to-end

#### F1 — Tests unitaires JWT utils `BACKEND`
- [ ] Test : create_access_token + decode_token → payload correct (sub, role, type)
- [ ] Test : token expiré → HTTPException(401)
- [ ] Test : token avec signature incorrecte → HTTPException(401)
- [ ] Test : create_refresh_token → jti présent et unique (UUID4)
- [ ] Lancer : `pytest services/auth-service/ -v`

#### F2 — Tests manuels flow login/refresh/logout `BACKEND`
- [ ] Scénario 1 — Login valide : POST /auth/login → 200 + access_token + refresh_token
- [ ] Scénario 2 — Login invalide : mauvais password → 401
- [ ] Scénario 3 — Compte inactif : user avec actif=false → 403
- [ ] Scénario 4 — Refresh valide : POST /auth/refresh → nouveau access_token
- [ ] Scénario 5 — Refresh après logout : POST /auth/logout, puis POST /auth/refresh → 401
- [ ] Scénario 6 — Access token expiré (forcer TTL à 1 min) → appel MS-1 → 401

#### F3 — Tests guards MS-1 `BACKEND`
- [ ] Sans token : GET /forests/ → 401
- [ ] Token agent : POST /forests/ → 403
- [ ] Token superviseur : POST /forests/ → 201
- [ ] Token superviseur : DELETE /users/{id} → 403
- [ ] Token admin : DELETE /users/{id} → 200
- [ ] GET /health → 200 sans token
- [ ] GET /users/by-email/{email} sans X-Service-Secret → 403
- [ ] GET /users/by-email/{email} avec X-Service-Secret correct → 200 (include_in_schema=False vérifié)

#### F4 — Test Flutter flow complet émulateur `FLUTTER`
- [ ] Lancer l'app → écran login apparaît
- [ ] Credentials invalides → message d'erreur en français
- [ ] Credentials valides → redirection home_screen
- [ ] Tokens stockés dans flutter_secure_storage (vérifier via logs)
- [ ] Tuer et relancer l'app → home_screen direct (tokens persistants)
- [ ] "Déconnexion" → retour login_screen, tokens effacés
- [ ] Naviguer vers un écran MS-1 (ex: forêts) → requête avec Authorization header → données chargées

#### F5 — Validation docker-compose up global `INFRA`
- [ ] `docker-compose down -v` (reset complet)
- [ ] `docker-compose up --build`
- [ ] Vérifier démarrage : db, redis, user-forest-service, auth-service
- [ ] Vérifier healthchecks verts dans `docker ps`
- [ ] Logs : "Redis connected" dans auth-service, "Database connected" dans user-forest-service
- [ ] `GET http://localhost:8000/health` → 200
- [ ] `GET http://localhost:8001/health` → 200

---

## 4. Récapitulatif

| ID | Tâche | Type | Sous-tâches | Statut |
|---|---|---|---|---|
| A1 | Renommage dossiers monorepo | REFACTOR | 5 | ⬜ |
| A2 | Pinning requirements.txt user-forest-service | REFACTOR | 3 | ⬜ |
| A3 | Version docker-compose + bloc Redis | REFACTOR | 2 | ⬜ |
| B1 | Redis dans docker-compose.yml | INFRA | 5 | ⬜ |
| B2 | Scaffold auth-service + Dockerfile | INFRA | 6 | ⬜ |
| B3 | Config pydantic-settings auth-service | CONFIG | 4 | ⬜ |
| C1 | Connexion Redis + ping startup | BACKEND | 4 | ⬜ |
| C2 | JWT utils — création + décodage | BACKEND | 6 | ⬜ |
| C3 | Password utils — vérification | BACKEND | 3 | ⬜ |
| C4 | Schemas Pydantic auth | BACKEND | 5 | ⬜ |
| C5 | Service métier — logique auth complète | BACKEND | 5 | ⬜ |
| C6 | Router auth — 3 endpoints | BACKEND | 5 | ⬜ |
| C7 | main.py auth-service | BACKEND | 5 | ⬜ |
| D1 | JWT_SECRET_KEY + SERVICE_SECRET dans MS-1 | CONFIG | 4 | ⬜ |
| D2 | jwt_guard.py — dépendances FastAPI | BACKEND | 5 | ⬜ |
| D3 | Guards RBAC sur tous les routers MS-1 | BACKEND | 6 | ⬜ |
| D4 | GET /users/by-email/{email} | BACKEND | 4 | ⬜ |
| D5 | GET /geo/parcelle-at | BACKEND | 5 | ⬜ |
| E1 | flutter_secure_storage dans pubspec | FLUTTER | 4 | ⬜ |
| E2 | token_storage.dart | FLUTTER | 7 | ⬜ |
| E3 | auth_service.dart | FLUTTER | 5 | ⬜ |
| E4 | http_client.dart avec auto-refresh | FLUTTER | 7 | ⬜ |
| E5 | login_screen.dart | FLUTTER | 6 | ⬜ |
| E6 | Modifier home_screen.dart | FLUTTER | 4 | ⬜ |
| E7 | Mettre à jour main.dart | FLUTTER | 3 | ⬜ |
| F1 | Tests unitaires JWT | BACKEND | 5 | ⬜ |
| F2 | Tests manuels login/refresh/logout | BACKEND | 6 | ⬜ |
| F3 | Tests guards MS-1 | BACKEND | 7 | ⬜ |
| F4 | Test Flutter flow complet émulateur | FLUTTER | 7 | ⬜ |
| F5 | Validation docker-compose up global | INFRA | 7 | ⬜ |

**TOTAL : 30 tâches | 162 sous-tâches**

---

## 5. Règles non négociables

- `JWT_SECRET_KEY` : valeur identique dans auth-service et user-forest-service — une seule source dans le .env racine
- `SERVICE_SECRET` : partagé uniquement entre auth-service et user-forest-service — jamais dans les logs
- auth-service ne touche **jamais** forest_db directement — uniquement via HTTP user-forest-service
- `GET /users/by-email` ne figure pas dans Swagger public (`include_in_schema=False`)
- Refresh tokens dans Redis **uniquement** — pas de table refresh_tokens en PostgreSQL
- `.env` jamais versionné — seul `.env.example` l'est (règle héritée de M0)
- `depends_on: condition: service_healthy` obligatoire pour auth-service (db + redis)
- `flutter_secure_storage` uniquement pour les tokens — jamais SharedPreferences
- Auto-refresh transparent : l'utilisateur ne voit jamais d'erreur 401 si le refresh réussit
- Ordre d'implémentation : **A → B → C → D → E → F** — ne pas coder Flutter avant que le backend soit opérationnel
