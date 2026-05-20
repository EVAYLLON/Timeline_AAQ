from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
from gantt import build_ms_project_gantt_html, export_gantt_html

# ======================
# SUPABASE
# ======================
SUPABASE_URL = "https://brrghdszvwvwxwouvqgl.supabase.co"
SUPABASE_KEY = "sb_publishable_Kjb0Rhsp_tWeWxdof7-zWA_htBXB3MP"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ======================
# CARGA DATOS
# ======================
def cargar_datos():
    response = supabase.table("projects").select("*").execute()
    data = response.data

    if not data:
        return pd.DataFrame(columns=[
            "nivel","project_name","item_name","responsible",
            "start_date","end_date","progress","estado","document_url"
        ])

    return pd.DataFrame(data)

# ======================
# GUARDAR DATOS
# ======================
def guardar_todo(df):
    supabase.table("projects").delete().gt("id", 0).execute()

    columnas_validas = [
        "nivel","project_name","item_name","responsible",
        "start_date","end_date","progress","estado","document_url"
    ]

    df_clean = df.reindex(columns=columnas_validas)
    df_clean = df_clean.where(pd.notnull(df_clean), None)

    df_clean["start_date"] = df_clean["start_date"].astype(str)
    df_clean["end_date"] = df_clean["end_date"].astype(str)
    df_clean["progress"] = pd.to_numeric(df_clean["progress"], errors="coerce").fillna(0)

    data = df_clean.to_dict(orient="records")
    supabase.table("projects").insert(data).execute()

# ======================
# CONFIG
# ======================
BASE_DIR = Path(__file__).resolve().parent
REPORT_PATH = BASE_DIR / "reports" / "gantt.html"

st.set_page_config(layout="wide")
st.title("Project Tracker (Jerarquía real)")

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
# DATA
# ======================
df = cargar_datos()

# limpieza
df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

for col in ["nivel","project_name","item_name","responsible"]:
    df[col] = df[col].fillna("").astype(str)

df["estado"] = df["progress"].apply(calcular_estado)
df["timeline_status"] = df.apply(calcular_timeline, axis=1)

df["start_date"] = df["start_date"].dt.date
df["end_date"] = df["end_date"].dt.date

# ======================
# UI
# ======================
df_display = df.drop(
    columns=["id","item_id","parent_id","project_id","nivel_order"],
    errors="ignore"
)

edited_df = st.data_editor(
    df_display,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "nivel": st.column_config.SelectboxColumn(
            "Nivel",
            options=["Proyecto","Tarea","Subtarea"]
        ),
        "start_date": st.column_config.DateColumn("Inicio"),
        "end_date": st.column_config.DateColumn("Fin"),
        "estado": st.column_config.TextColumn("Estado", disabled=True),
        "timeline_status": st.column_config.TextColumn("Estado plazo", disabled=True)
    },
    disabled=["estado","timeline_status"]
)

# ======================
# RECONSTRUCCION
# ======================
full_df = edited_df.copy()

full_df["start_date"] = pd.to_datetime(full_df["start_date"], errors="coerce")
full_df["end_date"] = pd.to_datetime(full_df["end_date"], errors="coerce")

full_df["progress"] = pd.to_numeric(full_df["progress"], errors="coerce").fillna(0)

full_df["estado"] = full_df["progress"].apply(calcular_estado)
full_df["timeline_status"] = full_df.apply(calcular_timeline, axis=1)

# ======================
# 🔥 FIX FINAL GANTT (CLAVE)
# ======================
orden = {"Proyecto": 0, "Tarea": 1, "Subtarea": 2}
full_df["nivel_order"] = full_df["nivel"].map(orden)

proyectos = full_df[full_df["nivel"] == "Proyecto"]
tareas = full_df[full_df["nivel"] != "Proyecto"]

df_ordenado = []

for _, proj in proyectos.iterrows():
    df_ordenado.append(proj.to_dict())

    tareas_proj = tareas[tareas["project_name"] == proj["project_name"]]
    tareas_proj = tareas_proj.sort_values(by=["nivel_order","start_date"])

    df_ordenado.extend(tareas_proj.to_dict("records"))

full_df = pd.DataFrame(df_ordenado).reset_index(drop=True)

# ======================
# BOTONES
# ======================
if st.button("Guardar cambios"):
    full_df["start_date"] = full_df["start_date"].astype(str)
    full_df["end_date"] = full_df["end_date"].astype(str)

    guardar_todo(full_df)
    st.success("Guardado en Supabase ✅")
    st.rerun()

if st.button("Exportar HTML"):
    html = build_ms_project_gantt_html(full_df)
    export_gantt_html(html, REPORT_PATH)
    st.success("Exportado ✅")

# ======================
# GANTT
# ======================
zoom = st.selectbox("Zoom", ["Proyecto completo","30 días","60 días"])

html = build_ms_project_gantt_html(full_df, zoom=zoom)

components.html(html, height=600, scrolling=True)