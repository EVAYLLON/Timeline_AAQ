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

# ======================
# CONFIG
# ======================
BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "config" / "tasks.json"
REPORT_PATH = BASE_DIR / "reports" / "gantt.html"

st.set_page_config(layout="wide")
st.title("Project Tracker (Jerarquía real)")

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
def calcular_estado(x):
    try: x = float(x)
    except: x = 0

    if x >= 100: return "Completado"
    if x <= 0: return "No iniciado"
    return "En curso"


def calcular_timeline(row):
    today = pd.Timestamp.today().normalize()
    end = row["end_date"]

    if pd.isna(end): return ""

    if end < today: return "Vencido"
    elif (end - today).days <= 5: return "En riesgo"
    return "En plazo"


# ======================
# LIMPIEZA
# ======================
df = st.session_state["df"].copy()

df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

for col in ["level", "project_name", "item_name", "responsible"]:
    df[col] = df[col].fillna("").astype(str)

df["status"] = df["progress"].apply(calcular_estado)
df["timeline_status"] = df.apply(calcular_timeline, axis=1)

df["start_date"] = df["start_date"].dt.date
df["end_date"] = df["end_date"].dt.date


# ======================
# UI SIN CAMPOS TECNICOS
# ======================
df_display = df.drop(
    columns=["item_id", "parent_id", "project_id", "level_order"],
    errors="ignore"
)

edited_df = st.data_editor(
    df_display,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "level": st.column_config.SelectboxColumn(
            "Nivel",
            options=["Proyecto", "Tarea", "Subtarea"],
            required=True
        ),
        "status": st.column_config.TextColumn("Estado", disabled=True),
        "timeline_status": st.column_config.TextColumn("Estado plazo", disabled=True)
    },
    disabled=["status", "timeline_status"]
)

# ======================
# RECONSTRUCCION
# ======================
full_df = edited_df.copy()

full_df["start_date"] = pd.to_datetime(full_df["start_date"], errors="coerce")
full_df["end_date"] = pd.to_datetime(full_df["end_date"], errors="coerce")
full_df["progress"] = pd.to_numeric(full_df["progress"], errors="coerce").fillna(0)

full_df["status"] = full_df["progress"].apply(calcular_estado)
full_df["timeline_status"] = full_df.apply(calcular_timeline, axis=1)

# ======================
# LEVEL ORDER
# ======================
level_map = {"Proyecto": 0, "Tarea": 1, "Subtarea": 2}
full_df["level_order"] = full_df["level"].map(level_map).fillna(2)

# ======================
# 🔥 JERARQUIA REAL
# ======================
full_df["item_id"] = range(1, len(full_df) + 1)

current_project_id = None
current_task_id = None

parent_ids = []

for idx, row in full_df.iterrows():

    if row["level"] == "Proyecto":
        current_project_id = row["item_id"]
        parent_ids.append("")

    elif row["level"] == "Tarea":
        parent_ids.append(current_project_id)
        current_task_id = row["item_id"]

    elif row["level"] == "Subtarea":
        parent_ids.append(current_task_id)

    else:
        parent_ids.append("")

full_df["parent_id"] = parent_ids

# ======================
# PROJECT_ID POR GRUPO
# ======================
project_map = {}
counter = 1

for i in full_df.index:
    name = full_df.loc[i, "project_name"]

    if name not in project_map:
        project_map[name] = f"PRJ-{str(counter).zfill(3)}"
        counter += 1

    full_df.loc[i, "project_id"] = project_map[name]


# ======================
# VALIDACION
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
            st.error("Completa todos los campos obligatorios")
        else:
            save_tasks(dataframe_to_nested_json(full_df), JSON_PATH)
            reload_data()
            st.success("Guardado ✅")

with col2:
    if st.button("Actualizar Gantt"):
        invalid = validar(full_df)

        if not invalid.empty:
            st.error("Datos incompletos")
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
# KPI
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