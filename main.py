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
    page_title="Project Tracker",
    page_icon="📊",
    layout="wide"
)

st.title("Project Tracker")

# ======================
# LOAD
# ======================
@st.cache_data(show_spinner=False)
def cached_load(path: str):
    return flatten_tasks(load_tasks(path))


def reload_data():
    st.cache_data.clear()
    st.session_state["df"] = cached_load(str(JSON_PATH))


if "df" not in st.session_state:
    reload_data()


# ======================
# STATUS AUTOMÁTICO ✅
# ======================
def calcular_estado(avance):
    try:
        avance = float(avance)
    except:
        return "No iniciado"

    if avance >= 100:
        return "Completado"
    elif avance <= 0:
        return "No iniciado"
    else:
        return "En curso"


# ======================
# CLEAN DATA
# ======================
df = st.session_state["df"].copy()

df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

for col in [
    "level", "project_id", "project_name",
    "item_name", "responsible",
    "timeline_status", "document_url"
]:
    df[col] = df[col].fillna("").astype(str)

df = df.fillna("")

# ✅ recalcular SIEMPRE el status
df["status"] = df["progress"].apply(calcular_estado)

# ======================
# DATA EDITOR
# ======================
df_display = df.drop(
    columns=["item_id", "parent_id", "level_order"],
    errors="ignore"
)

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
        "project_id": "ID Proyecto",
        "project_name": "Nombre Proyecto",
        "item_name": "Nombre Item",
        "responsible": "Responsable",
        "start_date": "Fecha inicio",
        "end_date": "Fecha fin",
        "progress": "Avance %",
        "status": st.column_config.TextColumn("Estado", disabled=True),  # ✅ SOLO LECTURA
        "timeline_status": "Estado plazo",
        "document_url": "Documento"
    },
    disabled=["status"],
    key="editor"
)

# ======================
# RECONSTRUCT DF
# ======================
full_df = edited_df.copy()

full_df["start_date"] = pd.to_datetime(full_df["start_date"], errors="coerce")
full_df["end_date"] = pd.to_datetime(full_df["end_date"], errors="coerce")
full_df["progress"] = pd.to_numeric(full_df["progress"], errors="coerce").fillna(0)

# ✅ status SIEMPRE automático
full_df["status"] = full_df["progress"].apply(calcular_estado)

# ✅ nivel automático
mapping = {"Proyecto": 0, "Tarea": 1, "Subtarea": 2}
full_df["level_order"] = full_df["level"].map(mapping).fillna(2).astype(int)

# internos
full_df["item_id"] = range(1, len(full_df) + 1)
full_df["parent_id"] = ""


# ======================
# BUTTONS
# ======================
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Guardar JSON"):
        save_tasks(dataframe_to_nested_json(full_df), JSON_PATH)
        reload_data()
        st.success("Guardado ✅")

with col2:
    if st.button("Actualizar Gantt"):
        st.session_state["df"] = flatten_tasks(
            dataframe_to_nested_json(full_df)
        )
        st.success("Actualizado ✅")

with col3:
    if st.button("Exportar HTML"):
        html = build_ms_project_gantt_html(full_df)
        export_gantt_html(html, REPORT_PATH)
        st.success(f"Exportado ✅")


# ======================
# KPIs
# ======================
st.markdown("---")

k1, k2, k3 = st.columns(3)

k1.metric("Total", len(full_df))
k2.metric("Completados", (full_df["status"] == "Completado").sum())
k3.metric("En curso", (full_df["status"] == "En curso").sum())


# ======================
# GANTT
# ======================
zoom = st.selectbox("Zoom", ["Proyecto completo", "30 días", "60 días"])

html = build_ms_project_gantt_html(full_df, zoom=zoom)

components.html(html, height=600, scrolling=True)
