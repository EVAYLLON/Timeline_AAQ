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


def build_ms_project_gantt_html(df, zoom="Proyecto completo"):

    if df.empty:
        return "<h3>⚠️ No hay datos para mostrar</h3>"

    df = df.copy()
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

    min_date = df["start_date"].min()
    max_date = df["end_date"].max()

    if pd.isna(min_date) or pd.isna(max_date):
        return "<h3>⚠️ No hay fechas válidas</h3>"

    # ✅ Zoom (igual que antes)
    if zoom == "30 días":
        max_date = min_date + pd.Timedelta(days=30)
    elif zoom == "60 días":
        max_date = min_date + pd.Timedelta(days=60)

    total_days = max((max_date - min_date).days, 1)
    today = datetime.today()

    # ================= HEADER TIEMPO =================
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

    # ================= FILAS =================
    rows_html = ""

    for _, row in df.iterrows():

        style = LEVEL_STYLES.get(row["nivel"], LEVEL_STYLES["Subtarea"])
        color = STATUS_COLORS.get(row["timeline_status"], "#607D8B")

        start = max(row["start_date"], min_date)
        end = min(row["end_date"], max_date)

        left = ((start - min_date).days / total_days) * 100
        width = max(((end - start).days / total_days) * 100, 1.5)

        project_id = escape(str(row.get("project_name", "Sin Proyecto")))
        is_project = row["nivel"] == "Proyecto"

        click = f'onclick="toggleProject(\'{project_id}\')"' if is_project else ""

        rows_html += f'''
        <div class="gantt-row {'project-row' if is_project else 'task-row'}" data-project="{project_id}">
        
            <div class="task-table">

                <div style="padding-left:{style["indent"]}px; font-weight:{style["font_weight"]}; cursor:pointer;" {click}>
                    <span class="expander">{style["icon"]}</span>
                    {escape(str(row["item_name"]))}
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

    # ================= HTML FINAL =================
    html = f'''
<style>

body {{
    font-family: Arial;
}}

.controls {{
    padding:10px;
    background:#f3f4f6;
    display:flex;
    gap:10px;
}}

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

.timeline-cell {{
    position:relative;
    height:32px;
    background: repeating-linear-gradient(to right,#fff 0,#fff 19px,#e5e7eb 20px);
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
    transform:translateX(-50%);
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
    width:2px;
    top:0;
    bottom:0;
    background:red;
    left:{today_pos:.2f}%;
}}

</style>

<div class="controls">
    <label>Inicio:</label>
    <input type="date" id="startDate">
    <button onclick="setToday()">Hoy</button>
    <button onclick="setMonthStart()">Inicio Mes</button>
</div>

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

function setToday() {{
    document.getElementById("startDate").value = new Date().toISOString().split('T')[0];
}}

function setMonthStart() {{
    let d = new Date();
    d.setDate(1);
    document.getElementById("startDate").value = d.toISOString().split('T')[0];
}}

</script>
'''

    return html


def export_gantt_html(html, output_path="reports/gantt.html"):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
