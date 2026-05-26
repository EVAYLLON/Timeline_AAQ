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
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJycmdoZHN6dnd2d3h3b3V2cWdsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkyMTc0ODMsImV4cCI6MjA5NDc5MzQ4M30.dnt7f4qTGfbr66JJiKg8TpPmgJ_Et31_OLVz3_CBpdA"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ======================
# CARGAR
# ======================
def cargar():
    res = supabase.table("projects").select("*").execute()

    columnas = ["nivel","project_name","item_name","responsible",
                "start_date","end_date","progress"]

    if not res.data:
        return pd.DataFrame(columns=columnas)

    df = pd.DataFrame(res.data)

    for col in columnas:
        if col not in df.columns:
            df[col] = None

    return df

# ======================
# INSERT SIMPLE ✅
# ======================
def insertar_registro(row):
    supabase.table("projects").insert(row).execute()

# ======================
# TIMELINE
# ======================
def timeline(row):
    today = pd.Timestamp.today().normalize()

    if row["progress"] >= 100:
        return "Completado"

    end = pd.to_datetime(row["end_date"], errors="coerce")

    if pd.isna(end):
        return ""

    if end < today:
        return "Vencido"

    if (end - today).days <= 5:
        return "En riesgo"

    return "En plazo"

# ======================
# UI
# ======================
st.set_page_config(layout="wide")
st.title("Project Tracker ✅")

df = cargar()

# ======================
# PROYECTOS
# ======================
proyectos = df[df["nivel"] == "Proyecto"]["project_name"].dropna().unique()

# ======================
# CREAR PROYECTO
# ======================
st.subheader("Crear nuevo proyecto")

nuevo_nombre = st.text_input("Nombre del proyecto")

if st.button("✅ Crear proyecto"):

    if nuevo_nombre.strip() == "":
        st.warning("Ingresa nombre válido")
    else:

        nuevo = {
            "nivel": "Proyecto",
            "project_name": nuevo_nombre,
            "item_name": nuevo_nombre,
            "start_date": datetime.today().strftime("%Y-%m-%d"),
            "end_date": datetime.today().strftime("%Y-%m-%d"),
            "progress": 0
        }

        insertar_registro(nuevo)
        st.success("Proyecto creado ✅")
        st.rerun()

# ======================
# SELECTOR
# ======================
if len(proyectos) == 0:
    st.warning("⚠️ No hay proyectos")
    selected = None
else:
    selected = st.selectbox("Proyecto", proyectos, key="select_proyecto")

# ======================
# BOTONES
# ======================
col1, col2 = st.columns(2)

# ➕ TAREA
with col1:
    if selected and st.button("➕ Tarea"):

        nueva_tarea = {
            "nivel": "Tarea",
            "project_name": selected,
            "item_name": "Nueva tarea",
            "start_date": datetime.today().strftime("%Y-%m-%d"),
            "end_date": datetime.today().strftime("%Y-%m-%d"),
            "progress": 0
        }

        insertar_registro(nueva_tarea)
        st.rerun()

# 🗑 BORRAR PROYECTO
with col2:
    if selected and st.button("🗑️ Eliminar Proyecto"):

        supabase.table("projects")\
            .delete()\
            .eq("project_name", selected)\
            .execute()

        st.success("Eliminado ✅")
        st.rerun()

# ======================
# EDITOR
# ======================
if selected:

    st.subheader("Editor")

    df_edit = df[df["project_name"] == selected].copy()

    edited = st.data_editor(
        df_edit,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "nivel": st.column_config.TextColumn("Nivel", disabled=True),
            "start_date": st.column_config.DateColumn("Inicio"),
            "end_date": st.column_config.DateColumn("Fin"),
        }
    )

    if st.button("💾 Guardar cambios"):

        # eliminar proyecto actual
        supabase.table("projects")\
            .delete()\
            .eq("project_name", selected)\
            .execute()

        # insertar de nuevo (limpio)
        for _, row in edited.iterrows():
            insertar_registro(row.to_dict())

        st.success("Guardado ✅")
        st.rerun()

# ======================
# GANTT
# ======================
st.subheader("Timeline")

if not df.empty:
    df["timeline_status"] = df.apply(timeline, axis=1)
    html = build_ms_project_gantt_html(df)
    components.html(html, height=650)
