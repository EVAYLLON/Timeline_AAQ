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
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJycmdoZHN6dnd2d3h3b3V2cWdsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkyMTc0ODMsImV4cCI6MjA5NDc5MzQ4M30.dnt7f4qTGfbr66JJiKg8TpPmgJ_Et31_OLVz3_CBpdA"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ======================
# CARGAR
# ======================
def cargar():
    res = supabase.table("projects").select("*").execute()

    columnas = [
        "nivel","project_name","item_name",
        "responsible","start_date","end_date","progress"
    ]

    if not res.data:
        return pd.DataFrame(columns=columnas)

    df = pd.DataFrame(res.data)

    for col in columnas:
        if col not in df.columns:
            df[col] = None

    return df

# ======================
# INSERT LIMPIO ✅
# ======================
def insertar_registro(row):
    try:
        supabase.table("projects").insert(row).execute()
    except Exception as e:
        st.error("Error al insertar:")
        st.write(row)
        st.write(e)

# ======================
# TIMELINE
# ======================
def timeline(row):
    today = pd.Timestamp.today().normalize()

    if row["progress"] >= 100:
        return "Completado"

    end = pd.to_datetime(row["end_date"], errors="coerce")

    if pd.isna(end):
        return ""

    if end < today:
        return "Vencido"

    if (end - today).days <= 5:
        return "En riesgo"

    return "En plazo"

# ======================
# UI
# ======================
st.set_page_config(layout="wide")
st.title("Project Tracker ✅")

if "df_temp" not in st.session_state:
    st.session_state["df_temp"] = cargar()

df = st.session_state.get("df_temp", cargar())
df = df.copy()
df["project_name"] = df["project_name"].astype(str).str.strip()

if "project_name" not in df.columns:
    df["project_name"] = ""
# ======================
# PROYECTOS
# ======================
df["project_name"] = df.get("project_name", "")
proyectos = df[df["nivel"] == "Proyecto"]["project_name"].dropna().unique()

# ======================
# CREAR PROYECTO
# ======================
st.subheader("Crear nuevo proyecto")

nuevo_nombre = st.text_input("Nombre del proyecto")

if st.button("✅ Crear proyecto"):

    if nuevo_nombre.strip() == "":
        st.warning("Ingresa nombre válido")
    else:

        nuevo = {
            "nivel": "Proyecto",
            "project_name": nuevo_nombre.strip(),
            "item_name": nuevo_nombre.strip(),
            "responsible": "",
            "start_date": datetime.today().strftime("%Y-%m-%d"),
            "end_date": datetime.today().strftime("%Y-%m-%d"),
            "progress": 0
        }

        insertar_registro(nuevo)

        # 🔥 FORZAR ACTUALIZACIÓN DESDE SUPABASE
        st.session_state["df_temp"] = cargar()

        st.success("Proyecto creado ✅")
        st.rerun()

# ======================
# SELECTOR
# ======================
if len(proyectos) == 0:
    st.warning("⚠️ No hay proyectos")
    selected = None
else:
    selected = st.selectbox("Proyecto", proyectos, key="select_proyecto")

# ======================
# BOTONES
# ======================
col1, col2 = st.columns(2)

with col1:
    if selected and st.button("➕ Tarea"):

        nueva_fila = {
            "nivel": "Tarea",
            "project_name": selected,  # 🔥 ESTA LÍNEA SOLUCIONA EL ERROR
            "item_name": "Nueva tarea",
            "responsible": "",
            "start_date": datetime.today().strftime("%Y-%m-%d"),
            "end_date": datetime.today().strftime("%Y-%m-%d"),
            "progress": 0
        }


        # ✅ agregar al dataframe en memoria
        df = pd.concat([df, pd.DataFrame([nueva_fila])], ignore_index=True)

        st.session_state["df_temp"] = df  # 🔥 CLAVE

        st.rerun()


# 🗑 BORRAR PROYECTO
with col2:
    if selected and st.button("🗑️ Eliminar Proyecto"):

        supabase.table("projects")\
            .delete()\
            .eq("project_name", selected)\
            .execute()

        st.success("Eliminado ✅")
        st.rerun()

# ======================
# EDITOR
# ======================
if selected:

    st.subheader("Editor")
    df_edit = df[df["project_name"] == selected][[
        "nivel","item_name","responsible",
        "start_date","end_date","progress"
    ]].copy()

    # ✅ LIMPIEZA CRÍTICA
    df_edit = df_edit.dropna(subset=["item_name"])

    df_edit["nivel"] = df_edit["nivel"].fillna("Tarea").astype(str)
    df_edit["item_name"] = df_edit["item_name"].fillna("").astype(str)
    df_edit["responsible"] = df_edit["responsible"].fillna("").astype(str)

    df_edit["start_date"] = pd.to_datetime(df_edit["start_date"], errors="coerce")
    df_edit["end_date"] = pd.to_datetime(df_edit["end_date"], errors="coerce")

    df_edit["progress"] = pd.to_numeric(df_edit["progress"], errors="coerce").fillna(0)

    edited = st.data_editor(
        df_edit,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "nivel": st.column_config.TextColumn("Nivel", disabled=True),
            "start_date": st.column_config.DateColumn("Inicio"),
            "end_date": st.column_config.DateColumn("Fin"),
        }
    )
    df_actual = st.session_state["df_temp"]

    # eliminar solo el proyecto actual
    df_actual = df_actual[df_actual["project_name"] != selected]

    # agregar lo editado nuevamente
    edited = edited.copy()
    edited["project_name"] = selected

    df_actual = pd.concat([df_actual, edited], ignore_index=True)

    st.session_state["df_temp"] = df_actual



if st.button("💾 Guardar cambios"):

    # ✅ borrar proyecto actual
    supabase.table("projects")\
        .delete()\
        .eq("project_name", selected)\
        .execute()

    # ✅ insertar limpio con validación
    for _, row in edited.iterrows():

        item = str(row.get("item_name", "")).strip()

        if item == "":
            continue

        start = pd.to_datetime(row.get("start_date"), errors="coerce")
        end = pd.to_datetime(row.get("end_date"), errors="coerce")

        # ✅ FIX REAL
        nivel = str(row.get("nivel", "Tarea")).strip()
        if nivel not in ["Proyecto", "Tarea", "Subtarea"]:
            nivel = "Tarea"

        # ✅ fechas seguras
        try:
            start_str = pd.to_datetime(row.get("start_date")).strftime("%Y-%m-%d")
        except:
            start_str = datetime.today().strftime("%Y-%m-%d")

        try:
            end_str = pd.to_datetime(row.get("end_date")).strftime("%Y-%m-%d")
        except:
            end_str = datetime.today().strftime("%Y-%m-%d")

        # ✅ progreso seguro
        try:
            prog = int(float(row.get("progress") or 0))
        except:
            prog = 0

        registro = {
            "nivel": nivel,
            "project_name": selected,  # ✅ ESTO ESTÁ BIEN
            "item_name": item,
            "responsible": str(row.get("responsible") or ""),
            "start_date": start_str,
            "end_date": end_str,
            "progress": prog
        }

        insertar_registro(registro)


# ======================
# GANTT
# ======================
st.subheader("Timeline")
# ======================
# FILTRO DE FECHAS GANTT
# ======================

col_f1, col_f2 = st.columns(2)

with col_f1:
    fecha_inicio = st.date_input(
        "📅 Ver desde",
        value=pd.to_datetime(df["start_date"]).min() if not df.empty else datetime.today()
    )

with col_f2:
    fecha_fin = st.date_input(
        "📅 Ver hasta",
        value=pd.to_datetime(df["end_date"]).max() if not df.empty else datetime.today()
    )

if not df.empty:

    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

    # ✅ FILTRO GANTT
    df_filtrado = df[
        (df["end_date"] >= pd.to_datetime(fecha_inicio)) &
        (df["start_date"] <= pd.to_datetime(fecha_fin))
    ].copy()

    st.write("Filtrado:", len(df_filtrado))
    # ✅ timeline status
    df_filtrado["timeline_status"] = df_filtrado.apply(timeline, axis=1)


    html = build_ms_project_gantt_html(
        df_filtrado,
        start_date=fecha_inicio,
        end_date=fecha_fin
    )


    components.html(html, height=650)
