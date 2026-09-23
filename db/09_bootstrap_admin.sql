-- =====================================================================
-- library/db/09_bootstrap_admin.sql
-- Migracion: habilitar al administrador inicial (bootstrap)
-- Motor: PostgreSQL  |  Base: library_db
-- =====================================================================
--
-- PROBLEMA
-- ---------------------------------------------------------------------
-- A partir de la version 2 del microservicio de login, /login rechaza a las
-- cuentas cuyo correo no esta verificado (ERR_CORREO_NO_VERIFICADO), y el
-- CRUD de libros queda reservado a usuarios con rol 'administrador'.
--
-- El esquema permite un unico administrador (indice parcial
-- ux_un_solo_administrador), y el que existe -- admin@libreria.test, creado
-- por el seed del monolito -- nunca puede verificarse por la via normal:
-- el dominio .test esta reservado por el RFC 2606, no tiene registros MX y
-- ningun correo puede entregarse ahi. Sin esta migracion nadie podria
-- administrar el catalogo.
--
-- DECISION
-- ---------------------------------------------------------------------
-- Se marca al administrador inicial como verificado de forma explicita y
-- documentada. Es el patron de "bootstrap": la primera cuenta privilegiada
-- la provisiona quien opera el sistema, no se auto-registra, porque no
-- existe todavia nadie con autoridad para aprobarla.
--
-- La excepcion es deliberadamente estrecha: aplica SOLO a la cuenta con
-- rol 'administrador'. Cualquier otro usuario sigue necesitando el token de
-- verificacion enviado por correo.
--
-- RECOMENDACION POSTERIOR
-- ---------------------------------------------------------------------
-- La contrasena del administrador inicial viene del seed del monolito y por
-- lo tanto es conocida. Debe cambiarse con PATCH /profile en cuanto se
-- inicie sesion por primera vez.
-- =====================================================================

BEGIN;

UPDATE usuarios
SET email_verificado = TRUE,
    actualizado_en   = now()
WHERE rol = 'administrador'
  AND email_verificado = FALSE;

COMMIT;

-- =====================================================================
-- VERIFICACION POSTERIOR
-- =====================================================================
-- SELECT email, rol, email_verificado, activo
-- FROM usuarios WHERE rol = 'administrador';
-- =====================================================================
