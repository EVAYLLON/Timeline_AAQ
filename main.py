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
# CARGA DATOS
# ======================
def cargar_datos():
    response = supabase.table("projects").select("*").execute()
    data = response.data

    if not data:
        return pd.DataFrame(columns=[
            "nivel","project_name","item_name","responsible",
            "start_date","end_date","progress","estado","document_url"
        ])

    df = pd.DataFrame(data)

    return df

# ======================
# GUARDAR DATOS (FIX)
# ======================
def guardar_todo(df):

    columnas_validas = [
        "nivel","project_name","item_name","responsible",
        "start_date","end_date","progress","estado","document_url"
    ]

    df_clean = df.reindex(columns=columnas_validas)

    # ✅ reemplazar NaN → None
    df_clean = df_clean.where(pd.notnull(df_clean), None)

    # ✅ fechas SOLO día (sin hora)
    df_clean["start_date"] = pd.to_datetime(df_clean["start_date"], errors="coerce").dt.date
    df_clean["end_date"] = pd.to_datetime(df_clean["end_date"], errors="coerce").dt.date

    # ✅ convertir a string limpio
    df_clean["start_date"] = df_clean["start_date"].astype(str)
    df_clean["end_date"] = df_clean["end_date"].astype(str)

    # ✅ progress válido
    df_clean["progress"] = pd.to_numeric(df_clean["progress"], errors="coerce").fillna(0)

    data = df_clean.to_dict(orient="records")

    try:
        supabase.table("projects").insert(data).execute()
    except Exception as e:
        st.error("❌ Error al guardar en Supabase")
        st.write(e)

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
# DATA
# ======================
df = cargar_datos()

df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")
df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

for col in ["nivel","project_name","item_name","responsible"]:
    df[col] = df[col].fillna("").astype(str)

df["estado"] = df["progress"].apply(calcular_estado)
df["timeline_status"] = df.apply(calcular_timeline, axis=1)

# ✅ SOLO fecha (no hora)
df["start_date"] = df["start_date"].dt.date
df["end_date"] = df["end_date"].dt.date

# ======================
# EDITOR POR PROYECTO (ORIGINAL)
# ======================
st.subheader("Editor por Proyecto")

df_display = df.drop(
    columns=["id","item_id","parent_id","project_id","nivel_order"],
    errors="ignore"
)

projects_list = df_display["project_name"].dropna().unique()
edited_blocks = []

for project in projects_list:

    proj_df = df_display[df_display["project_name"] == project].copy()

    with st.expander(f"📁 {project}", expanded=False):

        edited_proj = st.data_editor(
            proj_df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{project}",

            column_config={
                "nivel": st.column_config.SelectboxColumn(
                    "Nivel",
                    options=["Proyecto","Tarea","Subtarea"]
                ),
                "start_date": st.column_config.DateColumn("Inicio"),
                "end_date": st.column_config.DateColumn("Fin"),
                "estado": st.column_config.TextColumn("Estado", disabled=True),
                "timeline_status": st.column_config.TextColumn("Estado plazo", disabled=True)
            },
            disabled=["estado","timeline_status"]
        )

        edited_blocks.append(edited_proj)

# ======================
# RECONSTRUCCIÓN (FIX)
# ======================
if edited_blocks:
    full_df = pd.concat(edited_blocks, ignore_index=True)
else:
    full_df = df.copy()

# ======================
# LIMPIEZA FINAL
# ======================
full_df["start_date"] = pd.to_datetime(full_df["start_date"], errors="coerce")
full_df["end_date"] = pd.to_datetime(full_df["end_date"], errors="coerce")
full_df["progress"] = pd.to_numeric(full_df["progress"], errors="coerce").fillna(0)

full_df["estado"] = full_df["progress"].apply(calcular_estado)
full_df["timeline_status"] = full_df.apply(calcular_timeline, axis=1)

# ======================
# BOTONES
# ======================
col1, col2 = st.columns(2)

with col1:
    if st.button("Guardar cambios"):
        guardar_todo(full_df)
        st.success("Guardado en Supabase ✅")

with col2:
    if st.button("Exportar HTML"):
        html = build_ms_project_gantt_html(full_df)
        export_gantt_html(html, REPORT_PATH)
        st.success("Exportado ✅")

# ======================
# GANTT
# ======================
st.subheader("Timeline")

if not full_df.empty:

    start_date = st.date_input("Inicio", value=full_df["start_date"].min())
    end_date = st.date_input("Fin", value=full_df["end_date"].max())

    html = build_ms_project_gantt_html(full_df, start_date, end_date)

    components.html(html, height=650, scrolling=False)

else:
    st.warning("⚠️ No hay datos para mostrar")
