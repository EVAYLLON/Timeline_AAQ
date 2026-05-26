from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
from gantt import build_ms_project_gantt_html, export_gantt_html

# ======================
# SUPABASE
# ======================
SUPABASE_URL = "https://brrghdszvwvwxwouvqgl.supabase.co"
SUPABASE_KEY = "sb_publishable_Kjb0Rhsp_tWeWxdof7-zWA_htBXB3MP"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ======================
# SESSION STATE
# ======================
if "data" not in st.session_state:
    response = supabase.table("projects").select("*").execute()
    st.session_state.data = pd.DataFrame(response.data if response.data else [])

df = st.session_state.data.copy()

# ======================
# CONFIG
# ======================
BASE_DIR = Path(__file__).resolve().parent
REPORT_PATH = BASE_DIR / "reports" / "gantt.html"

st.set_page_config(layout="wide")
st.title("Project Tracker (Jerarquía real)")

# ======================
# FUNCIONES
# ======================
def calcular_estado(x):
    x = float(x) if pd.notna(x) else 0
    if x >= 100:
        return "Completado"
    elif x <= 0:
        return "No iniciado"
    return "En curso"

def calcular_timeline(row):
    today = pd.Timestamp.today().normalize()
    progress = float(row.get("progress", 0) or 0)

    if progress >= 100:
        return "Completado"

    end = pd.to_datetime(row.get("end_date"), errors="coerce")
    if pd.isna(end):
        return ""

    if end < today:
        return "Vencido"
    elif (end - today).days <= 5:
        return "En riesgo"
    return "En plazo"

# ======================
# LIMPIEZA BASE
# ======================
if not df.empty:
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
    df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

    for col in ["nivel","project_name","item_name","responsible"]:
        df[col] = df[col].fillna("").astype(str)

# ======================
# BOTONES
# ======================
st.subheader("Gestión")

col1, col2 = st.columns(2)

with col1:
    if st.button("➕ Agregar Proyecto"):
        new_row = {
            "nivel": "Proyecto",
            "project_name": f"Proyecto {len(df)+1}",
            "item_name": f"Proyecto {len(df)+1}",
            "responsible": "",
            "start_date": pd.Timestamp.today().date(),
            "end_date": pd.Timestamp.today().date(),
            "progress": 0,
            "estado": "",
            "document_url": ""
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        st.session_state.data = df
        st.rerun()

with col2:
    if st.button("➕ Agregar Tarea"):

        proyectos = df[df["nivel"] == "Proyecto"]

        project_name = proyectos["project_name"].iloc[0] if not proyectos.empty else "Proyecto 1"

        new_row = {
            "nivel": "Tarea",
            "project_name": project_name,
            "item_name": "Nueva Tarea",
            "responsible": "",
            "start_date": pd.Timestamp.today().date(),
            "end_date": pd.Timestamp.today().date(),
            "progress": 0,
            "estado": "",
            "document_url": ""
        }

        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        st.session_state.data = df
        st.rerun()

# ======================
# EDITOR
# ======================
st.subheader("Editor por Proyecto")

projects = df["project_name"].unique()
edited_blocks = []

for project in projects:

    proj_df = df[df["project_name"] == project].copy()

    expanded_state = st.session_state.get(f"exp_{project}", True)

    with st.expander(f"📁 {project}", expanded=expanded_state):

        st.session_state[f"exp_{project}"] = True

        edited = st.data_editor(
            proj_df,
            use_container_width=True,
            num_rows="dynamic",
            key=f"editor_{project}"
        )

        edited_blocks.append(edited)

# ======================
# RECONSTRUCCION SEGURA
# ======================
if edited_blocks:
    full_df = pd.concat(edited_blocks, ignore_index=True)
else:
    full_df = df.copy()

# ======================
# CALCULOS
# ======================
full_df["start_date"] = pd.to_datetime(full_df["start_date"], errors="coerce")
full_df["end_date"] = pd.to_datetime(full_df["end_date"], errors="coerce")
full_df["progress"] = pd.to_numeric(full_df["progress"], errors="coerce").fillna(0)

full_df["estado"] = full_df["progress"].apply(calcular_estado)
full_df["timeline_status"] = full_df.apply(calcular_timeline, axis=1)

# ======================
# GUARDADO SEGURO (FIX)
# ======================
if st.button("Guardar cambios"):

    if not full_df.empty:

        df_save = full_df.copy()

        columnas_validas = [
            "nivel","project_name","item_name","responsible",
            "start_date","end_date","progress","estado","document_url"
        ]

        df_save = df_save.reindex(columns=columnas_validas)

        # limpiar nulls
        df_save = df_save.where(pd.notnull(df_save), None)

        # tipos correctos
        df_save["progress"] = pd.to_numeric(df_save["progress"], errors="coerce").fillna(0)
        df_save["start_date"] = df_save["start_date"].astype(str)
        df_save["end_date"] = df_save["end_date"].astype(str)

        data = df_save.to_dict(orient="records")

        try:
            # ✅ insert sin borrar tabla
            supabase.table("projects").insert(data).execute()
            st.success("✅ Guardado correctamente")

        except Exception as e:
            st.error("❌ Error al guardar en Supabase")
            st.write(e)

# ======================
# GANTT
# ======================
st.subheader("Timeline")

if full_df.empty:
    st.warning("⚠️ No hay datos. Agrega un proyecto.")
else:
    start_date = st.date_input("Inicio", value=full_df["start_date"].min())
    end_date = st.date_input("Fin", value=full_df["end_date"].max())

    html = build_ms_project_gantt_html(full_df, start_date, end_date)
    components.html(html, height=650, scrolling=False)
