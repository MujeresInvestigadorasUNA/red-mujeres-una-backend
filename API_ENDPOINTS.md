# API Endpoints (Backend)

Esta guía resume los endpoints disponibles para consumo desde otro backend.

## Formato recomendado (Swagger / OpenAPI)

- Contrato generado automáticamente: `docs/openapi.json`
- Este archivo mapea entradas, salidas, parámetros, request bodies y response models por endpoint.
- Se puede abrir en:
	- Swagger Editor (importando el JSON)
	- Postman (Import -> OpenAPI)
	- Redoc CLI / herramientas OpenAPI de CI

### Regenerar contrato

Ejecuta:

`d:/dylan/Documents/Mujeres Investigadoras/red-mujeres-una-backend/.venv/Scripts/python.exe scripts/export_openapi.py`

## Condición de documentación por entorno

- Si `ENV=dev`: se habilitan `GET /docs`, `GET /redoc`, `GET /openapi.json`.
- Si `ENV` es distinto de `dev` (por ejemplo `prod`): esos endpoints de documentación quedan deshabilitados.
- En producción puedes seguir publicando el contrato estático `docs/openapi.json` sin exponer `/docs` ni `/openapi.json` en runtime.

## Health

- `GET /` → estado general de la API.

## Users (`/users`)

- `GET /users/` → lista usuarios (`skip`, `limit`).
- `GET /users/{user_id}` → detalle de usuario.
- `POST /users/register` → registro con `multipart/form-data` (incluye `photo` opcional).
- `POST /users/` → crear usuario por JSON.
- `POST /users/{user_id}/profile-picture` → actualizar foto de perfil (`multipart/form-data`).
- `PUT /users/{user_id}` → actualizar usuario.
- `DELETE /users/{user_id}` → eliminar usuario.
- `POST /users/login` → autenticación.

## User Types (`/user_types`)

- `GET /user_types/` → lista tipos de usuario.
- `GET /user_types/{user_type_id}` → detalle tipo de usuario.
- `POST /user_types/` → crear tipo de usuario.

## Courses (`/courses`)

- `GET /courses/` → lista cursos (`skip`, `limit`).
- `GET /courses/public` → lista cursos públicos.
- `GET /courses/{course_id}` → detalle de curso.
- `GET /courses/user/{user_id}` → cursos por usuario.
- `POST /courses/` → crear curso.
- `PUT /courses/{course_id}` → actualizar curso.
- `DELETE /courses/{course_id}` → eliminar curso.

## Forums (`/forums`)

- `GET /forums/` → lista foros (`skip`, `limit`).
- `GET /forums/{forum_id}` → detalle de foro.
- `POST /forums/` → crear foro.
- `PUT /forums/{forum_id}` → actualizar foro.
- `DELETE /forums/{forum_id}` → eliminar foro.

## Research (`/research`)

- `GET /research/` → lista investigaciones (`skip`, `limit`).
- `GET /research/user/{user_id}` → investigaciones por usuario.
- `GET /research/{research_id}` → detalle de investigación.
- `GET /research/{research_id}/related?limit=5` → investigaciones relacionadas por similitud vectorial (global en blobs embebidos).
- `POST /research/` → crear investigación con PDF (`multipart/form-data`: `user_id`, `title`, `document`).
- `DELETE /research/{research_id}` → eliminar investigación.

## Notas para integración desde backend

- Usa `Content-Type: application/json` en endpoints JSON.
- Usa `multipart/form-data` para endpoints con archivo.
- En producción, integra contra rutas funcionales (por ejemplo `/users`, `/research`, etc.) y no dependas de `/docs` o `/openapi.json`.