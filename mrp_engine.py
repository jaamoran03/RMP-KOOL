"""
mrp_engine.py — Motor MRP + Menús + Costeo de paquetes
"""
from datetime import datetime, timedelta
from database import get_connection


# ── Proveedores ───────────────────────────────────────────────────────────────
def agregar_proveedor(nombre, contacto="", telefono="", email="", lead_time=1):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO proveedores (nombre,contacto,telefono,email,lead_time) VALUES (?,?,?,?,?)",
            (nombre, contacto, telefono, email, lead_time))
        return cur.lastrowid


# ── Ingredientes ──────────────────────────────────────────────────────────────
def agregar_ingrediente(nombre, tipo="fresco", unidad="unidad", stock_actual=0,
                        stock_minimo=0, costo_unitario=0, proveedor_id=None,
                        calorias=0, proteinas_g=0, vegetales=0):
    with get_connection() as conn:
        cur = conn.execute("""
            INSERT INTO ingredientes
                (nombre,tipo,unidad,stock_actual,stock_minimo,costo_unitario,
                 proveedor_id,calorias,proteinas_g,vegetales)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (nombre, tipo, unidad, stock_actual, stock_minimo, costo_unitario,
              proveedor_id, calorias, proteinas_g, vegetales))
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


# ── Recetas ───────────────────────────────────────────────────────────────────
def agregar_receta(nombre, descripcion=""):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO recetas (nombre,descripcion) VALUES (?,?)", (nombre, descripcion))
        return cur.lastrowid

def agregar_ingrediente_receta(receta_id, ingrediente_id, cantidad):
    with get_connection() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO receta_ingredientes (receta_id,ingrediente_id,cantidad)
            VALUES (?,?,?)""", (receta_id, ingrediente_id, cantidad))


# ── Cajas ─────────────────────────────────────────────────────────────────────
def agregar_caja(nombre, descripcion="", precio_venta=0):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO cajas (nombre,descripcion,precio_venta) VALUES (?,?,?)",
            (nombre, descripcion, precio_venta))
        return cur.lastrowid

def agregar_receta_a_caja(caja_id, receta_id):
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO caja_recetas (caja_id,receta_id) VALUES (?,?)",
                     (caja_id, receta_id))


# ── Menús ─────────────────────────────────────────────────────────────────────
def agregar_menu(nombre, descripcion="", categoria="nivel_medio", racion=2):
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO menus (nombre,descripcion,categoria,racion) VALUES (?,?,?,?)",
            (nombre, descripcion, categoria, racion))
        return cur.lastrowid

def agregar_receta_a_menu(menu_id, receta_id):
    with get_connection() as conn:
        conn.execute("INSERT OR IGNORE INTO menu_recetas (menu_id,receta_id) VALUES (?,?)",
                     (menu_id, receta_id))

def get_menu_recetas(menu_id):
    with get_connection() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT r.id, r.nombre, r.descripcion FROM menu_recetas mr
            JOIN recetas r ON r.id=mr.receta_id WHERE mr.menu_id=?""", (menu_id,)).fetchall()]


# ── Costeo de receta ──────────────────────────────────────────────────────────
def calcular_costo_receta(receta_id, porciones=1):
    """
    Calcula costo, calorías, proteínas y cuenta vegetales de una receta
    multiplicado por el número de porciones.
    """
    with get_connection() as conn:
        items = conn.execute("""
            SELECT ri.cantidad, i.costo_unitario, i.calorias, i.proteinas_g, i.vegetales, i.nombre
            FROM receta_ingredientes ri
            JOIN ingredientes i ON i.id=ri.ingrediente_id
            WHERE ri.receta_id=?""", (receta_id,)).fetchall()

    costo      = sum(r["cantidad"] * r["costo_unitario"] * porciones for r in items)
    calorias   = sum(r["cantidad"] * r["calorias"]   * porciones for r in items)
    proteinas  = sum(r["cantidad"] * r["proteinas_g"] * porciones for r in items)
    n_veg      = sum(1 for r in items if r["vegetales"])

    return {
        "costo":     round(costo, 4),
        "calorias":  round(calorias, 2),
        "proteinas": round(proteinas, 2),
        "vegetales": n_veg,
        "items":     len(items),
    }


# ── Costeo de menú (paquete completo) ────────────────────────────────────────
def calcular_costo_menu(menu_id, margen_pct=35, empaque=5.0):
    """
    Calcula el costo total del menú (todas sus recetas × ración),
    margen de ganancia, precio sugerido y perfil nutricional.

    margen_pct : % de ganancia sobre el costo
    empaque    : costo fijo de empaque/caja
    """
    with get_connection() as conn:
        menu = conn.execute("SELECT * FROM menus WHERE id=?", (menu_id,)).fetchone()
        if not menu:
            return None
        menu = dict(menu)
        recetas = conn.execute("""
            SELECT r.id, r.nombre FROM menu_recetas mr
            JOIN recetas r ON r.id=mr.receta_id WHERE mr.menu_id=?""", (menu_id,)).fetchall()

    racion       = menu["racion"]
    costo_total  = empaque
    cal_total    = 0
    prot_total   = 0
    veg_total    = 0
    detalle      = []

    for r in recetas:
        c = calcular_costo_receta(r["id"], porciones=racion)
        costo_total += c["costo"]
        cal_total   += c["calorias"]
        prot_total  += c["proteinas"]
        veg_total   += c["vegetales"]
        detalle.append({
            "receta":    r["nombre"],
            "costo":     c["costo"],
            "calorias":  c["calorias"],
            "proteinas": c["proteinas"],
            "vegetales": c["vegetales"],
        })

    precio_sugerido = round(costo_total * (1 + margen_pct / 100), 2)
    costo_p_persona = round(costo_total / racion, 2) if racion else 0
    precio_p_persona = round(precio_sugerido / racion, 2) if racion else 0

    return {
        "menu":             menu,
        "racion":           racion,
        "costo_ingredientes": round(costo_total - empaque, 2),
        "costo_empaque":    empaque,
        "costo_total":      round(costo_total, 2),
        "margen_pct":       margen_pct,
        "precio_sugerido":  precio_sugerido,
        "ganancia":         round(precio_sugerido - costo_total, 2),
        "costo_p_persona":  costo_p_persona,
        "precio_p_persona": precio_p_persona,
        "calorias_total":   round(cal_total, 1),
        "proteinas_total":  round(prot_total, 1),
        "vegetales_total":  veg_total,
        "detalle_recetas":  detalle,
    }


# ── Comparador de menús ───────────────────────────────────────────────────────
def comparar_menus(filtro_categoria=None, filtro_racion=None, margen_pct=35, empaque=5.0):
    """
    Devuelve lista de todos los menús activos con su costeo completo,
    opcionalmente filtrada por categoría y/o ración.
    """
    with get_connection() as conn:
        sql = "SELECT id FROM menus WHERE activo=1"
        params = []
        if filtro_categoria:
            sql += " AND categoria=?"; params.append(filtro_categoria)
        if filtro_racion:
            sql += " AND racion=?"; params.append(filtro_racion)
        ids = [r["id"] for r in conn.execute(sql, params).fetchall()]

    resultados = []
    for mid in ids:
        c = calcular_costo_menu(mid, margen_pct, empaque)
        if c:
            resultados.append(c)

    # Ordenar por costo ascendente
    resultados.sort(key=lambda x: x["costo_total"])
    return resultados


# ── Pedidos ───────────────────────────────────────────────────────────────────
def crear_pedido(cliente, fecha_entrega, items):
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


# ── Motor MRP ─────────────────────────────────────────────────────────────────
def calcular_requerimientos():
    conn = get_connection()
    lineas = conn.execute("""
        SELECT pd.caja_id, pd.cantidad, pd.porciones
        FROM pedidos p JOIN pedido_detalle pd ON pd.pedido_id=p.id
        WHERE p.estado='pendiente'""").fetchall()

    reqs = {}
    for ln in lineas:
        factor  = ln["cantidad"] * ln["porciones"]
        recetas = conn.execute(
            "SELECT receta_id FROM caja_recetas WHERE caja_id=?", (ln["caja_id"],)).fetchall()

        for rec in recetas:
            bom = conn.execute("""
                SELECT ri.ingrediente_id, ri.cantidad,
                       i.nombre, i.unidad, i.stock_actual, i.stock_minimo,
                       i.costo_unitario, i.proveedor_id,
                       COALESCE(pv.lead_time,1) lead_time
                FROM receta_ingredientes ri
                JOIN ingredientes i  ON i.id=ri.ingrediente_id
                LEFT JOIN proveedores pv ON pv.id=i.proveedor_id
                WHERE ri.receta_id=?""", (rec["receta_id"],)).fetchall()

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
        if not d["faltante"]: continue
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
            cur   = conn.execute("""
                INSERT INTO ordenes_compra (proveedor_id,fecha_emision,fecha_entrega_esperada,total)
                VALUES (?,?,?,?)""", (pv, hoy.strftime("%Y-%m-%d"), fecha, total))
            oid = cur.lastrowid
            for i in items:
                conn.execute("""
                    INSERT INTO orden_compra_detalle (orden_id,ingrediente_id,cantidad,costo_unitario)
                    VALUES (?,?,?,?)""", (oid, i["ingrediente_id"], i["cantidad"], i["costo"]))
            ordenes.append({"orden_id": oid, "proveedor_id": pv,
                            "items": items, "fecha": fecha, "total": total})
    return ordenes
