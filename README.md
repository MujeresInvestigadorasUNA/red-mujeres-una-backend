# Red Mujeres UNA – Backend (FastAPI)

Backend base con **FastAPI**, **SQLAlchemy**, **JWT** y **SQLite** (local). Listo para migrar a **Azure Container Apps** con **MySQL** o **Azure SQL**.

## Stack
- FastAPI (ASGI) + Uvicorn
- SQLAlchemy 2.x (ORM)
- Pydantic v2 (schemas) + pydantic-settings (config)
- Auth JWT (python-jose) + bcrypt (passlib)

## Requisitos
- Python 3.11+ (recomendado 3.12)
- (Opcional) Docker / Docker Compose

## Configuración
Variables en `.env` (ver `.env.example`):
```env
APP_NAME=backend
ENV=dev
DEBUG=True
API_V1_PREFIX=/api/v1
JWT_SECRET=CHANGE_ME
JWT_ALG=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
DATABASE_URL=sqlite:///./app.db
```

## Desarrollo (local)
python -m venv .venv
# Win: .venv\Scripts\activate | Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
OpenAPI JSON: http://localhost:8000/openapi.json
Health: http://localhost:8000/healthz

## Endpoints principales
POST /api/v1/auth/register → crear usuario
POST /api/v1/auth/login → token JWT
GET /api/v1/users/me → perfil (requiere Bearer)
GET /api/v1/users/ → listado (requiere Bearer)
PATCH /api/v1/users/me → actualizar (requiere Bearer)
GET /research/{research_id}/related?limit=5 → documentos relacionados por similitud vectorial

## Base de datos
Local: SQLite (por defecto)
Azure SQL (Produccion): mssql+pyodbc://... (requiere ODBC Driver 18 en el contenedor)

Docker (local)
docker compose up --build -d

## API: http://localhost:8080

## Despliegue Orden
Despliegue (Azure Container Apps)
Construye y sube la imagen (ACR o Docker Hub).
Configura variables: DATABASE_URL, JWT_SECRET.
Ingress en puerto 8080, health probe /healthz.
Escala mínima (0–1) para ahorrar.

## Estructura
app/
  core/ (config, db, security)
  models/ (ORM)
  schemas/ (Pydantic)
  services/ (lógica)
  controllers/ (orquestación)
  routes/ (FastAPI routers)
  main.py (app)

## Scripts útiles
Exportar OpenAPI a docs/openapi.json:
python scripts/export_openapi.py
