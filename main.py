from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
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
def guardar_todo(df):

    columnas_validas = [
        "nivel","project_name","item_name","responsible",
        "start_date","end_date","progress","estado","document_url"
    ]

    df_clean = df.reindex(columns=columnas_validas)

    # ✅ eliminar NaN
    df_clean = df_clean.replace({pd.NA: None})
    df_clean = df_clean.where(df_clean.notnull(), None)

    # ✅ eliminar duplicados (CRÍTICO)
    df_clean = df_clean.drop_duplicates(
        subset=["project_name", "item_name", "nivel"],
        keep="last"
    )

    # ✅ fechas
    df_clean["start_date"] = pd.to_datetime(df_clean["start_date"], errors="coerce").dt.date
    df_clean["end_date"] = pd.to_datetime(df_clean["end_date"], errors="coerce").dt.date

    df_clean["start_date"] = df_clean["start_date"].astype(str)
    df_clean["end_date"] = df_clean["end_date"].astype(str)

    df_clean["progress"] = pd.to_numeric(df_clean["progress"], errors="coerce").fillna(0)

    df_clean["updated_at"] = datetime.utcnow().isoformat()

    data = df_clean.to_dict(orient="records")

    try:
        supabase.table("projects").upsert(
            data,
            on_conflict="project_name,item_name,nivel"
        ).execute()

        st.success("✅ Guardado corretamente (sin duplicados)")

    except Exception as e:
        st.error("❌ Error Supabase")
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
    x = float(x) if pd.notna(x) else 0
    if x >= 100:
        return "Completado"
    elif x <= 0:
        return "No iniciado"
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

df["start_date"] = df["start_date"].dt.date
df["end_date"] = df["end_date"].dt.date

# ======================
# EDITOR
# ======================
st.subheader("Editor por Proyecto")

projects = df["project_name"].unique()
edited_blocks = []

for project in projects:

    proj_df = df[df["project_name"] == project]

    with st.expander(f"📁 {project}", expanded=True):

        edited = st.data_editor(
            proj_df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{project}"
        )

        edited_blocks.append(edited)

# ======================
# RECONSTRUCCIÓN
# ======================
if edited_blocks:
    full_df = pd.concat(edited_blocks, ignore_index=True)
else:
    full_df = df.copy()

# ======================
# BOTONES
# ======================
col1, col2 = st.columns(2)

with col1:
    if st.button("Guardar cambios"):
        guardar_todo(full_df)

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
    st.warning("⚠️ No hay datos")