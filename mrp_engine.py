"""
mrp_engine.py — Motor MRP
Cálculo: cantidad_cajas × porciones × ingrediente_por_porcion
"""
from datetime import datetime, timedelta
from database import get_connection


def agregar_proveedor(nombre, contacto="", telefono="", email="", lead_time=1):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO proveedores (nombre,contacto,telefono,email,lead_time) VALUES (?,?,?,?,?)",
            (nombre, contacto, telefono, email, lead_time))
        return cur.lastrowid


def agregar_ingrediente(nombre, tipo="fresco", unidad="unidad",
                        stock_actual=0, stock_minimo=0, costo_unitario=0, proveedor_id=None):
    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO ingredientes
                (nombre,tipo,unidad,stock_actual,stock_minimo,costo_unitario,proveedor_id)
            VALUES (?,?,?,?,?,?,?)
        """, (nombre, tipo, unidad, stock_actual, stock_minimo, costo_unitario, proveedor_id))
        return cur.lastrowid


def actualizar_stock(ingrediente_id, cantidad, tipo="entrada"):
    with get_connection() as conn:
        ing = conn.execute("SELECT stock_actual FROM ingredientes WHERE id=?",
                           (ingrediente_id,)).fetchone()
        delta = cantidad if tipo != "salida" else -cantidad
        nuevo = ing["stock_actual"] + delta
        conn.execute("UPDATE ingredientes SET stock_actual=? WHERE id=?", (nuevo, ingrediente_id))
        conn.execute("INSERT INTO movimientos_inventario (ingrediente_id,tipo,cantidad,fecha) VALUES (?,?,?,?)",
                     (ingrediente_id, tipo, cantidad, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        return nuevo


def agregar_receta(nombre, descripcion=""):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO recetas (nombre,descripcion) VALUES (?,?)", (nombre, descripcion))
        return cur.lastrowid


def agregar_ingrediente_receta(receta_id, ingrediente_id, cantidad):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO receta_ingredientes (receta_id,ingrediente_id,cantidad)
            VALUES (?,?,?)
        """, (receta_id, ingrediente_id, cantidad))


def agregar_caja(nombre, descripcion="", precio_venta=0):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO cajas (nombre,descripcion,precio_venta) VALUES (?,?,?)",
            (nombre, descripcion, precio_venta))
        return cur.lastrowid


def agregar_receta_a_caja(caja_id, receta_id):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO caja_recetas (caja_id,receta_id) VALUES (?,?)",
            (caja_id, receta_id))


def crear_pedido(cliente, fecha_entrega, items):
    """
    items = [
        {"caja_id": 1, "cantidad": 10, "porciones": 2},
        ...
    ]
    MRP calcula: cantidad × porciones × ingrediente_por_porcion
    """
    hoy = datetime.now().strftime("%Y-%m-%d")
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO pedidos (cliente,fecha_pedido,fecha_entrega) VALUES (?,?,?)",
            (cliente, hoy, fecha_entrega))
        pedido_id = cur.lastrowid
        for it in items:
            conn.execute(
                "INSERT INTO pedido_detalle (pedido_id,caja_id,cantidad,porciones) VALUES (?,?,?,?)",
                (pedido_id, it["caja_id"], it["cantidad"], it["porciones"]))
    return pedido_id


def calcular_requerimientos():
    """
    Requerido por ingrediente =
        SUM(cantidad_cajas × porciones × cantidad_ingrediente_por_porcion)
    sobre todos los pedidos pendientes.
    """
    conn = get_connection()
    lineas = conn.execute("""
        SELECT pd.caja_id, pd.cantidad, pd.porciones
        FROM pedidos p
        JOIN pedido_detalle pd ON pd.pedido_id = p.id
        WHERE p.estado = 'pendiente'
    """).fetchall()

    reqs = {}
    for ln in lineas:
        factor = ln["cantidad"] * ln["porciones"]  # cajas × porciones

        # Todas las recetas de esa caja
        recetas = conn.execute(
            "SELECT receta_id FROM caja_recetas WHERE caja_id=?", (ln["caja_id"],)).fetchall()

        for rec in recetas:
            bom = conn.execute("""
                SELECT ri.ingrediente_id, ri.cantidad,
                       i.nombre, i.unidad, i.stock_actual, i.stock_minimo,
                       i.costo_unitario, i.proveedor_id,
                       COALESCE(pv.lead_time,1) lead_time
                FROM receta_ingredientes ri
                JOIN ingredientes i  ON i.id  = ri.ingrediente_id
                LEFT JOIN proveedores pv ON pv.id = i.proveedor_id
                WHERE ri.receta_id = ?
            """, (rec["receta_id"],)).fetchall()

            for row in bom:
                iid = row["ingrediente_id"]
                if iid not in reqs:
                    reqs[iid] = {
                        "nombre":       row["nombre"],
                        "unidad":       row["unidad"],
                        "stock":        row["stock_actual"],
                        "stock_min":    row["stock_minimo"],
                        "costo":        row["costo_unitario"],
                        "proveedor_id": row["proveedor_id"],
                        "lead_time":    row["lead_time"],
                        "requerido":    0,
                    }
                reqs[iid]["requerido"] += row["cantidad"] * factor

    for d in reqs.values():
        d["neto"]     = max(d["requerido"] - d["stock"], 0)
        d["faltante"] = d["neto"] > 0

    conn.close()
    return reqs


def generar_ordenes_compra(reqs, buffer_pct=0.10):
    hoy = datetime.now()
    por_proveedor = {}
    for iid, d in reqs.items():
        if not d["faltante"]:
            continue
        pv = d["proveedor_id"]
        por_proveedor.setdefault(pv, []).append({
            "ingrediente_id": iid,
            "nombre":   d["nombre"],
            "neto":     d["neto"],
            "cantidad": round(d["neto"] * (1 + buffer_pct), 4),
            "costo":    d["costo"],
            "lead_time":d["lead_time"],
        })

    ordenes = []
    with get_connection() as conn:
        for pv, items in por_proveedor.items():
            fecha = (hoy + timedelta(days=items[0]["lead_time"])).strftime("%Y-%m-%d")
            total = sum(i["cantidad"] * i["costo"] for i in items)
            cur = conn.execute("""
                INSERT INTO ordenes_compra (proveedor_id,fecha_emision,fecha_entrega_esperada,total)
                VALUES (?,?,?,?)
            """, (pv, hoy.strftime("%Y-%m-%d"), fecha, total))
            oid = cur.lastrowid
            for i in items:
                conn.execute("""
                    INSERT INTO orden_compra_detalle (orden_id,ingrediente_id,cantidad,costo_unitario)
                    VALUES (?,?,?,?)
                """, (oid, i["ingrediente_id"], i["cantidad"], i["costo"]))
            ordenes.append({"orden_id": oid, "proveedor_id": pv,
                            "items": items, "fecha": fecha, "total": total})
    return ordenes
