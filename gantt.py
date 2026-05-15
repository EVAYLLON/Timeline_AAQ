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
    "Proyecto": {"indent": 0, "font_weight": "700", "bar_height": 22, "opacity": 1.0, "icon": "▾"},
    "Tarea": {"indent": 20, "font_weight": "600", "bar_height": 18, "opacity": 0.95, "icon": "•"},
    "Subtarea": {"indent": 42, "font_weight": "400", "bar_height": 14, "opacity": 0.85, "icon": "◦"}
}


def _safe_link(url):
    if isinstance(url, str) and url.startswith("http"):
        return f'<a href="{escape(url)}" target="_blank">Abrir</a>'
    return ""


def build_ms_project_gantt_html(df, zoom="Proyecto completo"):

    if df.empty:
        return "<p>No existen datos</p>"

    data = df.copy()

    data["start_date"] = pd.to_datetime(data["start_date"])
    data["end_date"] = pd.to_datetime(data["end_date"])

    min_date = data["start_date"].min()
    max_date = data["end_date"].max()

    if zoom == "30 días":
        max_date = min_date + pd.Timedelta(days=30)
    elif zoom == "60 días":
        max_date = min_date + pd.Timedelta(days=60)

    data = data[(data["end_date"] >= min_date) & (data["start_date"] <= max_date)]

    total_days = max((max_date - min_date).days, 1)

    today = datetime.today()

    # ✅ HEADER meses
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

    # ✅ línea HOY
    today_pos = ((today - min_date).days / total_days) * 100

    # ✅ FILAS
    rows_html = ""

    for _, row in data.iterrows():
        style = LEVEL_STYLES.get(row["level"], LEVEL_STYLES["Subtarea"])
        color = STATUS_COLORS.get(row["timeline_status"], "#607D8B")

        start = max(row["start_date"], min_date)
        end = min(row["end_date"], max_date)

        left = ((start - min_date).days / total_days) * 100
        width = max(((end - start).days / total_days) * 100, 1.5)

        progress_width = max(min(float(row["progress"]), 100), 0)
        link_html = _safe_link(row.get("document_url", ""))

        rows_html += f'''
        <div class="gantt-row">

            <div class="task-table">

                <div style="padding-left:{style["indent"]}px; font-weight:{style["font_weight"]};">
                    {style["icon"]} {escape(str(row["item_name"]))}
                </div>

                <div>{escape(str(row["responsible"]))}</div>
                <div>{row["start_date"].strftime("%d/%m/%Y")}</div>
                <div>{row["end_date"].strftime("%d/%m/%Y")}</div>
                <div>{int(row["progress"])}%</div>

                <div>
                    <span class="status-pill" style="background:{color};">
                        {escape(str(row["timeline_status"]))}
                    </span>
                </div>

                <div>{link_html}</div>

            </div>

            <div class="timeline-cell">
                <div class="bar" style="
                    left:{left:.2f}%;
                    width:{width:.2f}%;
                    height:{style["bar_height"]}px;
                    background:{color};
                ">
                    <div class="bar-progress" style="width:{progress_width:.2f}%;"></div>
                </div>
            </div>

        </div>
        '''

    html = f'''
<style>

.gantt-header {{
    display: grid;
    grid-template-columns: 740px 1fr;
    background: #e5e7eb;
}}

.table-header {{
    display: grid;
    grid-template-columns: 220px 120px 90px 90px 65px 105px 70px;
    font-weight: bold;
}}

.task-table {{
    display: grid;
    grid-template-columns: 220px 120px 90px 90px 65px 105px 70px;
}}

.gantt-row {{
    display: grid;
    grid-template-columns: 740px 1fr;
    min-height: 34px;
    align-items: center;
}}

.timeline-header {{
    position: relative;
    height: 34px;
    border-left: 1px solid #ccc;
}}

.timeline-cell {{
    position: relative;
    height: 34px;

    /* ✅ GRID DE DÍAS */
    background: repeating-linear-gradient(
        to right,
        #ffffff 0px,
        #ffffff 19px,
        #e5e7eb 20px
    );
}}

.month-header {{
    position: absolute;
    text-align: center;
    font-size: 12px;
    font-weight: bold;
}}

.bar {{
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    border-radius: 4px;
}}

.bar-progress {{
    height: 100%;
    background: rgba(255,255,255,0.35);
}}

.status-pill {{
    color: white;
    padding: 2px 6px;
    border-radius: 6px;
}}

.today-line {{
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background: red;
    left: {today_pos:.2f}%;
    z-index: 2;
}}

</style>

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
        <div class="today-line"></div>
    </div>
</div>

{rows_html}
'''

    return html


def export_gantt_html(html, output_path="reports/gantt.html"):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path