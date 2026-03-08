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

### Instalación
```bash
python -m venv .venv
# Win: .venv\Scripts\activate | Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

### Ejecutar servidor
```bash
uvicorn app.main:app --reload
```

### Documentación de API

**Interfaz interactiva (solo en desarrollo):**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json

**Health check:**
- http://localhost:8000/

**Notas de entorno:**
- Con `ENV=dev` se habilitan `/docs`, `/redoc` y `/openapi.json`.
- En producción (`ENV` distinto de `dev`) esos endpoints de documentación se deshabilitan automáticamente.
- Para integración con otros backends en producción, usa el contrato estático `docs/openapi.json` (ver Scripts útiles).

## Endpoints principales

### Autenticación y usuarios
- `POST /users/register` → Registro con foto de perfil opcional
- `POST /users/login` → Autenticación y generación de token JWT
- `GET /users/` → Listado de usuarios
- `GET /users/{user_id}` → Detalle de usuario
- `PUT /users/{user_id}` → Actualizar usuario
- `POST /users/{user_id}/profile-picture` → Actualizar foto de perfil

### Investigaciones (Research) y búsqueda vectorial
- `POST /research/` → Subir PDF de investigación (genera embeddings automáticamente)
- `GET /research/` → Listar investigaciones
- `GET /research/{research_id}` → Detalle de investigación
- `GET /research/{research_id}/related?limit=5` → **Documentos relacionados por similitud vectorial**
- `DELETE /research/{research_id}` → Eliminar investigación

**Búsqueda vectorial:**
El endpoint `/research/{research_id}/related` compara embeddings (Azure OpenAI) de todos los PDFs vectorizados en Blob Storage y retorna los documentos más similares por score de coseno. No requiere que estén del mismo usuario.

### Cursos
- `GET /courses/` → Listar cursos
- `GET /courses/public` → Cursos públicos
- `POST /courses/` → Crear curso
- `PUT /courses/{course_id}` → Actualizar curso
- `DELETE /courses/{course_id}` → Eliminar curso

### Foros
- `GET /forums/` → Listar foros
- `POST /forums/` → Crear foro
- `PUT /forums/{forum_id}` → Actualizar foro
- `DELETE /forums/{forum_id}` → Eliminar foro

### Tipos de usuario
- `GET /user_types/` → Listar tipos
- `POST /user_types/` → Crear tipo

**Documentación completa:**
- Listado de endpoints: `API_ENDPOINTS.md`
- Contrato OpenAPI/Swagger: `docs/openapi.json` (generar con script, ver Scripts útiles)
- Interfaz interactiva (solo desarrollo): http://localhost:8000/docs

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

### Generar contrato OpenAPI estático
Para exportar la especificación completa de endpoints a `docs/openapi.json` (útil para Swagger Editor, Postman, o integración con otros backends):

```bash
# Windows (con venv activado)
python scripts/export_openapi.py

# O con path completo al venv:
.venv/Scripts/python.exe scripts/export_openapi.py
```

Este comando genera un archivo `docs/openapi.json` que incluye:
- Todos los endpoints con métodos HTTP
- Request/response schemas detallados
- Parámetros de query, path, headers y body
- Códigos de respuesta y tipos de contenido

**Uso del archivo generado:**
- Importar en Swagger Editor: https://editor.swagger.io/
- Importar en Postman: Import → OpenAPI 3.0
- Compartir con otros equipos/backends sin exponer `/docs` en producción
- Generar clientes automáticos (TypeScript, Python, etc.)
