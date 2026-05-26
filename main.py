from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
from supabase import create_client
from gantt import build_ms_project_gantt_html

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
    res = supabase.table("projects").select("*").execute()
    return pd.DataFrame(res.data if res.data else [])

# ======================
# GUARDAR (UPSERT)
# ======================
def guardar(df):

    df = df.copy()

    # columnas válidas
    columnas = [
        "nivel","project_name","item_name","responsible",
        "start_date","end_date","progress","estado","document_url"
    ]

    df = df.reindex(columns=columnas)

    df = df.replace({pd.NA: None})
    df = df.where(df.notnull(), None)

    # eliminar duplicados
    df = df.drop_duplicates(
        subset=["project_name","item_name","nivel"],
        keep="last"
    )

    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.date.astype(str)
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce").dt.date.astype(str)

    df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

    df["updated_at"] = datetime.utcnow().isoformat()

    supabase.table("projects").upsert(
        df.to_dict("records"),
        on_conflict="project_name,item_name,nivel"
    ).execute()

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
    progress = float(row.get("progress", 0) or 0)

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
st.set_page_config(layout="wide")
st.title("Project Tracker (Simple y limpio)")

# ======================
# DATA
# ======================
df = cargar_datos()

if df.empty:
    st.warning("⚠️ No hay datos. Crea un proyecto")

df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

df["estado"] = df["progress"].apply(calcular_estado)
df["timeline_status"] = df.apply(calcular_timeline, axis=1)

df["start_date"] = df["start_date"].dt.date
df["end_date"] = df["end_date"].dt.date

# ======================
# SELECTOR PROYECTO
# ======================
projects = df[df["nivel"] == "Proyecto"]["project_name"].unique()

selected = st.selectbox("Proyecto", projects)

col1, col2 = st.columns(2)

# ======================
# NUEVO PROYECTO
# ======================
with col1:
    if st.button("➕ Nuevo Proyecto"):
        new = pd.DataFrame([{
            "nivel": "Proyecto",
            "project_name": f"Proyecto {len(projects)+1}",
            "item_name": f"Proyecto {len(projects)+1}",
            "responsible": "",
            "start_date": datetime.today(),
            "end_date": datetime.today(),
            "progress": 0
        }])
        guardar(pd.concat([df, new]))
        st.rerun()

# ======================
# NUEVA TAREA
# ======================
with col2:
    if st.button("➕ Nueva Tarea"):
        new = pd.DataFrame([{
            "nivel": "Tarea",
            "project_name": selected,
            "item_name": "Nueva tarea",
            "responsible": "",
            "start_date": datetime.today(),
            "end_date": datetime.today(),
            "progress": 0
        }])
        guardar(pd.concat([df, new]))
        st.rerun()

# ======================
# EDITOR LIMPIO
# ======================
st.subheader("Editor")

df_edit = df[df["project_name"] == selected][[
    "item_name","responsible","start_date","end_date","progress","document_url"
]]

edited = st.data_editor(
    df_edit,
    use_container_width=True,
    num_rows="dynamic"
)

# ======================
# GUARDAR
# ======================
if st.button("💾 Guardar Cambios"):

    df_total = df.copy()

    # eliminar viejo bloque
    df_total = df_total[df_total["project_name"] != selected]

    # reconstruir con valores automáticos
    edited["nivel"] = edited["item_name"].apply(
        lambda x: "Proyecto" if x == selected else "Tarea"
    )
    edited["project_name"] = selected

    df_total = pd.concat([df_total, edited])

    guardar(df_total)

    st.success("✅ Cambios guardados")

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
