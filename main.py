from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client

supabase = create_client("https://brrghdszvwvwxwouvqgl.supabase.co","sb_publishable_Kjb0Rhsp_tWeWxdof7-zWA_htBXB3MP")


def cargar_datos():
    response = supabase.table("projects").select("*").execute()
    data = response.data

    if not data:
        # estructura vacía con columnas correctas
        return pd.DataFrame(columns=[
            "nivel",
            "project_name",
            "item_name",
            "responsible",
            "start_date",
            "end_date",
            "progress",
            "estado",
            "document_url"
        ])

    return pd.DataFrame(data)


def load_data():
    response = supabase.table("projects").select("*").execute()
    return pd.DataFrame(response.data)


def guardar_todo(df):
    columnas_validas = [
        "id",
        "nivel",
        "project_name",
        "item_name",
        "responsible",
        "start_date",
        "end_date",
        "progress",
        "estado",
        "document_url"
    ]

    df_clean = df.reindex(columns=columnas_validas)

    df_clean = df_clean.replace({pd.NA: None})
    df_clean = df_clean.astype(object)
    df_clean = df_clean.where(pd.notnull(df_clean), None)

    df_clean["start_date"] = df_clean["start_date"].astype(str)
    df_clean["end_date"] = df_clean["end_date"].astype(str)
    df_clean["progress"] = pd.to_numeric(df_clean["progress"], errors="coerce").fillna(0)

    data = df_clean.to_dict(orient="records")

    for row in data:
        try:
            if row.get("id") is None:
                del row["id"]

            supabase.table("projects").upsert(row, on_conflict="id").execute()

        except Exception as e:
            st.error(f"Error en fila: {row}")
            st.error(str(e))







from gantt import build_ms_project_gantt_html, export_gantt_html

# ======================
# CONFIG
# ======================
BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "config" / "tasks.json"
REPORT_PATH = BASE_DIR / "reports" / "gantt.html"

st.set_page_config(layout="wide")
st.title("Project Tracker (Jerarquía real)")

df = cargar_datos()
# ======================
# FUNCIONES
# ======================
def calcular_estado(x):
    try:
        x = float(x)
    except:
        x = 0

    if x >= 100:
        return "Completado"
    elif x <= 0:
        return "No iniciado"
    else:
        return "En curso"


def calcular_timeline(row):
    today = pd.Timestamp.today().normalize()

    progress = pd.to_numeric(row.get("progress", 0), errors="coerce")
    progress = 0 if pd.isna(progress) else progress

    # ✅ PRIORIDAD
    if progress >= 100:
        return "Completado"

    end = pd.to_datetime(row.get("end_date"), errors="coerce")

    if pd.isna(end):
        return ""

    if end < today:
        return "Vencido"
    elif (end - today).days <= 5:
        return "En riesgo"
    else:
        return "En plazo"


# ======================
# LIMPIEZA
# ======================

df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

for col in ["nivel", "project_name", "item_name", "responsible"]:
    df[col] = df[col].fillna("").astype(str)

# 🔥 CLAVE: BORRAR estado antiguo
df["timeline_status"] = ""

# ✅ recalcular limpio SIEMPRE
df["estado"] = df["progress"].apply(calcular_estado)
df["timeline_status"] = df.apply(calcular_timeline, axis=1)

# quitar hora
df["start_date"] = df["start_date"].dt.date
df["end_date"] = df["end_date"].dt.date


# ======================
# UI
# ======================
df_display = df.copy()

edited_df = st.data_editor(
    df_display,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "nivel": st.column_config.SelectboxColumn(
            "nivel",
            options=["Proyecto", "Tarea", "Subtarea"],
        ),
        "estado": st.column_config.TextColumn("Estado", disabled=True),
        "timeline_status": st.column_config.TextColumn("Estado plazo", disabled=True),
        "start_date": st.column_config.DateColumn("Inicio"),
        "end_date": st.column_config.DateColumn("Fin"),
        "id": None  # 🔥 ocultar ID
    },
    disabled=["id", "status", "timeline_status"]
)


# 🔥 FIX DEFINITIVO
edited_df["progress"] = pd.to_numeric(edited_df["progress"], errors="coerce").fillna(0)





# ======================
# RECONSTRUCCION
# ======================
full_df = edited_df.copy()

full_df["start_date"] = pd.to_datetime(full_df["start_date"], errors="coerce")
full_df["end_date"] = pd.to_datetime(full_df["end_date"], errors="coerce")

full_df["progress"] = pd.to_numeric(full_df["progress"], errors="coerce").fillna(0)

# 🔥 DOBLE SEGURIDAD
full_df["status"] = full_df["progress"].apply(calcular_estado)
full_df["timeline_status"] = full_df.apply(calcular_timeline, axis=1)


# ======================
# JERARQUIA
# ======================
nivel_map = {"Proyecto": 0, "Tarea": 1, "Subtarea": 2}
full_df["nivel_order"] = full_df["nivel"].map(nivel_map).fillna(2)

full_df["item_id"] = range(1, len(full_df) + 1)

parents = []

# mapa: nombre de proyecto → item_id del proyecto
project_ids = {}

for _, r in full_df.iterrows():
    if r["nivel"] == "Proyecto":
        project_ids[r["project_name"]] = r["item_id"]
        parents.append("")
    elif r["nivel"] == "Tarea":
        parent_id = project_ids.get(r["project_name"], "")
        parents.append(parent_id)
    elif r["nivel"] == "Subtarea":
        parent_id = project_ids.get(r["project_name"], "")
        parents.append(parent_id)
    else:
        parents.append("")


# ======================
# PROJECT ID
# ======================
project_map = {}
counter = 1

for i in full_df.index:
    name = full_df.loc[i, "project_name"]

    if name not in project_map:
        project_map[name] = f"PRJ-{str(counter).zfill(3)}"
        counter += 1

    full_df.loc[i, "project_id"] = project_map[name]


# ======================
# BOTONES
# ======================
if st.button("Guardar cambios"):
    full_df["start_date"] = full_df["start_date"].astype(str)
    full_df["end_date"] = full_df["end_date"].astype(str)
    
    full_df["estado"] = full_df["status"]

    guardar_todo(full_df)
    st.success("Guardado en Supabase ✅")
    st.rerun()

    
if st.button("Actualizar Gantt"):
    st.success("Solo visualización actualizada ✅")


if st.button("Exportar HTML"):
    html = build_ms_project_gantt_html(full_df)
    export_gantt_html(html, REPORT_PATH)
    st.success("Exportado ✅")

# ✅ AQUÍ VA
full_df["nivel_order"] = full_df["nivel"].map({
    "Proyecto": 0,
    "Tarea": 1,
    "Subtarea": 2
})

full_df = full_df.sort_values(
    by=["project_name", "nivel_order", "start_date"]
).reset_index(drop=True)

# ======================
# GANTT
# ======================
zoom = st.selectbox("Zoom", ["Proyecto completo", "30 días", "60 días"])

html = build_ms_project_gantt_html(full_df, zoom=zoom)

components.html(html, height=600, scrolling=True)
