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
st.caption("Seguimiento jerárquico tipo Microsoft Project: proyectos, tareas, subtareas, responsables, plazos y documentos.")


@st.cache_data(show_spinner=False)
def cached_load(path: str):
    data = load_tasks(path)
    return flatten_tasks(data)


def reload_data():
    st.cache_data.clear()
    st.session_state["df"] = cached_load(str(JSON_PATH))


if "df" not in st.session_state:
    reload_data()


with st.sidebar:
    st.header("Controles")

    if st.button("Recargar desde JSON"):
        reload_data()
        st.success("Datos recargados desde tasks.json")

    st.markdown("---")
    st.subheader("Leyenda")
    st.markdown("""
    - 🟢 **Completado**
    - 🔵 **En plazo**
    - 🟡 **En riesgo**
    - 🔴 **Vencido**
    """)

    st.markdown("---")
    st.info("Edita la tabla, guarda cambios y actualiza el Gantt.")


def calcular_estado(avance):
    if avance >= 100:
        return "Completado"
    elif avance == 0:
        return "No iniciado"
    else:
        return "En curso"

df = st.session_state["df"].copy()


# fechas correctas
df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

# numérico
df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

# strings SOLO donde aplica
text_cols = ["level", "project_id", "project_name", "item_name",
             "responsible", "status", "timeline_status", "document_url"]

for col in text_cols:
    df[col] = df[col].fillna("").astype(str)


cols_to_hide = ["item_id", "parent_id"]


# asegurar tipos consistentes
df["level"] = df["level"].astype(str)
df["project_id"] = df["project_id"].astype(str)
df["project_name"] = df["project_name"].astype(str)
df["item_name"] = df["item_name"].astype(str)
df["responsible"] = df["responsible"].astype(str)
df["status"] = df["status"].astype(str)
df["timeline_status"] = df["timeline_status"].astype(str)
df["document_url"] = df["document_url"].astype(str)

df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

# limpiar NaN y tipos conflictivos
df = df.fillna("")



df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

df_display = df.drop(columns=["item_id", "parent_id"], errors="ignore")
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
        "level_order": st.column_config.NumberColumn("Orden nivel", disabled=True),
        "project_id": st.column_config.TextColumn("ID Proyecto"),
        "project_name": st.column_config.TextColumn("Nombre Proyecto"),
        "item_name": st.column_config.TextColumn("Nombre Item"),
        "responsible": st.column_config.TextColumn("Responsable"),
        "start_date": st.column_config.DateColumn("Fecha inicio"),
        "end_date": st.column_config.DateColumn("Fecha fin"),
        "progress": st.column_config.NumberColumn(
            "Avance %",
            min_value=0,
            max_value=100,
            step=5
        ),
        "status": st.column_config.TextColumn(
            "Estado operativo",
            disabled=True
        ),
        "timeline_status": st.column_config.TextColumn(
            "Estado plazo",
            disabled=True
        ),
        "document_url": st.column_config.LinkColumn(
            "Documento",
            display_text="Abrir documento",
            validate=r"^https?://.*"
        )
    },
    disabled=["timeline_status", "level_order"],
    key="task_editor"
)


# reconstruir dataframe completo (con columnas ocultas)
full_df = df.copy()
full_df.update(edited_df)

full_df["status"] = full_df["progress"].apply(calcular_estado)

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Guardar cambios en JSON", type="primary"):
        clean_df = edited_df.copy()
        # volver a agregar columnas internas
        clean_df["item_id"] = df["item_id"]
        clean_df["parent_id"] = df["parent_id"]
        clean_df["start_date"] = pd.to_datetime(clean_df["start_date"])
        clean_df["end_date"] = pd.to_datetime(clean_df["end_date"])

        new_json = dataframe_to_nested_json(clean_df)
        save_tasks(new_json, JSON_PATH)

        reload_data()
        st.success("Cambios guardados correctamente en tasks.json")

with col2:
    if st.button("Actualizar Gantt"):
        st.session_state["df"] = flatten_tasks(dataframe_to_nested_json(full_df))
        st.success("Gantt actualizado")

with col3:
    if st.button("Exportar Gantt HTML"):
        current_df = flatten_tasks(dataframe_to_nested_json(full_df))
        html = build_ms_project_gantt_html(current_df, zoom=zoom)
        export_gantt_html(html, REPORT_PATH)
        st.success(f"Gantt exportado en: {REPORT_PATH}")


st.markdown("---")

current_df = flatten_tasks(dataframe_to_nested_json(full_df))

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("Total elementos", len(current_df))
kpi2.metric("Completados", int((current_df["timeline_status"] == "Completado").sum()))
kpi3.metric("En riesgo", int((current_df["timeline_status"] == "En riesgo").sum()))
kpi4.metric("Vencidos", int((current_df["timeline_status"] == "Vencido").sum()))

zoom = st.selectbox(
    "Zoom del Gantt",
    ["Proyecto completo", "30 días", "60 días"]
)

st.subheader("Gantt jerárquico tipo Microsoft Project")

html = build_ms_project_gantt_html(current_df, zoom=zoom)
num_rows = len(current_df)
height = max(400, 40 * num_rows)
components.html(html, height=height, scrolling=True)


st.subheader("Referencias documentales")

links_df = current_df[
    current_df["document_url"].fillna("").str.startswith("http")
][["level", "project_name", "item_name", "responsible", "document_url"]]

if links_df.empty:
    st.info("No existen links documentales cargados.")
else:
    st.dataframe(links_df, use_container_width=True)
