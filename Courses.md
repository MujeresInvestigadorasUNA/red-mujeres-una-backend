Cómo usar (pruebas rápidas)

Crear curso con dos sesiones:

POST /api/v1/courses
{
  "title": "Introducción a Sistemas Embebidos",
  "description": "Curso base para la red de mujeres de la UNA.",
  "instructor_name": "Ing. María López",
  "capacity": 25,
  "sessions": [
    {"date": "2025-10-05", "start_time": "18:00:00", "end_time": "20:00:00", "timezone": "America/Costa_Rica"},
    {"date": "2025-10-12", "start_time": "18:00:00", "end_time": "20:00:00", "location": "Sala 2"}
  ]
}

Agregar sesión luego:

POST /api/v1/courses/1/sessions
{
  "date": "2025-10-19",
  "start_time": "18:00:00",
  "end_time": "20:00:00",
  "location": "Zoom"
}

Inscribirse / Desinscribirse:

POST /api/v1/courses/1/enroll
POST /api/v1/courses/1/unenroll

Ver inscritos:
GET /api/v1/courses/1/enrollments

Notas de diseño (breve)
Capacidad: el servicio no permite bajar la capacidad por debajo de los ya inscritos.

Días múltiples: el curso puede tener cualquier número de sesiones; se validan duplicados exactos de franja horaria por curso.

Permisos: solo el creador puede editar/borrar curso y gestionar sesiones. La inscripción/retirada es por el usuario autenticado.

Waitlist: el campo waitlisted queda listo para futuro (si quieres promover automáticamente de lista de espera cuando se libera un cupo).

Extensiones fáciles: certificados de asistencia por sesión, cancelación de sesión individual, recordatorios por correo, etc.