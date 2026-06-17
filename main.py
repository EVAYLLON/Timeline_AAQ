"""
main.py  —  Project Tracker con Supabase + Gantt

Esquema real de la tabla `projects`:
  id            bigint  (auto-generado por Supabase)
  nivel         text
  project_name  text
  item_name     text
  responsible   text
  start_date    date
  end_date      date
  progress      bigint
  status        text        (antes llamada 'estado', renombrada en migration.sql)
  document_url  text
  item_id       bigint      (= id para Proyectos; id propio para Tareas/Subtareas)
  parent_id     bigint      (NULL para Proyectos; id del proyecto para Tareas; id de tarea para Subtareas)
  project_id    text        (texto con el id del proyecto raíz — creada en migration.sql)
  updated_at    timestamp
"""

from datetime import date
import inspect

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from supabase import create_client

from gantt import build_ms_project_gantt_html

# El parámetro `theme` solo existe en la versión nueva de gantt.py.
# Si se está usando una versión anterior, lo omitimos para no romper la app.
_GANTT_ACEPTA_THEME = "theme" in inspect.signature(build_ms_project_gantt_html).parameters


def render_gantt_html(df_g, start_date=None, end_date=None, theme="light"):
    """Llama a build_ms_project_gantt_html pasando `theme` solo si está soportado."""
    if _GANTT_ACEPTA_THEME:
        return build_ms_project_gantt_html(df_g, start_date=start_date, end_date=end_date, theme=theme)
    return build_ms_project_gantt_html(df_g, start_date=start_date, end_date=end_date)

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

# Columnas a leer
_COLS_SELECT = (
    "id,nivel,project_id,project_name,"
    "item_id,item_name,parent_id,"
    "responsible,start_date,end_date,progress,status,document_url,sort_order,notes"
)

STATUS_OPTIONS = ["No iniciado", "En curso", "Completado", "Cancelado", "En riesgo"]
PROJECT_STATUS_OPTIONS = ["En curso", "Completado", "Cancelado", "En riesgo", "No iniciado"]

# ══════════════════════════════════════════════
# SUPABASE
# ══════════════════════════════════════════════
@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ══════════════════════════════════════════════
# CARGA
# ══════════════════════════════════════════════
def cargar_datos() -> pd.DataFrame:
    sb = get_supabase()
    try:
        res = sb.table(TABLE).select(_COLS_SELECT).execute()
    except Exception as exc:
        st.error(f"❌ Error Supabase: {exc}")
        return pd.DataFrame()

    if not res.data:
        return pd.DataFrame()

    df = pd.DataFrame(res.data)

    # Columnas opcionales con default
    for col, default in [
        ("responsible",  ""),
        ("status",       "No iniciado"),
        ("document_url", ""),
        ("parent_id",    None),
        ("project_id",   ""),
        ("progress",     0),
        ("sort_order",   0),
        ("notes",        ""),
    ]:
        if col not in df.columns:
            df[col] = default

    # Tipos numéricos
    df["id"]        = pd.to_numeric(df["id"],        errors="coerce").astype("Int64")
    df["item_id"]   = pd.to_numeric(df["item_id"],   errors="coerce").astype("Int64")
    df["parent_id"] = pd.to_numeric(df["parent_id"], errors="coerce").astype("Int64")
    df["progress"]  = pd.to_numeric(df["progress"],  errors="coerce").fillna(0).clip(0, 100).astype(int)
    df["sort_order"]= pd.to_numeric(df["sort_order"],errors="coerce").fillna(0).astype(int)

    # Fechas
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"]   = pd.to_datetime(df["end_date"],   errors="coerce")

    # Strings limpios
    for col in ["nivel", "project_name", "item_name", "responsible", "status", "document_url", "notes"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    # project_id: clave de aislamiento — CRÍTICO
    # Para proyectos: project_id debe ser igual a su propio id (como string)
    # Si está vacío o es NULL, lo reconstruimos desde id para proyectos
    df["project_id"] = df["project_id"].fillna("").astype(str).str.strip()

    mask_proj_sin_pid = (df["nivel"] == "Proyecto") & (df["project_id"] == "")
    df.loc[mask_proj_sin_pid, "project_id"] = df.loc[mask_proj_sin_pid, "id"].astype("Int64").astype(str)

    # Para tareas/subtareas sin project_id, intentar recuperar por project_name
    pid_por_nombre = (
        df[df["nivel"] == "Proyecto"]
        .drop_duplicates("project_name")
        .set_index("project_name")["id"]
        .apply(lambda x: str(int(x)) if pd.notna(x) else "")
        .to_dict()
    )
    mask_tarea_sin_pid = (df["nivel"] != "Proyecto") & (df["project_id"] == "")
    df.loc[mask_tarea_sin_pid, "project_id"] = (
        df.loc[mask_tarea_sin_pid, "project_name"].map(pid_por_nombre).fillna("")
    )

    # Eliminar filas que siguen sin project_id válido (huérfanas reales)
    df = df[df["project_id"] != ""].reset_index(drop=True)

    return df


def calcular_timeline_status(row: pd.Series) -> str:
    today    = pd.Timestamp.today().normalize()
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
def insertar_fila(row: dict) -> dict:
    """Inserta y devuelve el registro creado (con su id auto-asignado)."""
    res = get_supabase().table(TABLE).insert(row).execute()
    return res.data[0] if res.data else {}


def actualizar_fila(row_id: int, updates: dict) -> None:
    get_supabase().table(TABLE).update(updates).eq("id", int(row_id)).execute()


def eliminar_por_project_id(project_id: str) -> None:
    """Elimina TODO lo del proyecto usando project_id (text)."""
    get_supabase().table(TABLE).delete().eq("project_id", project_id).execute()


# ══════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════
st.set_page_config(
    page_title="Project Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Detectar tema (claro / oscuro) de forma robusta ──
def _detectar_tema() -> str:
    try:
        base = st.context.theme.type  # Streamlit reciente: "light" | "dark"
        if base in ("light", "dark"):
            return base
    except Exception:
        pass
    try:
        base = st.get_option("theme.base")
        if base in ("light", "dark"):
            return base
    except Exception:
        pass
    return "light"

APP_THEME = _detectar_tema()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }
.block-container { padding-top: 1.2rem !important; padding-bottom: 2rem !important; max-width: 100% !important; }
h1 { font-size: 1.5rem !important; font-weight: 700 !important; letter-spacing: -0.03em; }
h2 { font-size: 1.1rem !important; font-weight: 600 !important; }
h3 { font-size: 1rem !important; font-weight: 600 !important; }
h4 { font-size: 0.9rem !important; font-weight: 600 !important; }
.pt-badge {
  display: inline-block; font-size: 11px; font-weight: 600;
  padding: 2px 9px; border-radius: 99px;
  background: #e0f2fe; color: #0369a1;
}
.pt-divider { height: 1px; background: rgba(148,163,184,0.22); margin: 14px 0; }

section[data-testid="stSidebar"] { display: none; }

/* Friendlier buttons */
.stButton > button, .stDownloadButton > button {
  border-radius: 10px !important;
  font-weight: 600 !important;
  transition: all 0.15s ease !important;
  border: 1px solid transparent !important;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 3px 10px rgba(0,0,0,0.10) !important;
}
/* Popover / expander triggers rounded */
div[data-testid="stPopover"] > button {
  border-radius: 10px !important;
  font-weight: 600 !important;
}
div[data-testid="stExpander"] {
  border-radius: 10px !important;
  border: 1px solid rgba(148,163,184,0.20) !important;
}
div[data-testid="stExpander"] summary { font-size: 13.5px !important; font-weight: 600 !important; }

/* Metrics */
[data-testid="stMetricValue"] { font-size: 1.4rem !important; }
[data-testid="stMetricLabel"] { font-size: 0.78rem !important; }

/* Tabs */
.stTabs [role="tab"] {
  font-size: 13px !important;
  font-weight: 600 !important;
  padding: 6px 16px !important;
}
.stTabs [role="tabpanel"] { padding-top: 8px !important; }

[data-testid="stDateInput"] label { font-size: 12px !important; margin-bottom: 2px !important; }

/* Alertas */
.pt-alert-overdue {
  background: rgba(185,28,28,0.10); border-left: 3px solid #b91c1c;
  padding: 7px 10px; border-radius: 6px; margin-bottom: 6px; font-size: 13px;
}
.pt-alert-risk {
  background: rgba(230,81,0,0.10); border-left: 3px solid #E65100;
  padding: 7px 10px; border-radius: 6px; margin-bottom: 6px; font-size: 13px;
}
.pt-alert-proj { font-weight: 600; }
.pt-alert-meta { font-size: 11.5px; opacity: 0.8; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# CARGA INICIAL
# ══════════════════════════════════════════════
df_all = cargar_datos()

proyectos_df   = df_all[df_all["nivel"] == "Proyecto"].drop_duplicates(subset=["project_id"])
proyecto_names = proyectos_df["project_name"].tolist()
proyecto_ids   = proyectos_df["project_id"].tolist()   # strings (bigint casteado a text)

# ══════════════════════════════════════════════
# ALERTAS — tareas vencidas / en riesgo (global)
# ══════════════════════════════════════════════
def _calcular_alertas(df: pd.DataFrame):
    """Devuelve (vencidas, en_riesgo) — cada una lista de dicts ordenados por urgencia."""
    today = pd.Timestamp.today().normalize()
    vencidas, en_riesgo = [], []
    cand = df[df["nivel"] != "Proyecto"].copy()
    for _, r in cand.iterrows():
        ts = calcular_timeline_status(r)
        end = pd.to_datetime(r.get("end_date"), errors="coerce")
        if pd.isna(end):
            continue
        dias = (end.normalize() - today).days
        info = {
            "proyecto": str(r.get("project_name", "")),
            "tarea":    str(r.get("item_name", "")),
            "nivel":    str(r.get("nivel", "")),
            "resp":     str(r.get("responsible", "")),
            "fin":      end.strftime("%d/%m/%Y"),
            "dias":     dias,
        }
        if ts == "Vencido":
            vencidas.append(info)
        elif ts == "En riesgo":
            en_riesgo.append(info)
    vencidas.sort(key=lambda x: x["dias"])          # más vencidas primero
    en_riesgo.sort(key=lambda x: x["dias"])          # las que vencen antes primero
    return vencidas, en_riesgo

_vencidas, _en_riesgo = _calcular_alertas(df_all)
_n_alertas = len(_vencidas) + len(_en_riesgo)


def _render_alertas_popover():
    """Botón desplegable con las tareas vencidas / en riesgo."""
    _alert_label = f"🔔 Alertas ({_n_alertas})" if _n_alertas else "🔔 Sin alertas"
    with st.popover(_alert_label, use_container_width=True):
        if _n_alertas == 0:
            st.success("Todo en orden — no hay tareas vencidas ni en riesgo. ✅")
        else:
            if _vencidas:
                st.markdown(f"**🔴 Vencidas ({len(_vencidas)})**")
                for a in _vencidas:
                    dias_txt = f"hace {abs(a['dias'])} día(s)" if a["dias"] < 0 else "hoy"
                    st.markdown(
                        f"<div class='pt-alert-overdue'>"
                        f"<span class='pt-alert-proj'>{a['proyecto']}</span> · {a['tarea']}<br>"
                        f"<span class='pt-alert-meta'>Venció {a['fin']} ({dias_txt})"
                        f"{' · ' + a['resp'] if a['resp'] else ''}</span></div>",
                        unsafe_allow_html=True,
                    )
            if _en_riesgo:
                st.markdown(f"**🟠 En riesgo ({len(_en_riesgo)})**")
                for a in _en_riesgo:
                    dias_txt = f"vence en {a['dias']} día(s)" if a["dias"] > 0 else "vence hoy"
                    st.markdown(
                        f"<div class='pt-alert-risk'>"
                        f"<span class='pt-alert-proj'>{a['proyecto']}</span> · {a['tarea']}<br>"
                        f"<span class='pt-alert-meta'>{a['fin']} ({dias_txt})"
                        f"{' · ' + a['resp'] if a['resp'] else ''}</span></div>",
                        unsafe_allow_html=True,
                    )


# ══════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════
c_logo, c_title = st.columns([0.05, 0.95])
with c_logo:
    st.markdown("<div style='font-size:2rem;margin-top:6px'>📊</div>", unsafe_allow_html=True)
with c_title:
    st.markdown("<h1>Project Tracker</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<span class='pt-badge'>{len(proyecto_ids)} proyecto{'s' if len(proyecto_ids)!=1 else ''}</span>&nbsp;"
        f"<span class='pt-badge' style='background:#dcfce7;color:#166534;'>{len(df_all)} registros</span>",
        unsafe_allow_html=True,
    )

st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# BARRA SUPERIOR — Selector de proyecto + Nuevo proyecto
# ══════════════════════════════════════════════
top_sel, top_new = st.columns([0.78, 0.22], gap="medium")

with top_new:
    with st.popover("➕ Nuevo proyecto", use_container_width=True):
        np_nombre = st.text_input("Nombre", key="np_nombre", placeholder="Ej: Rediseño Web 2025")
        np_owner  = st.text_input("Responsable", key="np_owner")
        c1, c2    = st.columns(2)
        np_inicio = c1.date_input("Inicio", value=date.today(), key="np_inicio")
        np_fin    = c2.date_input("Fin",    value=date.today(), key="np_fin")

        if st.button("Crear proyecto", use_container_width=True, type="primary"):
            nombre = np_nombre.strip()
            if not nombre:
                st.warning("Escribe un nombre.")
            elif nombre in proyecto_names:
                st.warning(f"Ya existe **{nombre}**.")
            else:
                nuevo = insertar_fila({
                    "nivel":        "Proyecto",
                    "project_name": nombre,
                    "item_name":    nombre,
                    "responsible":  np_owner.strip(),
                    "start_date":   np_inicio.isoformat(),
                    "end_date":     np_fin.isoformat(),
                    "progress":     0,
                    "status":       "En curso",
                    "document_url": "",
                    "parent_id":    None,
                })
                if nuevo.get("id"):
                    real_id = int(nuevo["id"])
                    actualizar_fila(real_id, {
                        "project_id": str(real_id),
                        "item_id":    real_id,
                    })
                st.success(f"Proyecto **{nombre}** creado ✅")
                st.rerun()

if not proyecto_ids:
    st.info("Aún no tienes proyectos. Crea uno con el botón **➕ Nuevo proyecto**.")
    st.stop()

with top_sel:
    idx_sel = st.selectbox(
        "Proyecto activo",
        range(len(proyecto_names)),
        format_func=lambda i: proyecto_names[i],
        key="sel_proyecto",
    )

selected_project_id   = proyecto_ids[idx_sel]        # string
selected_project_name = proyecto_names[idx_sel]

# FILTRO POR project_id (texto con bigint del proyecto)
df_proj = df_all[df_all["project_id"] == selected_project_id].copy()

tareas      = df_proj[df_proj["nivel"] == "Tarea"]
subtareas   = df_proj[df_proj["nivel"] == "Subtarea"]
completadas = tareas[tareas["status"] == "Completado"]

# ── Estado del proyecto ────────────────────
proj_row = df_proj[df_proj["nivel"] == "Proyecto"]
proj_db_id = None
proj_current_status = "En curso"
proj_current_notes  = ""
proj_current_start  = date.today()
proj_current_end    = date.today()
proj_current_prog   = 0
if not proj_row.empty:
    _pr = proj_row.iloc[0]
    proj_db_id = int(_pr["id"])
    proj_current_status = str(_pr.get("status", "En curso"))
    proj_current_notes  = str(_pr.get("notes", "") or "")
    try:
        proj_current_start = pd.to_datetime(_pr.get("start_date")).date()
    except Exception:
        pass
    try:
        proj_current_end = pd.to_datetime(_pr.get("end_date")).date()
    except Exception:
        pass
    try:
        proj_current_prog = int(float(_pr.get("progress", 0)))
    except Exception:
        pass

_status_colors = {
    "Completado": ("#166534", "#dcfce7"),
    "En curso":   ("#1e40af", "#dbeafe"),
    "Cancelado":  ("#6b7280", "#f3f4f6"),
    "En riesgo":  ("#92400e", "#fef3c7"),
    "No iniciado":("#475569", "#f1f5f9"),
}

# ── Fila de estado + métricas + alertas ────
b_badge, b_m1, b_m2, b_m3, b_alert, b_cfg = st.columns([0.24, 0.13, 0.13, 0.15, 0.17, 0.18])

with b_badge:
    _sc, _sb = _status_colors.get(proj_current_status, ("#475569", "#f1f5f9"))
    st.markdown(
        f"<div style='margin-top:6px;'>"
        f"<span style='font-size:12px;font-weight:600;color:{_sc};"
        f"background:{_sb};padding:4px 12px;border-radius:99px;'>"
        f"● {proj_current_status}</span></div>",
        unsafe_allow_html=True
    )
b_m1.metric("Tareas",      len(tareas))
b_m2.metric("Subtareas",   len(subtareas))
b_m3.metric("Completadas", f"{len(completadas)}/{len(tareas)}")

with b_alert:
    st.write("")  # pequeño espacio para alinear el botón
    _render_alertas_popover()

with b_cfg:
    st.write("")
    with st.popover("⚙️ Editar proyecto", use_container_width=True):
        new_proj_name = st.text_input(
            "Nombre del proyecto",
            value=selected_project_name,
            key="proj_name_input",
        )
        pc1, pc2 = st.columns(2)
        new_proj_start = pc1.date_input("Inicio", value=proj_current_start, key="proj_start_input")
        new_proj_end   = pc2.date_input("Fin",    value=proj_current_end,   key="proj_end_input")
        new_proj_prog  = st.number_input(
            "Avance %", min_value=0, max_value=100, step=5,
            value=int(proj_current_prog), key="proj_prog_input",
        )
        new_proj_status = st.selectbox(
            "Estado del proyecto",
            PROJECT_STATUS_OPTIONS,
            index=PROJECT_STATUS_OPTIONS.index(proj_current_status) if proj_current_status in PROJECT_STATUS_OPTIONS else 0,
            key="proj_status_sel",
        )
        new_proj_notes = st.text_area(
            "Notas del proyecto",
            value=proj_current_notes,
            height=80,
            placeholder="Observaciones, decisiones clave, riesgos…",
            key="proj_notes_input",
        )
        if st.button("💾 Guardar cambios", use_container_width=True, type="primary", key="save_proj_meta"):
            nombre_nuevo = new_proj_name.strip()
            if not nombre_nuevo:
                st.warning("El nombre no puede quedar vacío.")
            elif new_proj_end < new_proj_start:
                st.warning("La fecha Fin no puede ser anterior a Inicio.")
            elif nombre_nuevo != selected_project_name and nombre_nuevo in proyecto_names:
                st.warning(f"Ya existe un proyecto llamado **{nombre_nuevo}**.")
            elif proj_db_id:
                # Actualiza datos en la fila del proyecto
                actualizar_fila(proj_db_id, {
                    "status":       new_proj_status,
                    "notes":        new_proj_notes.strip(),
                    "item_name":    nombre_nuevo,
                    "project_name": nombre_nuevo,
                    "start_date":   new_proj_start.isoformat(),
                    "end_date":     new_proj_end.isoformat(),
                    "progress":     int(new_proj_prog),
                })
                # Si cambió el nombre, propágalo a tareas/subtareas (project_name)
                # — no toca project_id ni el orden, solo la etiqueta visible.
                if nombre_nuevo != selected_project_name:
                    get_supabase().table(TABLE).update(
                        {"project_name": nombre_nuevo}
                    ).eq("project_id", selected_project_id).execute()
                st.success("Proyecto actualizado ✅")
                st.rerun()

st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# GANTT — ancho completo
# ══════════════════════════════════════════════
st.markdown("### 📅 Timeline — Gantt")

def _render_gantt(df_g: pd.DataFrame, key_suffix: str) -> None:
    if df_g.empty:
        st.info("No hay datos para mostrar.")
        return

    df_g = df_g.copy()
    df_g["start_date"] = pd.to_datetime(df_g["start_date"], errors="coerce")
    df_g["end_date"]   = pd.to_datetime(df_g["end_date"],   errors="coerce")

    min_d = df_g["start_date"].min()
    max_d = df_g["end_date"].max()

    # Fechas por defecto (rango completo de los datos)
    def _to_date(x, fallback):
        try:
            return pd.to_datetime(x).date()
        except Exception:
            return fallback

    default_ini = _to_date(min_d, date.today())
    default_fin = _to_date(max_d, date.today())

    gi_key = f"gi_{key_suffix}"
    gf_key = f"gf_{key_suffix}"

    # Inicializa una sola vez; luego conserva la elección del usuario
    if gi_key not in st.session_state:
        st.session_state[gi_key] = default_ini
    if gf_key not in st.session_state:
        st.session_state[gf_key] = default_fin

    # ── Controles de rango ───────────────────
    cf1, cf2, cf3 = st.columns([0.20, 0.20, 0.60])
    f_inicio = cf1.date_input("Desde", key=gi_key)
    f_fin    = cf2.date_input("Hasta", key=gf_key)
    with cf3:
        st.write("")  # alinea verticalmente
        if st.button("🔄 Ajustar al rango completo", key=f"reset_{key_suffix}"):
            st.session_state[gi_key] = default_ini
            st.session_state[gf_key] = default_fin
            st.rerun()

    df_g["timeline_status"] = df_g.apply(calcular_timeline_status, axis=1)

    # ── Ordenar antes de pasar al gantt ──────
    df_g["_sort_order_tmp"] = pd.to_numeric(df_g.get("sort_order", 0), errors="coerce").fillna(999)

    proyectos_ord = (
        df_g[df_g["nivel"] == "Proyecto"][["project_id", "start_date"]]
        .drop_duplicates("project_id")
        .sort_values(["start_date", "project_id"])
        .reset_index(drop=True)
    )
    proyectos_ord["_grank"] = range(len(proyectos_ord))
    rank_map = dict(zip(proyectos_ord["project_id"], proyectos_ord["_grank"]))

    df_g["_grank"] = df_g["project_id"].map(rank_map)
    df_g["_grank"] = pd.to_numeric(df_g["_grank"], errors="coerce").fillna(99999).astype(int)

    proyectos_f = df_g[df_g["nivel"] == "Proyecto"].copy().sort_values("_grank", kind="stable")
    resto_f     = df_g[df_g["nivel"] != "Proyecto"].copy().sort_values(
        ["_grank", "_sort_order_tmp", "start_date"], kind="stable"
    )

    idx_ord = []
    for _, pr in proyectos_f.iterrows():
        idx_ord.append(pr.name)
        idx_ord.extend(resto_f[resto_f["_grank"] == int(pr["_grank"])].index.tolist())
    for i in resto_f[resto_f["_grank"] == 99999].index:
        if i not in idx_ord:
            idx_ord.append(i)

    df_g = df_g.loc[idx_ord].reset_index(drop=True)

    html_inner = render_gantt_html(df_g, start_date=f_inicio, end_date=f_fin, theme=APP_THEME)

    # ── Gantt embebido ───────────────────────
    altura = max(200, len(df_g) * 36 + 110)
    components.html(html_inner, height=altura, scrolling=True)

    # ── Exportar HTML (debajo del gantt) ─────
    # Siempre en tema claro para impresión / PDF
    html_export = render_gantt_html(df_g, start_date=f_inicio, end_date=f_fin, theme="light")
    html_standalone = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Gantt — Project Tracker</title>
<style>
  body {{ margin: 0; padding: 16px 20px; background: #f8f9fb;
          font-family: 'DM Sans', sans-serif; }}
  .top-bar {{
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 14px;
  }}
  .top-bar h2 {{ margin:0; font-size:16px; color:#1e293b; font-weight:700; }}
  .top-bar span {{ font-size:12px; color:#64748b; }}
  @media print {{
    .top-bar {{ display: none; }}
    body {{ padding: 0; }}
  }}
</style>
</head><body>
<div class="top-bar">
  <h2>📊 Project Tracker — Gantt</h2>
  <span>Desde {f_inicio} hasta {f_fin} &nbsp;|&nbsp;
        <a href="javascript:window.print()" style="color:#2563eb;text-decoration:none;font-weight:600;">🖨 Imprimir / Guardar PDF</a>
  </span>
</div>
{html_export}
</body></html>"""

    st.download_button(
        label="⬇ Exportar Gantt como HTML",
        data=html_standalone.encode("utf-8"),
        file_name=f"gantt_{key_suffix}_{f_inicio}_{f_fin}.html",
        mime="text/html",
        use_container_width=True,
        key=f"dl_{key_suffix}",
    )

tab_uno, tab_todos = st.tabs([
    f"Solo: {selected_project_name}",
    "Todos los proyectos",
])
with tab_uno:
    _render_gantt(df_proj, f"uno_{selected_project_id}")
with tab_todos:
    _render_gantt(df_all, "todos")

st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# GESTIÓN — debajo del Gantt
# ══════════════════════════════════════════════
st.markdown("### 🛠️ Gestión del proyecto")

g1, g2, g3 = st.columns(3, gap="medium")

# ── Nueva tarea ────────────────────────────
with g1:
    with st.expander("➕ Nueva tarea", expanded=False):
        t_nombre = st.text_input("Nombre",       key="t_nombre")
        t_resp   = st.text_input("Responsable",  key="t_resp")
        tc1, tc2 = st.columns(2)
        t_inicio = tc1.date_input("Inicio", value=date.today(), key="t_inicio")
        t_fin    = tc2.date_input("Fin",    value=date.today(), key="t_fin")
        t_status = st.selectbox("Estado", STATUS_OPTIONS, key="t_status")

        if st.button("Agregar tarea", use_container_width=True, type="primary"):
            nombre = t_nombre.strip()
            if not nombre:
                st.warning("Escribe un nombre.")
            else:
                nueva = insertar_fila({
                    "nivel":        "Tarea",
                    "project_name": selected_project_name,
                    "project_id":   selected_project_id,
                    "item_name":    nombre,
                    "responsible":  t_resp.strip(),
                    "start_date":   t_inicio.isoformat(),
                    "end_date":     t_fin.isoformat(),
                    "progress":     0,
                    "status":       t_status,
                    "document_url": "",
                    "parent_id":    int(selected_project_id),
                })
                if nueva.get("id"):
                    actualizar_fila(int(nueva["id"]), {"item_id": int(nueva["id"])})
                st.success(f"Tarea **{nombre}** agregada ✅")
                st.rerun()

# ── Nueva subtarea ─────────────────────────
with g2:
    with st.expander("➕ Nueva subtarea", expanded=False):
        if tareas.empty:
            st.caption("Primero crea una tarea.")
        else:
            t_lista = tareas[["item_id", "item_name"]].drop_duplicates()
            t_idx = st.selectbox(
                "Tarea padre",
                range(len(t_lista)),
                format_func=lambda i: t_lista.iloc[i]["item_name"],
                key="st_padre",
            )
            tarea_padre_id = int(t_lista.iloc[t_idx]["item_id"])

            st_nombre = st.text_input("Nombre",      key="st_nombre")
            st_resp   = st.text_input("Responsable", key="st_resp")
            sc1, sc2  = st.columns(2)
            st_inicio = sc1.date_input("Inicio", value=date.today(), key="st_inicio")
            st_fin    = sc2.date_input("Fin",    value=date.today(), key="st_fin")
            st_status = st.selectbox("Estado", STATUS_OPTIONS, key="st_status")

            if st.button("Agregar subtarea", use_container_width=True, type="primary"):
                nombre = st_nombre.strip()
                if not nombre:
                    st.warning("Escribe un nombre.")
                else:
                    nueva = insertar_fila({
                        "nivel":        "Subtarea",
                        "project_name": selected_project_name,
                        "project_id":   selected_project_id,
                        "item_name":    nombre,
                        "responsible":  st_resp.strip(),
                        "start_date":   st_inicio.isoformat(),
                        "end_date":     st_fin.isoformat(),
                        "progress":     0,
                        "status":       st_status,
                        "document_url": "",
                        "parent_id":    tarea_padre_id,
                    })
                    if nueva.get("id"):
                        actualizar_fila(int(nueva["id"]), {"item_id": int(nueva["id"])})
                    st.success(f"Subtarea **{nombre}** agregada ✅")
                    st.rerun()

# ── Eliminar tarea / subtarea ──────────────
with g3:
    with st.expander("🗑️ Eliminar tarea / subtarea", expanded=False):
        eliminables = df_proj[df_proj["nivel"] != "Proyecto"][["id", "nivel", "item_name"]].copy()
        if eliminables.empty:
            st.caption("No hay tareas para eliminar.")
        else:
            eliminables["_label"] = eliminables.apply(
                lambda r: f"[{r['nivel']}] {r['item_name']}  (ID: {int(r['id'])})", axis=1
            )
            opciones = eliminables["_label"].tolist()
            ids_map  = dict(zip(eliminables["_label"], eliminables["id"]))

            sel_eliminar = st.selectbox("Elemento a eliminar", opciones, key="sel_eliminar")

            if eliminables[eliminables["id"] == ids_map.get(sel_eliminar, -1)]["nivel"].values[0] == "Tarea":
                st.caption("⚠️ Al eliminar una Tarea se borran también todas sus Subtareas.")

            if st.button("🗑️ Eliminar", type="secondary", use_container_width=True):
                fila_id    = int(ids_map[sel_eliminar])
                fila_nivel = eliminables[eliminables["id"] == fila_id]["nivel"].values[0]
                if fila_nivel == "Tarea":
                    get_supabase().table(TABLE).delete().eq("parent_id", fila_id).execute()
                get_supabase().table(TABLE).delete().eq("id", fila_id).execute()
                st.success(f"Eliminado: {sel_eliminar}")
                st.rerun()

# ── Editor inline (ancho completo) ─────────
st.markdown("#### ✏️ Editar tareas")

if df_proj.empty:
    st.caption("Este proyecto no tiene tareas aún.")
else:
    df_edit = df_proj[df_proj["nivel"] != "Proyecto"][[
        "id", "nivel", "item_name", "responsible",
        "start_date", "end_date", "progress", "status", "document_url", "notes"
    ]].copy()

    df_edit["start_date"] = pd.to_datetime(df_edit["start_date"], errors="coerce")
    df_edit["end_date"]   = pd.to_datetime(df_edit["end_date"],   errors="coerce")

    if "sort_order" in df_proj.columns:
        df_edit["orden"] = df_proj[df_proj["nivel"] != "Proyecto"]["sort_order"].values
    else:
        df_edit["orden"] = range(len(df_edit))

    df_edit = df_edit.sort_values("orden").reset_index(drop=True)

    if df_edit.empty:
        st.caption("Agrega tareas usando los formularios de arriba.")
    else:
        st.caption("Edita los campos y pulsa **Guardar cambios**. El orden se ajusta en «↕️ Reordenar».")
        edited = st.data_editor(
            df_edit,
            num_rows="fixed",
            use_container_width=True,
            hide_index=True,
            column_config={
                "orden":        None,   # oculto — se gestiona en «Reordenar»
                "id":           None,   # oculto — uso interno
                "nivel":        st.column_config.TextColumn("Nivel",      disabled=True, width="small"),
                "item_name":    st.column_config.TextColumn("Nombre"),
                "responsible":  st.column_config.TextColumn("Responsable"),
                "start_date":   st.column_config.DateColumn("Inicio"),
                "end_date":     st.column_config.DateColumn("Fin"),
                "progress":     st.column_config.NumberColumn("Avance %", min_value=0, max_value=100, step=5),
                "status":       st.column_config.SelectboxColumn("Estado", options=STATUS_OPTIONS),
                "document_url": st.column_config.LinkColumn("Documento"),
                "notes":        st.column_config.TextColumn("Notas 💬", help="Notas visibles en el Gantt como ícono 💬"),
            },
            column_order=["nivel","item_name","responsible","start_date","end_date","progress","status","document_url","notes"],
            key="editor_tareas",
        )

        if st.button("💾 Guardar cambios", use_container_width=True, type="primary"):
            errores = 0
            for _, row in edited.iterrows():
                try:
                    actualizar_fila(int(row["id"]), {
                        "item_name":    str(row["item_name"]).strip(),
                        "responsible":  str(row.get("responsible", "")).strip(),
                        "start_date":   pd.to_datetime(row["start_date"]).strftime("%Y-%m-%d"),
                        "end_date":     pd.to_datetime(row["end_date"]).strftime("%Y-%m-%d"),
                        "progress":     int(row.get("progress", 0)),
                        "status":       str(row.get("status", "No iniciado")),
                        "document_url": str(row.get("document_url", "")).strip(),
                        "sort_order":   int(row.get("orden", 0)),
                        "notes":        str(row.get("notes", "")).strip(),
                    })
                except Exception as exc:
                    st.warning(f"Error fila {row['id']}: {exc}")
                    errores += 1

            if errores == 0:
                st.success("Cambios guardados ✅")
            else:
                st.warning(f"Guardado con {errores} error(es).")
            st.rerun()

        # ── Reordenar (orden oculto del editor principal) ──
        with st.expander("↕️ Reordenar tareas en el Gantt"):
            st.caption("Asigna un número de orden a cada tarea (menor = más arriba). Luego guarda.")
            df_orden = df_edit[["id", "nivel", "item_name", "orden"]].copy()
            orden_edit = st.data_editor(
                df_orden,
                num_rows="fixed",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "id":        None,
                    "nivel":     st.column_config.TextColumn("Nivel", disabled=True, width="small"),
                    "item_name": st.column_config.TextColumn("Nombre", disabled=True),
                    "orden":     st.column_config.NumberColumn("Orden", min_value=0, max_value=999, step=1, width="small"),
                },
                column_order=["nivel", "item_name", "orden"],
                key="editor_orden",
            )
            if st.button("💾 Guardar orden", use_container_width=True, key="save_orden"):
                for _, r in orden_edit.iterrows():
                    try:
                        actualizar_fila(int(r["id"]), {"sort_order": int(r.get("orden", 0))})
                    except Exception as exc:
                        st.warning(f"Error fila {r['id']}: {exc}")
                st.success("Orden actualizado ✅")
                st.rerun()

# ── Zona peligrosa — eliminar proyecto ─────
st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)
with st.expander("⚠️ Zona peligrosa — eliminar proyecto"):
    st.warning("Esta acción eliminará el proyecto seleccionado y **todas** sus tareas y subtareas. No se puede deshacer.")

    proj_opts  = ["— Selecciona un proyecto —"] + proyecto_names
    proj_del_i = st.selectbox("Proyecto a eliminar", range(len(proj_opts)),
                               format_func=lambda i: proj_opts[i], key="sel_del_proj")

    if proj_del_i > 0:
        nombre_a_borrar = proj_opts[proj_del_i]
        pid_a_borrar    = proyecto_ids[proj_del_i - 1]
        st.error(f"Vas a eliminar: **{nombre_a_borrar}**")

        confirmar_check = st.checkbox(f'Confirmo que quiero eliminar "{nombre_a_borrar}" permanentemente', key="chk_del")
        if confirmar_check:
            if st.button("🗑️ Eliminar proyecto ahora", type="secondary", use_container_width=True):
                eliminar_por_project_id(pid_a_borrar)
                st.success(f"Proyecto **{nombre_a_borrar}** eliminado.")
                st.rerun()
