"""
database.py — MRP Delivery
Modelo: Pedido → (Caja, cantidad_cajas, porciones) → Recetas de la Caja → Ingredientes
"""
import sqlite3

DB_PATH = "mrp_delivery.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    c = get_connection()
    cur = c.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS proveedores (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre    TEXT    NOT NULL,
        contacto  TEXT    DEFAULT '',
        telefono  TEXT    DEFAULT '',
        email     TEXT    DEFAULT '',
        lead_time INTEGER NOT NULL DEFAULT 1,
        activo    INTEGER NOT NULL DEFAULT 1
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS ingredientes (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre         TEXT NOT NULL,
        tipo           TEXT NOT NULL DEFAULT 'fresco'
                           CHECK(tipo IN ('fresco','condimento','empaque','otro')),
        unidad         TEXT NOT NULL DEFAULT 'unidad',
        stock_actual   REAL NOT NULL DEFAULT 0,
        stock_minimo   REAL NOT NULL DEFAULT 0,
        costo_unitario REAL NOT NULL DEFAULT 0,
        proveedor_id   INTEGER REFERENCES proveedores(id)
    )""")

    # Receta individual con su BOM (ingredientes por porción)
    cur.execute("""CREATE TABLE IF NOT EXISTS recetas (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre      TEXT NOT NULL,
        descripcion TEXT DEFAULT '',
        activa      INTEGER NOT NULL DEFAULT 1
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS receta_ingredientes (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        receta_id      INTEGER NOT NULL REFERENCES recetas(id),
        ingrediente_id INTEGER NOT NULL REFERENCES ingredientes(id),
        cantidad       REAL NOT NULL,
        UNIQUE(receta_id, ingrediente_id)
    )""")

    # Caja = conjunto fijo de recetas
    cur.execute("""CREATE TABLE IF NOT EXISTS cajas (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre       TEXT NOT NULL,
        descripcion  TEXT DEFAULT '',
        precio_venta REAL NOT NULL DEFAULT 0,
        activa       INTEGER NOT NULL DEFAULT 1
    )""")

    # Qué recetas contiene cada caja (estructura fija)
    cur.execute("""CREATE TABLE IF NOT EXISTS caja_recetas (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        caja_id   INTEGER NOT NULL REFERENCES cajas(id),
        receta_id INTEGER NOT NULL REFERENCES recetas(id),
        UNIQUE(caja_id, receta_id)
    )""")

    # Pedido: cliente + fecha
    cur.execute("""CREATE TABLE IF NOT EXISTS pedidos (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente       TEXT NOT NULL,
        fecha_pedido  TEXT NOT NULL,
        fecha_entrega TEXT NOT NULL,
        estado        TEXT NOT NULL DEFAULT 'pendiente'
            CHECK(estado IN ('pendiente','en_proceso','completado','cancelado'))
    )""")

    # Detalle: qué caja, cuántas cajas y cuántas porciones (igual para todas las recetas de esa caja)
    cur.execute("""CREATE TABLE IF NOT EXISTS pedido_detalle (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
        caja_id   INTEGER NOT NULL REFERENCES cajas(id),
        cantidad  INTEGER NOT NULL DEFAULT 1,  -- número de cajas
        porciones REAL    NOT NULL DEFAULT 1   -- porciones por receta (igual para todas)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS ordenes_compra (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        proveedor_id           INTEGER NOT NULL REFERENCES proveedores(id),
        fecha_emision          TEXT NOT NULL,
        fecha_entrega_esperada TEXT NOT NULL,
        estado                 TEXT NOT NULL DEFAULT 'pendiente'
            CHECK(estado IN ('pendiente','enviada','recibida','cancelada')),
        total                  REAL NOT NULL DEFAULT 0
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS orden_compra_detalle (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        orden_id       INTEGER NOT NULL REFERENCES ordenes_compra(id),
        ingrediente_id INTEGER NOT NULL REFERENCES ingredientes(id),
        cantidad       REAL NOT NULL,
        costo_unitario REAL NOT NULL
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS movimientos_inventario (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        ingrediente_id INTEGER NOT NULL REFERENCES ingredientes(id),
        tipo           TEXT NOT NULL CHECK(tipo IN ('entrada','salida','ajuste')),
        cantidad       REAL NOT NULL,
        fecha          TEXT NOT NULL,
        notas          TEXT DEFAULT ''
    )""")

    c.commit()
    c.close()
    print("✅ Base de datos lista.")

if __name__ == "__main__":
    init_db()
