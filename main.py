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
# LOAD
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
    try:
        x = float(x)
    except:
        x = 0

    if x >= 100:
        return "Completado"
    elif x <= 0:
        return "No iniciado"
    else:
        return "En curso"


def calcular_timeline(row):
    today = pd.Timestamp.today().normalize()

    # 🔥 FORZAR lectura correcta de progress
    progress = pd.to_numeric(row.get("progress", 0), errors="coerce")
    progress = 0 if pd.isna(progress) else progress

    # ✅ PRIORIDAD ABSOLUTA
    if progress >= 100:
        return "Sin riesgo"

    end = pd.to_datetime(row.get("end_date"), errors="coerce")

    if pd.isna(end):
        return ""

    if end < today:
        return "Vencido"
    elif (end - today).days <= 5:
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

for col in ["level", "project_name", "item_name", "responsible"]:
    df[col] = df[col].fillna("").astype(str)

# 🔥 CLAVE: BORRAR estado antiguo
df["status"] = ""
df["timeline_status"] = ""

# ✅ recalcular limpio SIEMPRE
df["status"] = df["progress"].apply(calcular_estado)
df["timeline_status"] = df.apply(calcular_timeline, axis=1)

# quitar hora
df["start_date"] = df["start_date"].dt.date
df["end_date"] = df["end_date"].dt.date


# ======================
# UI
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
            options=["Proyecto", "Tarea", "Subtarea"]
        ),
        "status": st.column_config.TextColumn("Estado", disabled=True),
        "timeline_status": st.column_config.TextColumn("Estado plazo", disabled=True)
    },
    disabled=["status", "timeline_status"]
)

# 🔥 FIX DEFINITIVO
edited_df["progress"] = pd.to_numeric(edited_df["progress"], errors="coerce").fillna(0)

edited_df["status"] = edited_df["progress"].apply(calcular_estado)
edited_df["timeline_status"] = edited_df.apply(calcular_timeline, axis=1)


# ======================
# RECONSTRUCCION
# ======================
full_df = edited_df.copy()

full_df["start_date"] = pd.to_datetime(full_df["start_date"], errors="coerce")
full_df["end_date"] = pd.to_datetime(full_df["end_date"], errors="coerce")

full_df["progress"] = pd.to_numeric(full_df["progress"], errors="coerce").fillna(0)

# 🔥 DOBLE SEGURIDAD
full_df["status"] = full_df["progress"].apply(calcular_estado)
full_df["timeline_status"] = full_df.apply(calcular_timeline, axis=1)


# ======================
# JERARQUIA
# ======================
level_map = {"Proyecto": 0, "Tarea": 1, "Subtarea": 2}
full_df["level_order"] = full_df["level"].map(level_map).fillna(2)

full_df["item_id"] = range(1, len(full_df) + 1)

current_project = None
current_task = None
parents = []

for _, r in full_df.iterrows():
    if r["level"] == "Proyecto":
        current_project = r["item_id"]
        parents.append("")
    elif r["level"] == "Tarea":
        parents.append(current_project)
        current_task = r["item_id"]
    elif r["level"] == "Subtarea":
        parents.append(current_task)
    else:
        parents.append("")

full_df["parent_id"] = parents


# ======================
# PROJECT ID
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
# BOTONES
# ======================
if st.button("Guardar JSON"):
    save_tasks(dataframe_to_nested_json(full_df), JSON_PATH)
    reload_data()
    st.success("Guardado ✅")

if st.button("Actualizar Gantt"):
    save_tasks(dataframe_to_nested_json(full_df), JSON_PATH)
    reload_data()
    st.success("Actualizado ✅")

if st.button("Exportar HTML"):
    html = build_ms_project_gantt_html(full_df)
    export_gantt_html(html, REPORT_PATH)
    st.success("Exportado ✅")

# ======================
# GANTT
# ======================
zoom = st.selectbox("Zoom", ["Proyecto completo", "30 días", "60 días"])

html = build_ms_project_gantt_html(full_df, zoom=zoom)

components.html(html, height=600, scrolling=True)
