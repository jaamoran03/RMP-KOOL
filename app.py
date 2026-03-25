"""
app.py — MRP Cajas de Alimentos Delivery
Base de datos permanente en Supabase (PostgreSQL)
"""
import streamlit as st
import pandas as pd
from datetime import date
from database import init_db, get_connection, sync_save
from mrp_engine import (
    agregar_proveedor, agregar_ingrediente, agregar_receta,
    agregar_ingrediente_receta, agregar_caja, agregar_receta_a_caja,
    agregar_menu, agregar_receta_a_menu,
    crear_pedido, calcular_requerimientos, generar_ordenes_compra,
    actualizar_stock, calcular_costo_menu, comparar_menus,
)

st.set_page_config(page_title="MRP — Cajas Delivery", page_icon="🥗", layout="wide")
init_db()

# ── Helpers DB ────────────────────────────────────────────────────────────────
def Q(sql, p=()):
    with get_connection() as c:
        return [dict(r) for r in c.execute(sql, p).fetchall()]

def Qexec(sql, p=()):
    with get_connection() as c:
        c.execute(sql, p)
        c.commit()
    sync_save()

def Qexec_update(tabla, data, filtros):
    sets = ", ".join(f"{k}=?" for k in data)
    wheres = " AND ".join(f"{k}=?" for k in filtros)
    vals = list(data.values()) + list(filtros.values())
    Qexec(f"UPDATE {tabla} SET {sets} WHERE {wheres}", vals)

def Qexec_delete(tabla, filtros):
    wheres = " AND ".join(f"{k}=?" for k in filtros)
    vals = list(filtros.values())
    Qexec(f"DELETE FROM {tabla} WHERE {wheres}", vals)

def get_proveedores():
    return Q("SELECT id,nombre,contacto,telefono,email,lead_time FROM proveedores WHERE activo=1")

def get_ingredientes():
    return Q("""SELECT i.*,COALESCE(p.nombre,'—') proveedor
                FROM ingredientes i LEFT JOIN proveedores p ON p.id=i.proveedor_id""")

def get_recetas():
    return Q("SELECT * FROM recetas WHERE activa=1")

def get_cajas():
    return Q("SELECT * FROM cajas WHERE activa=1")

def get_menus():
    return Q("SELECT * FROM menus WHERE activo=1 ORDER BY categoria,racion")

def get_bom(rid):
    return Q("""SELECT ri.id,ri.cantidad,i.id ing_id,i.nombre,i.unidad,
                       i.costo_unitario,i.calorias,i.proteinas_g,i.vegetales,
                       COALESCE(p.nombre,'—') proveedor
                FROM receta_ingredientes ri
                JOIN ingredientes i ON i.id=ri.ingrediente_id
                LEFT JOIN proveedores p ON p.id=i.proveedor_id
                WHERE ri.receta_id=?""", (rid,))

def get_caja_recetas(cid):
    return Q("""SELECT cr.id,r.id rec_id,r.nombre FROM caja_recetas cr
                JOIN recetas r ON r.id=cr.receta_id WHERE cr.caja_id=?""", (cid,))

def get_menu_recetas(mid):
    return Q("""SELECT mr.id,r.id rec_id,r.nombre FROM menu_recetas mr
                JOIN recetas r ON r.id=mr.receta_id WHERE mr.menu_id=?""", (mid,))

def get_pedidos():
    return Q("""SELECT p.id,p.cliente,p.fecha_entrega,p.estado,
                       c.nombre caja,pd.cantidad,pd.porciones,pd.id pd_id
                FROM pedidos p JOIN pedido_detalle pd ON pd.pedido_id=p.id
                JOIN cajas c ON c.id=pd.caja_id ORDER BY p.fecha_entrega""")

TIPOS   = ["fresco","condimento","empaque","otro"]
ESTADOS = ["pendiente","en_proceso","completado","cancelado"]
CATS    = ["economico","nivel_medio","alto_proteina","vegetariano","alto_vegetales"]
CATS_LBL = {"economico":"💰 Económico","nivel_medio":"⭐ Nivel Medio",
             "alto_proteina":"💪 Alto en Proteína","vegetariano":"🥦 Vegetariano",
             "alto_vegetales":"🥗 Alto en Vegetales"}
RACIONES = [2,4,6]

st.markdown("""<style>
[data-testid="stSidebar"]{background:#0d1b2a}
[data-testid="stSidebar"] *{color:#e8f5e9!important}
.hdr{background:linear-gradient(120deg,#0d1b2a,#1b4332);color:#e8f5e9;
     padding:20px 28px;border-radius:12px;margin-bottom:20px}
.hdr h1{margin:0;font-size:1.6rem}.hdr p{margin:4px 0 0;opacity:.65;font-size:.85rem}
</style>""", unsafe_allow_html=True)

st.markdown("""<div class='hdr'>
<h1>🥗 MRP — Cajas de Alimentos Delivery</h1>
<p>Gestión de recetas · menús · costeo · MRP · planificación</p>
</div>""", unsafe_allow_html=True)

pagina = st.sidebar.radio("Navegación", [
    "📦 Proveedores","🥬 Ingredientes","📋 Recetas / BOM",
    "🍽️ Menús","💰 Costeo de Paquetes",
    "📦 Cajas","📬 Pedidos","⚙️ MRP"])

# ══════════════════════════════════════════════════════════════════════════════
# PROVEEDORES
# ══════════════════════════════════════════════════════════════════════════════
if pagina == "📦 Proveedores":
    st.subheader("📦 Proveedores")
    tab_ver,tab_nuevo,tab_editar = st.tabs(["📄 Ver todos","➕ Nuevo","✏️ Editar / Eliminar"])

    with tab_nuevo:
        c1,c2,c3 = st.columns(3)
        pn=c1.text_input("Nombre *",key="pn"); pc=c2.text_input("Contacto",key="pc"); pt=c3.text_input("Teléfono",key="pt")
        c4,c5 = st.columns(2)
        pe=c4.text_input("Email",key="pe"); pl=c5.number_input("Lead time (días)",min_value=1,max_value=60,value=2,key="pl")
        if st.button("💾 Guardar proveedor",type="primary",key="btn_pnew"):
            if not pn.strip(): st.error("Nombre obligatorio.")
            else:
                agregar_proveedor(pn.strip(),pc.strip(),pt.strip(),pe.strip(),int(pl))
                st.success(f"✅ **{pn}** guardado."); st.rerun()

    with tab_ver:
        rows=get_proveedores()
        if rows:
            df=pd.DataFrame(rows); df.columns=["#","Nombre","Contacto","Teléfono","Email","Lead time"]
            st.dataframe(df,use_container_width=True,hide_index=True)
        else: st.info("Sin proveedores.")

    with tab_editar:
        rows=get_proveedores()
        if rows:
            opts={p["nombre"]:p for p in rows}
            sel=st.selectbox("Proveedor",list(opts.keys()),key="pedit_sel"); pv=opts[sel]
            c1,c2,c3=st.columns(3)
            en=c1.text_input("Nombre",value=pv["nombre"],key="pe_n")
            ec=c2.text_input("Contacto",value=pv["contacto"],key="pe_c")
            et=c3.text_input("Teléfono",value=pv["telefono"],key="pe_t")
            c4,c5=st.columns(2)
            ee=c4.text_input("Email",value=pv["email"],key="pe_e")
            el=c5.number_input("Lead time",min_value=1,max_value=60,value=int(pv["lead_time"]),key="pe_l")
            col1,col2=st.columns(2)
            if col1.button("💾 Guardar",type="primary",key="btn_pupd"):
                Qexec_update("proveedores",{"nombre":en.strip(),"contacto":ec.strip(),"telefono":et.strip(),"email":ee.strip(),"lead_time":int(el)},{"id":pv["id"]})
                st.success("✅ Actualizado."); st.rerun()
            if col2.button("🗑 Eliminar",type="secondary",key="btn_pdel"):
                Qexec_update("proveedores",{"activo":0},{"id":pv["id"]})
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
            df=pd.DataFrame(rows)[["id","nombre","tipo","unidad","stock_actual","stock_minimo","costo_unitario","proteinas_g","vegetales","proveedor"]]
            df.columns=["#","Nombre","Tipo","Unidad","Stock","Mínimo","Costo Q","Proteínas g","¿Vegetal?","Proveedor"]
            df["¿Vegetal?"]=df["¿Vegetal?"].apply(lambda x:"🥦 Sí" if x else "No")
            def cs(row): return ["background-color:#fee2e2"]*len(row) if row["Stock"]<=row["Mínimo"] else [""]*len(row)
            st.dataframe(df.style.apply(cs,axis=1),use_container_width=True,hide_index=True)
            st.caption("🔴 Rojo = stock bajo mínimo")
        else: st.info("Sin ingredientes.")

    with tab_nuevo:
        st.markdown("**Datos básicos**")
        c1,c2,c3=st.columns(3)
        i_n=c1.text_input("Nombre *",key="in_n"); i_t=c2.selectbox("Tipo",TIPOS,key="in_t"); i_u=c3.text_input("Unidad",key="in_u")
        c4,c5,c6,c7=st.columns(4)
        i_st=c4.number_input("Stock actual",min_value=0.0,step=0.1,key="in_st")
        i_sm=c5.number_input("Stock mínimo",min_value=0.0,step=0.1,key="in_sm")
        i_co=c6.number_input("Costo Q",min_value=0.0,step=0.5,key="in_co")
        i_pv=c7.selectbox("Proveedor",prov_lista,key="in_pv")
        st.markdown("**Info nutricional** *(por unidad)*")
        c1,c2,c3=st.columns(3)
        i_cal=c1.number_input("Calorías",min_value=0.0,step=1.0,key="in_cal")
        i_pro=c2.number_input("Proteínas (g)",min_value=0.0,step=0.1,key="in_pro")
        i_veg=c3.checkbox("¿Es vegetal?",key="in_veg")
        if st.button("💾 Guardar ingrediente",type="primary",key="btn_inew"):
            if not i_n.strip(): st.error("Nombre obligatorio.")
            else:
                agregar_ingrediente(i_n.strip(),i_t,i_u.strip(),i_st,i_sm,i_co,
                                    prov_opts.get(i_pv),i_cal,i_pro,1 if i_veg else 0)
                st.success(f"✅ **{i_n}** guardado."); st.rerun()

    with tab_editar:
        rows=get_ingredientes()
        if rows:
            ing_opts={f"{i['nombre']} ({i['unidad']})":i for i in rows}
            sel=st.selectbox("Ingrediente",list(ing_opts.keys()),key="iedit_sel"); ing=ing_opts[sel]
            st.markdown("**Datos básicos**")
            c1,c2,c3=st.columns(3)
            en=c1.text_input("Nombre",value=ing["nombre"],key="ie_n")
            et=c2.selectbox("Tipo",TIPOS,index=TIPOS.index(ing["tipo"]),key="ie_t")
            eu=c3.text_input("Unidad",value=ing["unidad"],key="ie_u")
            c4,c5,c6=st.columns(3)
            esm=c4.number_input("Stock mínimo",min_value=0.0,step=0.1,value=float(ing["stock_minimo"]),key="ie_sm")
            eco=c5.number_input("Costo Q",min_value=0.0,step=0.5,value=float(ing["costo_unitario"]),key="ie_co")
            pv_act=ing["proveedor"] if ing["proveedor"] in prov_opts else "— Sin proveedor —"
            epv=c6.selectbox("Proveedor",prov_lista,index=prov_lista.index(pv_act) if pv_act in prov_lista else 0,key="ie_pv")
            st.markdown("**Info nutricional**")
            c1,c2,c3=st.columns(3)
            ecal=c1.number_input("Calorías",min_value=0.0,step=1.0,value=float(ing["calorias"]),key="ie_cal")
            epro=c2.number_input("Proteínas (g)",min_value=0.0,step=0.1,value=float(ing["proteinas_g"]),key="ie_pro")
            eveg=c3.checkbox("¿Es vegetal?",value=bool(ing["vegetales"]),key="ie_veg")
            col1,col2=st.columns(2)
            if col1.button("💾 Guardar cambios",type="primary",key="btn_iupd"):
                Qexec_update("ingredientes",{"nombre":en.strip(),"tipo":et,"unidad":eu.strip(),"stock_minimo":esm,"costo_unitario":eco,"proveedor_id":prov_opts.get(epv),"calorias":ecal,"proteinas_g":epro,"vegetales":1 if eveg else 0},{"id":ing["id"]})
                st.success("✅ Actualizado."); st.rerun()
            if col2.button("🗑 Eliminar",type="secondary",key="btn_idel"):
                Qexec_delete("receta_ingredientes",{"ingrediente_id":ing["id"]})
                Qexec_delete("ingredientes",{"id":ing["id"]})
                st.warning(f"🗑 **{ing['nombre']}** eliminado."); st.rerun()

    with tab_stock:
        rows=get_ingredientes()
        if rows:
            io2={f"{i['nombre']} ({i['unidad']})":i for i in rows}
            sel2=st.selectbox("Ingrediente",list(io2.keys()),key="stk_sel"); ing2=io2[sel2]
            st.info(f"Stock actual: **{ing2['stock_actual']} {ing2['unidad']}**")
            c1,c2=st.columns(2)
            mt=c1.radio("Movimiento",["📥 Entrada","📤 Salida","🔧 Ajuste"],key="stk_radio")
            mc=c2.number_input("Cantidad",min_value=0.0,step=0.1,value=1.0,key="stk_cant")
            if st.button("💾 Registrar",type="primary",key="btn_stk"):
                tm={"📥 Entrada":"entrada","📤 Salida":"salida","🔧 Ajuste":"ajuste"}
                nuevo=actualizar_stock(ing2["id"],mc,tm[mt])
                st.success(f"✅ Nuevo stock: **{nuevo} {ing2['unidad']}**"); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# RECETAS / BOM
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📋 Recetas / BOM":
    st.subheader("📋 Recetas / BOM")
    tab_ver,tab_nuevo,tab_editar,tab_bom=st.tabs(["📄 Ver todas","➕ Nueva","✏️ Editar","🧾 Editar BOM"])

    with tab_nuevo:
        c1,c2=st.columns(2)
        rn=c1.text_input("Nombre *",key="rec_n"); rd=c2.text_input("Descripción",key="rec_d")
        if st.button("💾 Crear receta",type="primary",key="btn_rnew"):
            if not rn.strip(): st.error("Nombre obligatorio.")
            else:
                agregar_receta(rn.strip(),rd.strip())
                st.success(f"✅ **{rn}** creada."); st.rerun()

    with tab_ver:
        recetas=get_recetas()
        if recetas:
            for r in recetas:
                bom=get_bom(r["id"])
                costo=sum(b["cantidad"]*b["costo_unitario"] for b in bom)
                prot=sum(b["cantidad"]*b["proteinas_g"] for b in bom)
                veg=sum(1 for b in bom if b["vegetales"])
                with st.expander(f"**{r['nombre']}** — {len(bom)} ingredientes | Q {costo:.2f}/porción"):
                    col1,col2,col3=st.columns(3)
                    col1.metric("Costo/porción",f"Q {costo:.2f}")
                    col2.metric("Proteínas",f"{prot:.1f} g")
                    col3.metric("Vegetales",veg)
                    if bom:
                        df=pd.DataFrame(bom)[["nombre","cantidad","unidad","costo_unitario","proteinas_g","vegetales","proveedor"]]
                        df.columns=["Ingrediente","Cant./porción","Unidad","Costo Q","Proteínas g","Vegetal","Proveedor"]
                        df["Vegetal"]=df["Vegetal"].apply(lambda x:"🥦" if x else "")
                        st.dataframe(df,use_container_width=True,hide_index=True)
        else: st.info("Sin recetas.")

    with tab_editar:
        recetas=get_recetas()
        if recetas:
            ro={r["nombre"]:r for r in recetas}
            sel=st.selectbox("Receta",list(ro.keys()),key="redit_sel"); rec=ro[sel]
            c1,c2=st.columns(2)
            en=c1.text_input("Nombre",value=rec["nombre"],key="re_n")
            ed=c2.text_input("Descripción",value=rec["descripcion"],key="re_d")
            col1,col2=st.columns(2)
            if col1.button("💾 Guardar",type="primary",key="btn_rupd"):
                Qexec_update("recetas",{"nombre":en.strip(),"descripcion":ed.strip()},{"id":rec["id"]})
                st.success("✅ Actualizado."); st.rerun()
            if col2.button("🗑 Eliminar",type="secondary",key="btn_rdel"):
                Qexec_delete("receta_ingredientes",{"receta_id":rec["id"]})
                Qexec_delete("caja_recetas",{"receta_id":rec["id"]})
                Qexec_delete("menu_recetas",{"receta_id":rec["id"]})
                Qexec_update("recetas",{"activa":0},{"id":rec["id"]})
                st.warning(f"🗑 **{rec['nombre']}** eliminada."); st.rerun()

    with tab_bom:
        recetas=get_recetas(); ings=get_ingredientes()
        if not recetas: st.warning("Primero crea una receta.")
        elif not ings:  st.warning("Primero agrega ingredientes.")
        else:
            ro={r["nombre"]:r["id"] for r in recetas}
            io={f"{i['nombre']} ({i['unidad']})":i["id"] for i in ings}
            sel_r=st.selectbox("Receta",list(ro.keys()),key="bom_rsel"); rid=ro[sel_r]
            bom=get_bom(rid)
            if bom:
                for b in bom:
                    col1,col2,col3=st.columns([3,2,1])
                    col1.write(f"**{b['nombre']}** ({b['unidad']}) — {b['proveedor']}")
                    nc=col2.number_input("Cant.",min_value=0.0,step=0.1,value=float(b["cantidad"]),key=f"bc_{b['id']}")
                    if col2.button("💾",key=f"bs_{b['id']}"):
                        Qexec_update("receta_ingredientes",{"cantidad":nc},{"id":b["id"]})
                        st.success("✅"); st.rerun()
                    if col3.button("🗑",key=f"bd_{b['id']}"):
                        Qexec_delete("receta_ingredientes",{"id":b["id"]})
                        st.rerun()
            else: st.info("Sin ingredientes.")
            st.markdown("---")
            c1,c2=st.columns(2)
            si=c1.selectbox("Agregar ingrediente",list(io.keys()),key="bom_isel")
            cant=c2.number_input("Cantidad/porción",min_value=0.0,step=0.1,value=1.0,key="bom_cant")
            if st.button("➕ Agregar al BOM",type="primary",key="btn_badd"):
                agregar_ingrediente_receta(rid,io[si],cant)
                st.success("✅ Agregado."); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# MENÚS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "🍽️ Menús":
    st.subheader("🍽️ Menús")
    tab_ver,tab_nuevo,tab_editar,tab_recetas=st.tabs(["📄 Ver menús","➕ Nuevo menú","✏️ Editar","🔗 Recetas del menú"])

    with tab_nuevo:
        c1,c2=st.columns(2)
        mn=c1.text_input("Nombre *",key="mn_n"); md=c2.text_input("Descripción",key="mn_d")
        c3,c4=st.columns(2)
        mc=c3.selectbox("Categoría",[CATS_LBL[k] for k in CATS],key="mn_cat")
        mr=c4.selectbox("Ración (personas)",[2,4,6],key="mn_rac")
        if st.button("💾 Crear menú",type="primary",key="btn_mnew"):
            if not mn.strip(): st.error("Nombre obligatorio.")
            else:
                cat_key=CATS[[CATS_LBL[k] for k in CATS].index(mc)]
                agregar_menu(mn.strip(),md.strip(),cat_key,mr)
                st.success(f"✅ Menú **{mn}** creado."); st.rerun()

    with tab_ver:
        menus=get_menus()
        if menus:
            for m in menus:
                recs=get_menu_recetas(m["id"])
                with st.expander(f"**{m['nombre']}** — {CATS_LBL[m['categoria']]} | 👥 {m['racion']} personas | {len(recs)} recetas"):
                    st.write(f"*{m['descripcion']}*")
                    for r in recs: st.write(f"  • {r['nombre']}")
        else: st.info("Sin menús.")

    with tab_editar:
        menus=get_menus()
        if menus:
            mo={m["nombre"]:m for m in menus}
            sel=st.selectbox("Menú",list(mo.keys()),key="medit_sel"); m=mo[sel]
            c1,c2=st.columns(2)
            en=c1.text_input("Nombre",value=m["nombre"],key="me_n")
            ed=c2.text_input("Descripción",value=m["descripcion"],key="me_d")
            c3,c4=st.columns(2)
            cat_lbls=[CATS_LBL[k] for k in CATS]
            ec=c3.selectbox("Categoría",cat_lbls,index=CATS.index(m["categoria"]),key="me_cat")
            er=c4.selectbox("Ración",[2,4,6],index=[2,4,6].index(m["racion"]),key="me_rac")
            col1,col2=st.columns(2)
            if col1.button("💾 Guardar",type="primary",key="btn_mupd"):
                cat_key=CATS[cat_lbls.index(ec)]
                Qexec_update("menus",{"nombre":en.strip(),"descripcion":ed.strip(),"categoria":cat_key,"racion":er},{"id":m["id"]})
                st.success("✅ Actualizado."); st.rerun()
            if col2.button("🗑 Eliminar",type="secondary",key="btn_mdel"):
                Qexec_delete("menu_recetas",{"menu_id":m["id"]})
                Qexec_update("menus",{"activo":0},{"id":m["id"]})
                st.warning("🗑 Menú eliminado."); st.rerun()

    with tab_recetas:
        menus=get_menus(); recetas=get_recetas()
        if not menus: st.warning("Primero crea un menú.")
        elif not recetas: st.warning("Primero crea recetas.")
        else:
            mo={m["nombre"]:m["id"] for m in menus}
            ro={r["nombre"]:r["id"] for r in recetas}
            sel_m=st.selectbox("Menú",list(mo.keys()),key="mrec_msel"); mid=mo[sel_m]
            actuales=get_menu_recetas(mid)
            if actuales:
                st.markdown("**Recetas actuales:**")
                for r in actuales:
                    col1,col2=st.columns([4,1])
                    col1.write(f"• {r['nombre']}")
                    if col2.button("🗑",key=f"dmr_{r['id']}"):
                        Qexec_delete("menu_recetas",{"id":r["id"]})
                        st.rerun()
            else: st.info("Sin recetas.")
            st.markdown("---")
            sel_r=st.selectbox("Receta a agregar",list(ro.keys()),key="mrec_rsel")
            if st.button("➕ Agregar receta al menú",type="primary",key="btn_mradd"):
                agregar_receta_a_menu(mid,ro[sel_r])
                st.success("✅ Receta agregada."); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# COSTEO DE PAQUETES
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "💰 Costeo de Paquetes":
    st.subheader("💰 Costeo de Paquetes")
    menus=get_menus()
    if not menus:
        st.warning("Primero crea menús con recetas asignadas.")
    else:
        tab_individual,tab_comparar=st.tabs(["📊 Costeo individual","🔍 Comparar menús"])

        with tab_individual:
            mo={f"{m['nombre']} — {CATS_LBL[m['categoria']]} | {m['racion']} personas":m["id"] for m in menus}
            sel=st.selectbox("Selecciona un menú",list(mo.keys()),key="cost_sel")
            c1,c2=st.columns(2)
            margen=c1.slider("Margen de ganancia %",10,80,35,key="cost_margen")
            empaque=c2.number_input("Costo de empaque Q",min_value=0.0,step=0.5,value=5.0,key="cost_emp")
            if st.button("📊 Calcular costo",type="primary",key="btn_cost"):
                res=calcular_costo_menu(mo[sel],margen,empaque)
                if res:
                    m=res["menu"]
                    st.markdown(f"### {m['nombre']} — {CATS_LBL[m['categoria']]} | 👥 {res['racion']} personas")
                    col1,col2,col3,col4=st.columns(4)
                    col1.metric("Costo ingredientes",f"Q {res['costo_ingredientes']:.2f}")
                    col2.metric("Costo empaque",f"Q {res['costo_empaque']:.2f}")
                    col3.metric("Costo total",f"Q {res['costo_total']:.2f}")
                    col4.metric("💰 Precio sugerido",f"Q {res['precio_sugerido']:.2f}",delta=f"+Q {res['ganancia']:.2f}")
                    col1,col2,col3=st.columns(3)
                    col1.metric("Costo/persona",f"Q {res['costo_p_persona']:.2f}")
                    col2.metric("Precio/persona",f"Q {res['precio_p_persona']:.2f}")
                    col3.metric("Margen",f"{margen}%")
                    st.markdown("---")
                    st.markdown("**🥗 Perfil nutricional:**")
                    col1,col2,col3=st.columns(3)
                    col1.metric("🔥 Calorías",f"{res['calorias_total']:.0f} kcal")
                    col2.metric("💪 Proteínas",f"{res['proteinas_total']:.1f} g")
                    col3.metric("🥦 Vegetales",res['vegetales_total'])
                    st.markdown("---")
                    st.markdown("**📋 Desglose por receta:**")
                    df=pd.DataFrame(res["detalle_recetas"])
                    df.columns=["Receta","Costo Q","Calorías","Proteínas g","Vegetales"]
                    df["% del costo"]=df["Costo Q"].apply(lambda x:f"{x/res['costo_total']*100:.1f}%")
                    st.dataframe(df,use_container_width=True,hide_index=True)

        with tab_comparar:
            c1,c2,c3=st.columns(3)
            f_cat=c1.selectbox("Categoría",["Todas"]+[CATS_LBL[k] for k in CATS],key="cmp_cat")
            f_rac=c2.selectbox("Ración",["Todas"]+[str(r) for r in RACIONES],key="cmp_rac")
            f_mar=c3.slider("Margen %",10,80,35,key="cmp_mar")
            f_emp=st.number_input("Costo empaque Q",min_value=0.0,step=0.5,value=5.0,key="cmp_emp")
            if st.button("🔍 Comparar menús",type="primary",key="btn_cmp"):
                cat_key=CATS[([CATS_LBL[k] for k in CATS]).index(f_cat)] if f_cat!="Todas" else None
                rac_key=int(f_rac) if f_rac!="Todas" else None
                resultados=comparar_menus(cat_key,rac_key,f_mar,f_emp)
                if not resultados:
                    st.warning("Sin menús para los filtros seleccionados.")
                else:
                    rows=[{"Menú":r["menu"]["nombre"],"Categoría":CATS_LBL[r["menu"]["categoria"]],
                           "Ración":f"{r['racion']} personas","Costo total Q":r["costo_total"],
                           "Precio sugerido Q":r["precio_sugerido"],"Ganancia Q":r["ganancia"],
                           "Costo/persona Q":r["costo_p_persona"],"Precio/persona Q":r["precio_p_persona"],
                           "Proteínas g":r["proteinas_total"],"Vegetales":r["vegetales_total"]}
                          for r in resultados]
                    df=pd.DataFrame(rows)
                    min_costo=df["Costo total Q"].min()
                    max_prot=df["Proteínas g"].max()
                    max_veg=df["Vegetales"].max()
                    def highlight(row):
                        if row["Costo total Q"]==min_costo: return ["background-color:#fef9c3"]*len(row)
                        if row["Proteínas g"]==max_prot:    return ["background-color:#dbeafe"]*len(row)
                        if row["Vegetales"]==max_veg:       return ["background-color:#dcfce7"]*len(row)
                        return [""]*len(row)
                    st.dataframe(df.style.apply(highlight,axis=1),use_container_width=True,hide_index=True)
                    st.markdown("🟡 **Amarillo** = más económico &nbsp;|&nbsp; 🔵 **Azul** = mayor proteína &nbsp;|&nbsp; 🟢 **Verde** = más vegetales")
                    st.markdown("---")
                    st.markdown("**🏆 Recomendaciones:**")
                    col1,col2,col3=st.columns(3)
                    eco=min(resultados,key=lambda x:x["costo_total"])
                    prt=max(resultados,key=lambda x:x["proteinas_total"])
                    veg=max(resultados,key=lambda x:x["vegetales_total"])
                    col1.success(f"💰 **Más económico**\n\n{eco['menu']['nombre']}\nQ {eco['costo_total']:.2f}")
                    col2.info(f"💪 **Mayor proteína**\n\n{prt['menu']['nombre']}\n{prt['proteinas_total']:.1f} g")
                    col3.success(f"🥦 **Más vegetales**\n\n{veg['menu']['nombre']}\n{veg['vegetales_total']} ingredientes")

# ══════════════════════════════════════════════════════════════════════════════
# CAJAS
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "📦 Cajas":
    st.subheader("📦 Cajas")
    tab_ver,tab_nuevo,tab_editar,tab_rec=st.tabs(["📄 Ver todas","➕ Nueva","✏️ Editar","🔗 Recetas"])

    with tab_nuevo:
        c1,c2,c3=st.columns(3)
        cn=c1.text_input("Nombre *",key="cj_n"); cd=c2.text_input("Descripción",key="cj_d")
        cp=c3.number_input("Precio Q",min_value=0.0,step=5.0,key="cj_p")
        if st.button("💾 Crear caja",type="primary",key="btn_cjnew"):
            if not cn.strip(): st.error("Nombre obligatorio.")
            else:
                agregar_caja(cn.strip(),cd.strip(),cp)
                st.success(f"✅ **{cn}** creada."); st.rerun()

    with tab_ver:
        cajas=get_cajas()
        if cajas:
            for c in cajas:
                recs=get_caja_recetas(c["id"]); nombres=", ".join(r["nombre"] for r in recs) or "Sin recetas"
                with st.expander(f"**{c['nombre']}** — Q {c['precio_venta']:.2f}"):
                    st.write(f"**Recetas:** {nombres}")
        else: st.info("Sin cajas.")

    with tab_editar:
        cajas=get_cajas()
        if cajas:
            co={c["nombre"]:c for c in cajas}
            sel=st.selectbox("Caja",list(co.keys()),key="cjedit_sel"); caja=co[sel]
            c1,c2,c3=st.columns(3)
            en=c1.text_input("Nombre",value=caja["nombre"],key="cje_n")
            ed=c2.text_input("Descripción",value=caja["descripcion"],key="cje_d")
            ep=c3.number_input("Precio Q",min_value=0.0,step=5.0,value=float(caja["precio_venta"]),key="cje_p")
            col1,col2=st.columns(2)
            if col1.button("💾 Guardar",type="primary",key="btn_cjupd"):
                Qexec_update("cajas",{"nombre":en.strip(),"descripcion":ed.strip(),"precio_venta":ep},{"id":caja["id"]})
                st.success("✅ Actualizado."); st.rerun()
            if col2.button("🗑 Eliminar",type="secondary",key="btn_cjdel"):
                Qexec_delete("caja_recetas",{"caja_id":caja["id"]})
                Qexec_update("cajas",{"activa":0},{"id":caja["id"]})
                st.warning(f"🗑 **{caja['nombre']}** eliminada."); st.rerun()

    with tab_rec:
        cajas=get_cajas(); recetas=get_recetas()
        if not cajas: st.warning("Primero crea una caja.")
        elif not recetas: st.warning("Primero crea recetas.")
        else:
            co={c["nombre"]:c["id"] for c in cajas}; ro={r["nombre"]:r["id"] for r in recetas}
            sel_c=st.selectbox("Caja",list(co.keys()),key="cjrec_csel"); cid=co[sel_c]
            actuales=get_caja_recetas(cid)
            if actuales:
                for r in actuales:
                    col1,col2=st.columns([4,1]); col1.write(f"• {r['nombre']}")
                    if col2.button("🗑",key=f"dcr_{r['id']}"):
                        Qexec_delete("caja_recetas",{"id":r["id"]})
                        st.rerun()
            else: st.info("Sin recetas.")
            sel_r=st.selectbox("Agregar receta",list(ro.keys()),key="cjrec_rsel")
            if st.button("➕ Agregar",type="primary",key="btn_cjradd"):
                agregar_receta_a_caja(cid,ro[sel_r])
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
            cliente=c1.text_input("Cliente *",key="ped_cli")
            fecha_ent=c2.date_input("Fecha entrega",min_value=date.today(),key="ped_fec")
            co={c["nombre"]:c["id"] for c in cajas}
            if "items_pedido" not in st.session_state: st.session_state.items_pedido=[]
            st.caption("💡 Las porciones aplican igual para todas las recetas de la caja.")
            c1,c2,c3=st.columns(3)
            sc=c1.selectbox("Caja",list(co.keys()),key="ped_caja")
            cant=c2.number_input("Cantidad",min_value=1,value=1,key="ped_cant")
            porc=c3.number_input("Porciones",min_value=0.5,value=1.0,step=0.5,key="ped_porc")
            col1,col2=st.columns([1,3])
            if col1.button("➕ Agregar",key="btn_ped_add"):
                st.session_state.items_pedido.append({"caja_id":co[sc],"nombre":sc,"cantidad":cant,"porciones":porc})
            if col2.button("🗑 Limpiar",key="btn_ped_clr"): st.session_state.items_pedido=[]
            if st.session_state.items_pedido:
                df=pd.DataFrame(st.session_state.items_pedido)[["nombre","cantidad","porciones"]]
                df["Factor"]=df["cantidad"]*df["porciones"]; df.columns=["Caja","Cajas","Porciones","Factor MRP"]
                st.dataframe(df,use_container_width=True,hide_index=True)
                if st.button("💾 Guardar pedido",type="primary",key="btn_ped_save"):
                    if not cliente.strip(): st.error("Cliente obligatorio.")
                    else:
                        items=[{"caja_id":i["caja_id"],"cantidad":i["cantidad"],"porciones":i["porciones"]} for i in st.session_state.items_pedido]
                        pid=crear_pedido(cliente.strip(),fecha_ent.strftime("%Y-%m-%d"),items)
                        st.success(f"✅ Pedido #{pid} guardado."); st.session_state.items_pedido=[]; st.rerun()

    with tab_ver:
        rows=get_pedidos()
        if rows:
            df=pd.DataFrame(rows)[["id","cliente","caja","cantidad","porciones","fecha_entrega","estado"]]
            df.columns=["#","Cliente","Caja","Cajas","Porciones","Fecha","Estado"]
            st.dataframe(df,use_container_width=True,hide_index=True)
        else: st.success("✅ Sin pedidos.")

    with tab_estado:
        rows=get_pedidos()
        if rows:
            pu={}
            for r in rows:
                if r["id"] not in pu: pu[r["id"]]=r
            opts={f"#{p['id']} — {p['cliente']}":p for p in pu.values()}
            sel=st.selectbox("Pedido",list(opts.keys()),key="ped_esel"); ped=opts[sel]
            ne=st.selectbox("Nuevo estado",ESTADOS,index=ESTADOS.index(ped["estado"]),key="ped_enew")
            if st.button("💾 Actualizar",type="primary",key="btn_ped_est"):
                Qexec_update("pedidos",{"estado":ne},{"id":ped["id"]})
                st.success(f"✅ Pedido #{ped['id']} → **{ne}**."); st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# MRP
# ══════════════════════════════════════════════════════════════════════════════
elif pagina == "⚙️ MRP":
    st.subheader("⚙️ Cálculo MRP")
    col1,col2=st.columns([2,1]); buffer=col2.slider("Buffer %",0,50,10,key="mrp_buf")
    if col1.button("⚙️ Calcular requerimientos",type="primary",use_container_width=True,key="btn_mrp"):
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
        if st.button("📋 Generar Órdenes de Compra",type="primary",use_container_width=True,key="btn_oc"):
            ordenes=generar_ordenes_compra(reqs,buffer_pct=buffer/100)
            if not ordenes: st.success("✅ Stock suficiente.")
            else:
                for o in ordenes:
                    pv=Q("SELECT nombre FROM proveedores WHERE id=?",(o["proveedor_id"],))
                    pn=pv[0]["nombre"] if pv else "Sin proveedor"
                    with st.expander(f"📋 Orden #{o['orden_id']} — {pn} | Q {o['total']:.2f}",expanded=True):
                        st.write(f"**Entrega:** {o['fecha']}")
                        df2=pd.DataFrame(o["items"])[["nombre","neto","cantidad","costo"]]
                        df2["subtotal"]=df2["cantidad"]*df2["costo"]
                        df2.columns=["Ingrediente","Neto",f"Con buffer {buffer}%","Costo unit.","Subtotal Q"]
                        st.dataframe(df2,use_container_width=True,hide_index=True)
    elif "mrp_reqs" in st.session_state and not st.session_state.mrp_reqs:
        st.warning("⚠ Sin pedidos pendientes.")
