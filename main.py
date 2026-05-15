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

st.set_page_config(layout="wide")
st.title("Project Tracker")


# ======================
# LOAD DATA
# ======================
@st.cache_data(show_spinner=False)
def cached_load(path):
    return flatten_tasks(load_tasks(path))


def reload_data():
    st.cache_data.clear()
    st.session_state["df"] = cached_load(str(JSON_PATH))


if "df" not in st.session_state:
    reload_data()


# ======================
# FUNCIONES
# ======================
def calcular_estado(avance):
    avance = float(avance) if pd.notnull(avance) else 0
    if avance >= 100:
        return "Completado"
    elif avance <= 0:
        return "No iniciado"
    else:
        return "En curso"


def calcular_timeline(row):
    today = pd.Timestamp.today()

    if row["end_date"] < today:
        return "Vencido"
    elif (row["end_date"] - today).days <= 5:
        return "En riesgo"
    else:
        return "En plazo"


# ======================
# LIMPIEZA
# ======================
df = st.session_state["df"].copy()

df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

for col in ["level", "item_name", "responsible", "document_url"]:
    df[col] = df[col].fillna("").astype(str)

# ✅ status automático SIEMPRE
df["status"] = df["progress"].apply(calcular_estado)

# ✅ timeline automático
df["timeline_status"] = df.apply(calcular_timeline, axis=1)

# ======================
# OCULTAR COLUMNAS PROBLEMA
# ======================
df_display = df.drop(
    columns=["item_id", "parent_id", "level_order", "project_id"],
    errors="ignore"
)

# ======================
# EDITOR
# ======================
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
        "progress": st.column_config.NumberColumn("Avance %", min_value=0, max_value=100),
        "status": st.column_config.TextColumn("Estado", disabled=True),
        "timeline_status": st.column_config.TextColumn("Estado plazo", disabled=True)
    },
    disabled=["status", "timeline_status"],
    key="editor"
)

# ======================
# RECONSTRUIR DATAFRAME
# ======================
full_df = edited_df.copy()

full_df["start_date"] = pd.to_datetime(full_df["start_date"], errors="coerce")
full_df["end_date"] = pd.to_datetime(full_df["end_date"], errors="coerce")
full_df["progress"] = pd.to_numeric(full_df["progress"], errors="coerce").fillna(0)

# ✅ recalcular SIEMPRE
full_df["status"] = full_df["progress"].apply(calcular_estado)
full_df["timeline_status"] = full_df.apply(calcular_timeline, axis=1)

# ✅ nivel automático
level_map = {"Proyecto": 0, "Tarea": 1, "Subtarea": 2}
full_df["level_order"] = full_df["level"].map(level_map).fillna(2).astype(int)

# ✅ IDs
full_df["item_id"] = range(1, len(full_df) + 1)
full_df["parent_id"] = ""
full_df["project_id"] = full_df.apply(
    lambda x: f"PRJ-{str(x.name+1).zfill(3)}", axis=1
)

# ======================
# VALIDACIÓN FUERTE
# ======================
def validar(df):
    return df[
        (df["item_name"] == "") |
        (df["start_date"].isna()) |
        (df["end_date"].isna())
    ]


# ======================
# BOTONES
# ======================
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Guardar JSON"):
        invalid = validar(full_df)

        if not invalid.empty:
            st.error("❌ Filas incompletas: completa nombre y fechas")
        else:
            save_tasks(dataframe_to_nested_json(full_df), JSON_PATH)
            reload_data()
            st.success("Guardado ✅")

with col2:
    if st.button("Actualizar Gantt"):
        invalid = validar(full_df)

        if not invalid.empty:
            st.error("❌ No se puede actualizar")
        else:
            save_tasks(dataframe_to_nested_json(full_df), JSON_PATH)
            reload_data()
            st.success("Actualizado ✅")

with col3:
    if st.button("Exportar HTML"):
        html = build_ms_project_gantt_html(full_df)
        export_gantt_html(html, REPORT_PATH)
        st.success("Exportado ✅")


# ======================
# METRICS
# ======================
st.markdown("---")

k1, k2, k3, k4 = st.columns(4)

k1.metric("Total", len(full_df))
k2.metric("Completados", (full_df["status"] == "Completado").sum())
k3.metric("En curso", (full_df["status"] == "En curso").sum())
k4.metric("Vencidos", (full_df["timeline_status"] == "Vencido").sum())


# ======================
# GANTT
# ======================
zoom = st.selectbox("Zoom", ["Proyecto completo", "30 días", "60 días"])

html = build_ms_project_gantt_html(full_df, zoom=zoom)

components.html(html, height=600, scrolling=True)