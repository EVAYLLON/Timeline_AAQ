from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from task_loader import (
    load_tasks,
    save_tasks,
    flatten_tasks,
    dataframe_to_nested_json
)
from gantt import build_ms_project_gantt_html, export_gantt_html


BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "config" / "tasks.json"
REPORT_PATH = BASE_DIR / "reports" / "gantt.html"

st.set_page_config(
    page_title="Project Tracker MS Project Style",
    page_icon="📊",
    layout="wide"
)

st.title("Project Tracker")


# ========================
# CARGA DATOS
# ========================

@st.cache_data(show_spinner=False)
def cached_load(path: str):
    data = load_tasks(path)
    return flatten_tasks(data)


def reload_data():
    st.cache_data.clear()
    st.session_state["df"] = cached_load(str(JSON_PATH))


if "df" not in st.session_state:
    reload_data()


def calcular_estado(avance):
    if avance >= 100:
        return "Completado"
    elif avance == 0:
        return "No iniciado"
    else:
        return "En curso"


df = st.session_state["df"].copy()

# ========================
# LIMPIEZA DE DATOS
# ========================

df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

text_cols = [
    "level", "project_id", "project_name",
    "item_name", "responsible",
    "status", "timeline_status", "document_url"
]

for col in text_cols:
    df[col] = df[col].fillna("").astype(str)

df = df.fillna("")

# ========================
# DATA EDITOR (FIX CLAVE)
# ========================

# ❌ quitar columnas internas
df_display = df.drop(columns=["item_id", "parent_id", "level_order"], errors="ignore")

# ✅ recalcular estado
df_display["status"] = df_display["progress"].apply(calcular_estado)

edited_df = st.data_editor(
    df_display,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "level": st.column_config.SelectboxColumn(
            "Nivel",
            options=["Proyecto", "Tarea", "Subtarea"],
            required=True
        ),
        "project_id": st.column_config.TextColumn("ID Proyecto"),
        "project_name": st.column_config.TextColumn("Nombre Proyecto"),
        "item_name": st.column_config.TextColumn("Nombre Item"),
        "responsible": st.column_config.TextColumn("Responsable"),
        "start_date": st.column_config.DateColumn("Fecha inicio"),
        "end_date": st.column_config.DateColumn("Fecha fin"),
        "progress": st.column_config.NumberColumn("Avance %"),
        "status": st.column_config.TextColumn("Estado operativo", disabled=True),
        "timeline_status": st.column_config.TextColumn("Estado plazo", disabled=True),
        "document_url": st.column_config.TextColumn("Documento")
    },
    disabled=["status", "timeline_status"],
    key="task_editor"
)

# ========================
# RECONSTRUCCIÓN SEGURA
# ========================

full_df = edited_df.copy()

# ✅ TIPOS SEGUROS
full_df["start_date"] = pd.to_datetime(full_df["start_date"], errors="coerce")
full_df["end_date"] = pd.to_datetime(full_df["end_date"], errors="coerce")
full_df["progress"] = pd.to_numeric(full_df["progress"], errors="coerce").fillna(0)

# ✅ limpiar valores vacíos peligrosos
full_df = full_df.fillna("")

# ✅ estado recalculado
full_df["status"] = full_df["progress"].apply(calcular_estado)

# ✅ nivel automático (FIX clave)
mapping = {"Proyecto": 0, "Tarea": 1, "Subtarea": 2}
full_df["level_order"] = full_df["level"].map(mapping).fillna(2).astype(int)

# ✅ columnas internas
full_df["item_id"] = range(1, len(full_df) + 1)
full_df["parent_id"] = ""


# ========================
# BOTONES
# ========================

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Guardar JSON", type="primary"):
        new_json = dataframe_to_nested_json(full_df)
        save_tasks(new_json, JSON_PATH)
        reload_data()
        st.success("Guardado correctamente")

with col2:
    if st.button("Actualizar Gantt"):
        st.session_state["df"] = flatten_tasks(
            dataframe_to_nested_json(full_df)
        )
        st.success("Actualizado")

with col3:
    if st.button("Exportar HTML"):
        html = build_ms_project_gantt_html(full_df)
        export_gantt_html(html, REPORT_PATH)
        st.success(f"Exportado en {REPORT_PATH}")


# ========================
# KPIs
# ========================

st.markdown("---")

current_df = flatten_tasks(dataframe_to_nested_json(full_df))

k1, k2, k3, k4 = st.columns(4)

k1.metric("Total", len(current_df))
k2.metric("Completados", (current_df["timeline_status"] == "Completado").sum())
k3.metric("En riesgo", (current_df["timeline_status"] == "En riesgo").sum())
k4.metric("Vencidos", (current_df["timeline_status"] == "Vencido").sum())


# ========================
# GANTT
# ========================

zoom = st.selectbox(
    "Zoom",
    ["Proyecto completo", "30 días", "60 días"]
)

html = build_ms_project_gantt_html(current_df, zoom=zoom)

components.html(html, height=600, scrolling=True)