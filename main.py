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
    return pd.DataFrame(res.data if res.data else [])

# ======================
# GUARDAR (SEGURO)
# ======================
def guardar(df):

    if df.empty:
        return

    df = df.copy()

    df = df.fillna("")

    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").fillna(datetime.today())
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce").fillna(datetime.today())

    df["start_date"] = df["start_date"].dt.strftime("%Y-%m-%d")
    df["end_date"] = df["end_date"].dt.strftime("%Y-%m-%d")

    df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

    df["updated_at"] = datetime.utcnow().isoformat()

    data = df.to_dict("records")

    if len(data) == 0:
        return

    supabase.table("projects").upsert(
        data,
        on_conflict="project_name,item_name,nivel"
    ).execute()

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
# SELECTOR PROYECTO
# ======================
proyectos = df[df["nivel"] == "Proyecto"]["project_name"].unique()

selected = st.selectbox("Proyecto", proyectos) if len(proyectos) > 0 else None

# ======================
# CREAR PROYECTO CON NOMBRE
# ======================
st.subheader("Crear nuevo proyecto")

nuevo_nombre = st.text_input("Nombre del proyecto")

if st.button("✅ Crear proyecto"):

    if nuevo_nombre.strip() == "":
        st.warning("Ingresa un nombre válido")
    else:
        new = pd.DataFrame([{
            "nivel": "Proyecto",
            "project_name": nuevo_nombre,
            "item_name": nuevo_nombre,
            "start_date": datetime.today(),
            "end_date": datetime.today(),
            "progress": 0
        }])

        guardar(pd.concat([df, new], ignore_index=True))
        st.success("Proyecto creado ✅")
        st.rerun()

# ======================
# BOTONES
# ======================
col1, col2 = st.columns(2)

# ➕ TAREA
with col1:
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

# 🗑 ELIMINAR PROYECTO
with col2:
    if selected and st.button("🗑️ Eliminar Proyecto"):

        supabase.table("projects")\
            .delete()\
            .eq("project_name", selected)\
            .execute()

        st.success(f"{selected} eliminado ✅")
        st.rerun()

# ======================
# EDITOR
# ======================
if selected:

    st.subheader("Editor")

    df_edit = df[df["project_name"] == selected][[
        "nivel","item_name","responsible",
        "start_date","end_date","progress"
    ]].copy()

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

        edited["project_name"] = selected

        # 🔥 FORZAR NIVELES
        edited["nivel"] = edited["item_name"].apply(
            lambda x: "Proyecto" if x == selected else "Tarea"
        )

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

    df["timeline_status"] = df.apply(timeline, axis=1)

    html = build_ms_project_gantt_html(df)

    components.html(html, height=650)
