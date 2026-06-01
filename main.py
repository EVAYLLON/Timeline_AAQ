"""
main.py  —  Project Tracker con Supabase + Gantt

Esquema esperado en Supabase (tabla `projects`):
  id            uuid  PRIMARY KEY DEFAULT gen_random_uuid()
  nivel         text  ("Proyecto" | "Tarea" | "Subtarea")
  project_id    uuid  (FK al id del Proyecto padre)
  project_name  text
  item_id       uuid  (= id para Proyectos; ID propio para Tareas/Subtareas)
  item_name     text
  parent_id     uuid  (vacío para Proyectos; project_id para Tareas; task_id para Subtareas)
  responsible   text
  start_date    date
  end_date      date
  progress      int   DEFAULT 0
  status        text  DEFAULT 'No iniciado'
  document_url  text

NOTA: Si tu tabla actual no tiene todas esas columnas, ejecuta las migraciones
      indicadas en el README o adapta las columnas en _COLS_SELECT.
"""

import uuid
from datetime import date, datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client

from gantt import build_ms_project_gantt_html

# ══════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════
SUPABASE_URL = "https://brrghdszvwvwxwouvqgl.supabase.co"
SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJycmdoZHN6dnd2d3h3b3V2cWdsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzkyMTc0ODMsImV4cCI6MjA5NDc5MzQ4M30"
    ".dnt7f4qTGfbr66JJiKg8TpPmgJ_Et31_OLVz3_CBpdA"
)

TABLE = "projects"

# Columnas que leemos de Supabase
_COLS_SELECT = (
    "id,nivel,project_id,project_name,"
    "item_id,item_name,parent_id,"
    "responsible,start_date,end_date,progress,status,document_url"
)

STATUS_OPTIONS = ["No iniciado", "En curso", "Completado", "Cancelado", "En riesgo"]
NIVEL_OPTIONS  = ["Proyecto", "Tarea", "Subtarea"]

# ══════════════════════════════════════════════
# SUPABASE HELPERS
# ══════════════════════════════════════════════
@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _today() -> str:
    return date.today().isoformat()


# ══════════════════════════════════════════════
# CARGA DE DATOS
# ══════════════════════════════════════════════
def cargar_datos() -> pd.DataFrame:
    """
    Lee TODOS los registros de Supabase y devuelve un DataFrame limpio.
    Usa `project_id` (UUID) como clave de aislamiento — nunca project_name.
    """
    sb = get_supabase()
    try:
        res = sb.table(TABLE).select(_COLS_SELECT).execute()
    except Exception as exc:
        st.error(f"❌ Error al conectar con Supabase: {exc}")
        return pd.DataFrame()

    if not res.data:
        return pd.DataFrame()

    df = pd.DataFrame(res.data)

    # Asegurar columnas opcionales
    for col, default in [
        ("responsible", ""),
        ("status", "No iniciado"),
        ("document_url", ""),
        ("parent_id", ""),
        ("progress", 0),
    ]:
        if col not in df.columns:
            df[col] = default

    # Conversiones
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"]   = pd.to_datetime(df["end_date"],   errors="coerce")
    df["progress"]   = pd.to_numeric(df["progress"], errors="coerce").fillna(0).clip(0, 100).astype(int)

    # Limpiar strings
    for col in ["nivel", "project_name", "item_name", "responsible", "status", "document_url"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    return df


def calcular_timeline_status(row: pd.Series) -> str:
    today = pd.Timestamp.today().normalize()
    progress = float(row.get("progress", 0))
    status   = str(row.get("status", ""))

    if progress >= 100 or status == "Completado":
        return "Completado"

    end = pd.to_datetime(row.get("end_date"), errors="coerce")
    if pd.isna(end):
        return ""
    if end < today:
        return "Vencido"
    if (end - today).days <= 7 and progress < 80:
        return "En riesgo"
    return "En plazo"


# ══════════════════════════════════════════════
# CRUD
# ══════════════════════════════════════════════
def insertar_fila(row: dict) -> None:
    get_supabase().table(TABLE).insert(row).execute()


def actualizar_fila(row_id: str, updates: dict) -> None:
    get_supabase().table(TABLE).update(updates).eq("id", row_id).execute()


def eliminar_por_project_id(project_id: str) -> None:
    """Elimina TODAS las filas cuyo project_id coincide (proyecto + sus tareas/subtareas)."""
    get_supabase().table(TABLE).delete().eq("project_id", project_id).execute()
    # También eliminar la fila del proyecto en sí (donde item_id == project_id)
    get_supabase().table(TABLE).delete().eq("item_id", project_id).execute()


def eliminar_fila(row_id: str) -> None:
    get_supabase().table(TABLE).delete().eq("id", row_id).execute()


# ══════════════════════════════════════════════
# STREAMLIT UI
# ══════════════════════════════════════════════
st.set_page_config(
    page_title="Project Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Estilos globales ───────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }

.block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }

/* Título principal */
h1 { font-size: 1.6rem !important; font-weight: 700 !important; letter-spacing: -0.03em; color: #0f172a; }
h2 { font-size: 1.15rem !important; font-weight: 600 !important; color: #1e293b; letter-spacing: -0.01em; }
h3 { font-size: 1rem !important; font-weight: 600 !important; color: #334155; }

/* Cards */
.pt-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 18px 20px;
  margin-bottom: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

/* Badges */
.pt-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 9px;
  border-radius: 99px;
  background: #e0f2fe;
  color: #0369a1;
}

/* Divider */
.pt-divider {
  height: 1px;
  background: #f1f5f9;
  margin: 18px 0;
}

/* Botones Streamlit: limpiar bordes */
div[data-testid="stHorizontalBlock"] .stButton > button {
  border-radius: 7px !important;
  font-size: 12.5px !important;
  font-weight: 500 !important;
}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# CARGA
# ══════════════════════════════════════════════
df_all = cargar_datos()

# ── Selector de proyecto en sidebar ───────────
proyectos_df = df_all[df_all["nivel"] == "Proyecto"][["project_id", "project_name", "item_id"]].copy()
# item_id == project_id para proyectos; usamos project_id como clave
proyectos_df = proyectos_df.drop_duplicates(subset=["project_id"])

proyecto_names = proyectos_df["project_name"].tolist()
proyecto_ids   = proyectos_df["project_id"].tolist()  # lista de UUIDs

# ══════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════
col_logo, col_title, col_meta = st.columns([0.08, 0.7, 0.22])
with col_logo:
    st.markdown("<div style='font-size:2rem;margin-top:4px'>📊</div>", unsafe_allow_html=True)
with col_title:
    st.markdown("<h1>Project Tracker</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<span class='pt-badge'>{len(proyecto_ids)} proyecto{'s' if len(proyecto_ids) != 1 else ''}</span>&nbsp;"
        f"<span class='pt-badge' style='background:#dcfce7;color:#166534;'>{len(df_all)} registros</span>",
        unsafe_allow_html=True,
    )

st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# PANEL IZQUIERDO — GESTIÓN
# ══════════════════════════════════════════════
col_mgmt, col_gantt = st.columns([0.32, 0.68], gap="large")

with col_mgmt:

    # ── Crear proyecto ─────────────────────────
    with st.expander("➕ Nuevo proyecto", expanded=(len(proyecto_ids) == 0)):
        nuevo_nombre = st.text_input("Nombre", key="inp_nuevo_proyecto", placeholder="Ej: Rediseño Web 2025")
        nuevo_owner  = st.text_input("Responsable", key="inp_nuevo_owner", placeholder="Nombre o equipo")
        c1, c2 = st.columns(2)
        nuevo_inicio = c1.date_input("Inicio", value=date.today(), key="inp_nuevo_inicio")
        nuevo_fin    = c2.date_input("Fin",    value=date.today(), key="inp_nuevo_fin")

        if st.button("Crear proyecto", use_container_width=True, type="primary"):
            nombre = nuevo_nombre.strip()
            if not nombre:
                st.warning("Escribe un nombre para el proyecto.")
            elif nombre in proyecto_names:
                st.warning(f'Ya existe un proyecto llamado **{nombre}**.')
            else:
                new_pid = _new_uuid()
                insertar_fila({
                    "id":           new_pid,
                    "nivel":        "Proyecto",
                    "project_id":   new_pid,   # ← clave: project_id == id propio
                    "project_name": nombre,
                    "item_id":      new_pid,
                    "item_name":    nombre,
                    "parent_id":    "",
                    "responsible":  nuevo_owner.strip(),
                    "start_date":   nuevo_inicio.isoformat(),
                    "end_date":     nuevo_fin.isoformat(),
                    "progress":     0,
                    "status":       "En curso",
                    "document_url": "",
                })
                st.success(f"Proyecto **{nombre}** creado ✅")
                st.rerun()

    st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)

    # ── Selector proyecto activo ───────────────
    if not proyecto_ids:
        st.info("Aún no tienes proyectos. Crea uno arriba.")
        st.stop()

    idx_sel = st.selectbox(
        "Proyecto activo",
        range(len(proyecto_names)),
        format_func=lambda i: proyecto_names[i],
        key="sel_proyecto",
    )
    selected_project_id   = proyecto_ids[idx_sel]
    selected_project_name = proyecto_names[idx_sel]

    # ── DataFrame del proyecto seleccionado ───
    # CLAVE: filtramos por project_id (UUID), no por nombre
    df_proj = df_all[df_all["project_id"] == selected_project_id].copy()

    # ── Métricas rápidas ───────────────────────
    tareas     = df_proj[df_proj["nivel"] == "Tarea"]
    subtareas  = df_proj[df_proj["nivel"] == "Subtarea"]
    completadas = tareas[tareas["status"] == "Completado"]

    m1, m2, m3 = st.columns(3)
    m1.metric("Tareas",    len(tareas))
    m2.metric("Subtareas", len(subtareas))
    m3.metric("Completadas", f"{len(completadas)}/{len(tareas)}")

    st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)

    # ══════════════════════════════════════════
    # AGREGAR TAREA
    # ══════════════════════════════════════════
    with st.expander("➕ Nueva tarea"):
        t_nombre = st.text_input("Nombre de la tarea", key="inp_t_nombre")
        t_resp   = st.text_input("Responsable",        key="inp_t_resp")
        tc1, tc2 = st.columns(2)
        t_inicio = tc1.date_input("Inicio", value=date.today(), key="inp_t_inicio")
        t_fin    = tc2.date_input("Fin",    value=date.today(), key="inp_t_fin")
        t_status = st.selectbox("Estado", STATUS_OPTIONS, key="inp_t_status")

        if st.button("Agregar tarea", use_container_width=True, type="primary"):
            nombre = t_nombre.strip()
            if not nombre:
                st.warning("Escribe un nombre para la tarea.")
            else:
                new_tid = _new_uuid()
                insertar_fila({
                    "id":           new_tid,
                    "nivel":        "Tarea",
                    "project_id":   selected_project_id,    # ← asociación explícita por UUID
                    "project_name": selected_project_name,
                    "item_id":      new_tid,
                    "item_name":    nombre,
                    "parent_id":    selected_project_id,    # padre = el proyecto
                    "responsible":  t_resp.strip(),
                    "start_date":   t_inicio.isoformat(),
                    "end_date":     t_fin.isoformat(),
                    "progress":     0,
                    "status":       t_status,
                    "document_url": "",
                })
                st.success(f"Tarea **{nombre}** agregada ✅")
                st.rerun()

    # ══════════════════════════════════════════
    # AGREGAR SUBTAREA
    # ══════════════════════════════════════════
    tareas_lista = tareas[["item_id", "item_name"]].drop_duplicates()

    if not tareas_lista.empty:
        with st.expander("➕ Nueva subtarea"):
            tarea_sel_idx = st.selectbox(
                "Tarea padre",
                range(len(tareas_lista)),
                format_func=lambda i: tareas_lista.iloc[i]["item_name"],
                key="inp_st_padre",
            )
            tarea_padre_id = tareas_lista.iloc[tarea_sel_idx]["item_id"]

            st_nombre = st.text_input("Nombre de la subtarea", key="inp_st_nombre")
            st_resp   = st.text_input("Responsable",           key="inp_st_resp")
            sc1, sc2  = st.columns(2)
            st_inicio = sc1.date_input("Inicio", value=date.today(), key="inp_st_inicio")
            st_fin    = sc2.date_input("Fin",    value=date.today(), key="inp_st_fin")
            st_status = st.selectbox("Estado", STATUS_OPTIONS, key="inp_st_status")

            if st.button("Agregar subtarea", use_container_width=True, type="primary"):
                nombre = st_nombre.strip()
                if not nombre:
                    st.warning("Escribe un nombre para la subtarea.")
                else:
                    new_sid = _new_uuid()
                    insertar_fila({
                        "id":           new_sid,
                        "nivel":        "Subtarea",
                        "project_id":   selected_project_id,   # ← siempre el proyecto raíz
                        "project_name": selected_project_name,
                        "item_id":      new_sid,
                        "item_name":    nombre,
                        "parent_id":    tarea_padre_id,         # padre = la tarea
                        "responsible":  st_resp.strip(),
                        "start_date":   st_inicio.isoformat(),
                        "end_date":     st_fin.isoformat(),
                        "progress":     0,
                        "status":       st_status,
                        "document_url": "",
                    })
                    st.success(f"Subtarea **{nombre}** agregada ✅")
                    st.rerun()

    st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)

    # ══════════════════════════════════════════
    # EDITOR INLINE (solo el proyecto activo)
    # ══════════════════════════════════════════
    st.markdown("### ✏️ Editar tareas")

    if df_proj.empty:
        st.caption("Este proyecto no tiene tareas aún.")
    else:
        # Preparar para el editor:  incluimos `id` oculto para poder hacer UPDATE
        df_edit = df_proj[[
            "id", "nivel", "item_name", "responsible",
            "start_date", "end_date", "progress", "status", "document_url"
        ]].copy()

        df_edit["start_date"] = pd.to_datetime(df_edit["start_date"], errors="coerce")
        df_edit["end_date"]   = pd.to_datetime(df_edit["end_date"],   errors="coerce")

        edited = st.data_editor(
            df_edit,
            num_rows="fixed",           # ← no permitir agregar/borrar filas aquí
            use_container_width=True,
            hide_index=True,
            column_config={
                "id":           st.column_config.TextColumn("ID",       disabled=True, width="small"),
                "nivel":        st.column_config.TextColumn("Nivel",    disabled=True, width="small"),
                "item_name":    st.column_config.TextColumn("Nombre"),
                "responsible":  st.column_config.TextColumn("Responsable"),
                "start_date":   st.column_config.DateColumn("Inicio"),
                "end_date":     st.column_config.DateColumn("Fin"),
                "progress":     st.column_config.NumberColumn("Avance %", min_value=0, max_value=100, step=5),
                "status":       st.column_config.SelectboxColumn("Estado", options=STATUS_OPTIONS),
                "document_url": st.column_config.LinkColumn("Documento"),
            },
            key="editor_tareas",
        )

        if st.button("💾 Guardar cambios", use_container_width=True, type="primary"):
            errores = 0
            for _, row in edited.iterrows():
                row_id = str(row["id"])
                try:
                    actualizar_fila(row_id, {
                        "item_name":    str(row["item_name"]).strip(),
                        "responsible":  str(row.get("responsible", "")).strip(),
                        "start_date":   pd.to_datetime(row["start_date"]).strftime("%Y-%m-%d"),
                        "end_date":     pd.to_datetime(row["end_date"]).strftime("%Y-%m-%d"),
                        "progress":     int(row.get("progress", 0)),
                        "status":       str(row.get("status", "No iniciado")),
                        "document_url": str(row.get("document_url", "")).strip(),
                    })
                except Exception as exc:
                    st.warning(f"Error en fila {row_id}: {exc}")
                    errores += 1

            if errores == 0:
                st.success("Cambios guardados ✅")
            else:
                st.warning(f"Se guardaron con {errores} error(es).")
            st.rerun()

    st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)

    # ── Eliminar proyecto ─────────────────────
    with st.expander("⚠️ Zona peligrosa"):
        st.warning(
            f"Esto eliminará el proyecto **{selected_project_name}** "
            "y **todas** sus tareas y subtareas. Esta acción no se puede deshacer."
        )
        confirmar = st.text_input(
            f'Escribe el nombre del proyecto para confirmar:',
            key="confirm_delete",
            placeholder=selected_project_name,
        )
        if st.button("🗑️ Eliminar proyecto", type="secondary", use_container_width=True):
            if confirmar.strip() == selected_project_name:
                eliminar_por_project_id(selected_project_id)
                st.success("Proyecto eliminado.")
                st.rerun()
            else:
                st.error("El nombre no coincide. Operación cancelada.")


# ══════════════════════════════════════════════
# PANEL DERECHO — GANTT
# ══════════════════════════════════════════════
with col_gantt:

    st.markdown("### 📅 Timeline — Gantt")

    # Opción: ver solo el proyecto activo o todos
    tab_uno, tab_todos = st.tabs([
        f"Solo: {selected_project_name}",
        "Todos los proyectos",
    ])

    def _render_gantt(df_gantt: pd.DataFrame) -> None:
        if df_gantt.empty:
            st.info("No hay datos para mostrar en el Gantt.")
            return

        df_gantt = df_gantt.copy()
        df_gantt["start_date"] = pd.to_datetime(df_gantt["start_date"], errors="coerce")
        df_gantt["end_date"]   = pd.to_datetime(df_gantt["end_date"],   errors="coerce")

        min_d = df_gantt["start_date"].min()
        max_d = df_gantt["end_date"].max()

        col_f1, col_f2, _ = st.columns([1, 1, 2])
        fecha_inicio = col_f1.date_input("Desde", value=min_d, key=f"gi_{id(df_gantt)}")
        fecha_fin    = col_f2.date_input("Hasta", value=max_d, key=f"gf_{id(df_gantt)}")

        df_gantt["timeline_status"] = df_gantt.apply(calcular_timeline_status, axis=1)

        html = build_ms_project_gantt_html(
            df_gantt,
            start_date=fecha_inicio,
            end_date=fecha_fin,
        )

        # Altura dinámica según filas
        altura = max(200, min(len(df_gantt) * 36 + 90, 850))
        components.html(html, height=altura, scrolling=True)

    with tab_uno:
        _render_gantt(df_proj)

    with tab_todos:
        _render_gantt(df_all)
