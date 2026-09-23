-- =====================================================================
-- library/db/08_email_verification.sql
-- Migracion: verificacion real de correo por token (services/login)
-- Motor: PostgreSQL  |  Base: library_db
-- =====================================================================
--
-- POR QUE ESTA MIGRACION
-- ---------------------------------------------------------------------
-- La version anterior del microservicio marcaba `email_verificado = TRUE`
-- en el momento del registro, apoyandose solo en la validacion de sintaxis
-- y de registro MX. Eso era incorrecto:
--
--   * La sintaxis prueba que la direccion esta bien escrita.
--   * El registro MX prueba que el DOMINIO puede recibir correo.
--   * Ninguna de las dos prueba que el BUZON exista, ni que le pertenezca
--     a quien se esta registrando.
--
-- La unica prueba real de propiedad es enviar un correo con un token y que
-- alguien con acceso a ese buzon lo devuelva. A partir de esta migracion
-- `email_verificado` solo se pone en TRUE por esa via (endpoint /verify).
--
-- POR QUE UNA TABLA APARTE Y NO COLUMNAS EN `usuarios`
-- ---------------------------------------------------------------------
-- Un token no es un atributo de la persona: es un evento con ciclo de vida
-- propio (se emite, expira, se usa una sola vez) y un mismo usuario puede
-- solicitar varios a lo largo del tiempo. Guardarlo en `usuarios` obligaria
-- a sobrescribir el anterior y perderia el rastro de cuando se emitio y
-- cuando se uso. Es una relacion 1:N real, no un 1:1 disfrazado.
--
-- (Distinto del caso de `password_hash`, que SI es un atributo de la cuenta
-- y por eso vive en `usuarios`, sin tabla propia.)
--
-- Se guarda el HASH del token, no el token en claro: si alguien leyera la
-- tabla, no podria usar los tokens pendientes. Mismo criterio que con las
-- contrasenas.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS verificaciones_email (
    id             SERIAL PRIMARY KEY,
    usuario_id     UUID         NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token_hash     VARCHAR(64)  NOT NULL UNIQUE,
    email_destino  VARCHAR(150) NOT NULL,
    creado_en      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expira_en      TIMESTAMPTZ  NOT NULL,
    usado_en       TIMESTAMPTZ,
    enviado        BOOLEAN      NOT NULL DEFAULT FALSE
);

COMMENT ON TABLE verificaciones_email IS
    'Tokens de verificacion de correo. Un usuario puede tener varios a lo largo del tiempo.';
COMMENT ON COLUMN verificaciones_email.token_hash IS
    'SHA-256 del token. El token en claro solo viaja en el correo, nunca se almacena.';
COMMENT ON COLUMN verificaciones_email.usado_en IS
    'Fecha en que se canjeo. NULL = pendiente. Impide reutilizar el mismo token.';
COMMENT ON COLUMN verificaciones_email.enviado IS
    'TRUE si el MTA (Postfix) acepto el mensaje para entrega.';

-- Busqueda por token al canjear (/verify) y de tokens pendientes por usuario.
CREATE INDEX IF NOT EXISTS ix_verificaciones_usuario
    ON verificaciones_email (usuario_id);

CREATE INDEX IF NOT EXISTS ix_verificaciones_pendientes
    ON verificaciones_email (usuario_id, expira_en)
    WHERE usado_en IS NULL;

-- ---------------------------------------------------------------------
-- Correccion semantica de los registros existentes
-- ---------------------------------------------------------------------
-- Los usuarios que se registraron con la logica anterior quedaron marcados
-- como verificados sin haber confirmado su buzon. Se revierte el flag: la
-- base no debe afirmar algo que nunca se comprobo.
UPDATE usuarios
SET email_verificado = FALSE
WHERE email_verificado = TRUE
  AND NOT EXISTS (
      SELECT 1 FROM verificaciones_email v
      WHERE v.usuario_id = usuarios.id AND v.usado_en IS NOT NULL
  );

-- ---------------------------------------------------------------------
-- Permisos para el rol del microservicio
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'login_app_user') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE ON verificaciones_email TO login_app_user';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE verificaciones_email_id_seq TO login_app_user';
    ELSE
        RAISE NOTICE 'El rol login_app_user no existe: se omiten los GRANT.';
    END IF;
END $$;

COMMIT;

-- =====================================================================
-- VERIFICACION POSTERIOR
-- =====================================================================
-- SELECT u.email, u.email_verificado, v.creado_en, v.expira_en, v.usado_en, v.enviado
-- FROM usuarios u
-- LEFT JOIN verificaciones_email v ON v.usuario_id = u.id
-- ORDER BY v.creado_en DESC NULLS LAST LIMIT 10;
-- =====================================================================
