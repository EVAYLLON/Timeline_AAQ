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

    if not data:
        return pd.DataFrame(columns=[
            "nivel","project_name","item_name","responsible",
            "start_date","end_date","progress","estado","document_url"
        ])

    df = pd.DataFrame(data)

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

    df = df.copy()

    columnas = [
        "nivel","project_name","item_name","responsible",
        "start_date","end_date","progress","estado","document_url"
    ]

    df = df.reindex(columns=columnas)

    df = df.replace({pd.NA: None})
    df = df.where(pd.notnull(df), None)

    # ✅ limpiar strings
    for col in ["project_name","item_name","responsible","document_url"]:
        df[col] = df[col].fillna("").astype(str)

    # ✅ quitar filas vacías o inválidas
    df = df[df["item_name"] != ""]
    df = df[df["project_name"] != ""]

    # ✅ quitar tareas huérfanas
    proyectos_validos = df[df["nivel"] == "Proyecto"]["project_name"]

    df = df[
        (df["nivel"] == "Proyecto") |
        (df["project_name"].isin(proyectos_validos))
    ]

    # ✅ fechas
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")\
        .dt.strftime("%Y-%m-%d")

    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")\
        .dt.strftime("%Y-%m-%d")

    # ✅ progreso
    df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

    df["updated_at"] = datetime.utcnow().isoformat()

    # ✅ evitar duplicados
    df = df.drop_duplicates(
        subset=["project_name","item_name","nivel"],
        keep="last"
    )

    supabase.table("projects").upsert(
        df.to_dict("records"),
        on_conflict="project_name,item_name,nivel"
    ).execute()


# ======================
# EDITOR
# ======================
st.subheader("Editor")

if selected:

    df_edit = df[df["project_name"] == selected][[
        "nivel","item_name","responsible","start_date","end_date","progress","document_url"
    ]].copy()

    df_edit["start_date"] = pd.to_datetime(df_edit["start_date"], errors="coerce")
    df_edit["end_date"] = pd.to_datetime(df_edit["end_date"], errors="coerce")

    edited = st.data_editor(
        df_edit,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "nivel": st.column_config.SelectboxColumn(
                "Nivel", options=["Proyecto","Tarea","Subtarea"]
            ),
            "start_date": st.column_config.DateColumn("Inicio"),
            "end_date": st.column_config.DateColumn("Fin"),
        }
    )

    # ✅ BOTÓN ELIMINAR FILAS
    col_del1, col_del2 = st.columns([1,3])

    with col_del1:
        if st.button("🗑 Eliminar filtrar"):
            edited = edited[~edited["item_name"].isin([""])]  # limpieza simple

    # ======================
    # GUARDAR
    # ======================
    if st.button("💾 Guardar cambios"):

        edited = edited.copy()

        edited["start_date"] = pd.to_datetime(edited["start_date"], errors="coerce")
        edited["end_date"] = pd.to_datetime(edited["end_date"], errors="coerce")

        # ✅ proyecto renombrado
        if (edited["nivel"] == "Proyecto").any():
            nuevo_nombre = edited.loc[
                edited["nivel"] == "Proyecto", "item_name"
            ].iloc[0]
        else:
            nuevo_nombre = selected

        edited["project_name"] = nuevo_nombre

        # ✅ eliminar duplicados internos
        edited = edited.drop_duplicates()

        # ✅ eliminar filas borradas
        df_rest = df[df["project_name"] != selected]

        df_total = pd.concat([df_rest, edited]).reset_index(drop=True)

        # ✅ limpieza final (CRÍTICA)
        df_total = df_total[df_total["item_name"] != ""]
        df_total = df_total[df_total["project_name"] != ""]

        guardar(df_total)

        st.success("✅ Guardado correctamente")
        st.rerun()

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
st.title("Project Tracker ✅")

df = cargar()

# ======================
# PROYECTOS
# ======================
proyectos = df[df["nivel"] == "Proyecto"]["project_name"].unique()

if len(proyectos) == 0:
    st.warning("No hay proyectos. Crea uno 👇")
    selected = None
else:
    selected = st.selectbox("Proyecto", proyectos)

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
        st.warning("Selecciona un proyecto")

# ======================
# BORRAR PROYECTO
# ======================
with col3:
    if selected and st.button("🗑️ Eliminar Proyecto"):
        supabase.table("projects").delete().eq("project_name", selected).execute()
        st.rerun()

# ======================
# EDITOR
# ======================
st.subheader("Editor")

if selected:

    df_edit = df[df["project_name"] == selected][[
        "nivel","item_name","responsible","start_date","end_date","progress","document_url"
    ]].copy()

    # ✅ asegurar datetime para calendario
    df_edit["start_date"] = pd.to_datetime(df_edit["start_date"], errors="coerce")
    df_edit["end_date"] = pd.to_datetime(df_edit["end_date"], errors="coerce")

    edited = st.data_editor(
        df_edit,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "nivel": st.column_config.SelectboxColumn(
                "Nivel", options=["Proyecto","Tarea"]
            ),
            "start_date": st.column_config.DateColumn("Inicio"),
            "end_date": st.column_config.DateColumn("Fin")
        }
    )

    if st.button("💾 Guardar cambios"):

        # ✅ detectar nuevo nombre del proyecto
        if (edited["nivel"] == "Proyecto").any():
            nuevo_nombre = edited.loc[
                edited["nivel"] == "Proyecto", "item_name"
            ].iloc[0]
        else:
            nuevo_nombre = selected

        # ✅ actualizar TODAS las filas
        edited["project_name"] = nuevo_nombre

        df_rest = df[df["project_name"] != selected]

        df_total = pd.concat([df_rest, edited]).reset_index(drop=True)

        edited = edited.copy()

        edited["start_date"] = pd.to_datetime(edited["start_date"], errors="coerce")
        edited["end_date"] = pd.to_datetime(edited["end_date"], errors="coerce")


        guardar(df_total)

        st.success("✅ Guardado correctamente")
        st.rerun()

# ======================
# GANTT
# ======================
st.subheader("Timeline")

if not df.empty:

    df["estado"] = df["progress"].apply(estado)
    df["timeline_status"] = df.apply(timeline, axis=1)

    start_series = pd.to_datetime(df["start_date"], errors="coerce").dropna()
    end_series = pd.to_datetime(df["end_date"], errors="coerce").dropna()

    start_date = st.date_input(
        "Inicio",
        value=start_series.min().date() if not start_series.empty else datetime.today().date()
    )

    end_date = st.date_input(
        "Fin",
        value=end_series.max().date() if not end_series.empty else datetime.today().date()
    )

    html = build_ms_project_gantt_html(df, start_date, end_date)

    components.html(html, height=650, scrolling=False)
