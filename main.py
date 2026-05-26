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

    # ======================
    # LIMPIEZA FUERTE (CRÍTICO)
    # ======================
    df = df.replace({pd.NA: None})

    # ✅ convertir NaN reales
    df = df.where(pd.notnull(df), None)

    # ✅ strings obligatorios
    for col in ["nivel","project_name","item_name","responsible","document_url"]:
        df[col] = df[col].apply(lambda x: str(x) if x is not None else "")

    # ✅ eliminar filas vacías
    df = df[df["item_name"].str.strip() != ""]
    df = df[df["project_name"].str.strip() != ""]

    # ✅ fechas seguras
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

    # ✅ eliminar fechas inválidas
    df = df.dropna(subset=["start_date","end_date"])

    # ✅ convertir fechas a string limpio
    df["start_date"] = df["start_date"].dt.strftime("%Y-%m-%d")
    df["end_date"] = df["end_date"].dt.strftime("%Y-%m-%d")

    # ✅ progreso correcto
    df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0)

    # ✅ eliminar tareas sin proyecto válido
    proyectos = df[df["nivel"] == "Proyecto"]["project_name"].unique()

    df = df[
        (df["nivel"] == "Proyecto") |
        (df["project_name"].isin(proyectos))
    ]

    # ✅ eliminar duplicados internos
    df = df.drop_duplicates(
        subset=["project_name","item_name","nivel"],
        keep="last"
    )

    # ✅ timestamp
    df["updated_at"] = datetime.utcnow().isoformat()

    # ======================
    # CONVERSIÓN FINAL JSON
    # ======================
    data = df.to_dict(orient="records")

    try:
        supabase.table("projects").upsert(
            data,
            on_conflict="project_name,item_name,nivel"
        ).execute()

    except Exception as e:
        st.error("❌ Error al guardar en Supabase")
        st.write(data)  # 👈 te muestra exactamente qué se envía
        st.write(e)


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
        guardar(pd.concat([df, new], ignore_index=True))
        st.success("✅ Creado correctamente")
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

    # 🔥 FILTRO FINAL ANTIBASURA
    proyectos_validos = df[df["nivel"] == "Proyecto"]["project_name"].dropna().unique()

    df = df[
        (df["nivel"] == "Proyecto") |
        (df["project_name"].isin(proyectos_validos))
    ]

    # 🔥 PROTECCIÓN TOTAL (NUNCA MÁS BASURA)
    proyectos_validos = df[df["nivel"] == "Proyecto"]["project_name"].dropna().unique()

    df = df[
        (df["nivel"] == "Proyecto") |
        (
            df["project_name"].isin(proyectos_validos)
            & (df["project_name"].str.strip() != "")
        )
    ]

    df_gantt = df.copy()

    # ✅ usar datos ya actualizados
    df_gantt["start_date"] = pd.to_datetime(df_gantt["start_date"], errors="coerce")
    df_gantt["end_date"] = pd.to_datetime(df_gantt["end_date"], errors="coerce")

    html = build_ms_project_gantt_html(df_gantt)



    components.html(html, height=650, scrolling=False)