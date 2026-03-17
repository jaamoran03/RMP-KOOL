"""
app.py — MRP Cajas de Alimentos Delivery
App Streamlit: corre con `streamlit run app.py`
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import init_db, get_connection
from mrp_engine import (
    agregar_proveedor, agregar_ingrediente, agregar_receta,
    agregar_ingrediente_receta, agregar_caja, agregar_receta_a_caja,
    crear_pedido, calcular_requerimientos, generar_ordenes_compra,
)

# ── Configuración de la app ───────────────────────────────────────────────────
st.set_page_config(
    page_title="MRP — Cajas Delivery",
    page_icon="🥗",
    layout="wide",
)

init_db()

# ── Helpers DB ────────────────────────────────────────────────────────────────
def Q(sql, p=()):
    with get_connection() as c:
        return [dict(r) for r in c.execute(sql, p).fetchall()]

def get_proveedores():
    return Q("SELECT id, nombre, contacto, telefono, email, lead_time FROM proveedores WHERE activo=1")

def get_ingredientes():
    return Q("""SELECT i.*, COALESCE(p.nombre,'—') proveedor
                FROM ingredientes i LEFT JOIN proveedores p ON p.id=i.proveedor_id""")

def get_recetas():
    return Q("SELECT * FROM recetas WHERE activa=1")

def get_cajas():
    return Q("SELECT * FROM cajas WHERE activa=1")

def get_bom(rid):
    return Q("""SELECT ri.cantidad, i.nombre, i.unidad, i.costo_unitario,
                       COALESCE(p.nombre,'—') proveedor
                FROM receta_ingredientes ri
                JOIN ingredientes i ON i.id=ri.ingrediente_id
                LEFT JOIN proveedores p ON p.id=i.proveedor_id
                WHERE ri.receta_id=?""", (rid,))

def get_caja_recetas(cid):
    return Q("""SELECT r.id, r.nombre FROM caja_recetas cr
                JOIN recetas r ON r.id=cr.receta_id WHERE cr.caja_id=?""", (cid,))

def get_pedidos():
    return Q("""SELECT p.id, p.cliente, p.fecha_entrega, p.estado,
                       c.nombre caja, pd.cantidad, pd.porciones
                FROM pedidos p JOIN pedido_detalle pd ON pd.pedido_id=p.id
                JOIN cajas c ON c.id=pd.caja_id
                WHERE p.estado='pendiente' ORDER BY p.fecha_entrega""")

# ── Estilos ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] { background: #0d1b2a; }
[data-testid="stSidebar"] * { color: #e8f5e9 !important; }
.main-header {
    background: linear-gradient(120deg, #0d1b2a, #1b4332);
    color: #e8f5e9; padding: 20px 28px; border-radius: 12px; margin-bottom: 20px;
}
.main-header h1 { margin: 0; font-size: 1.6rem; }
.main-header p  { margin: 4px 0 0; opacity: .65; font-size: .85rem; }
.metric-card {
    background: #fff; border: 1px solid #e2e8f0;
    border-radius: 10px; padding: 14px 18px; text-align: center;
}
.metric-num { font-size: 2rem; font-weight: 700; color: #1b4332; }
.metric-lbl { font-size: .78rem; color: #64748b; }
.badge-ok   { background:#dcfce7; color:#166534; padding:2px 10px;
              border-radius:20px; font-size:.75rem; font-weight:600; }
.badge-err  { background:#fee2e2; color:#991b1b; padding:2px 10px;
              border-radius:20px; font-size:.75rem; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class='main-header'>
  <h1>🥗 MRP — Cajas de Alimentos Delivery</h1>
  <p>Gestión de recetas · ingredientes · proveedores · pedidos · planificación de materiales</p>
</div>
""", unsafe_allow_html=True)

# ── Navegación ────────────────────────────────────────────────────────────────
pagina = st.sidebar.radio("Navegación", [
    "📦 Proveedores",
    "🥬 Ingredientes",
    "📋 Recetas / BOM",
    "📦 Cajas",
    "📬 Pedidos",
    "⚙️ MRP",
])

# ══════════════════════════════════════════════════════════════════════════════
# PROVEEDORES
# ══════════════════════════════════════════════════════════════════════════════
if pagina == "📦 Proveedores":
    st.subheader("📦 Proveedores")

    with st.expander("➕ Agregar nuevo proveedor", expanded=False):
        c1, c2, c3 = st.columns(3)
        pn = c1.text_input("Nombre *")
        pc = c2.text_input("Contacto")
        pt = c3.text_input("Teléfono")
        c4, c5 = st.columns(2)
        pe = c4.text_input("Email")
        pl = c5.number_input("Lead time (días)", min_value=1, max_value=60, value=2)
        if st.button("💾 Guardar proveedor", type="primary"):
            if not pn.strip():
                st.error("El nombre es obligatorio.")
            else:
                agregar_proveedor(pn.strip(), pc.strip(), pt.strip(), pe.strip(), int(pl))
                st.success(f"✅ Proveedor **{pn}** guardado.")
                st.rerun()

    rows = get_proveedores()
    if rows:
        df = pd.DataFrame(rows)
        df.columns = ["#", "Nombre", "Contacto", "Teléfono", "Email", "Lead time (días)"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No hay proveedores registrados aún.")

# ══════════════════════════════════════════════════════════════════════════════
# INGREDIENTES
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "🥬 Ingredientes":
    st.subheader("🥬 Ingredientes")

    provs = get_proveedores()
    prov_opts = {p["nombre"]: p["id"] for p in provs}

    with st.expander("➕ Agregar nuevo ingrediente", expanded=False):
        c1, c2, c3 = st.columns(3)
        i_nombre = c1.text_input("Nombre *")
        i_tipo   = c2.selectbox("Tipo", ["fresco", "condimento", "empaque", "otro"])
        i_unidad = c3.text_input("Unidad (kg, litro, unidad…)")
        c4, c5, c6, c7 = st.columns(4)
        i_stock  = c4.number_input("Stock actual", min_value=0.0, step=0.1)
        i_stockm = c5.number_input("Stock mínimo", min_value=0.0, step=0.1)
        i_costo  = c6.number_input("Costo unitario Q", min_value=0.0, step=0.5)
        i_prov   = c7.selectbox("Proveedor", ["— Sin proveedor —"] + list(prov_opts.keys()))
        if st.button("💾 Guardar ingrediente", type="primary"):
            if not i_nombre.strip():
                st.error("El nombre es obligatorio.")
            else:
                pv_id = prov_opts.get(i_prov)
                agregar_ingrediente(i_nombre.strip(), i_tipo, i_unidad.strip(),
                                    i_stock, i_stockm, i_costo, pv_id)
                st.success(f"✅ Ingrediente **{i_nombre}** guardado.")
                st.rerun()

    rows = get_ingredientes()
    if rows:
        df = pd.DataFrame(rows)[["id","nombre","tipo","unidad","stock_actual","stock_minimo","costo_unitario","proveedor"]]
        df.columns = ["#","Nombre","Tipo","Unidad","Stock actual","Stock mínimo","Costo Q","Proveedor"]
        # Marcar en rojo los que están bajo mínimo
        def color_stock(row):
            if row["Stock actual"] <= row["Stock mínimo"]:
                return ["background-color:#fee2e2"] * len(row)
            return [""] * len(row)
        st.dataframe(df.style.apply(color_stock, axis=1), use_container_width=True, hide_index=True)
        st.caption("🔴 Rojo = stock igual o bajo el mínimo")
    else:
        st.info("No hay ingredientes registrados.")

# ══════════════════════════════════════════════════════════════════════════════
# RECETAS / BOM
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📋 Recetas / BOM":
    st.subheader("📋 Recetas / BOM")

    tab_ver, tab_nueva, tab_bom = st.tabs(["📄 Ver recetas", "➕ Nueva receta", "🧾 Editar BOM"])

    with tab_nueva:
        c1, c2 = st.columns(2)
        rn = c1.text_input("Nombre de la receta *")
        rd = c2.text_input("Descripción")
        if st.button("💾 Crear receta", type="primary"):
            if not rn.strip():
                st.error("El nombre es obligatorio.")
            else:
                agregar_receta(rn.strip(), rd.strip())
                st.success(f"✅ Receta **{rn}** creada.")
                st.rerun()

    with tab_ver:
        recetas = get_recetas()
        if recetas:
            for r in recetas:
                bom = get_bom(r["id"])
                costo = sum(b["cantidad"] * b["costo_unitario"] for b in bom)
                with st.expander(f"**{r['nombre']}** — {len(bom)} ingredientes | Costo/porción: Q {costo:.2f}"):
                    if bom:
                        df = pd.DataFrame(bom)[["nombre","cantidad","unidad","costo_unitario","proveedor"]]
                        df.columns = ["Ingrediente","Cantidad/porción","Unidad","Costo unit.","Proveedor"]
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    else:
                        st.warning("Sin ingredientes. Agrégalos en la pestaña 'Editar BOM'.")
        else:
            st.info("No hay recetas. Crea una en la pestaña '➕ Nueva receta'.")

    with tab_bom:
        recetas = get_recetas()
        ings    = get_ingredientes()
        if not recetas:
            st.warning("Primero crea una receta.")
        elif not ings:
            st.warning("Primero agrega ingredientes.")
        else:
            rec_opts = {r["nombre"]: r["id"] for r in recetas}
            ing_opts = {f"{i['nombre']} ({i['unidad']})": i["id"] for i in ings}
            sel_rec  = st.selectbox("Selecciona la receta", list(rec_opts.keys()))
            c1, c2  = st.columns(2)
            sel_ing  = c1.selectbox("Ingrediente", list(ing_opts.keys()))
            cantidad = c2.number_input("Cantidad por porción", min_value=0.0, step=0.1, value=1.0)
            if st.button("➕ Agregar al BOM", type="primary"):
                agregar_ingrediente_receta(rec_opts[sel_rec], ing_opts[sel_ing], cantidad)
                st.success("✅ Ingrediente agregado.")
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# CAJAS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📦 Cajas":
    st.subheader("📦 Cajas")

    tab_ver, tab_nueva, tab_rec = st.tabs(["📄 Ver cajas", "➕ Nueva caja", "🔗 Asignar recetas"])

    with tab_nueva:
        c1, c2, c3 = st.columns(3)
        cn = c1.text_input("Nombre *")
        cd = c2.text_input("Descripción")
        cp = c3.number_input("Precio de venta Q", min_value=0.0, step=5.0)
        if st.button("💾 Crear caja", type="primary"):
            if not cn.strip():
                st.error("El nombre es obligatorio.")
            else:
                agregar_caja(cn.strip(), cd.strip(), cp)
                st.success(f"✅ Caja **{cn}** creada.")
                st.rerun()

    with tab_ver:
        cajas = get_cajas()
        if cajas:
            for c in cajas:
                recs = get_caja_recetas(c["id"])
                nombres_rec = ", ".join(r["nombre"] for r in recs) if recs else "Sin recetas"
                with st.expander(f"**{c['nombre']}** — Q {c['precio_venta']:.2f} | {len(recs)} recetas"):
                    st.write(f"**Descripción:** {c['descripcion']}")
                    st.write(f"**Recetas:** {nombres_rec}")
        else:
            st.info("No hay cajas registradas.")

    with tab_rec:
        cajas   = get_cajas()
        recetas = get_recetas()
        if not cajas:
            st.warning("Primero crea una caja.")
        elif not recetas:
            st.warning("Primero crea recetas.")
        else:
            caja_opts = {c["nombre"]: c["id"] for c in cajas}
            rec_opts  = {r["nombre"]: r["id"] for r in recetas}
            sel_caja  = st.selectbox("Selecciona la caja", list(caja_opts.keys()))
            sel_rec   = st.selectbox("Receta a agregar", list(rec_opts.keys()))

            # Mostrar recetas actuales
            actuales = get_caja_recetas(caja_opts[sel_caja])
            if actuales:
                st.write("**Recetas actuales en esta caja:**")
                for r in actuales:
                    st.write(f"  • {r['nombre']}")

            if st.button("➕ Agregar receta a la caja", type="primary"):
                agregar_receta_a_caja(caja_opts[sel_caja], rec_opts[sel_rec])
                st.success("✅ Receta agregada.")
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PEDIDOS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📬 Pedidos":
    st.subheader("📬 Pedidos")

    cajas = get_cajas()

    with st.expander("➕ Nuevo pedido", expanded=True):
        if not cajas:
            st.warning("Primero crea cajas.")
        else:
            c1, c2 = st.columns(2)
            cliente   = c1.text_input("Cliente *")
            fecha_ent = c2.date_input("Fecha de entrega", min_value=date.today())

            st.markdown("**Cajas del pedido:**")
            st.caption("💡 Las *porciones* aplican igual para todas las recetas de la caja.")
            caja_opts = {c["nombre"]: c["id"] for c in cajas}

            if "items_pedido" not in st.session_state:
                st.session_state.items_pedido = []

            c1, c2, c3 = st.columns(3)
            sel_caja  = c1.selectbox("Caja", list(caja_opts.keys()))
            cantidad  = c2.number_input("Cantidad de cajas", min_value=1, value=1)
            porciones = c3.number_input("Porciones por receta", min_value=0.5, value=1.0, step=0.5)

            col1, col2 = st.columns([1, 3])
            if col1.button("➕ Agregar ítem"):
                st.session_state.items_pedido.append({
                    "caja_id":   caja_opts[sel_caja],
                    "nombre":    sel_caja,
                    "cantidad":  cantidad,
                    "porciones": porciones,
                })
            if col2.button("🗑 Limpiar ítems"):
                st.session_state.items_pedido = []

            if st.session_state.items_pedido:
                df_items = pd.DataFrame(st.session_state.items_pedido)[["nombre","cantidad","porciones"]]
                df_items["Factor MRP"] = df_items["cantidad"] * df_items["porciones"]
                df_items.columns = ["Caja","Cajas","Porciones","Factor MRP"]
                st.dataframe(df_items, use_container_width=True, hide_index=True)

                if st.button("💾 Guardar pedido", type="primary"):
                    if not cliente.strip():
                        st.error("El cliente es obligatorio.")
                    else:
                        items = [{"caja_id": i["caja_id"], "cantidad": i["cantidad"],
                                  "porciones": i["porciones"]}
                                 for i in st.session_state.items_pedido]
                        pid = crear_pedido(cliente.strip(), fecha_ent.strftime("%Y-%m-%d"), items)
                        st.success(f"✅ Pedido #{pid} guardado para **{cliente}**.")
                        st.session_state.items_pedido = []
                        st.rerun()

    st.markdown("---")
    st.markdown("**Pedidos pendientes:**")
    rows = get_pedidos()
    if rows:
        df = pd.DataFrame(rows)[["id","cliente","caja","cantidad","porciones","fecha_entrega"]]
        df.columns = ["#","Cliente","Caja","Cajas","Porciones","Fecha entrega"]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.success("✅ No hay pedidos pendientes.")

# ══════════════════════════════════════════════════════════════════════════════
# MRP
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "⚙️ MRP":
    st.subheader("⚙️ Cálculo MRP")

    col1, col2 = st.columns([2, 1])
    buffer = col2.slider("Buffer de seguridad %", 0, 50, 10)

    if col1.button("⚙️ Calcular requerimientos", type="primary", use_container_width=True):
        reqs = calcular_requerimientos()
        st.session_state.mrp_reqs = reqs

    if "mrp_reqs" in st.session_state and st.session_state.mrp_reqs:
        reqs = st.session_state.mrp_reqs
        falta = [d for d in reqs.values() if d["faltante"]]
        ok_   = [d for d in reqs.values() if not d["faltante"]]
        costo = sum(d["neto"] * d["costo"] for d in falta)

        # Métricas
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Ingredientes analizados", len(reqs))
        m2.metric("⚠ Con faltante",  len(falta))
        m3.metric("✅ Stock OK",      len(ok_))
        m4.metric("Costo estimado",   f"Q {costo:.2f}")

        st.markdown("---")

        # Tabla de requerimientos
        rows = []
        for iid, d in sorted(reqs.items(), key=lambda x: (-x[1]["faltante"], x[1]["nombre"])):
            rows.append({
                "Ingrediente":    d["nombre"],
                "Requerido":      f"{d['requerido']:.3f} {d['unidad']}",
                "Stock actual":   d["stock"],
                "Neto faltante":  d["neto"] if d["faltante"] else 0,
                "Costo compra Q": round(d["neto"] * d["costo"], 2) if d["faltante"] else 0,
                "Estado":         "⚠ FALTA" if d["faltante"] else "✅ OK",
            })
        df = pd.DataFrame(rows)

        def color_estado(row):
            if row["Estado"] == "⚠ FALTA":
                return ["background-color:#fee2e2"] * len(row)
            return ["background-color:#f0fdf4"] * len(row)

        st.dataframe(df.style.apply(color_estado, axis=1),
                     use_container_width=True, hide_index=True)

        st.markdown("---")

        if st.button("📋 Generar Órdenes de Compra", type="primary", use_container_width=True):
            ordenes = generar_ordenes_compra(reqs, buffer_pct=buffer/100)
            if not ordenes:
                st.success("✅ No se necesitan órdenes de compra. Stock suficiente.")
            else:
                for o in ordenes:
                    pv = Q("SELECT nombre FROM proveedores WHERE id=?", (o["proveedor_id"],))
                    pnombre = pv[0]["nombre"] if pv else "Sin proveedor"
                    with st.expander(f"📋 Orden #{o['orden_id']} — {pnombre} | Total: Q {o['total']:.2f}", expanded=True):
                        st.write(f"**Entrega esperada:** {o['fecha']}")
                        items_df = pd.DataFrame(o["items"])[["nombre","neto","cantidad","costo"]]
                        items_df["subtotal"] = items_df["cantidad"] * items_df["costo"]
                        items_df.columns = ["Ingrediente", "Neto", f"Con buffer {buffer}%", "Costo unit.", "Subtotal Q"]
                        st.dataframe(items_df, use_container_width=True, hide_index=True)

    elif "mrp_reqs" in st.session_state and not st.session_state.mrp_reqs:
        st.warning("⚠ No hay pedidos pendientes para calcular.")
