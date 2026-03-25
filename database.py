"""
database.py — SQLite sincronizado con GitHub
Los datos se guardan en un archivo .db en tu repositorio de GitHub.
Nunca se pierden aunque Streamlit se reinicie.
"""
import sqlite3
import os
import base64
import requests
import tempfile

DB_PATH = "/tmp/mrp_delivery.db"

def _get_secrets():
    try:
        import streamlit as st
        return (st.secrets["GITHUB_TOKEN"],
                st.secrets["GITHUB_REPO"],
                st.secrets["GITHUB_FILE"])
    except Exception:
        return (os.environ.get("GITHUB_TOKEN",""),
                os.environ.get("GITHUB_REPO",""),
                os.environ.get("GITHUB_FILE","mrp_delivery.db"))

def _download_db():
    """Descarga la BD de GitHub si existe."""
    token, repo, filepath = _get_secrets()
    if not token or not repo:
        return False
    headers = {"Authorization": f"token {token}",
               "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{repo}/contents/{filepath}"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data["content"])
        with open(DB_PATH, "wb") as f:
            f.write(content)
        return True
    return False

def _upload_db():
    """Sube la BD a GitHub."""
    token, repo, filepath = _get_secrets()
    if not token or not repo:
        return False
    headers = {"Authorization": f"token {token}",
               "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{repo}/contents/{filepath}"

    # Leer archivo local
    with open(DB_PATH, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    # Obtener SHA actual si existe
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None

    payload = {
        "message": "sync: actualizar base de datos MRP",
        "content": content,
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=headers, json=payload)
    return r.status_code in (200, 201)

def get_connection():
    """Retorna conexión SQLite local."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def sync_save():
    """Guarda la BD en GitHub después de cambios."""
    try:
        _upload_db()
    except Exception:
        pass  # No bloquear la app si falla el sync

def init_db():
    """Descarga BD de GitHub (si existe) y crea tablas si no existen."""
    _download_db()  # Intenta descargar primero

    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS proveedores (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
        contacto TEXT DEFAULT '', telefono TEXT DEFAULT '',
        email TEXT DEFAULT '', lead_time INTEGER NOT NULL DEFAULT 1,
        activo INTEGER NOT NULL DEFAULT 1)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS ingredientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
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
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
        descripcion TEXT DEFAULT '', activa INTEGER NOT NULL DEFAULT 1)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS receta_ingredientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receta_id INTEGER NOT NULL REFERENCES recetas(id),
        ingrediente_id INTEGER NOT NULL REFERENCES ingredientes(id),
        cantidad REAL NOT NULL, UNIQUE(receta_id, ingrediente_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS menus (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
        descripcion TEXT DEFAULT '',
        categoria TEXT NOT NULL DEFAULT 'nivel_medio',
        racion INTEGER NOT NULL DEFAULT 2,
        activo INTEGER NOT NULL DEFAULT 1)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS menu_recetas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        menu_id INTEGER NOT NULL REFERENCES menus(id),
        receta_id INTEGER NOT NULL REFERENCES recetas(id),
        UNIQUE(menu_id, receta_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS cajas (
        id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL,
        descripcion TEXT DEFAULT '',
        precio_venta REAL NOT NULL DEFAULT 0,
        activa INTEGER NOT NULL DEFAULT 1)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS caja_recetas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caja_id INTEGER NOT NULL REFERENCES cajas(id),
        receta_id INTEGER NOT NULL REFERENCES recetas(id),
        UNIQUE(caja_id, receta_id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS pedidos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT NOT NULL,
        fecha_pedido TEXT NOT NULL, fecha_entrega TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'pendiente')""")

    cur.execute("""CREATE TABLE IF NOT EXISTS pedido_detalle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INTEGER NOT NULL REFERENCES pedidos(id),
        caja_id INTEGER NOT NULL REFERENCES cajas(id),
        cantidad INTEGER NOT NULL DEFAULT 1,
        porciones REAL NOT NULL DEFAULT 1)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS ordenes_compra (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proveedor_id INTEGER NOT NULL REFERENCES proveedores(id),
        fecha_emision TEXT NOT NULL,
        fecha_entrega_esperada TEXT NOT NULL,
        estado TEXT NOT NULL DEFAULT 'pendiente',
        total REAL NOT NULL DEFAULT 0)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS orden_compra_detalle (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        orden_id INTEGER NOT NULL REFERENCES ordenes_compra(id),
        ingrediente_id INTEGER NOT NULL REFERENCES ingredientes(id),
        cantidad REAL NOT NULL, costo_unitario REAL NOT NULL)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS movimientos_inventario (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ingrediente_id INTEGER NOT NULL REFERENCES ingredientes(id),
        tipo TEXT NOT NULL, cantidad REAL NOT NULL,
        fecha TEXT NOT NULL, notas TEXT DEFAULT '')""")

    conn.commit()
    conn.close()
    sync_save()  # Subir a GitHub si es BD nueva
