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

    if not res.data:
        return pd.DataFrame(columns=[
            "nivel","project_name","item_name",
            "responsible","start_date","end_date","progress"
        ])

    df = pd.DataFrame(res.data)
    df["project_name"] = df["project_name"].astype(str).str.strip()

    return df

# ======================
# INSERT
# ======================
def insertar(row):
    supabase.table("projects").insert(row).execute()

# ======================
# UI
# ======================
st.set_page_config(layout="wide")
st.title("Project Tracker ✅")

# 🔥 SIEMPRE DESDE DB (NO session_state)
df = cargar()

# ======================
# PROYECTOS
# ======================
proyectos = df[df["nivel"] == "Proyecto"]["project_name"].unique()

# ======================
# CREAR PROYECTO
# ======================
st.subheader("Crear nuevo proyecto")
nuevo = st.text_input("Nombre del proyecto")

if st.button("✅ Crear proyecto"):
    nombre = nuevo.strip()

    if nombre == "":
        st.warning("Nombre inválido")

    elif nombre in proyectos:
        st.warning("Ya existe")

    else:
        insertar({
            "nivel": "Proyecto",
            "project_name": nombre,
            "item_name": nombre,
            "responsible": "",
            "start_date": datetime.today().strftime("%Y-%m-%d"),
            "end_date": datetime.today().strftime("%Y-%m-%d"),
            "progress": 0
        })

        st.rerun()

# ======================
# SELECTOR
# ======================
selected = st.selectbox("Proyecto", proyectos) if len(proyectos) > 0 else None

# ======================
# AGREGAR TAREA
# ======================
if selected and st.button("➕ Tarea"):
    insertar({
        "nivel": "Tarea",
        "project_name": selected,
        "item_name": "Nueva tarea",
        "responsible": "",
        "start_date": datetime.today().strftime("%Y-%m-%d"),
        "end_date": datetime.today().strftime("%Y-%m-%d"),
        "progress": 0
    })
    st.rerun()

# ======================
# ELIMINAR PROYECTO
# ======================
if selected and st.button("🗑️ Eliminar Proyecto"):
    supabase.table("projects")\
        .delete()\
        .eq("project_name", selected)\
        .execute()
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
        use_container_width=True
    )

    if st.button("💾 Guardar cambios"):

        # 🔥 BORRAR TODO EL PROYECTO
        supabase.table("projects")\
            .delete()\
            .eq("project_name", selected)\
            .execute()

        # ✅ INSERTAR PROYECTO UNA SOLA VEZ
        insertar({
            "nivel": "Proyecto",
            "project_name": selected,
            "item_name": selected,
            "responsible": "",
            "start_date": datetime.today().strftime("%Y-%m-%d"),
            "end_date": datetime.today().strftime("%Y-%m-%d"),
            "progress": 0
        })

        # ✅ INSERTAR TAREAS
        for _, row in edited.iterrows():

            item = str(row["item_name"]).strip()

            if item == "" or item == selected:
                continue

            insertar({
                "nivel": "Tarea",
                "project_name": selected,
                "item_name": item,
                "responsible": str(row.get("responsible","")),
                "start_date": pd.to_datetime(row["start_date"]).strftime("%Y-%m-%d"),
                "end_date": pd.to_datetime(row["end_date"]).strftime("%Y-%m-%d"),
                "progress": int(row.get("progress",0))
            })

        st.success("Guardado ✅")
        st.rerun()

# ======================
# GANTT
# ======================
st.subheader("Timeline")

if not df.empty:

    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])

    html = build_ms_project_gantt_html(df)
    components.html(html, height=650)
