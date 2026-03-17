"""
importar_csv.py — Importa y sincroniza recetas desde CSV al MRP
Uso: python importar_csv.py
"""
import csv, re, os
from database import init_db, get_connection
from mrp_engine import agregar_receta, agregar_ingrediente

def parsear_cantidad(texto):
    texto = texto.strip().lower()
    if not texto or texto in ("al gusto", ""):
        return 0.0, "al gusto"
    fraccion = re.match(r'^(\d+)/(\d+)', texto)
    if fraccion:
        num = int(fraccion.group(1)) / int(fraccion.group(2))
        resto = texto[fraccion.end():].strip()
    else:
        numero = re.match(r'^(\d+\.?\d*)', texto)
        if numero:
            num = float(numero.group(1))
            resto = texto[numero.end():].strip()
        else:
            return 0.0, texto
    resto = resto.replace("unidades","unidad").replace("units","unidad").strip()
    return round(num, 4), resto or "unidad"

FRESCOS     = ["zanahoria","cebolla","naranja","aguacate","limon","limón","tomate",
               "pollo","huevo","arroz","papa","ajo","brotes","ensalada","lechuga",
               "pepino","chile","pimiento","fruta","verdura","carne","res","cerdo"]
CONDIMENTOS = ["sal","pimienta","aceite","mantequilla","harina","pesto","comino",
               "paprika","papikra","caldo","crema","vinagre","azucar","azúcar",
               "miel","salsa","mostaza","oregano","orégano","curry","canela"]
EMPAQUES    = ["pan","empaque","caja","bolsa","envase","wrap","tortilla"]

def clasificar_tipo(nombre):
    n = nombre.lower()
    for f in FRESCOS:
        if f in n: return "fresco"
    for c in CONDIMENTOS:
        if c in n: return "condimento"
    for e in EMPAQUES:
        if e in n: return "empaque"
    return "otro"

def leer_csv(ruta):
    recetas = []
    receta_actual = None
    with open(ruta, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        next(reader)
        for fila in reader:
            while len(fila) < 9: fila.append("")
            nombre_rec = fila[0].strip()
            tiempo     = fila[1].strip()
            min_prep   = fila[2].strip()
            personas   = fila[3].strip()
            ing_nombre = fila[4].strip()
            ing_cant   = fila[5].strip()
            link       = fila[8].strip()
            if nombre_rec:
                receta_actual = {"nombre": nombre_rec, "tiempo": tiempo,
                    "min_prep": int(min_prep) if min_prep.isdigit() else 0,
                    "personas": int(personas) if personas.isdigit() else 1,
                    "link": link, "ingredientes": []}
                recetas.append(receta_actual)
            if ing_nombre and receta_actual is not None:
                cantidad, unidad = parsear_cantidad(ing_cant)
                receta_actual["ingredientes"].append({
                    "nombre": ing_nombre.strip().capitalize(),
                    "cantidad": cantidad, "unidad": unidad,
                    "tipo": clasificar_tipo(ing_nombre)})
    return recetas

def importar(ruta_csv):
    init_db()
    recetas = leer_csv(ruta_csv)
    print(f"\n📥 Sincronizando {len(recetas)} recetas...\n")
    conn = get_connection()
    ing_cache = {r["nombre"].lower(): r["id"] for r in conn.execute("SELECT id,nombre FROM ingredientes")}
    conn.close()
    resumen = {"nuevas":0,"actualizadas":0,"ings_nuevos":0,"actualizados":0,"sin_cambio":0}
    for receta in recetas:
        desc = f"{receta['tiempo']} · {receta['min_prep']} min · {receta['personas']} personas"
        if receta['link']: desc += f" · {receta['link']}"
        conn = get_connection()
        existe = conn.execute("SELECT id FROM recetas WHERE nombre=?", (receta['nombre'],)).fetchone()
        conn.close()
        if existe:
            receta_id = existe["id"]
            print(f"  🔄 {receta['nombre']} — actualizando")
            resumen["actualizadas"] += 1
        else:
            receta_id = agregar_receta(receta['nombre'], desc)
            print(f"  ✅ {receta['nombre']} — nueva (id={receta_id})")
            resumen["nuevas"] += 1
        for ing in receta['ingredientes']:
            key = ing['nombre'].lower()
            if key not in ing_cache:
                ing_id = agregar_ingrediente(ing['nombre'], ing['tipo'], ing['unidad'], 0, 0, 0, None)
                ing_cache[key] = ing_id
                resumen["ings_nuevos"] += 1
            else:
                ing_id = ing_cache[key]
            conn = get_connection()
            bom_ex = conn.execute("SELECT cantidad FROM receta_ingredientes WHERE receta_id=? AND ingrediente_id=?",
                                  (receta_id, ing_id)).fetchone()
            conn.close()
            if bom_ex is None:
                with get_connection() as c:
                    c.execute("INSERT OR REPLACE INTO receta_ingredientes (receta_id,ingrediente_id,cantidad) VALUES (?,?,?)",
                              (receta_id, ing_id, ing['cantidad']))
                resumen["ings_nuevos"] += 1
            elif round(bom_ex["cantidad"],4) != round(ing['cantidad'],4):
                with get_connection() as c:
                    c.execute("UPDATE receta_ingredientes SET cantidad=? WHERE receta_id=? AND ingrediente_id=?",
                              (ing['cantidad'], receta_id, ing_id))
                resumen["actualizados"] += 1
            else:
                resumen["sin_cambio"] += 1
    print(f"\n🎉 Listo: {resumen['nuevas']} recetas nuevas, {resumen['actualizadas']} actualizadas, {resumen['ings_nuevos']} ingredientes nuevos.")

if __name__ == "__main__":
    carpeta = os.path.dirname(os.path.abspath(__file__))
    csvs = [f for f in os.listdir(carpeta) if f.endswith(".csv")]
    if not csvs:
        print("❌ No se encontró CSV en la carpeta.")
    elif len(csvs) == 1:
        importar(os.path.join(carpeta, csvs[0]))
    else:
        print("Varios CSV:"); [print(f"  {i+1}. {f}") for i,f in enumerate(csvs)]
        importar(os.path.join(carpeta, csvs[int(input("¿Cuál? "))-1]))
