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
# CARGAR
# ======================
def cargar():
    res = supabase.table("projects").select("*").execute()
    data = res.data

    if not data:
        return pd.DataFrame(columns=[
            "nivel","project_name","item_name","responsible",
            "start_date","end_date","progress","estado","document_url"
        ])

    df = pd.DataFrame(data)

    # ✅ asegurar columnas
    cols = ["nivel","project_name","item_name","responsible","start_date","end_date","progress","estado","document_url"]
    for c in cols:
        if c not in df.columns:
            df[c] = None

    return df


# ======================
# GUARDAR LIMPIO
# ======================
def guardar(df):

    df = df.copy()

    # ✅ limpieza dura
    df = df.replace({pd.NA: None})
    df = df.where(pd.notnull(df), None)

    # ✅ strings
    for col in ["project_name","item_name","responsible","document_url"]:
        df[col] = df[col].fillna("").astype(str)

    # ✅ eliminar filas inválidas
    df = df[df["item_name"] != ""]
    df = df[df["project_name"] != ""]

    # ✅ asegurar que TODA tarea tenga proyecto válido
    proyectos = df[df["nivel"] == "Proyecto"]["project_name"].unique()

    df = df[
        (df["nivel"] == "Proyecto") |
        (df["project_name"].isin(proyectos))
    ]

    # ✅ fechas seguras
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce").dt.strftime("%Y-%m-%d")

    # ✅ progreso
    df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

    df["updated_at"] = datetime.utcnow().isoformat()

    # ✅ eliminar duplicados
    df = df.drop_duplicates(
        subset=["project_name","item_name","nivel"],
        keep="last"
    )

    supabase.table("projects").upsert(
        df.to_dict("records"),
        on_conflict="project_name,item_name,nivel"
    ).execute()


# ======================
# UI
# ======================
st.set_page_config(layout="wide")
st.title("Project Tracker ✅")

df = cargar()

# ======================
# PROYECTOS
# ======================
proyectos = df[df["nivel"] == "Proyecto"]["project_name"].unique()

selected = None
if len(proyectos) > 0:
    selected = st.selectbox("Proyecto", proyectos)
else:
    st.warning("Crea un proyecto primero")

col1, col2, col3 = st.columns(3)

# ======================
# NUEVO PROYECTO
# ======================
with col1:
    if st.button("➕ Proyecto"):
        nombre = f"Proyecto {len(proyectos)+1}"

        new = pd.DataFrame([{
            "nivel": "Proyecto",
            "project_name": nombre,
            "item_name": nombre,
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
    if selected and st.button("➕ Tarea"):
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

# ======================
# ELIMINAR PROYECTO
# ======================
with col3:
    if selected and st.button("🗑️ Eliminar Proyecto"):
        supabase.table("projects").delete().eq("project_name", selected).execute()
        st.rerun()

# ======================
# EDITOR
# ======================
if selected:

    st.subheader("Editor")

    df_proj = df[df["project_name"] == selected].copy()

    df_proj["start_date"] = pd.to_datetime(df_proj["start_date"], errors="coerce")
    df_proj["end_date"] = pd.to_datetime(df_proj["end_date"], errors="coerce")

    edited = st.data_editor(
        df_proj[["nivel","item_name","responsible","start_date","end_date","progress","document_url"]],
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "nivel": st.column_config.SelectboxColumn("Nivel", options=["Proyecto","Tarea","Subtarea"]),
            "start_date": st.column_config.DateColumn("Inicio"),
            "end_date": st.column_config.DateColumn("Fin")
        }
    )

    if st.button("💾 Guardar cambios"):

        edited = edited.copy()

        # ✅ detectar proyecto nuevo
        if (edited["nivel"] == "Proyecto").any():
            nuevo = edited.loc[edited["nivel"] == "Proyecto","item_name"].iloc[0]
        else:
            nuevo = selected

        edited["project_name"] = nuevo

        # ✅ eliminar elementos borrados (clave)
        df_total = df[df["project_name"] != selected]

        # ✅ SOLO lo que queda en editor (NO más)
        df_total = pd.concat([df_total, edited], ignore_index=True)

        guardar(df_total)

        st.success("✅ Guardado")
        st.rerun()

# ======================
# GANTT
# ======================
st.subheader("Timeline")

if not df.empty:

    df["estado"] = df["progress"].apply(lambda x: "Completado" if x>=100 else "En curso")
    df["timeline_status"] = df.apply(lambda r: "Completado" if r["progress"]>=100 else "", axis=1)

    # ✅ FILTRO FINAL (CRÍTICO)
    proyectos_validos = df[df["nivel"] == "Proyecto"]["project_name"]

    df = df[
        (df["nivel"] == "Proyecto") |
        (df["project_name"].isin(proyectos_validos))
    ]

    html = build_ms_project_gantt_html(df)

    components.html(html, height=650, scrolling=False)