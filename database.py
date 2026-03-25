"""
database.py — Conexión a Supabase via Transaction Pooler (psycopg2)
"""
import os
import psycopg2
import psycopg2.extras

def get_secrets():
    try:
        import streamlit as st
        return st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
    except Exception:
        return os.environ.get("SUPABASE_URL",""), os.environ.get("SUPABASE_KEY","")

def get_connection():
    url, key = get_secrets()
    # Extraer project_ref: https://iuhnscliqevkyggeomty.supabase.co → iuhnscliqevkyggeomty
    project_ref = url.replace("https://","").replace("http://","").split(".")[0]
    conn = psycopg2.connect(
        host=f"db.{project_ref}.supabase.co",
        port=5432,
        dbname="postgres",
        user="postgres",
        password=key,
        sslmode="require",
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn

def init_db():
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS proveedores (
        id SERIAL PRIMARY KEY, nombre TEXT NOT NULL,
        contacto TEXT DEFAULT '', telefono TEXT DEFAULT '',
        email TEXT DEFAULT '', lead_time INTEGER NOT NULL DEFAULT 1,
        activo INTEGER NOT NULL DEFAULT 1)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS ingredientes (
        id SERIAL PRIMARY KEY, nombre TEXT NOT NULL,
        tipo TEXT NOT NULL DEFAULT 'fresco',
        unidad TEXT NOT NULL DEFAULT 'unidad',
        stock_actual REAL NOT NULL DEFAULT 0,
        stock_minimo REAL NOT NULL DEFAULT 0,
        costo_unitario REAL NOT NULL DEFAULT 0,
        calorias REAL NOT NULL DEFAULT 0,
        proteinas_g REAL NOT NULL DEFAULT 0,
        vegetales INTEGER NOT NULL DEFAULT 0,
        proveedor_id INTEGER REFERENCES proveedores(id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS recetas (
        id SERIAL PRIMARY KEY, nombre TEXT NOT NULL,
        descripcion TEXT DEFAULT '', activa INTEGER NOT NULL DEFAULT 1)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS receta_ingredientes (
        id SERIAL PRIMARY KEY,
        receta_id INTEGER NOT NULL REFERENCES recetas(id),
        ingrediente_id INTEGER NOT NULL REFERENCES ingredientes(id),
        cantidad REAL NOT NULL,
        UNIQUE(receta_id, ingrediente_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS menus (
        id SERIAL PRIMARY KEY, nombre TEXT NOT NULL,
        descripcion TEXT DEFAULT '',
        categoria TEXT NOT NULL DEFAULT 'nivel_medio',
        racion INTEGER NOT NULL DEFAULT 2,
        activo INTEGER NOT NULL DEFAULT 1)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS menu_recetas (
        id SERIAL PRIMARY KEY,
        menu_id INTEGER NOT NULL REFERENCES menus(id),
        receta_id INTEGER NOT NULL REFERENCES recetas(id),
        UNIQUE(menu_id, receta_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS cajas (
        id SERIAL PRIMARY KEY, nombre TEXT NOT NULL,
        descripcion TEXT DEFAULT '',
        precio_venta REAL NOT NULL DEFAULT 0,
        activa INTEGER NOT NULL DEFAULT 1)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS caja_recetas (
        id SERIAL PRIMARY KEY,
        caja_id INTEGER NOT NULL REFERENCES cajas(id),
        receta_id INTEGER NOT NULL REFERENCES recetas(id),
        UNIQUE(caja_id, receta_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS pedidos (
        id SERIAL PRIMARY KEY, cliente TEXT NOT NULL,
        fecha_pedido TEXT NOT NULL, fecha_entrega TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'pendiente')""")

    cur.execute("""CREATE TABLE IF NOT EXISTS pedido_detalle (
        id SERIAL PRIMARY KEY,
        pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
        caja_id INTEGER NOT NULL REFERENCES cajas(id),
        cantidad INTEGER NOT NULL DEFAULT 1,
        porciones REAL NOT NULL DEFAULT 1)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS ordenes_compra (
        id SERIAL PRIMARY KEY,
        proveedor_id INTEGER NOT NULL REFERENCES proveedores(id),
        fecha_emision TEXT NOT NULL,
        fecha_entrega_esperada TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'pendiente',
        total REAL NOT NULL DEFAULT 0)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS orden_compra_detalle (
        id SERIAL PRIMARY KEY,
        orden_id INTEGER NOT NULL REFERENCES ordenes_compra(id),
        ingrediente_id INTEGER NOT NULL REFERENCES ingredientes(id),
        cantidad REAL NOT NULL, costo_unitario REAL NOT NULL)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS movimientos_inventario (
        id SERIAL PRIMARY KEY,
        ingrediente_id INTEGER NOT NULL REFERENCES ingredientes(id),
        tipo TEXT NOT NULL, cantidad REAL NOT NULL,
        fecha TEXT NOT NULL, notas TEXT DEFAULT '')""")

    conn.commit()
    cur.close()
    conn.close()
