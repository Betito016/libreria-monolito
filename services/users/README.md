# Microservicio users (:5004)

Administra usuarios, roles, correos y contraseñas sobre `library_db` (tablas `usuarios` y `roles`).

| Método | Endpoint | Acceso |
|---|---|---|
| GET | `/roles` | público |
| GET | `/users?q=&role_id=&activo=&page=&page_size=` | JWT administrador |
| GET | `/users/{id}` | JWT administrador o el propio usuario |
| POST | `/users` | JWT administrador |
| PATCH | `/users/{id}` | JWT administrador |
| DELETE | `/users/{id}` | JWT administrador |
| GET | `/health`, `/metrics` | público |

- **Roles:** tabla `roles` (1 administrador, 2 cliente), mapeada desde el enum `usuarios.rol`. Solo puede haber un administrador (índice único parcial): crear otro responde 409 `ERR_UN_SOLO_ADMINISTRADOR`.
- **Revocación:** cambiar contraseña, correo, rol, desactivar o eliminar a un usuario escribe `jwt:revoked_before:<user_id>` en Redis: sus JWT dejan de valer en los 6 servicios y login no renueva sus sesiones.
- El administrador no puede desactivarse ni eliminarse a sí mismo.
- Contraseñas con bcrypt (compatibles con el monolito y con login); `password_hash` nunca sale del servicio.

## Instalación

```bash
# rol propio con contraseña generada (no versionada)
CREATE ROLE users_app_user WITH LOGIN PASSWORD '<password-generada>';
psql -d library_db -f ../../db/10_roles.sql
psql -d library_db -f ../../db/11_users_service.sql
cp .env.example .env            # DB_PASSWORD, JWT_SECRET_KEY (la de login), REDIS_URL
python -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python app.py
venv/bin/python -m pytest -q    # 11 pruebas
```

Ver [docs/REDIS_MICROSERVICIOS.md](../../docs/REDIS_MICROSERVICIOS.md).
