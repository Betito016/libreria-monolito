-- =====================================================================
-- db/10_roles.sql
-- Catalogo de roles para el JWT (claim role_id) y el microservicio users.
--
-- La columna usuarios.rol (enum rol_usuario) NO cambia: la usa el
-- monolito Node.js. roles solo asigna un id numerico estable a cada valor
-- del enum, y los microservicios lo obtienen con
--     (SELECT r.id FROM roles r WHERE r.nombre = u.rol::text)
--
-- Idempotente. Ejecutar como superusuario en library_db:
--     psql -d library_db -f db/10_roles.sql
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS roles (
    id           SMALLINT     PRIMARY KEY,
    nombre       VARCHAR(30)  NOT NULL UNIQUE,
    descripcion  VARCHAR(200) NOT NULL
);

INSERT INTO roles (id, nombre, descripcion) VALUES
    (1, 'administrador', 'Administra el catalogo, usuarios, autores, pedidos y pagos'),
    (2, 'cliente',       'Consulta el catalogo y gestiona sus propios pedidos y pagos')
ON CONFLICT (id) DO UPDATE SET nombre = EXCLUDED.nombre, descripcion = EXCLUDED.descripcion;

-- Cada nombre de roles debe existir en el enum (y viceversa).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM unnest(enum_range(NULL::rol_usuario)) e
               WHERE e::text NOT IN (SELECT nombre FROM roles)) THEN
        RAISE EXCEPTION 'Hay valores de rol_usuario sin fila en roles';
    END IF;
END $$;

-- Permisos minimos: login y users solo leen el catalogo.
DO $$
DECLARE rol TEXT;
BEGIN
    FOREACH rol IN ARRAY ARRAY['login_app_user', 'users_app_user'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = rol) THEN
            EXECUTE format('GRANT SELECT ON roles TO %I', rol);
        END IF;
    END LOOP;
END $$;

COMMIT;
