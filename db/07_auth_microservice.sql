-- =====================================================================
-- library/db/07_auth_microservice.sql
-- Migracion: microservicio independiente de autenticacion (apps/services/login)
-- Motor: PostgreSQL  |  Base: library_db
-- =====================================================================
--
-- CONTEXTO
-- ---------------------------------------------------------------------
-- El microservicio de login opera sobre la MISMA tabla `usuarios` que ya
-- usa el monolito Node.js. No se crea una tabla de usuarios paralela ni
-- una tabla exclusiva de passwords: `password_hash` pertenece a la cuenta
-- de usuario y vive en `usuarios`.
--
-- Esta migracion es ADITIVA e IDEMPOTENTE: puede ejecutarse varias veces
-- sin efectos secundarios, y no rompe al monolito existente.
--
-- DECISIONES DE DISENO
-- ---------------------------------------------------------------------
-- 1. `apellido_paterno` y `apellido_materno` se agregan como NULLABLE.
--    Motivo: el monolito Node inserta unicamente
--    (nombre, email, password_hash, rol). Si fueran NOT NULL, el registro
--    del monolito fallaria de inmediato. La obligatoriedad de estos
--    campos se valida en el microservicio de login, no en el esquema.
--
-- 2. Los 31 usuarios preexistentes guardan el nombre completo en la
--    columna `nombre` (ej. 'Ana Torres'). Se hace un backfill que parte
--    el valor en el primer espacio: 'Ana Torres' -> nombre='Ana',
--    apellido_paterno='Torres'. El apellido materno queda NULL porque
--    ese dato simplemente no existe en los registros historicos; no se
--    inventa informacion.
--
-- 3. `email_verificado` registra el resultado de la validacion de correo
--    (sintaxis + registro MX del dominio) que aplica el microservicio.
--
-- 4. El hash de password se mantiene en formato bcrypt para conservar la
--    interoperabilidad con el monolito Node (bcrypt costo 10, $2a$/$2b$).
--    Cambiar de algoritmo dejaria a los 31 usuarios existentes sin poder
--    autenticarse en el microservicio, y viceversa.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. NUEVAS COLUMNAS EN `usuarios`
-- ---------------------------------------------------------------------
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS apellido_paterno VARCHAR(120);
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS apellido_materno VARCHAR(120);
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email_verificado BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN usuarios.apellido_paterno IS
    'Apellido paterno. NULL en registros historicos previos al microservicio de login.';
COMMENT ON COLUMN usuarios.apellido_materno IS
    'Apellido materno. Opcional: no existe en los registros historicos.';
COMMENT ON COLUMN usuarios.email_verificado IS
    'TRUE si el correo paso la validacion de sintaxis y de registro MX del dominio.';

-- ---------------------------------------------------------------------
-- 2. DATA MIGRATION: separar el nombre completo historico
-- ---------------------------------------------------------------------
-- Solo afecta filas que aun no tienen apellido_paterno y cuyo `nombre`
-- contiene al menos un espacio. Idempotente: al re-ejecutarse ya no
-- encuentra filas que cumplan la condicion.
UPDATE usuarios
SET apellido_paterno = split_part(nombre, ' ', 2),
    nombre           = split_part(nombre, ' ', 1)
WHERE apellido_paterno IS NULL
  AND position(' ' IN nombre) > 0;

-- ---------------------------------------------------------------------
-- 3. VALIDACION DE FORMATO DE CORREO A NIVEL DE ESQUEMA
-- ---------------------------------------------------------------------
-- Defensa en profundidad: aunque el microservicio valida el correo antes
-- de insertar, la base tambien rechaza formatos evidentemente invalidos.
-- NOT VALID evita que la restriccion falle por datos historicos; aplica
-- solo a filas nuevas o modificadas.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_usuarios_email_formato'
    ) THEN
        ALTER TABLE usuarios
            ADD CONSTRAINT ck_usuarios_email_formato
            CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
            NOT VALID;
    END IF;
END $$;

-- Indice para las busquedas por correo del endpoint /login.
-- `email` ya es UNIQUE (por lo tanto ya esta indexado), pero se agrega un
-- indice funcional en minusculas para permitir login case-insensitive.
CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_email_lower
    ON usuarios (lower(email));

-- ---------------------------------------------------------------------
-- 4. PERMISOS PARA EL ROL DE APLICACION (MINIMO PRIVILEGIO)
-- ---------------------------------------------------------------------
-- El microservicio NO se conecta como `postgres` ni reutiliza
-- `library_user` (el rol del monolito). Tiene su propio rol, limitado a
-- lo que necesitan sus cinco endpoints: leer y escribir usuarios.
--
-- El rol se crea ANTES de ejecutar este archivo, porque la contrasena no
-- debe quedar escrita en el repositorio (ver PASO 1 del README del
-- microservicio):
--
--   CREATE ROLE login_app_user WITH LOGIN PASSWORD '<password-generada>';
--
-- Esta seccion solo otorga permisos, y no falla si el rol aun no existe.
-- Nota: en PL/pgSQL los comandos DDL/utilitarios como GRANT solo pueden
-- ejecutarse via EXECUTE, no como sentencias directas.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'login_app_user') THEN
        EXECUTE 'GRANT CONNECT ON DATABASE library_db TO login_app_user';
        EXECUTE 'GRANT USAGE ON SCHEMA public TO login_app_user';

        -- Estrictamente lo necesario: leer usuarios para autenticar,
        -- insertarlos al registrar y actualizar email_verificado.
        -- Nunca DELETE, nunca el resto del catalogo.
        EXECUTE 'GRANT SELECT, INSERT, UPDATE ON usuarios TO login_app_user';
    ELSE
        RAISE NOTICE 'El rol login_app_user no existe: se omiten los GRANT.';
    END IF;
END $$;

-- NUNCA otorgar SUPERUSER, DROP, ALTER ni DELETE a login_app_user.

COMMIT;

-- =====================================================================
-- VERIFICACION POSTERIOR (ejecutar manualmente)
-- =====================================================================
-- SELECT nombre, apellido_paterno, apellido_materno, email, email_verificado
-- FROM usuarios ORDER BY fecha_registro LIMIT 10;
--
-- SELECT COUNT(*) FILTER (WHERE apellido_paterno IS NOT NULL) AS con_apellido,
--        COUNT(*) AS total
-- FROM usuarios;
-- =====================================================================
