from pathlib import Path
from html import escape
import pandas as pd
from datetime import datetime


STATUS_COLORS = {
    "Completado": "#2E7D32",
    "En plazo": "#1976D2",
    "En riesgo": "#F9A825",
    "Vencido": "#C62828"
}

LEVEL_STYLES = {
    "Proyecto": {"indent": 0, "font_weight": "700", "bar_height": 22, "icon": "▾"},
    "Tarea": {"indent": 20, "font_weight": "600", "bar_height": 18, "icon": "•"},
    "Subtarea": {"indent": 42, "font_weight": "400", "bar_height": 14, "icon": "◦"}
}


def _safe_link(url):
    if isinstance(url, str) and url.startswith("http"):
        return f'<a href="{escape(url)}" target="_blank">Abrir</a>'
    return ""


# ✅ IMPORTANTE: agregamos zoom=None para compatibilidad
def build_ms_project_gantt_html(df, start_date=None, end_date=None, zoom=None):

    if df.empty:
        return "<h3>⚠️ No hay datos</h3>"

    df = df.copy()
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

    data_min = df["start_date"].min()
    data_max = df["end_date"].max()

    if pd.isna(data_min) or pd.isna(data_max):
        return "<h3>⚠️ No hay fechas válidas</h3>"

    # ✅ si no pasas fechas → usa todo el proyecto (como antes)
    min_date = pd.to_datetime(start_date) if start_date else data_min
    max_date = pd.to_datetime(end_date) if end_date else data_max

    # ✅ evitar errores de orden
    if min_date > max_date:
        min_date, max_date = max_date, min_date

    total_days = max((max_date - min_date).days, 1)
    today = datetime.today()

    # ===== MESES =====
    months = pd.date_range(min_date, max_date, freq="MS")
    month_headers = ""

    for m in months:
        next_m = m + pd.offsets.MonthBegin(1)

        left = ((m - min_date).days / total_days) * 100
        width = ((next_m - m).days / total_days) * 100

        month_headers += f'''
        <div class="month-header" style="left:{left:.2f}%; width:{width:.2f}%;">
            {m.strftime("%b %Y")}
        </div>
        '''

    # ✅ NO SE TOCA (tu eje X original)
    day_headers = ""
    for i in range(total_days + 1):
        d = min_date + pd.Timedelta(days=i)

        left = ((i + 0.5) / total_days) * 100
        cls = "day-label day-today" if d.date() == today.date() else "day-label"

        day_headers += f'''
        <div class="{cls}" style="left:{left:.2f}%;">
            {d.day}
        </div>
        '''

    today_pos = ((today - min_date).days / total_days) * 100

    # ===== FILAS =====
    rows_html = ""

    for _, row in df.iterrows():

        if pd.isna(row["start_date"]) or pd.isna(row["end_date"]):
            continue

        # ✅ ignorar tareas fuera del rango visible
        if row["end_date"] < min_date or row["start_date"] > max_date:
            continue

        style = LEVEL_STYLES.get(row["nivel"], LEVEL_STYLES["Subtarea"])
        color = STATUS_COLORS.get(row["timeline_status"], "#607D8B")

        start = max(row["start_date"], min_date)
        end = min(row["end_date"], max_date)

        left_days = (start - min_date).days
        duration_days = max((end - start).days, 1)

        left = (left_days / total_days) * 100
        width = max((duration_days / total_days) * 100, 1.5)

        project_id = escape(str(row.get("project_name", "Sin Proyecto")))
        is_project = row["nivel"] == "Proyecto"

        click = f'onclick="toggleProject(\'{project_id}\')"' if is_project else ""

        rows_html += f'''
        <div class="gantt-row {'project-row' if is_project else 'task-row'}" data-project="{project_id}">
        
            <div class="task-table">

                <div style="padding-left:{style["indent"]}px; font-weight:{style["font_weight"]}; cursor:pointer;" {click}>
                    {style["icon"]} {escape(str(row["item_name"]))}
                </div>

                <div>{escape(str(row["responsible"]))}</div>
                <div>{row["start_date"].strftime("%d/%m/%Y")}</div>
                <div>{row["end_date"].strftime("%d/%m/%Y")}</div>
                <div>{int(row["progress"]) if pd.notna(row["progress"]) else 0}%</div>

                <div>
                    <span class="status-pill" style="background:{color};">
                        {escape(str(row.get("timeline_status", "")))}
                    </span>
                </div>

                <div>{_safe_link(row.get("document_url", ""))}</div>

            </div>

            <div class="timeline-cell">
                <div class="bar" style="
                    left:{left:.2f}%;
                    width:{width:.2f}%;
                    height:{style["bar_height"]}px;
                    background:{color};
                ">
                    <div class="bar-progress" style="width:{row.get("progress", 0)}%;"></div>
                </div>
            </div>

        </div>
        '''

    # ===== HTML =====
    html = f'''
<style>
.gantt-wrapper {{
    border:1px solid #ccc;
    overflow-x:auto;
}}

.gantt-header {{
    display:grid;
    grid-template-columns:740px 1fr;
    background:#e5e7eb;
}}

.table-header {{
    display:grid;
    grid-template-columns:220px 120px 90px 90px 65px 105px 70px;
    font-weight:600;
}}

.gantt-row {{
    display:grid;
    grid-template-columns:740px 1fr;
}}

.task-table {{
    display:grid;
    grid-template-columns:220px 120px 90px 90px 65px 105px 70px;
    font-size:12px;
}}

.timeline-header {{
    position:relative;
    height:45px;
}}

.timeline-cell {{
    position:relative;
    height:32px;
    background: repeating-linear-gradient(
        to right,
        #ffffff 0px,
        #ffffff 19px,
        #e5e7eb 20px
    );
}}

.month-header {{
    position:absolute;
    top:0;
    font-size:11px;
    text-align:center;
    font-weight:600;
}}

.day-label {{
    position:absolute;
    bottom:2px;
    transform: translateX(-50%);
    font-size:11px;
}}

.day-today {{
    color:red;
    font-weight:bold;
}}

.bar {{
    position:absolute;
    top:50%;
    transform:translateY(-50%);
    border-radius:4px;
}}

.bar-progress {{
    height:100%;
    background: rgba(255,255,255,0.3);
}}

.status-pill {{
    color:white;
    padding:2px 6px;
    border-radius:6px;
}}

.task-row.hidden {{
    display:none;
}}

.today-line {{
    position:absolute;
    top:0;
    bottom:0;
    width:2px;
    background:red;
    left:{today_pos:.2f}%;
}}
</style>

<div class="gantt-wrapper">
    <div class="gantt-header">
        <div class="table-header">
            <div>Proyecto</div>
            <div>Responsable</div>
            <div>Inicio</div>
            <div>Fin</div>
            <div>Avance</div>
            <div>Estado</div>
            <div>Link</div>
        </div>

        <div class="timeline-header">
            {month_headers}
            {day_headers}
            <div class="today-line"></div>
        </div>
    </div>

    {rows_html}
</div>

<script>
function toggleProject(project) {{
    const rows = document.querySelectorAll('[data-project="' + project + '"]');
    rows.forEach((row) => {{
        if (!row.classList.contains("project-row")) {{
            row.classList.toggle("hidden");
        }}
    }});
}}
</script>
'''

    return html


def export_gantt_html(html, output_path="reports/gantt.html"):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path