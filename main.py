from datetime import datetime
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
from gantt import build_ms_project_gantt_html

# ======================
# SUPABASE
# ======================
SUPABASE_URL = "https://brrghdszvwvwxwouvqgl.supabase.co"
SUPABASE_KEY = "sb_publishable_key"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ======================
# CARGAR
# ======================
def cargar():
    res = supabase.table("projects").select("*").execute()
    data = res.data

    if not data:
        return pd.DataFrame(columns=[
            "nivel","project_name","item_name",
            "responsible","start_date","end_date","progress"
        ])

    return pd.DataFrame(data)

# ======================
# GUARDAR
# ======================
def guardar(df):

    df = df.copy()

    # ✅ limpiar strings
    for col in ["nivel","project_name","item_name","responsible"]:
        df[col] = df[col].fillna("").astype(str)

    # ✅ eliminar filas inválidas
    df = df[df["item_name"].str.strip() != ""]
    df = df[df["project_name"].str.strip() != ""]

    # ✅ convertir fechas (NO eliminar filas)
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

    df["start_date"] = df["start_date"].dt.strftime("%Y-%m-%d")
    df["end_date"] = df["end_date"].dt.strftime("%Y-%m-%d")

    df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

    df["updated_at"] = datetime.utcnow().isoformat()

    supabase.table("projects").upsert(
        df.to_dict("records"),
        on_conflict="project_name,item_name,nivel"
    ).execute()

# ======================
# UI
# ======================
st.set_page_config(layout="wide")
st.title("Project Tracker ✅")

df = cargar()

# ======================
# PROYECTO
# ======================
proyectos = df[df["nivel"] == "Proyecto"]["project_name"].unique()

selected = None
if len(proyectos) > 0:
    selected = st.selectbox("Proyecto", proyectos)
else:
    st.warning("Crea un proyecto")

col1, col2 = st.columns(2)

# ✅ NUEVO PROYECTO
with col1:
    if st.button("➕ Proyecto"):
        nombre = f"Proyecto {len(proyectos)+1}"

        new = pd.DataFrame([{
            "nivel": "Proyecto",
            "project_name": nombre,
            "item_name": nombre,
            "start_date": datetime.today(),
            "end_date": datetime.today(),
            "progress": 0
        }])

        guardar(pd.concat([df, new], ignore_index=True))
        st.rerun()

# ✅ NUEVA TAREA
with col2:
    if selected and st.button("➕ Tarea"):
        new = pd.DataFrame([{
            "nivel": "Tarea",
            "project_name": selected,
            "item_name": "Nueva tarea",
            "start_date": datetime.today(),
            "end_date": datetime.today(),
            "progress": 0
        }])

        guardar(pd.concat([df, new], ignore_index=True))
        st.rerun()

# ======================
# EDITOR
# ======================
if selected:

    st.subheader("Editor")

    df_proj = df[df["project_name"] == selected].copy()

    df_proj["start_date"] = pd.to_datetime(df_proj["start_date"], errors="coerce")
    df_proj["end_date"] = pd.to_datetime(df_proj["end_date"], errors="coerce")

    edited = st.data_editor(
        df_proj,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "start_date": st.column_config.DateColumn("Inicio"),
            "end_date": st.column_config.DateColumn("Fin"),
        }
    )

    if st.button("💾 Guardar cambios"):

        edited = edited.copy()

        # ✅ asegurar proyecto
        edited["project_name"] = selected

        df_total = df[df["project_name"] != selected]
        df_total = pd.concat([df_total, edited], ignore_index=True)

        guardar(df_total)

        st.success("Guardado ✅")
        st.rerun()

# ======================
# GANTT
# ======================
st.subheader("Timeline")

if not df.empty:

    df = df.copy()

    # ✅ solo datos válidos
    proyectos_validos = df[df["nivel"] == "Proyecto"]["project_name"]

    df = df[
        (df["nivel"] == "Proyecto") |
        (df["project_name"].isin(proyectos_validos))
    ]

    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

    html = build_ms_project_gantt_html(df)

    components.html(html, height=650)
