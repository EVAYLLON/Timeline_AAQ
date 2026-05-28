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
    try:
        res = supabase.table("projects").select("*").execute()
    except Exception as e:
        st.error("Error en Supabase")
        st.write(e)
        return pd.DataFrame()

    if not res.data:
        return pd.DataFrame(columns=[
            "nivel","project_name","item_name",
            "responsible","start_date","end_date","progress"
        ])

    df = pd.DataFrame(res.data)

    # ✅ LIMPIAR SOLO COLUMNAS NECESARIAS
    columnas_ok = [
        "nivel","project_name","item_name",
        "responsible","start_date","end_date","progress"
    ]

    df = df[[c for c in columnas_ok if c in df.columns]]

    # ✅ LIMPIEZA
    df["project_name"] = df["project_name"].astype(str).str.strip()
    df["item_name"] = df["item_name"].astype(str).str.strip()

    return df

# ======================
# INSERT
# ======================
def insertar(row):
    supabase.table("projects").insert(row).execute()

# ======================
# TIMELINE STATUS
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

        st.success("Proyecto creado ✅")
        st.rerun()

# ======================
# SELECTOR
# ======================
selected = st.selectbox("Proyecto", proyectos) if len(proyectos) > 0 else None

# ======================
# BOTONES
# ======================
col1, col2 = st.columns(2)

# ➕ TAREA
with col1:
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

# ✅ asegurar columna de link
    if "document_url" not in df_edit.columns:
        df_edit["document_url"] = ""

    # ✅ FORMATO FECHAS PARA CALENDARIO
    df_edit["start_date"] = pd.to_datetime(df_edit["start_date"], errors="coerce")
    df_edit["end_date"] = pd.to_datetime(df_edit["end_date"], errors="coerce")

    # ✅ SOLO COLUMNAS LIMPIAS
    df_edit = df_edit[[
        "nivel","item_name","responsible",
        "start_date","end_date","progress","document_url"
    ]]

    edited = st.data_editor(
        df_edit,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "nivel": st.column_config.TextColumn("Nivel", disabled=True),
            "start_date": st.column_config.DateColumn("Inicio"),
            "end_date": st.column_config.DateColumn("Fin"),
            "progress": st.column_config.NumberColumn("Avance"),
            "document_url": st.column_config.LinkColumn("Documento")
        }
    )

    # ======================
    # GUARDAR
    # ======================
    if st.button("💾 Guardar cambios"):

        # 🔥 BORRAR TODO EL PROYECTO
        supabase.table("projects")\
            .delete()\
            .eq("project_name", selected)\
            .execute()


        row_proyecto = edited[edited["nivel"] == "Proyecto"].iloc[0]

        insertar({
            "nivel": "Proyecto",
            "project_name": selected,
            "item_name": selected,
            "responsible": str(row_proyecto.get("responsible","")),
            "start_date": pd.to_datetime(row_proyecto["start_date"]).strftime("%Y-%m-%d"),
            "end_date": pd.to_datetime(row_proyecto["end_date"]).strftime("%Y-%m-%d"),
            "progress": int(row_proyecto.get("progress",0)),
            "document_url": str(row_proyecto.get("document_url","")),
        })


        # ✅ REINSERTAR TAREAS
        for _, row in edited.iterrows():

            item = str(row.get("item_name","")).strip()

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

    # ✅ asegurar fechas
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

    # ======================
    # SESSION STATE ✅
    # ======================
    if "fecha_inicio" not in st.session_state:
        st.session_state["fecha_inicio"] = df["start_date"].min()

    if "fecha_fin" not in st.session_state:
        st.session_state["fecha_fin"] = df["end_date"].max()

    # ======================
    # SELECTOR DE FECHAS ✅
    # ======================
    col_f1, col_f2 = st.columns(2)

    with col_f1:
        fecha_inicio = st.date_input(
            "📅 Ver desde",
            value=st.session_state["fecha_inicio"]
        )

    with col_f2:
        fecha_fin = st.date_input(
            "📅 Ver hasta",
            value=st.session_state["fecha_fin"]
        )

    # ✅ guardar estado
    st.session_state["fecha_inicio"] = fecha_inicio
    st.session_state["fecha_fin"] = fecha_fin

    # ======================
    # NO FILTRAR FILAS ✅
    # ======================
    df_filtrado = df.copy()

    # ✅ status
    df_filtrado["timeline_status"] = df_filtrado.apply(timeline, axis=1)

    # ======================
    # GANTT ✅
    # ======================
    html = build_ms_project_gantt_html(
        df_filtrado,
        start_date=fecha_inicio,
        end_date=fecha_fin
    )

    components.html(html, height=650)