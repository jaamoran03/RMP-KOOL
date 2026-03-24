"""
mrp_engine.py — Motor MRP compatible con PostgreSQL (Supabase)
"""
from datetime import datetime, timedelta
from database import get_connection


def _exec(sql, params=(), fetch=None):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(sql, params)
    result = None
    if fetch == "all":
        result = [dict(r) for r in cur.fetchall()]
    elif fetch == "one":
        r = cur.fetchone()
        result = dict(r) if r else None
    conn.commit()
    cur.close()
    conn.close()
    return result

def _lastid(sql, params=()):
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute(sql + " RETURNING id", params)
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return row["id"] if row else None


# ── Proveedores ───────────────────────────────────────────────────────────────
def agregar_proveedor(nombre, contacto="", telefono="", email="", lead_time=1):
    return _lastid(
        "INSERT INTO proveedores (nombre,contacto,telefono,email,lead_time) VALUES (%s,%s,%s,%s,%s)",
        (nombre, contacto, telefono, email, lead_time))


# ── Ingredientes ──────────────────────────────────────────────────────────────
def agregar_ingrediente(nombre, tipo="fresco", unidad="unidad", stock_actual=0,
                        stock_minimo=0, costo_unitario=0, proveedor_id=None,
                        calorias=0, proteinas_g=0, vegetales=0):
    return _lastid("""
        INSERT INTO ingredientes
            (nombre,tipo,unidad,stock_actual,stock_minimo,costo_unitario,
             proveedor_id,calorias,proteinas_g,vegetales)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (nombre, tipo, unidad, stock_actual, stock_minimo, costo_unitario,
         proveedor_id, calorias, proteinas_g, vegetales))

def actualizar_stock(ingrediente_id, cantidad, tipo="entrada"):
    ing = _exec("SELECT stock_actual FROM ingredientes WHERE id=%s",
                (ingrediente_id,), fetch="one")
    delta = cantidad if tipo != "salida" else -cantidad
    nuevo = ing["stock_actual"] + delta
    _exec("UPDATE ingredientes SET stock_actual=%s WHERE id=%s", (nuevo, ingrediente_id))
    _exec("INSERT INTO movimientos_inventario (ingrediente_id,tipo,cantidad,fecha) VALUES (%s,%s,%s,%s)",
          (ingrediente_id, tipo, cantidad, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    return nuevo


# ── Recetas ───────────────────────────────────────────────────────────────────
def agregar_receta(nombre, descripcion=""):
    return _lastid("INSERT INTO recetas (nombre,descripcion) VALUES (%s,%s)",
                   (nombre, descripcion))

def agregar_ingrediente_receta(receta_id, ingrediente_id, cantidad):
    _exec("""INSERT INTO receta_ingredientes (receta_id,ingrediente_id,cantidad)
             VALUES (%s,%s,%s)
             ON CONFLICT (receta_id,ingrediente_id) DO UPDATE SET cantidad=EXCLUDED.cantidad""",
          (receta_id, ingrediente_id, cantidad))


# ── Cajas ─────────────────────────────────────────────────────────────────────
def agregar_caja(nombre, descripcion="", precio_venta=0):
    return _lastid("INSERT INTO cajas (nombre,descripcion,precio_venta) VALUES (%s,%s,%s)",
                   (nombre, descripcion, precio_venta))

def agregar_receta_a_caja(caja_id, receta_id):
    _exec("INSERT INTO caja_recetas (caja_id,receta_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
          (caja_id, receta_id))


# ── Menús ─────────────────────────────────────────────────────────────────────
def agregar_menu(nombre, descripcion="", categoria="nivel_medio", racion=2):
    return _lastid("INSERT INTO menus (nombre,descripcion,categoria,racion) VALUES (%s,%s,%s,%s)",
                   (nombre, descripcion, categoria, racion))

def agregar_receta_a_menu(menu_id, receta_id):
    _exec("INSERT INTO menu_recetas (menu_id,receta_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
          (menu_id, receta_id))


# ── Costeo ────────────────────────────────────────────────────────────────────
def calcular_costo_receta(receta_id, porciones=1):
    items = _exec("""
        SELECT ri.cantidad, i.costo_unitario, i.calorias, i.proteinas_g, i.vegetales
        FROM receta_ingredientes ri
        JOIN ingredientes i ON i.id=ri.ingrediente_id
        WHERE ri.receta_id=%s""", (receta_id,), fetch="all") or []
    return {
        "costo":     round(sum(r["cantidad"]*r["costo_unitario"]*porciones for r in items), 4),
        "calorias":  round(sum(r["cantidad"]*r["calorias"]*porciones for r in items), 2),
        "proteinas": round(sum(r["cantidad"]*r["proteinas_g"]*porciones for r in items), 2),
        "vegetales": sum(1 for r in items if r["vegetales"]),
        "items":     len(items),
    }

def calcular_costo_menu(menu_id, margen_pct=35, empaque=5.0):
    menu = _exec("SELECT * FROM menus WHERE id=%s", (menu_id,), fetch="one")
    if not menu: return None
    recetas = _exec("""SELECT r.id,r.nombre FROM menu_recetas mr
                       JOIN recetas r ON r.id=mr.receta_id WHERE mr.menu_id=%s""",
                    (menu_id,), fetch="all") or []
    racion = menu["racion"]
    costo_total = empaque; cal=0; prot=0; veg=0; detalle=[]
    for r in recetas:
        c = calcular_costo_receta(r["id"], porciones=racion)
        costo_total += c["costo"]; cal += c["calorias"]
        prot += c["proteinas"]; veg += c["vegetales"]
        detalle.append({"receta":r["nombre"],"costo":c["costo"],
                        "calorias":c["calorias"],"proteinas":c["proteinas"],"vegetales":c["vegetales"]})
    precio = round(costo_total*(1+margen_pct/100),2)
    return {
        "menu": menu, "racion": racion,
        "costo_ingredientes": round(costo_total-empaque,2),
        "costo_empaque": empaque, "costo_total": round(costo_total,2),
        "margen_pct": margen_pct, "precio_sugerido": precio,
        "ganancia": round(precio-costo_total,2),
        "costo_p_persona": round(costo_total/racion,2) if racion else 0,
        "precio_p_persona": round(precio/racion,2) if racion else 0,
        "calorias_total": round(cal,1), "proteinas_total": round(prot,1),
        "vegetales_total": veg, "detalle_recetas": detalle,
    }

def comparar_menus(filtro_categoria=None, filtro_racion=None, margen_pct=35, empaque=5.0):
    sql = "SELECT id FROM menus WHERE activo=1"
    params = []
    if filtro_categoria:
        sql += " AND categoria=%s"; params.append(filtro_categoria)
    if filtro_racion:
        sql += " AND racion=%s"; params.append(filtro_racion)
    ids = _exec(sql, params, fetch="all") or []
    resultados = [calcular_costo_menu(r["id"], margen_pct, empaque) for r in ids]
    resultados = [r for r in resultados if r]
    resultados.sort(key=lambda x: x["costo_total"])
    return resultados


# ── Pedidos ───────────────────────────────────────────────────────────────────
def crear_pedido(cliente, fecha_entrega, items):
    hoy = datetime.now().strftime("%Y-%m-%d")
    pedido_id = _lastid(
        "INSERT INTO pedidos (cliente,fecha_pedido,fecha_entrega) VALUES (%s,%s,%s)",
        (cliente, hoy, fecha_entrega))
    for it in items:
        _exec("INSERT INTO pedido_detalle (pedido_id,caja_id,cantidad,porciones) VALUES (%s,%s,%s,%s)",
              (pedido_id, it["caja_id"], it["cantidad"], it["porciones"]))
    return pedido_id


# ── Motor MRP ─────────────────────────────────────────────────────────────────
def calcular_requerimientos():
    lineas = _exec("""
        SELECT pd.caja_id, pd.cantidad, pd.porciones
        FROM pedidos p JOIN pedido_detalle pd ON pd.pedido_id=p.id
        WHERE p.estado='pendiente'""", fetch="all") or []
    reqs = {}
    for ln in lineas:
        factor  = ln["cantidad"] * ln["porciones"]
        recetas = _exec("SELECT receta_id FROM caja_recetas WHERE caja_id=%s",
                        (ln["caja_id"],), fetch="all") or []
        for rec in recetas:
            bom = _exec("""
                SELECT ri.ingrediente_id, ri.cantidad,
                       i.nombre, i.unidad, i.stock_actual, i.stock_minimo,
                       i.costo_unitario, i.proveedor_id,
                       COALESCE(pv.lead_time,1) lead_time
                FROM receta_ingredientes ri
                JOIN ingredientes i ON i.id=ri.ingrediente_id
                LEFT JOIN proveedores pv ON pv.id=i.proveedor_id
                WHERE ri.receta_id=%s""", (rec["receta_id"],), fetch="all") or []
            for row in bom:
                iid = row["ingrediente_id"]
                if iid not in reqs:
                    reqs[iid] = {
                        "nombre": row["nombre"], "unidad": row["unidad"],
                        "stock": row["stock_actual"], "stock_min": row["stock_minimo"],
                        "costo": row["costo_unitario"], "proveedor_id": row["proveedor_id"],
                        "lead_time": row["lead_time"], "requerido": 0,
                    }
                reqs[iid]["requerido"] += row["cantidad"] * factor
    for d in reqs.values():
        d["neto"] = max(d["requerido"]-d["stock"], 0)
        d["faltante"] = d["neto"] > 0
    return reqs

def generar_ordenes_compra(reqs, buffer_pct=0.10):
    hoy = datetime.now()
    por_proveedor = {}
    for iid, d in reqs.items():
        if not d["faltante"]: continue
        pv = d["proveedor_id"]
        por_proveedor.setdefault(pv, []).append({
            "ingrediente_id": iid, "nombre": d["nombre"],
            "neto": d["neto"], "cantidad": round(d["neto"]*(1+buffer_pct),4),
            "costo": d["costo"], "lead_time": d["lead_time"],
        })
    ordenes = []
    for pv, items in por_proveedor.items():
        fecha = (hoy+timedelta(days=items[0]["lead_time"])).strftime("%Y-%m-%d")
        total = sum(i["cantidad"]*i["costo"] for i in items)
        oid   = _lastid("""INSERT INTO ordenes_compra
                           (proveedor_id,fecha_emision,fecha_entrega_esperada,total)
                           VALUES (%s,%s,%s,%s)""",
                        (pv, hoy.strftime("%Y-%m-%d"), fecha, total))
        for i in items:
            _exec("""INSERT INTO orden_compra_detalle
                     (orden_id,ingrediente_id,cantidad,costo_unitario) VALUES (%s,%s,%s,%s)""",
                  (oid, i["ingrediente_id"], i["cantidad"], i["costo"]))
        ordenes.append({"orden_id":oid,"proveedor_id":pv,
                        "items":items,"fecha":fecha,"total":total})
    return ordenes
