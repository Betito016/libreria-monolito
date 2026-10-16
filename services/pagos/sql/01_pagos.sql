-- =====================================================================
-- services/pagos/sql/01_pagos.sql   (libreria_db; requiere 01_pedidos.sql)
-- Pagos de los pedidos. Registrar un pago aprobado y marcar el pedido como
-- 'pagado' ocurren en la MISMA transaccion: no puede quedar un pago sin
-- pedido actualizado ni al reves. Un reembolso cancela el pedido y devuelve
-- el stock.
--
-- El rol se crea aparte con contrasena generada (no se versiona):
--     CREATE ROLE payments_app_user WITH LOGIN PASSWORD '<password-generada>';
-- Idempotente.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS payments (
    id          SERIAL        PRIMARY KEY,
    order_id    INTEGER       NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    user_id     UUID          NOT NULL,
    monto       NUMERIC(12,2) NOT NULL CHECK (monto > 0),
    metodo      VARCHAR(20)   NOT NULL CHECK (metodo IN ('tarjeta', 'transferencia', 'efectivo')),
    estado      VARCHAR(20)   NOT NULL DEFAULT 'aprobado'
                CHECK (estado IN ('aprobado', 'rechazado', 'reembolsado')),
    referencia  VARCHAR(64)   NOT NULL UNIQUE,
    creado_en   TIMESTAMPTZ   NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_payments_order ON payments (order_id);
CREATE INDEX IF NOT EXISTS ix_payments_user ON payments (user_id);
-- A lo mas un pago aprobado por pedido.
CREATE UNIQUE INDEX IF NOT EXISTS ux_payments_un_aprobado ON payments (order_id) WHERE estado = 'aprobado';

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'payments_app_user') THEN
        EXECUTE 'GRANT CONNECT ON DATABASE libreria_db TO payments_app_user';
        EXECUTE 'GRANT USAGE ON SCHEMA public TO payments_app_user';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON payments TO payments_app_user';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE payments_id_seq TO payments_app_user';
        -- Coordinacion con pedidos: leer el pedido y cambiar su estado.
        EXECUTE 'GRANT SELECT ON orders, order_items TO payments_app_user';
        EXECUTE 'GRANT UPDATE (estado, actualizado_en) ON orders TO payments_app_user';
        -- Un reembolso devuelve el stock de los libros.
        EXECUTE 'GRANT SELECT ON books TO payments_app_user';
        EXECUTE 'GRANT UPDATE (stock) ON books TO payments_app_user';
    ELSE
        RAISE NOTICE 'El rol payments_app_user no existe: se omiten los GRANT.';
    END IF;
END $$;

COMMIT;
