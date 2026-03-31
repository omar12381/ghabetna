# User & Forest Management App - Setup Guide

## Project Overview
Full-stack application for managing users and forest data with geospatial features:
- **Backend**: FastAPI + PostgreSQL/PostGIS
- **Frontend**: Flutter mobile app

---

## Backend Setup (FastAPI)

### 1. Prerequisites
- Python 3.10+
- PostgreSQL with PostGIS extension
- Virtual environment activated

### 2. Installation

```bash
cd d:\user_management
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Database Setup

Create PostgreSQL database and enable PostGIS:

```sql
CREATE DATABASE forest_db;
\c forest_db;
CREATE EXTENSION postgis;
```

Update connection string in `app/db.py` if needed:
```python
DATABASE_URL = "postgresql+psycopg2://forest_user:password@localhost:5432/forest_db"
```

### 4. Run the API Server

```bash
uvicorn app.main:app --reload --port 8000
```

API Documentation available at: `http://localhost:8000/docs`

### API Endpoints

**Users**
- `POST /users/` - Create user
- `GET /users/` - List users
- `GET /users/{id}` - Get user
- `PUT /users/{id}` - Update user
- `DELETE /users/{id}` - Delete user

**Forests**
- `POST /forests/` - Create forest
- `GET /forests/` - List forests
- `GET /forests/{id}` - Get forest
- `PUT /forests/{id}` - Update forest (GeoJSON support)
- `DELETE /forests/{id}` - Delete forest

**Parcelles**
- `POST /parcelles/` - Create parcelle
- `GET /parcelles/` - List parcelles
- `GET /parcelles/{id}` - Get parcelle
- `PUT /parcelles/{id}` - Update parcelle

**Directions**
- `GET /directions-regionales/` - List regional directions
- `GET /directions-secondaires/` - List secondary directions

---

## Frontend Setup (Flutter)

### 1. Prerequisites
- Flutter SDK 3.10.7+
- Dart 3.10.7+

### 2. Installation

```bash
cd user_forest_app
flutter pub get
```

### 3. Configure API Connection

Edit `lib/config/api_config.dart` and ensure the API base URL is correct:

```dart
const String BASE_URL = 'http://localhost:8000';
```

For mobile deployment, use the actual API server IP/address.

### 4. Run the App

**Android/iOS:**
```bash
flutter run
```

**Web:**
```bash
flutter run -d chrome
```

**Windows:**
```bash
flutter run -d windows
```

---

## Project Structure

```
d:\user_management/
├── app/                          # FastAPI Backend
│   ├── main.py                  # Main app entry point
│   ├── db.py                    # Database configuration
│   ├── models.py                # SQLAlchemy models
│   ├── schemas.py               # Pydantic schemas
│   ├── geo_utils.py             # Geospatial utilities
│   └── routers/                 # API route handlers
│       ├── users.py
│       ├── forests.py
│       ├── parcelles.py
│       ├── directions_regionales.py
│       └── directions_secondaires.py
│
├── user_forest_app/             # Flutter Frontend
│   ├── lib/
│   │   ├── main.dart            # App entry point
│   │   ├── config/              # Configuration files
│   │   ├── models/              # Data models
│   │   ├── screens/             # UI screens
│   │   └── services/            # API client services
│   ├── pubspec.yaml             # Flutter dependencies
│   ├── android/                 # Android platform-specific code
│   ├── ios/                     # iOS platform-specific code
│   ├── web/                     # Web platform-specific code
│   └── windows/                 # Windows platform-specific code
│
├── requirements.txt             # Python dependencies
├── README.md                    # Backend documentation
└── EXPLICATION_PROJET.md        # Detailed project explanation
```

---

## Key Features

✅ **User Management** - Create, read, update, delete users with role-based access (admin, agent, supervisor)  
✅ **Forest Management** - Manage forests with GeoJSON polygon geometries  
✅ **Geospatial Support** - PostGIS integration for geographic data  
✅ **Multi-Platform** - Flutter app runs on Android, iOS, Web, Windows, macOS, Linux  
✅ **CORS Support** - API configured for frontend communication  
✅ **Auto-Documentation** - FastAPI Swagger docs at `/docs`

---

## Troubleshooting

### PostgreSQL Connection Error
- Check PostgreSQL is running: `psql -U postgres`
- Verify credentials in `app/db.py`
- Ensure `forest_db` database exists with PostGIS enabled

### Flutter Build Error
- Clear cache: `flutter clean && flutter pub get`
- Check Flutter setup: `flutter doctor`
- Ensure API server is running before testing API calls

### CORS Issues
- API is configured to allow all origins (`"*"`) - disable in production
- Edit `app/main.py` `CORSMiddleware` configuration

---

## Next Steps

1. Start PostgreSQL server
2. Create the `forest_db` database and enable PostGIS
3. Run the FastAPI backend: `uvicorn app.main:app --reload`
4. In another terminal, run the Flutter app: `flutter run`
5. Access API docs at `http://localhost:8000/docs`

---

## Publier sur GitHub (versionnage)

Le dépôt Git local est initialisé sur la branche `main` avec un premier commit. Pour pousser vers GitHub :

1. Créez un dépôt **public** vide sur [github.com](https://github.com/new) (sans README ni `.gitignore` générés par GitHub, pour éviter un conflit au premier push).
2. Dans PowerShell, depuis `D:\user_management` :

```powershell
git remote add origin https://github.com/VOTRE_UTILISATEUR/NOM_DU_REPO.git
git push -u origin main
```

3. Authentification : utilisez un **Personal Access Token** (HTTPS) ou configurez Git Credential Manager. Si `origin` existe déjà : `git remote set-url origin <URL>` puis `git push -u origin main`.

---

## Support Files

- **EXPLICATION_PROJET.md** - Detailed explanation of backend architecture
- **README.md** - Backend quick start guide
