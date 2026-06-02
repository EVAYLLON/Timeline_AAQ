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

# Columnas a leer
_COLS_SELECT = (
    "id,nivel,project_id,project_name,"
    "item_id,item_name,parent_id,"
    "responsible,start_date,end_date,progress,status,document_url,sort_order"
)

STATUS_OPTIONS = ["No iniciado", "En curso", "Completado", "Cancelado", "En riesgo"]

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
    ]:
        if col not in df.columns:
            df[col] = default

    # Tipos numéricos
    df["id"]        = pd.to_numeric(df["id"],       errors="coerce")
    df["item_id"]   = pd.to_numeric(df["item_id"],  errors="coerce")
    df["parent_id"] = pd.to_numeric(df["parent_id"],errors="coerce")
    df["progress"]  = pd.to_numeric(df["progress"], errors="coerce").fillna(0).clip(0, 100).astype(int)
    df["sort_order"]= pd.to_numeric(df["sort_order"],errors="coerce").fillna(0).astype(int)

    # Fechas
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"]   = pd.to_datetime(df["end_date"],   errors="coerce")

    # Strings limpios
    for col in ["nivel", "project_name", "item_name", "responsible", "status", "document_url"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    # project_id: clave de aislamiento — CRÍTICO
    # Para proyectos: project_id debe ser igual a su propio id (como string)
    # Si está vacío o es NULL, lo reconstruimos desde id para proyectos
    df["project_id"] = df["project_id"].fillna("").astype(str).str.strip()

    mask_proj_sin_pid = (df["nivel"] == "Proyecto") & (df["project_id"] == "")
    df.loc[mask_proj_sin_pid, "project_id"] = df.loc[mask_proj_sin_pid, "id"].astype(str)

    # Para tareas/subtareas sin project_id, intentar recuperar por project_name
    pid_por_nombre = (
        df[df["nivel"] == "Proyecto"]
        .drop_duplicates("project_name")
        .set_index("project_name")["id"]
        .apply(lambda x: str(int(x)))
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

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }
h1 { font-size: 1.6rem !important; font-weight: 700 !important; letter-spacing: -0.03em; color: #0f172a; }
h2 { font-size: 1.15rem !important; font-weight: 600 !important; color: #1e293b; }
h3 { font-size: 1rem !important; font-weight: 600 !important; color: #334155; }
.pt-badge {
  display: inline-block; font-size: 11px; font-weight: 600;
  padding: 2px 9px; border-radius: 99px;
  background: #e0f2fe; color: #0369a1;
}
.pt-divider { height: 1px; background: #f1f5f9; margin: 16px 0; }
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
# HEADER
# ══════════════════════════════════════════════
c_logo, c_title = st.columns([0.06, 0.94])
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
# LAYOUT
# ══════════════════════════════════════════════
col_mgmt, col_gantt = st.columns([0.32, 0.68], gap="large")

with col_mgmt:

    # ── Crear proyecto ─────────────────────────
    with st.expander("➕ Nuevo proyecto", expanded=(len(proyecto_ids) == 0)):
        np_nombre = st.text_input("Nombre",       key="np_nombre", placeholder="Ej: Rediseño Web 2025")
        np_owner  = st.text_input("Responsable",  key="np_owner")
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
                # Insertar proyecto — id lo genera Supabase
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
                # Una vez creado, actualizamos project_id e item_id con el id real
                if nuevo.get("id"):
                    real_id = int(nuevo["id"])
                    actualizar_fila(real_id, {
                        "project_id": str(real_id),
                        "item_id":    real_id,
                    })
                st.success(f"Proyecto **{nombre}** creado ✅")
                st.rerun()

    st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)

    if not proyecto_ids:
        st.info("Aún no tienes proyectos. Crea uno arriba.")
        st.stop()

    # ── Selector de proyecto ───────────────────
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

    tareas    = df_proj[df_proj["nivel"] == "Tarea"]
    subtareas = df_proj[df_proj["nivel"] == "Subtarea"]
    completadas = tareas[tareas["status"] == "Completado"]

    m1, m2, m3 = st.columns(3)
    m1.metric("Tareas",      len(tareas))
    m2.metric("Subtareas",   len(subtareas))
    m3.metric("Completadas", f"{len(completadas)}/{len(tareas)}")

    st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)

    # ── Nueva tarea ────────────────────────────
    with st.expander("➕ Nueva tarea"):
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
                    "project_id":   selected_project_id,   # ← clave de aislamiento
                    "item_name":    nombre,
                    "responsible":  t_resp.strip(),
                    "start_date":   t_inicio.isoformat(),
                    "end_date":     t_fin.isoformat(),
                    "progress":     0,
                    "status":       t_status,
                    "document_url": "",
                    "parent_id":    int(selected_project_id),  # padre = proyecto
                })
                if nueva.get("id"):
                    actualizar_fila(int(nueva["id"]), {"item_id": int(nueva["id"])})
                st.success(f"Tarea **{nombre}** agregada ✅")
                st.rerun()

    # ── Nueva subtarea ─────────────────────────
    if not tareas.empty:
        with st.expander("➕ Nueva subtarea"):
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
                        "project_id":   selected_project_id,   # ← siempre el proyecto raíz
                        "item_name":    nombre,
                        "responsible":  st_resp.strip(),
                        "start_date":   st_inicio.isoformat(),
                        "end_date":     st_fin.isoformat(),
                        "progress":     0,
                        "status":       st_status,
                        "document_url": "",
                        "parent_id":    tarea_padre_id,        # padre = la tarea
                    })
                    if nueva.get("id"):
                        actualizar_fila(int(nueva["id"]), {"item_id": int(nueva["id"])})
                    st.success(f"Subtarea **{nombre}** agregada ✅")
                    st.rerun()

    st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)

    # ── Editor inline ──────────────────────────
    st.markdown("### ✏️ Editar tareas")

    if df_proj.empty:
        st.caption("Este proyecto no tiene tareas aún.")
    else:
        # Excluir la fila del Proyecto del editor (solo tareas y subtareas)
        df_edit = df_proj[df_proj["nivel"] != "Proyecto"][[
            "id", "nivel", "item_name", "responsible",
            "start_date", "end_date", "progress", "status", "document_url"
        ]].copy()

        df_edit["start_date"] = pd.to_datetime(df_edit["start_date"], errors="coerce")
        df_edit["end_date"]   = pd.to_datetime(df_edit["end_date"],   errors="coerce")

        # Columna de orden: si ya existe en Supabase la usamos, si no asignamos 0,1,2...
        if "sort_order" in df_proj.columns:
            df_edit["orden"] = df_proj[df_proj["nivel"] != "Proyecto"]["sort_order"].values
        else:
            df_edit["orden"] = range(len(df_edit))

        df_edit = df_edit.sort_values("orden").reset_index(drop=True)

        if df_edit.empty:
            st.caption("Agrega tareas usando el formulario de arriba.")
        else:
            st.caption("💡 Cambia el número en **Orden** para reordenar las tareas en el Gantt. Luego guarda.")
            edited = st.data_editor(
                df_edit,
                num_rows="fixed",
                use_container_width=True,
                hide_index=True,
                column_config={
                    "orden":        st.column_config.NumberColumn("Orden", min_value=0, max_value=999, step=1, width="small"),
                    "id":           st.column_config.NumberColumn("ID",       disabled=True, width="small"),
                    "nivel":        st.column_config.TextColumn("Nivel",      disabled=True, width="small"),
                    "item_name":    st.column_config.TextColumn("Nombre"),
                    "responsible":  st.column_config.TextColumn("Responsable"),
                    "start_date":   st.column_config.DateColumn("Inicio"),
                    "end_date":     st.column_config.DateColumn("Fin"),
                    "progress":     st.column_config.NumberColumn("Avance %", min_value=0, max_value=100, step=5),
                    "status":       st.column_config.SelectboxColumn("Estado", options=STATUS_OPTIONS),
                    "document_url": st.column_config.LinkColumn("Documento"),
                },
                column_order=["orden","id","nivel","item_name","responsible","start_date","end_date","progress","status","document_url"],
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
                        })
                    except Exception as exc:
                        st.warning(f"Error fila {row['id']}: {exc}")
                        errores += 1

                if errores == 0:
                    st.success("Cambios guardados ✅")
                else:
                    st.warning(f"Guardado con {errores} error(es).")
                st.rerun()

        # ── Eliminar tarea o subtarea ──────────────
        st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)
        st.markdown("### 🗑️ Eliminar tarea / subtarea")

        # Solo tareas y subtareas (no el proyecto)
        eliminables = df_proj[df_proj["nivel"] != "Proyecto"][["id", "nivel", "item_name"]].copy()

        if eliminables.empty:
            st.caption("No hay tareas para eliminar.")
        else:
            # Construir etiquetas descriptivas: [Tarea] Nombre (ID: 123)
            eliminables["_label"] = eliminables.apply(
                lambda r: f"[{r['nivel']}] {r['item_name']}  (ID: {int(r['id'])})", axis=1
            )
            opciones = eliminables["_label"].tolist()
            ids_map  = dict(zip(eliminables["_label"], eliminables["id"]))

            sel_eliminar = st.selectbox("Selecciona el elemento a eliminar", opciones, key="sel_eliminar")

            col_btn, col_warn = st.columns([1, 2])
            with col_btn:
                if st.button("🗑️ Eliminar", type="secondary", use_container_width=True):
                    fila_id   = int(ids_map[sel_eliminar])
                    fila_nivel = eliminables[eliminables["id"] == fila_id]["nivel"].values[0]

                    if fila_nivel == "Tarea":
                        # Eliminar la tarea Y todas sus subtareas (parent_id == fila_id)
                        get_supabase().table(TABLE).delete().eq("parent_id", fila_id).execute()

                    # Eliminar la fila en sí
                    get_supabase().table(TABLE).delete().eq("id", fila_id).execute()
                    st.success(f"Eliminado: {sel_eliminar}")
                    st.rerun()
            with col_warn:
                if eliminables[eliminables["id"] == ids_map.get(sel_eliminar, -1)]["nivel"].values[0] == "Tarea":
                    st.caption("⚠️ Al eliminar una Tarea se borran también todas sus Subtareas.")

    st.markdown("<div class='pt-divider'></div>", unsafe_allow_html=True)

    # ── Eliminar proyecto ─────────────────────
    with st.expander("⚠️ Zona peligrosa"):
        st.warning("Esta acción eliminará el proyecto seleccionado y **todas** sus tareas y subtareas. No se puede deshacer.")

        # Selector con todos los proyectos existentes
        proj_opts  = ["— Selecciona un proyecto —"] + proyecto_names
        proj_del_i = st.selectbox("Proyecto a eliminar", range(len(proj_opts)),
                                   format_func=lambda i: proj_opts[i], key="sel_del_proj")

        if proj_del_i > 0:
            nombre_a_borrar = proj_opts[proj_del_i]
            pid_a_borrar    = proyecto_ids[proj_del_i - 1]
            st.error(f"Vas a eliminar: **{nombre_a_borrar}**")

            # Doble confirmación: checkbox
            confirmar_check = st.checkbox(f'Confirmo que quiero eliminar "{nombre_a_borrar}" permanentemente', key="chk_del")

            if confirmar_check:
                if st.button("🗑️ Eliminar proyecto ahora", type="secondary", use_container_width=True):
                    eliminar_por_project_id(pid_a_borrar)
                    st.success(f"Proyecto **{nombre_a_borrar}** eliminado.")
                    st.rerun()


# ══════════════════════════════════════════════
# GANTT
# ══════════════════════════════════════════════
with col_gantt:
    st.markdown("### 📅 Timeline — Gantt")

    tab_uno, tab_todos = st.tabs([
        f"Solo: {selected_project_name}",
        "Todos los proyectos",
    ])

    def _render_gantt(df_g: pd.DataFrame, key_suffix: str) -> None:
        if df_g.empty:
            st.info("No hay datos para mostrar.")
            return

        df_g = df_g.copy()
        df_g["start_date"] = pd.to_datetime(df_g["start_date"], errors="coerce")
        df_g["end_date"]   = pd.to_datetime(df_g["end_date"],   errors="coerce")

        min_d = df_g["start_date"].min()
        max_d = df_g["end_date"].max()

        # ── Controles ────────────────────────────
        cf1, cf2 = st.columns([1, 1])
        f_inicio = cf1.date_input("Desde", value=min_d, key=f"gi_{key_suffix}")
        f_fin    = cf2.date_input("Hasta", value=max_d, key=f"gf_{key_suffix}")

        df_g["timeline_status"] = df_g.apply(calcular_timeline_status, axis=1)
        html_inner = build_ms_project_gantt_html(df_g, start_date=f_inicio, end_date=f_fin)

        # ── Gantt embebido ───────────────────────
        altura = max(200, min(len(df_g) * 36 + 90, 620))
        components.html(html_inner, height=altura, scrolling=True)

        # ── Exportar HTML (debajo del gantt) ─────
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
{html_inner}
</body></html>"""

        st.download_button(
            label="⬇ Exportar Gantt como HTML",
            data=html_standalone.encode("utf-8"),
            file_name=f"gantt_{key_suffix}_{f_inicio}_{f_fin}.html",
            mime="text/html",
            use_container_width=True,
            key=f"dl_{key_suffix}",
        )

    with tab_uno:
        _render_gantt(df_proj, "uno")

    with tab_todos:
        _render_gantt(df_all, "todos")
