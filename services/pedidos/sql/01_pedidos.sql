-- =====================================================================
-- services/pedidos/sql/01_pedidos.sql   (libreria_db)
-- Pedidos y lineas de pedido. El stock vive en books.stock: crear un pedido
-- lo descuenta y cancelarlo lo devuelve, en la misma transaccion.
--
-- user_id es el id del usuario de library_db (otra base): no puede llevar
-- FK; lo garantiza el JWT, que solo emite login para usuarios existentes.
--
-- El rol se crea aparte con contrasena generada (no se versiona):
--     CREATE ROLE orders_app_user WITH LOGIN PASSWORD '<password-generada>';
-- Idempotente.
-- =====================================================================
BEGIN;

CREATE TABLE IF NOT EXISTS orders (
    id               SERIAL        PRIMARY KEY,
    user_id          UUID          NOT NULL,
    user_email       VARCHAR(150)  NOT NULL,
    estado           VARCHAR(20)   NOT NULL DEFAULT 'pendiente'
                     CHECK (estado IN ('pendiente', 'pagado', 'enviado', 'entregado', 'cancelado')),
    total            NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (total >= 0),
    direccion_envio  VARCHAR(300),
    creado_en        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    actualizado_en   TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_orders_user ON orders (user_id);
CREATE INDEX IF NOT EXISTS ix_orders_estado ON orders (estado, creado_en);

CREATE TABLE IF NOT EXISTS order_items (
    id               SERIAL        PRIMARY KEY,
    order_id         INTEGER       NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    book_isbn        VARCHAR(20)   NOT NULL REFERENCES books(isbn) ON DELETE RESTRICT,
    titulo           VARCHAR(255)  NOT NULL,
    cantidad         INTEGER       NOT NULL CHECK (cantidad > 0),
    precio_unitario  NUMERIC(10,2) NOT NULL CHECK (precio_unitario >= 0),
    UNIQUE (order_id, book_isbn)
);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'orders_app_user') THEN
        EXECUTE 'GRANT CONNECT ON DATABASE libreria_db TO orders_app_user';
        EXECUTE 'GRANT USAGE ON SCHEMA public TO orders_app_user';
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON orders, order_items TO orders_app_user';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE orders_id_seq, order_items_id_seq TO orders_app_user';
        -- Del catalogo solo lee titulo y precio, y actualiza el stock.
        EXECUTE 'GRANT SELECT ON books TO orders_app_user';
        EXECUTE 'GRANT UPDATE (stock) ON books TO orders_app_user';
    ELSE
        RAISE NOTICE 'El rol orders_app_user no existe: se omiten los GRANT.';
    END IF;
END $$;

COMMIT;
