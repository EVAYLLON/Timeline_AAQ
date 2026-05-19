from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client

supabase = create_client("https://brrghdszvwvwxwouvqgl.supabase.co","sb_publishable_Kjb0Rhsp_tWeWxdof7-zWA_htBXB3MP")

def cargar_datos():
    response = supabase.table("projects").select("*").execute()
    data = response.data

    if not data:
        # estructura vacía con columnas correctas
        return pd.DataFrame(columns=[
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

def guardar_todo(df):
    supabase.table("projects").delete().neq("id", 0).execute()

    columnas_validas = [
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

    df_clean = df[columnas_validas]

    data = df_clean.to_dict(orient="records")
    supabase.table("projects").insert(data).execute()


from gantt import build_ms_project_gantt_html, export_gantt_html

# ======================
# CONFIG
# ======================
BASE_DIR = Path(__file__).resolve().parent
JSON_PATH = BASE_DIR / "config" / "tasks.json"
REPORT_PATH = BASE_DIR / "reports" / "gantt.html"

st.set_page_config(layout="wide")
st.title("Project Tracker (Jerarquía real)")

df = cargar_datos()
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

    progress = pd.to_numeric(row.get("progress", 0), errors="coerce")
    progress = 0 if pd.isna(progress) else progress

    # ✅ PRIORIDAD
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

# 🔥 CLAVE: BORRAR estado antiguo
df["timeline_status"] = ""

# ✅ recalcular limpio SIEMPRE
df["estado"] = df["progress"].apply(calcular_estado)
df["timeline_status"] = df.apply(calcular_timeline, axis=1)

# quitar hora
df["start_date"] = df["start_date"].dt.date
df["end_date"] = df["end_date"].dt.date


# ======================
# UI
# ======================
df_display = df.drop(
    columns=["item_id", "parent_id", "project_id", "nivel_order"],
    errors="ignore"
)

edited_df = st.data_editor(
    df_display,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "nivel": st.column_config.SelectboxColumn(
            "nivel",
            options=["Proyecto", "Tarea", "Subtarea"],
        ),
        "status": st.column_config.TextColumn("Estado", disabled=True),
        "timeline_status": st.column_config.TextColumn("Estado plazo", disabled=True),
            "estado": st.column_config.TextColumn("Estado", disabled=True),
    "timeline_status": st.column_config.TextColumn("Estado plazo", disabled=True),
        "start_date": st.column_config.DateColumn("Inicio"),
"end_date": st.column_config.DateColumn("Fin"),

    },
    


    disabled=["status", "timeline_status"]
)

# 🔥 FIX DEFINITIVO
edited_df["progress"] = pd.to_numeric(edited_df["progress"], errors="coerce").fillna(0)





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
nivel_map = {"Proyecto": 0, "Tarea": 1, "Subtarea": 2}
full_df["nivel_order"] = full_df["nivel"].map(nivel_map).fillna(2)

full_df["item_id"] = range(1, len(full_df) + 1)

current_project = None
current_task = None
parents = []

for _, r in full_df.iterrows():
    if r["nivel"] == "Proyecto":
        current_project = r["item_id"]
        parents.append("")
    elif r["nivel"] == "Tarea":
        parents.append(current_project)
        current_task = r["item_id"]
    elif r["nivel"] == "Subtarea":
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
if st.button("Guardar cambios"):
    full_df["start_date"] = full_df["start_date"].astype(str)
    full_df["end_date"] = full_df["end_date"].astype(str)
    
    full_df["estado"] = full_df["status"]

    guardar_todo(full_df)
    st.success("Guardado en Supabase ✅")
    st.rerun()

    
if st.button("Actualizar Gantt"):
    st.success("Solo visualización actualizada ✅")


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
