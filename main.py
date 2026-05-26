from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
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
# GUARDAR (UPSERT PRO)
# ======================
def guardar_todo(df):

    columnas_validas = [
        "nivel","project_name","item_name","responsible",
        "start_date","end_date","progress","estado","document_url"
    ]

    df_clean = df.reindex(columns=columnas_validas)

    df_clean = df_clean.replace({pd.NA: None})
    df_clean = df_clean.where(df_clean.notnull(), None)

    # ✅ eliminar duplicados antes de upsert
    df_clean = df_clean.drop_duplicates(
        subset=["project_name","item_name","nivel"],
        keep="last"
    )

    df_clean["start_date"] = pd.to_datetime(df_clean["start_date"], errors="coerce").dt.date
    df_clean["end_date"] = pd.to_datetime(df_clean["end_date"], errors="coerce").dt.date

    df_clean["start_date"] = df_clean["start_date"].astype(str)
    df_clean["end_date"] = df_clean["end_date"].astype(str)

    df_clean["progress"] = pd.to_numeric(df_clean["progress"], errors="coerce").fillna(0)

    df_clean["updated_at"] = datetime.utcnow().isoformat()

    data = df_clean.to_dict(orient="records")

    supabase.table("projects").upsert(
        data,
        on_conflict="project_name,item_name,nivel"
    ).execute()

    st.success("✅ Guardado correctamente")


# ======================
# FUNCIONES
# ======================
def calcular_estado(x):
    x = float(x) if pd.notna(x) else 0
    if x >= 100:
        return "Completado"
    elif x <= 0:
        return "No iniciado"
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
    return "En plazo"


# ======================
# CONFIG
# ======================
BASE_DIR = Path(__file__).resolve().parent
REPORT_PATH = BASE_DIR / "reports" / "gantt.html"

st.set_page_config(layout="wide")
st.title("Project Tracker (Jerarquía real)")

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
# SELECTOR PROYECTO
# ======================
st.subheader("Gestión")

projects = df[df["nivel"] == "Proyecto"]["project_name"].unique()

selected_project = st.selectbox(
    "Selecciona Proyecto",
    projects if len(projects) > 0 else ["(sin proyectos)"]
)

col1, col2 = st.columns(2)

# ======================
# AGREGAR PROYECTO
# ======================
with col1:
    if st.button("➕ Nuevo Proyecto"):

        new_proj = pd.DataFrame([{
            "nivel": "Proyecto",
            "project_name": f"Proyecto {len(projects)+1}",
            "item_name": f"Proyecto {len(projects)+1}",
            "responsible": "",
            "start_date": datetime.today().date(),
            "end_date": datetime.today().date(),
            "progress": 0
        }])

        df = pd.concat([df, new_proj], ignore_index=True)
        guardar_todo(df)
        st.rerun()

# ======================
# AGREGAR TAREA
# ======================
with col2:
    if st.button("➕ Nueva Tarea") and selected_project != "(sin proyectos)":

        new_task = pd.DataFrame([{
            "nivel": "Tarea",
            "project_name": selected_project,
            "item_name": "Nueva tarea",
            "responsible": "",
            "start_date": datetime.today().date(),
            "end_date": datetime.today().date(),
            "progress": 0
        }])

        df = pd.concat([df, new_task], ignore_index=True)
        guardar_todo(df)
        st.rerun()


# ======================
# EDITOR (SOLO PROYECTO SELECCIONADO)
# ======================
st.subheader("Editor")

df_edit = df[df["project_name"] == selected_project]

edited = st.data_editor(
    df_edit,
    use_container_width=True,
    num_rows="dynamic",
    key="main_editor"
)

# ======================
# GUARDAR EDICIÓN
# ======================
if st.button("💾 Guardar Cambios"):

    df_total = df.copy()

    df_total = df_total[~df_total["project_name"].eq(selected_project)]
    df_total = pd.concat([df_total, edited], ignore_index=True)

    guardar_todo(df_total)


# ======================
# GANTT
# ======================
st.subheader("Timeline")

if not df.empty:

    start_series = pd.to_datetime(df["start_date"], errors="coerce").dropna()
    end_series = pd.to_datetime(df["end_date"], errors="coerce").dropna()

    start_default = start_series.min().date() if not start_series.empty else datetime.today().date()
    end_default = end_series.max().date() if not end_series.empty else datetime.today().date()

    start_date = st.date_input("Inicio", value=start_default)
    end_date = st.date_input("Fin", value=end_default)

    html = build_ms_project_gantt_html(df, start_date, end_date)
    components.html(html, height=650, scrolling=False)

else:
    st.warning("⚠️ No hay datos")
