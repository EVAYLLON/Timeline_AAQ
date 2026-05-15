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
    layout="wide"
)

st.title("Project Tracker")

# =========================
# LOAD DATA
# =========================
@st.cache_data(show_spinner=False)
def cached_load(path: str):
    return flatten_tasks(load_tasks(path))


def reload_data():
    st.cache_data.clear()
    st.session_state["df"] = cached_load(str(JSON_PATH))


if "df" not in st.session_state:
    reload_data()

# =========================
# STATUS AUTOMÁTICO
# =========================
def calcular_estado(avance):
    try:
        avance = float(avance)
    except:
        avance = 0

    if avance >= 100:
        return "Completado"
    elif avance <= 0:
        return "No iniciado"
    else:
        return "En curso"


# =========================
# CLEAN DATA
# =========================
df = st.session_state["df"].copy()

df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

text_cols = [
    "level", "project_id", "project_name",
    "item_name", "responsible",
    "timeline_status", "document_url"
]

for col in text_cols:
    df[col] = df[col].fillna("").astype(str)

df["status"] = df["progress"].apply(calcular_estado)

# =========================
# DATA EDITOR
# =========================
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
            options=["Proyecto", "Tarea", "Subtarea"]
        ),
        "progress": st.column_config.NumberColumn("Avance %"),
        "status": st.column_config.TextColumn("Estado", disabled=True)
    },
    disabled=["status"],
    key="editor"
)

# =========================
# RECONSTRUCT DF
# =========================
full_df = edited_df.copy()

# Tipos correctos
full_df["start_date"] = pd.to_datetime(full_df["start_date"], errors="coerce")
full_df["end_date"] = pd.to_datetime(full_df["end_date"], errors="coerce")
full_df["progress"] = pd.to_numeric(full_df["progress"], errors="coerce").fillna(0)

# Status automático SIEMPRE
full_df["status"] = full_df["progress"].apply(calcular_estado)

# Level automático
level_map = {"Proyecto": 0, "Tarea": 1, "Subtarea": 2}
full_df["level_order"] = full_df["level"].map(level_map).fillna(2)

# ✅ IMPORTANTE: preservar IDs
if "item_id" in df.columns and len(df) == len(full_df):
    full_df["item_id"] = df["item_id"]
else:
    full_df["item_id"] = range(1, len(full_df) + 1)

full_df["parent_id"] = ""

# =========================
# VALIDACIÓN (CLAVE)
# =========================
def validar_df(df):
    invalid = df[
        (df["item_name"] == "") |
        (df["level"] == "") |
        (df["start_date"].isna()) |
        (df["end_date"].isna())
    ]
    return invalid


# =========================
# BOTONES
# =========================
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Guardar JSON"):

        invalid = validar_df(full_df)

        if not invalid.empty:
            st.error("❌ Hay filas incompletas. Completa nombre, nivel y fechas.")
        else:
            save_tasks(
                dataframe_to_nested_json(full_df),
                JSON_PATH
            )
            reload_data()
            st.success("Guardado correctamente ✅")

with col2:
    if st.button("Actualizar Gantt"):

        invalid = validar_df(full_df)

        if not invalid.empty:
            st.error("❌ Hay filas incompletas. No se puede actualizar.")
        else:
            # ✅ AUTOGUARDAR
            save_tasks(
                dataframe_to_nested_json(full_df),
                JSON_PATH
            )
            reload_data()
            st.success("Actualizado ✅")

with col3:
    if st.button("Exportar HTML"):
        html = build_ms_project_gantt_html(full_df)
        export_gantt_html(html, REPORT_PATH)
        st.success("Exportado ✅")

# =========================
# KPIs
# =========================
st.markdown("---")

k1, k2, k3 = st.columns(3)

k1.metric("Total", len(full_df))
k2.metric("Completados", (full_df["status"] == "Completado").sum())
k3.metric("En curso", (full_df["status"] == "En curso").sum())

# =========================
# GANTT
# =========================
zoom = st.selectbox("Zoom", ["Proyecto completo", "30 días", "60 días"])

html = build_ms_project_gantt_html(full_df, zoom=zoom)

components.html(html, height=600, scrolling=True)