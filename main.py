from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client

# ======================
# SUPABASE
# ======================
supabase = create_client(
    "https://brrghdszvwvwxwouvqgl.supabase.co",
    "sb_publishable_Kjb0Rhsp_tWeWxdof7-zWA_htBXB3MP"
)

# ======================
# CARGA DATOS
# ======================
def cargar_datos():
    response = supabase.table("projects").select("*").execute()
    data = response.data

    if not data:
        return pd.DataFrame(columns=[
            "id",
            "nivel",
            "project_name",
            "item_name",
            "responsible",
            "start_date",
            "end_date",
            "progress",
            "estado",
            "document_url"
        ])

    return pd.DataFrame(data)

# ======================
# GUARDAR (FIX REAL)
# ======================
def guardar_todo(df):

    columnas_validas = [
        "id",
        "nivel",
        "project_name",
        "item_name",
        "responsible",
        "start_date",
        "end_date",
        "progress",
        "estado",
        "document_url"
    ]

    df_clean = df.reindex(columns=columnas_validas)

    # ✅ LIMPIEZA
    df_clean = df_clean.replace({pd.NA: None})
    df_clean = df_clean.astype(object)
    df_clean = df_clean.where(pd.notnull(df_clean), None)

    df_clean["start_date"] = df_clean["start_date"].astype(str)
    df_clean["end_date"] = df_clean["end_date"].astype(str)
    df_clean["progress"] = pd.to_numeric(df_clean["progress"], errors="coerce").fillna(0)

    # ✅ evitar vacíos
    df_clean["project_name"] = df_clean["project_name"].fillna("")
    df_clean["item_name"] = df_clean["item_name"].fillna("")

    data = df_clean.to_dict(orient="records")

    # ✅ limpiar ID
    for row in data:
        id_value = row.get("id")

        if id_value is None or id_value == "" or pd.isna(id_value):
            row.pop("id", None)
        else:
            row["id"] = int(id_value)

    # ✅ 🔥 UPSERT INTELIGENTE (CLAVE)
    supabase.table("projects").upsert(
        data,
        on_conflict="project_name,item_name"
    ).execute()

# ======================
# GANTT
# ======================
from gantt import build_ms_project_gantt_html, export_gantt_html

# ======================
# APP
# ======================
st.set_page_config(layout="wide")
st.title("Project Tracker (Jerarquía real)")

df = cargar_datos()

# ======================
# LOGICA
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

    progress = pd.to_numeric(row.get("progress", 0), errors="coerce")
    progress = 0 if pd.isna(progress) else progress

    if progress >= 100:
        return "Completado"

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
df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

for col in ["nivel", "project_name", "item_name", "responsible"]:
    df[col] = df[col].fillna("").astype(str)

df["estado"] = df["progress"].apply(calcular_estado)
df["timeline_status"] = df.apply(calcular_timeline, axis=1)

df["start_date"] = df["start_date"].dt.date
df["end_date"] = df["end_date"].dt.date

# ======================
# UI
# ======================
edited_df = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "nivel": st.column_config.SelectboxColumn(
            "Nivel",
            options=["Proyecto", "Tarea", "Subtarea"]
        ),
        "estado": st.column_config.TextColumn("Estado", disabled=True),
        "timeline_status": st.column_config.TextColumn("Estado plazo", disabled=True),
        "start_date": st.column_config.DateColumn("Inicio"),
        "end_date": st.column_config.DateColumn("Fin"),
        "id": None
    },
    disabled=["estado", "timeline_status"]
)

edited_df["progress"] = pd.to_numeric(edited_df["progress"], errors="coerce").fillna(0)

# ======================
# RECONSTRUCCION
# ======================
full_df = edited_df.copy()

full_df["start_date"] = pd.to_datetime(full_df["start_date"], errors="coerce")
full_df["end_date"] = pd.to_datetime(full_df["end_date"], errors="coerce")

full_df["progress"] = pd.to_numeric(full_df["progress"], errors="coerce").fillna(0)

full_df["estado"] = full_df["progress"].apply(calcular_estado)
full_df["timeline_status"] = full_df.apply(calcular_timeline, axis=1)

# ✅ eliminar duplicados (extra seguridad)
full_df = full_df.drop_duplicates(
    subset=["nivel", "project_name", "item_name"]
)

# ✅ ORDEN CORRECTO PARA GANTT
proyectos = full_df[full_df["nivel"] == "Proyecto"]
tareas = full_df[full_df["nivel"] != "Proyecto"]

full_df = pd.concat([
    proyectos.sort_values("project_name"),
    tareas.sort_values(["project_name", "start_date"])
]).reset_index(drop=True)

# ======================
# BOTONES
# ======================
if st.button("Guardar cambios"):
    full_df["start_date"] = full_df["start_date"].astype(str)
    full_df["end_date"] = full_df["end_date"].astype(str)

    guardar_todo(full_df)

    st.success("Guardado correctamente ✅")
    st.rerun()

if st.button("Exportar HTML"):
    html_export = build_ms_project_gantt_html(full_df)
    export_gantt_html(html_export, Path("gantt.html"))
    st.success("Exportado ✅")

# ======================
# GANTT
# ======================
zoom = st.selectbox(
    "Zoom",
    ["Proyecto completo", "30 días", "60 días"]
)

html = build_ms_project_gantt_html(full_df, zoom=zoom)

components.html(html, height=600, scrolling=True)
