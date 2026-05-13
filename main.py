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


df = st.session_state["df"].copy()

if df.empty:
    st.warning("No existen proyectos cargados.")
    st.stop()


st.subheader("Tabla editable de seguimiento")

edited_df = st.data_editor(
    df,
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
        "item_id": st.column_config.TextColumn("ID Item"),
        "item_name": st.column_config.TextColumn("Nombre Item"),
        "parent_id": st.column_config.TextColumn("ID Padre"),
        "responsible": st.column_config.TextColumn("Responsable"),
        "start_date": st.column_config.DateColumn("Fecha inicio"),
        "end_date": st.column_config.DateColumn("Fecha fin"),
        "progress": st.column_config.NumberColumn(
            "Avance %",
            min_value=0,
            max_value=100,
            step=5
        ),
        "status": st.column_config.SelectboxColumn(
            "Estado operativo",
            options=["No iniciado", "En curso", "Completado", "Bloqueado"],
            required=True
        ),
        "timeline_status": st.column_config.TextColumn(
            "Estado plazo",
            disabled=True
        ),
        "document_url": st.column_config.LinkColumn(
            "Documento SharePoint / Link",
            validate=r"^https?://.*"
        )
    },
    disabled=["timeline_status", "level_order"],
    key="task_editor"
)


col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Guardar cambios en JSON", type="primary"):
        clean_df = edited_df.copy()
        clean_df["start_date"] = pd.to_datetime(clean_df["start_date"])
        clean_df["end_date"] = pd.to_datetime(clean_df["end_date"])

        new_json = dataframe_to_nested_json(clean_df)
        save_tasks(new_json, JSON_PATH)

        reload_data()
        st.success("Cambios guardados correctamente en tasks.json")

with col2:
    if st.button("Actualizar Gantt"):
        st.session_state["df"] = flatten_tasks(dataframe_to_nested_json(edited_df))
        st.success("Gantt actualizado")

with col3:
    if st.button("Exportar Gantt HTML"):
        current_df = flatten_tasks(dataframe_to_nested_json(edited_df))
        html = build_ms_project_gantt_html(current_df, zoom=zoom)
        export_gantt_html(html, REPORT_PATH)
        st.success(f"Gantt exportado en: {REPORT_PATH}")


st.markdown("---")

current_df = flatten_tasks(dataframe_to_nested_json(edited_df))

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

html = build_ms_project_gantt_html(current_df)
components.html(html, height=720, scrolling=True)


st.subheader("Referencias documentales")

links_df = current_df[
    current_df["document_url"].fillna("").str.startswith("http")
][["level", "project_name", "item_name", "responsible", "document_url"]]

if links_df.empty:
    st.info("No existen links documentales cargados.")
else:
    st.dataframe(links_df, use_container_width=True)
