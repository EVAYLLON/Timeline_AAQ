from datetime import datetime
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client
from gantt import build_ms_project_gantt_html

# ======================
# SUPABASE
# ======================
SUPABASE_URL = "https://brrghdszvwvwxwouvqgl.supabase.co"
SUPABASE_KEY = "sb_publishable_Kjb0Rhsp_tWeWxdof7-zWA_htBXB3MP"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ======================
# CARGAR DATOS
# ======================
def cargar():
    res = supabase.table("projects").select("*").execute()
    data = res.data

    # ✅ SI NO HAY DATOS → crear DF con columnas
    if not data:
        return pd.DataFrame(columns=[
            "nivel","project_name","item_name","responsible",
            "start_date","end_date","progress","estado","document_url"
        ])

    df = pd.DataFrame(data)

    # ✅ asegurar columnas (por si acaso)
    for col in [
        "nivel","project_name","item_name","responsible",
        "start_date","end_date","progress","estado","document_url"
    ]:
        if col not in df.columns:
            df[col] = None

    return df



# ======================
# GUARDAR
# ======================
def guardar(df):

    columnas = [
        "nivel","project_name","item_name","responsible",
        "start_date","end_date","progress","estado","document_url"
    ]

    df = df.reindex(columns=columnas)

    df = df.replace({pd.NA: None})
    df = df.where(df.notnull(), None)

    # evitar duplicados
    df = df.drop_duplicates(
        subset=["project_name","item_name","nivel"],
        keep="last"
    )

    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.date.astype(str)
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce").dt.date.astype(str)
    df["progress"] = pd.to_numeric(df["progress"]).fillna(0)

    df["updated_at"] = datetime.utcnow().isoformat()

    supabase.table("projects").upsert(
        df.to_dict("records"),
        on_conflict="project_name,item_name,nivel"
    ).execute()


# ======================
# FUNCIONES
# ======================
def estado(x):
    if x >= 100: return "Completado"
    if x <= 0: return "No iniciado"
    return "En curso"


def timeline(row):
    today = pd.Timestamp.today().normalize()

    if row["progress"] >= 100:
        return "Completado"

    end = pd.to_datetime(row["end_date"], errors="coerce")

    if pd.isna(end): return ""
    if end < today: return "Vencido"
    if (end - today).days <= 5: return "En riesgo"

    return "En plazo"


# ======================
# UI
# ======================
st.set_page_config(layout="wide")
st.title("Project Tracker (Limpio ✅)")

df = cargar()

if df.empty:
    st.warning("No hay proyectos. Crea uno para empezar 👇")


# ======================
# PROYECTOS
# ======================
proyectos = df[df["nivel"] == "Proyecto"]["project_name"].unique()

if len(proyectos) == 0:
    st.warning("No hay proyectos")

if len(proyectos) == 0:
    selected = None
else:
    selected = st.selectbox("Proyecto", proyectos)



col1, col2, col3 = st.columns(3)

# ======================
# NUEVO PROYECTO
# ======================
with col1:
    if st.button("➕ Proyecto"):

        new = pd.DataFrame([{
            "nivel": "Proyecto",
            "project_name": f"Proyecto {len(proyectos)+1}",
            "item_name": f"Proyecto {len(proyectos)+1}",
            "start_date": datetime.today(),
            "end_date": datetime.today(),
            "progress": 0
        }])

        guardar(pd.concat([df, new]))
        st.rerun()


# ======================
# NUEVA TAREA
# ======================
with col2:

    if selected:
        if st.button("➕ Tarea"):

            new = pd.DataFrame([{
                "nivel": "Tarea",
                "project_name": selected,
                "item_name": "Nueva tarea",
                "start_date": datetime.today(),
                "end_date": datetime.today(),
                "progress": 0
            }])

            guardar(pd.concat([df, new]))
            st.rerun()

    else:
        st.warning("Selecciona un proyecto para crear tareas")


# ======================
# BORRAR PROYECTO
# ======================
with col3:
    if st.button("🗑️ Eliminar Proyecto"):

        # ✅ borrar en DB
        supabase.table("projects").delete().eq("project_name", selected).execute()

        st.success("Proyecto eliminado ✅")
        st.rerun()


# ======================
# EDITOR LIMPIO
# ======================
st.subheader("Editor")

df_edit = df[df["project_name"] == selected][[
    "item_name","responsible","start_date","end_date","progress","document_url"
]]

edit = st.data_editor(df_edit, use_container_width=True)

# ======================
# GUARDAR EDICIÓN
# ======================
if st.button("💾 Guardar cambios"):

    df_total = df[df["project_name"] != selected]

    edit["project_name"] = selected
    edit["nivel"] = edit["item_name"].apply(
        lambda x: "Proyecto" if x == selected else "Tarea"
    )

    df_total = pd.concat([df_total, edit])

    guardar(df_total)

    st.success("Guardado ✅")


# ======================
# GANTT
# ======================
st.subheader("Timeline")

if not df.empty:

    df["estado"] = df["progress"].apply(estado)
    df["timeline_status"] = df.apply(timeline, axis=1)

    start = pd.to_datetime(df["start_date"], errors="coerce").min()
    end = pd.to_datetime(df["end_date"], errors="coerce").max()

    start_date = st.date_input("Inicio", value=start)
    end_date = st.date_input("Fin", value=end)

    html = build_ms_project_gantt_html(df, start_date, end_date)

    components.html(html, height=650, scrolling=False)
