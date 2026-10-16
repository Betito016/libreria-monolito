-- =====================================================================
-- db/11_users_service.sql
-- Permisos minimos del rol del microservicio users en library_db.
-- El rol se crea aparte con una contrasena generada (no se versiona):
--     CREATE ROLE users_app_user WITH LOGIN PASSWORD '<password-generada>';
-- Idempotente. Ejecutar como superusuario:  psql -d library_db -f db/11_users_service.sql
-- =====================================================================
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'users_app_user') THEN
        EXECUTE 'GRANT CONNECT ON DATABASE library_db TO users_app_user';
        EXECUTE 'GRANT USAGE ON SCHEMA public TO users_app_user';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON usuarios TO users_app_user';
        -- Al eliminar un usuario se borran sus tokens de verificacion de correo.
        EXECUTE 'GRANT SELECT, DELETE ON verificaciones_email TO users_app_user';
        EXECUTE 'GRANT SELECT ON roles TO users_app_user';
    ELSE
        RAISE NOTICE 'El rol users_app_user no existe: se omiten los GRANT.';
    END IF;
END $$;
