-- =====================================================================
-- db/00_create_database.sql
-- Crea el rol de aplicación y la base de datos.
--
-- Principio de mínimo privilegio (ver docs/SECURITY_REVIEW.md, control 9):
-- "library_user" es el rol que usa el proceso Node.js en tiempo de
-- ejecución. NO es dueño de la base de datos ni tiene privilegios de
-- DDL (crear/eliminar tablas, roles u otras bases). Solo podrá leer y
-- escribir filas sobre las tablas ya creadas: esos permisos se otorgan
-- al final de db/01_schema.sql, una vez que las tablas existen.
--
-- Ejecutar como superusuario (el rol "postgres"), NO como library_user:
--   sudo -i -u postgres psql -f db/00_create_database.sql
-- =====================================================================

-- Usa solo caracteres ASCII en la contraseña real que pongas aquí: una
-- contraseña con acentos/ñ puede quedar guardada con una codificación
-- distinta a la que use tu cliente psql/Node al conectarse, y la
-- autenticación falla con un error de codificación en vez de uno de
-- credenciales (nos pasó probando este script en local).
CREATE ROLE library_user WITH LOGIN PASSWORD 'CAMBIA_ESTA_CLAVE_ANTES_DE_USAR';

-- El dueño de la base es el superusuario que ejecuta este script (no
-- library_user), para que un eventual compromiso del proceso Node no
-- pueda alterar el esquema, crear/borrar tablas ni la base misma.
CREATE DATABASE library_db;

-- library_user solo necesita poder conectarse a la base y usar el
-- esquema "public" para poder ejecutar sus SELECT/INSERT/UPDATE/DELETE.
GRANT CONNECT ON DATABASE library_db TO library_user;

\c library_db

GRANT USAGE ON SCHEMA public TO library_user;

-- Los GRANT de SELECT/INSERT/UPDATE/DELETE sobre las tablas se otorgan
-- al final de db/01_schema.sql (deben ejecutarse DESPUÉS de crear las
-- tablas, y ese script también debe correr como superusuario, no como
-- library_user).
