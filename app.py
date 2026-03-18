"""
app.py — MRP Cajas de Alimentos Delivery
Editar y eliminar en todas las secciones.
"""
import streamlit as st
import pandas as pd
from datetime import date
from database import init_db, get_connection
from mrp_engine import (
    agregar_proveedor, agregar_ingrediente, agregar_receta,
    agregar_ingrediente_receta, agregar_caja, agregar_receta_a_caja,
    crear_pedido, calcular_requerimientos, generar_ordenes_compra,
    actualizar_stock,
)

st.set_page_config(page_title="MRP — Cajas Delivery", page_icon="🥗", layout="wide")
init_db()

def Q(sql, p=()):
    with get_connection() as c:
        return [dict(r) for r in c.execute(sql, p).fetchall()]

def get_proveedores():
    return Q("SELECT id,nombre,contacto,telefono,email,lead_time FROM proveedores WHERE activo=1")

def get_ingredientes():
    return Q("""SELECT i.*,COALESCE(p.nombre,'—') proveedor
                FROM ingredientes i LEFT JOIN proveedores p ON p.id=i.proveedor_id""")

def get_recetas():
    return Q("SELECT * FROM recetas WHERE activa=1")

def get_cajas():
    return Q("SELECT * FROM cajas WHERE activa=1")

def get_bom(rid):
    return Q("""SELECT ri.id, ri.cantidad, i.id ing_id, i.nombre, i.unidad,
                       i.costo_unitario, COALESCE(p.nombre,'—') proveedor
                FROM receta_ingredientes ri
                JOIN ingredientes i ON i.id=ri.ingrediente_id
                LEFT JOIN proveedores p ON p.id=i.proveedor_id
                WHERE ri.receta_id=?""", (rid,))

def get_caja_recetas(cid):
    return Q("""SELECT cr.id, r.id rec_id, r.nombre FROM caja_recetas cr
                JOIN recetas r ON r.id=cr.receta_id WHERE cr.caja_id=?""", (cid,))

def get_pedidos():
    return Q("""SELECT p.id,p.cliente,p.fecha_entrega,p.estado,
                       c.nombre caja,pd.cantidad,pd.porciones,pd.id pd_id
                FROM pedidos p JOIN pedido_detalle pd ON pd.pedido_id=p.id
                JOIN cajas c ON c.id=pd.caja_id
                ORDER BY p.fecha_entrega""")

st.markdown("""
<style>
[data-testid="stSidebar"]{background:#0d1b2a}
[data-testid="stSidebar"] *{color:#e8f5e9!important}
.hdr{background:linear-gradient(120deg,#0d1b2a,#1b4332);color:#e8f5e9;
     padding:20px 28px;border-radius:12px;margin-bottom:20px}
.hdr h1{margin:0;font-size:1.6rem}
.hdr p{margin:4px 0 0;opacity:.65;font-size:.85rem}
</style>
""", unsafe_allow_html=True)

st.markdown("""<div class='hdr'>
<h1>🥗 MRP — Cajas de Alimentos Delivery</h1>
<p>Gestión de recetas · ingredientes · proveedores · pedidos · planificación</p>
</div>""", unsafe_allow_html=True)

pagina = st.sidebar.radio("Navegación", [
    "📦 Proveedores","🥬 Ingredientes","📋 Recetas / BOM",
    "📦 Cajas","📬 Pedidos","⚙️ MRP"])

# ══════════════════════════════════════════════════════════════════════════════
# PROVEEDORES
# ══════════════════════════════════════════════════════════════════════════════
if pagina == "📦 Proveedores":
    st.subheader("📦 Proveedores")
    tab_ver, tab_nuevo, tab_editar = st.tabs(["📄 Ver todos","➕ Nuevo","✏️ Editar / Eliminar"])

    with tab_nuevo:
        c1,c2,c3 = st.columns(3)
        pn=c1.text_input("Nombre *"); pc=c2.text_input("Contacto"); pt=c3.text_input("Teléfono")
        c4,c5 = st.columns(2)
        pe=c4.text_input("Email"); pl=c5.number_input("Lead time (días)",min_value=1,max_value=60,value=2)
        if st.button("💾 Guardar proveedor",type="primary"):
            if not pn.strip(): st.error("Nombre obligatorio.")
            else:
                agregar_proveedor(pn.strip(),pc.strip(),pt.strip(),pe.strip(),int(pl))
                st.success(f"✅ **{pn}** guardado."); st.rerun()

    with tab_ver:
        rows=get_proveedores()
        if rows:
            df=pd.DataFrame(rows); df.columns=["#","Nombre","Contacto","Teléfono","Email","Lead time (días)"]
            st.dataframe(df,use_container_width=True,hide_index=True)
        else: st.info("Sin proveedores.")

    with tab_editar:
        rows=get_proveedores()
        if not rows: st.info("Sin proveedores.")
        else:
            opts={f"{p['nombre']}":p for p in rows}
            sel=st.selectbox("Selecciona proveedor",list(opts.keys())); pv=opts[sel]
            st.markdown("---")
            c1,c2,c3=st.columns(3)
            en=c1.text_input("Nombre",value=pv["nombre"]); ec=c2.text_input("Contacto",value=pv["contacto"]); et=c3.text_input("Teléfono",value=pv["telefono"])
            c4,c5=st.columns(2)
            ee=c4.text_input("Email",value=pv["email"]); el=c5.number_input("Lead time",min_value=1,max_value=60,value=int(pv["lead_time"]))
            col1,col2=st.columns(2)
            if col1.button("💾 Guardar cambios",type="primary"):
                with get_connection() as conn:
                    conn.execute("UPDATE proveedores SET nombre=?,contacto=?,telefono=?,email=?,lead_time=? WHERE id=?",
                                 (en.strip(),ec.strip(),et.strip(),ee.strip(),int(el),pv["id"]))
                st.success(f"✅ **{en}** actualizado."); st.rerun()
            if col2.button("🗑 Eliminar",type="secondary"):
                with get_connection() as conn:
                    conn.execute("UPDATE proveedores SET activo=0 WHERE id=?",(pv["id"],))
                st.warning(f"🗑 **{pv['nombre']}** eliminado."); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# INGREDIENTES
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "🥬 Ingredientes":
    st.subheader("🥬 Ingredientes")
    provs=get_proveedores(); prov_opts={p["nombre"]:p["id"] for p in provs}
    prov_lista=["— Sin proveedor —"]+list(prov_opts.keys())

    tab_ver,tab_nuevo,tab_editar,tab_stock=st.tabs(["📄 Ver todos","➕ Nuevo","✏️ Editar","📦 Stock"])

    with tab_ver:
        rows=get_ingredientes()
        if rows:
            df=pd.DataFrame(rows)[["id","nombre","tipo","unidad","stock_actual","stock_minimo","costo_unitario","proveedor"]]
            df.columns=["#","Nombre","Tipo","Unidad","Stock actual","Stock mínimo","Costo Q","Proveedor"]
            def cs(row): return ["background-color:#fee2e2"]*len(row) if row["Stock actual"]<=row["Stock mínimo"] else [""]*len(row)
            st.dataframe(df.style.apply(cs,axis=1),use_container_width=True,hide_index=True)
            st.caption("🔴 Rojo = stock igual o bajo el mínimo")
        else: st.info("Sin ingredientes.")

    with tab_nuevo:
        c1,c2,c3=st.columns(3)
        i_n=c1.text_input("Nombre *"); i_t=c2.selectbox("Tipo",["fresco","condimento","empaque","otro"]); i_u=c3.text_input("Unidad")
        c4,c5,c6,c7=st.columns(4)
        i_st=c4.number_input("Stock actual",min_value=0.0,step=0.1); i_sm=c5.number_input("Stock mínimo",min_value=0.0,step=0.1)
        i_co=c6.number_input("Costo Q",min_value=0.0,step=0.5); i_pv=c7.selectbox("Proveedor",prov_lista)
        if st.button("💾 Guardar ingrediente",type="primary"):
            if not i_n.strip(): st.error("Nombre obligatorio.")
            else:
                agregar_ingrediente(i_n.strip(),i_t,i_u.strip(),i_st,i_sm,i_co,prov_opts.get(i_pv))
                st.success(f"✅ **{i_n}** guardado."); st.rerun()

    with tab_editar:
        rows=get_ingredientes()
        if not rows: st.info("Sin ingredientes.")
        else:
            ing_opts={f"{i['nombre']} ({i['unidad']})":i for i in rows}
            sel=st.selectbox("Selecciona ingrediente",list(ing_opts.keys())); ing=ing_opts[sel]
            st.markdown("---")
            c1,c2,c3=st.columns(3)
            en=c1.text_input("Nombre",value=ing["nombre"])
            et=c2.selectbox("Tipo",["fresco","condimento","empaque","otro"],index=["fresco","condimento","empaque","otro"].index(ing["tipo"]))
            eu=c3.text_input("Unidad",value=ing["unidad"])
            c4,c5,c6=st.columns(3)
            esm=c4.number_input("Stock mínimo",min_value=0.0,step=0.1,value=float(ing["stock_minimo"]))
            eco=c5.number_input("Costo Q",min_value=0.0,step=0.5,value=float(ing["costo_unitario"]))
            pv_actual=ing["proveedor"] if ing["proveedor"] in prov_opts else "— Sin proveedor —"
            epv=c6.selectbox("Proveedor",prov_lista,index=prov_lista.index(pv_actual) if pv_actual in prov_lista else 0)
            col1,col2=st.columns(2)
            if col1.button("💾 Guardar cambios",type="primary"):
                with get_connection() as conn:
                    conn.execute("UPDATE ingredientes SET nombre=?,tipo=?,unidad=?,stock_minimo=?,costo_unitario=?,proveedor_id=? WHERE id=?",
                                 (en.strip(),et,eu.strip(),esm,eco,prov_opts.get(epv),ing["id"]))
                st.success(f"✅ **{en}** actualizado."); st.rerun()
            if col2.button("🗑 Eliminar ingrediente",type="secondary"):
                with get_connection() as conn:
                    conn.execute("DELETE FROM receta_ingredientes WHERE ingrediente_id=?",(ing["id"],))
                    conn.execute("DELETE FROM ingredientes WHERE id=?",(ing["id"],))
                st.warning(f"🗑 **{ing['nombre']}** eliminado."); st.rerun()

    with tab_stock:
        rows=get_ingredientes()
        if rows:
            ing_opts2={f"{i['nombre']} ({i['unidad']})":i for i in rows}
            sel2=st.selectbox("Ingrediente",list(ing_opts2.keys()),key="sel_stock"); ing2=ing_opts2[sel2]
            st.info(f"Stock actual: **{ing2['stock_actual']} {ing2['unidad']}**")
            c1,c2=st.columns(2)
            mov_t=c1.radio("Movimiento",["📥 Entrada","📤 Salida","🔧 Ajuste"])
            mov_c=c2.number_input("Cantidad",min_value=0.0,step=0.1,value=1.0)
            if st.button("💾 Registrar",type="primary"):
                tipo_map={"📥 Entrada":"entrada","📤 Salida":"salida","🔧 Ajuste":"ajuste"}
                nuevo=actualizar_stock(ing2["id"],mov_c,tipo_map[mov_t])
                st.success(f"✅ Nuevo stock: **{nuevo} {ing2['unidad']}**"); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# RECETAS / BOM
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📋 Recetas / BOM":
    st.subheader("📋 Recetas / BOM")
    tab_ver,tab_nuevo,tab_editar,tab_bom=st.tabs(["📄 Ver todas","➕ Nueva","✏️ Editar receta","🧾 Editar BOM"])

    with tab_nuevo:
        c1,c2=st.columns(2)
        rn=c1.text_input("Nombre *"); rd=c2.text_input("Descripción")
        if st.button("💾 Crear receta",type="primary"):
            if not rn.strip(): st.error("Nombre obligatorio.")
            else:
                agregar_receta(rn.strip(),rd.strip())
                st.success(f"✅ **{rn}** creada."); st.rerun()

    with tab_ver:
        recetas=get_recetas()
        if recetas:
            for r in recetas:
                bom=get_bom(r["id"]); costo=sum(b["cantidad"]*b["costo_unitario"] for b in bom)
                with st.expander(f"**{r['nombre']}** — {len(bom)} ingredientes | Q {costo:.2f}/porción"):
                    st.write(f"*{r['descripcion']}*")
                    if bom:
                        df=pd.DataFrame(bom)[["nombre","cantidad","unidad","costo_unitario","proveedor"]]
                        df.columns=["Ingrediente","Cantidad/porción","Unidad","Costo unit.","Proveedor"]
                        st.dataframe(df,use_container_width=True,hide_index=True)
                    else: st.warning("Sin ingredientes.")
        else: st.info("Sin recetas.")

    with tab_editar:
        recetas=get_recetas()
        if not recetas: st.info("Sin recetas.")
        else:
            rec_opts={r["nombre"]:r for r in recetas}
            sel=st.selectbox("Selecciona receta",list(rec_opts.keys())); rec=rec_opts[sel]
            st.markdown("---")
            c1,c2=st.columns(2)
            en=c1.text_input("Nombre",value=rec["nombre"]); ed=c2.text_input("Descripción",value=rec["descripcion"])
            col1,col2=st.columns(2)
            if col1.button("💾 Guardar cambios",type="primary"):
                with get_connection() as conn:
                    conn.execute("UPDATE recetas SET nombre=?,descripcion=? WHERE id=?",(en.strip(),ed.strip(),rec["id"]))
                st.success(f"✅ **{en}** actualizado."); st.rerun()
            if col2.button("🗑 Eliminar receta",type="secondary"):
                with get_connection() as conn:
                    conn.execute("DELETE FROM receta_ingredientes WHERE receta_id=?",(rec["id"],))
                    conn.execute("DELETE FROM caja_recetas WHERE receta_id=?",(rec["id"],))
                    conn.execute("UPDATE recetas SET activa=0 WHERE id=?",(rec["id"],))
                st.warning(f"🗑 **{rec['nombre']}** eliminada."); st.rerun()

    with tab_bom:
        recetas=get_recetas(); ings=get_ingredientes()
        if not recetas: st.warning("Primero crea una receta.")
        elif not ings: st.warning("Primero agrega ingredientes.")
        else:
            rec_opts={r["nombre"]:r["id"] for r in recetas}
            ing_opts={f"{i['nombre']} ({i['unidad']})":i["id"] for i in ings}
            sel_rec=st.selectbox("Receta",list(rec_opts.keys())); rid=rec_opts[sel_rec]
            bom=get_bom(rid)
            if bom:
                st.markdown("**Ingredientes actuales:**")
                for b in bom:
                    col1,col2,col3=st.columns([3,2,1])
                    col1.write(f"**{b['nombre']}** ({b['unidad']}) — {b['proveedor']}")
                    nueva_cant=col2.number_input("Cant.",min_value=0.0,step=0.1,value=float(b["cantidad"]),key=f"bc_{b['id']}")
                    if col2.button("💾",key=f"bs_{b['id']}"):
                        with get_connection() as conn:
                            conn.execute("UPDATE receta_ingredientes SET cantidad=? WHERE id=?",(nueva_cant,b["id"]))
                        st.success("✅ Actualizado."); st.rerun()
                    if col3.button("🗑",key=f"bd_{b['id']}"):
                        with get_connection() as conn:
                            conn.execute("DELETE FROM receta_ingredientes WHERE id=?",(b["id"],))
                        st.warning("🗑 Eliminado."); st.rerun()
            else: st.info("Sin ingredientes en esta receta.")
            st.markdown("---")
            st.markdown("**Agregar ingrediente:**")
            c1,c2=st.columns(2)
            sel_ing=c1.selectbox("Ingrediente",list(ing_opts.keys()))
            cantidad=c2.number_input("Cantidad por porción",min_value=0.0,step=0.1,value=1.0)
            if st.button("➕ Agregar al BOM",type="primary"):
                agregar_ingrediente_receta(rid,ing_opts[sel_ing],cantidad)
                st.success("✅ Ingrediente agregado."); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# CAJAS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📦 Cajas":
    st.subheader("📦 Cajas")
    tab_ver,tab_nuevo,tab_editar,tab_rec=st.tabs(["📄 Ver todas","➕ Nueva","✏️ Editar caja","🔗 Editar recetas"])

    with tab_nuevo:
        c1,c2,c3=st.columns(3)
        cn=c1.text_input("Nombre *"); cd=c2.text_input("Descripción"); cp=c3.number_input("Precio venta Q",min_value=0.0,step=5.0)
        if st.button("💾 Crear caja",type="primary"):
            if not cn.strip(): st.error("Nombre obligatorio.")
            else:
                agregar_caja(cn.strip(),cd.strip(),cp)
                st.success(f"✅ Caja **{cn}** creada."); st.rerun()

    with tab_ver:
        cajas=get_cajas()
        if cajas:
            for c in cajas:
                recs=get_caja_recetas(c["id"]); nombres=", ".join(r["nombre"] for r in recs) or "Sin recetas"
                with st.expander(f"**{c['nombre']}** — Q {c['precio_venta']:.2f} | {len(recs)} recetas"):
                    st.write(f"**Descripción:** {c['descripcion']}"); st.write(f"**Recetas:** {nombres}")
        else: st.info("Sin cajas.")

    with tab_editar:
        cajas=get_cajas()
        if not cajas: st.info("Sin cajas.")
        else:
            caja_opts={c["nombre"]:c for c in cajas}
            sel=st.selectbox("Selecciona caja",list(caja_opts.keys())); caja=caja_opts[sel]
            st.markdown("---")
            c1,c2,c3=st.columns(3)
            en=c1.text_input("Nombre",value=caja["nombre"]); ed=c2.text_input("Descripción",value=caja["descripcion"])
            ep=c3.number_input("Precio Q",min_value=0.0,step=5.0,value=float(caja["precio_venta"]))
            col1,col2=st.columns(2)
            if col1.button("💾 Guardar cambios",type="primary"):
                with get_connection() as conn:
                    conn.execute("UPDATE cajas SET nombre=?,descripcion=?,precio_venta=? WHERE id=?",(en.strip(),ed.strip(),ep,caja["id"]))
                st.success(f"✅ **{en}** actualizado."); st.rerun()
            if col2.button("🗑 Eliminar caja",type="secondary"):
                with get_connection() as conn:
                    conn.execute("DELETE FROM caja_recetas WHERE caja_id=?",(caja["id"],))
                    conn.execute("UPDATE cajas SET activa=0 WHERE id=?",(caja["id"],))
                st.warning(f"🗑 **{caja['nombre']}** eliminada."); st.rerun()

    with tab_rec:
        cajas=get_cajas(); recetas=get_recetas()
        if not cajas: st.warning("Primero crea una caja.")
        elif not recetas: st.warning("Primero crea recetas.")
        else:
            caja_opts={c["nombre"]:c["id"] for c in cajas}; rec_opts={r["nombre"]:r["id"] for r in recetas}
            sel_caja=st.selectbox("Caja",list(caja_opts.keys())); cid=caja_opts[sel_caja]
            actuales=get_caja_recetas(cid)
            if actuales:
                st.markdown("**Recetas actuales:**")
                for r in actuales:
                    col1,col2=st.columns([4,1])
                    col1.write(f"• {r['nombre']}")
                    if col2.button("🗑",key=f"dcr_{r['id']}"):
                        with get_connection() as conn:
                            conn.execute("DELETE FROM caja_recetas WHERE id=?",(r["id"],))
                        st.warning("🗑 Receta removida."); st.rerun()
            else: st.info("Sin recetas asignadas.")
            st.markdown("---")
            sel_rec=st.selectbox("Receta a agregar",list(rec_opts.keys()))
            if st.button("➕ Agregar receta",type="primary"):
                agregar_receta_a_caja(cid,rec_opts[sel_rec])
                st.success("✅ Receta agregada."); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PEDIDOS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📬 Pedidos":
    st.subheader("📬 Pedidos")
    cajas=get_cajas()
    tab_nuevo,tab_ver,tab_estado=st.tabs(["➕ Nuevo pedido","📄 Ver pedidos","🔄 Cambiar estado"])

    with tab_nuevo:
        if not cajas: st.warning("Primero crea cajas.")
        else:
            c1,c2=st.columns(2)
            cliente=c1.text_input("Cliente *"); fecha_ent=c2.date_input("Fecha de entrega",min_value=date.today())
            caja_opts={c["nombre"]:c["id"] for c in cajas}
            if "items_pedido" not in st.session_state: st.session_state.items_pedido=[]
            st.markdown("**Cajas del pedido:**")
            st.caption("💡 Las porciones aplican igual para todas las recetas de la caja.")
            c1,c2,c3=st.columns(3)
            sel_caja=c1.selectbox("Caja",list(caja_opts.keys()))
            cantidad=c2.number_input("Cantidad de cajas",min_value=1,value=1)
            porciones=c3.number_input("Porciones por receta",min_value=0.5,value=1.0,step=0.5)
            col1,col2=st.columns([1,3])
            if col1.button("➕ Agregar ítem"):
                st.session_state.items_pedido.append({"caja_id":caja_opts[sel_caja],"nombre":sel_caja,"cantidad":cantidad,"porciones":porciones})
            if col2.button("🗑 Limpiar"): st.session_state.items_pedido=[]
            if st.session_state.items_pedido:
                df=pd.DataFrame(st.session_state.items_pedido)[["nombre","cantidad","porciones"]]
                df["Factor MRP"]=df["cantidad"]*df["porciones"]; df.columns=["Caja","Cajas","Porciones","Factor MRP"]
                st.dataframe(df,use_container_width=True,hide_index=True)
                if st.button("💾 Guardar pedido",type="primary"):
                    if not cliente.strip(): st.error("Cliente obligatorio.")
                    else:
                        items=[{"caja_id":i["caja_id"],"cantidad":i["cantidad"],"porciones":i["porciones"]} for i in st.session_state.items_pedido]
                        pid=crear_pedido(cliente.strip(),fecha_ent.strftime("%Y-%m-%d"),items)
                        st.success(f"✅ Pedido #{pid} para **{cliente}**."); st.session_state.items_pedido=[]; st.rerun()

    with tab_ver:
        rows=get_pedidos()
        if rows:
            df=pd.DataFrame(rows)[["id","cliente","caja","cantidad","porciones","fecha_entrega","estado"]]
            df.columns=["#","Cliente","Caja","Cajas","Porciones","Fecha entrega","Estado"]
            st.dataframe(df,use_container_width=True,hide_index=True)
        else: st.success("✅ Sin pedidos.")

    with tab_estado:
        rows=get_pedidos()
        if not rows: st.info("Sin pedidos.")
        else:
            ped_unicos={}
            for r in rows:
                if r["id"] not in ped_unicos: ped_unicos[r["id"]]=r
            opts={f"#{p['id']} — {p['cliente']} ({p['fecha_entrega']})":p for p in ped_unicos.values()}
            sel=st.selectbox("Pedido",list(opts.keys())); ped=opts[sel]
            estados=["pendiente","en_proceso","completado","cancelado"]
            nuevo_estado=st.selectbox("Nuevo estado",estados,index=estados.index(ped["estado"]))
            if st.button("💾 Actualizar estado",type="primary"):
                with get_connection() as conn:
                    conn.execute("UPDATE pedidos SET estado=? WHERE id=?",(nuevo_estado,ped["id"]))
                st.success(f"✅ Pedido #{ped['id']} → **{nuevo_estado}**."); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# MRP
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "⚙️ MRP":
    st.subheader("⚙️ Cálculo MRP")
    col1,col2=st.columns([2,1]); buffer=col2.slider("Buffer %",0,50,10)
    if col1.button("⚙️ Calcular requerimientos",type="primary",use_container_width=True):
        st.session_state.mrp_reqs=calcular_requerimientos()

    if "mrp_reqs" in st.session_state and st.session_state.mrp_reqs:
        reqs=st.session_state.mrp_reqs
        falta=[d for d in reqs.values() if d["faltante"]]; ok_=[d for d in reqs.values() if not d["faltante"]]
        costo=sum(d["neto"]*d["costo"] for d in falta)
        m1,m2,m3,m4=st.columns(4)
        m1.metric("Analizados",len(reqs)); m2.metric("⚠ Faltante",len(falta))
        m3.metric("✅ OK",len(ok_)); m4.metric("Costo estimado",f"Q {costo:.2f}")
        st.markdown("---")
        rows=[{"Ingrediente":d["nombre"],"Requerido":f"{d['requerido']:.3f} {d['unidad']}",
               "Stock":d["stock"],"Neto faltante":d["neto"] if d["faltante"] else 0,
               "Costo Q":round(d["neto"]*d["costo"],2) if d["faltante"] else 0,
               "Estado":"⚠ FALTA" if d["faltante"] else "✅ OK"}
              for _,d in sorted(reqs.items(),key=lambda x:(-x[1]["faltante"],x[1]["nombre"]))]
        df=pd.DataFrame(rows)
        def ce(row): return ["background-color:#fee2e2"]*len(row) if row["Estado"]=="⚠ FALTA" else ["background-color:#f0fdf4"]*len(row)
        st.dataframe(df.style.apply(ce,axis=1),use_container_width=True,hide_index=True)
        st.markdown("---")
        if st.button("📋 Generar Órdenes de Compra",type="primary",use_container_width=True):
            ordenes=generar_ordenes_compra(reqs,buffer_pct=buffer/100)
            if not ordenes: st.success("✅ Stock suficiente, sin órdenes necesarias.")
            else:
                for o in ordenes:
                    pv=Q("SELECT nombre FROM proveedores WHERE id=?",(o["proveedor_id"],))
                    pnombre=pv[0]["nombre"] if pv else "Sin proveedor"
                    with st.expander(f"📋 Orden #{o['orden_id']} — {pnombre} | Q {o['total']:.2f}",expanded=True):
                        st.write(f"**Entrega:** {o['fecha']}")
                        df2=pd.DataFrame(o["items"])[["nombre","neto","cantidad","costo"]]
                        df2["subtotal"]=df2["cantidad"]*df2["costo"]
                        df2.columns=["Ingrediente","Neto",f"Con buffer {buffer}%","Costo unit.","Subtotal Q"]
                        st.dataframe(df2,use_container_width=True,hide_index=True)
    elif "mrp_reqs" in st.session_state and not st.session_state.mrp_reqs:
        st.warning("⚠ Sin pedidos pendientes.")
