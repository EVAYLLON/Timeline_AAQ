from pathlib import Path
from html import escape
import pandas as pd


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



def _date_range_months(start, end):
    months = []
    current = start.replace(day=1)

    while current <= end:
        months.append(current)
        current = (current + pd.DateOffset(months=1)).replace(day=1)

    return months



def _safe_link(url: str) -> str:
    if isinstance(url, str) and url.startswith("http"):
        return f'<a href="{escape(url)}" target="_blank">Abrir</a>'
    return ""

def build_ms_project_gantt_html(
    df: pd.DataFrame,
    title: str = "Gantt de Seguimiento",
    zoom: str = "Proyecto completo"
) -> str:

    if df.empty:
        return "<p>No existen datos para construir el Gantt.</p>"

    data = df.copy()

    # =========================
    # ✅ BLOQUE LIMPIO (ÚNICO)
    # =========================
    data["start_date"] = pd.to_datetime(data["start_date"])
    data["end_date"] = pd.to_datetime(data["end_date"])

    base_min = data["start_date"].min()
    base_max = data["end_date"].max()

    min_date = base_min
    max_date = base_max

    # ✅ ZOOM
    if zoom == "30 días":
        max_date = base_min + pd.Timedelta(days=30)
    elif zoom == "60 días":
        max_date = base_min + pd.Timedelta(days=60)

    # ✅ RECORTE
    data = data[
        (data["end_date"] >= min_date) &
        (data["start_date"] <= max_date)
    ]

    # ✅ RANGO
    total_days = max((max_date - min_date).days, 1)

    months = _date_range_months(min_date, max_date)
    if not months:
        months = [min_date]

    # =========================
    # HEADER MESES
    # =========================
    month_headers = ""
    for m in months:
        next_m = m + pd.offsets.MonthBegin(1)

        left = ((m - min_date).days / total_days) * 100
        width = max(((next_m - m).days / total_days) * 100, 4)

        month_headers += f'''
        <div class="month-header" style="left:{left:.2f}%; width:{width:.2f}%;">
            {m.strftime("%b %Y")}
        </div>
        '''

    # =========================
    # FILAS
    # =========================
    rows_html = ""

    for _, row in data.iterrows():
        level = row["level"]
        style = LEVEL_STYLES.get(level, LEVEL_STYLES["Subtarea"])
        color = STATUS_COLORS.get(row["timeline_status"], "#607D8B")

        start = max(row["start_date"], min_date)
        end = min(row["end_date"], max_date)

        left = ((start - min_date).days / total_days) * 100
        width = max(((end - start).days / total_days) * 100, 1.5)

        progress_width = max(min(float(row["progress"]), 100), 0)
        link_html = _safe_link(row.get("document_url", ""))

        rows_html += f'''
        <div class="gantt-row {level.lower()}">
            <div class="task-table">
                <div class="task-name" style="padding-left:{style["indent"]}px; font-weight:{style["font_weight"]};">
                    <span class="tree-icon">{style["icon"]}</span>
                    {escape(str(row["item_name"]))}
                </div>
                <div class="task-owner">{escape(str(row["responsible"]))}</div>
                <div class="task-date">{row["start_date"].strftime("%d/%m/%Y")}</div>
                <div class="task-date">{row["end_date"].strftime("%d/%m/%Y")}</div>
                <div class="task-progress">{int(row["progress"])}%</div>
                <div class="task-status">
                    <span class="status-pill" style="background:{color};">{escape(str(row["timeline_status"]))}</span>
                </div>
                <div class="task-link">{link_html}</div>
            </div>

            <div class="timeline-cell">
                <div class="bar"
                     title="{escape(str(row['item_name']))}"
                     style="
                        left:{left:.2f}%;
                        width:{width:.2f}%;
                        height:{style["bar_height"]}px;
                        background:{color};
                        opacity:{style["opacity"]};
                     ">
                    <div class="bar-progress" style="width:{progress_width:.2f}%;"></div>
                </div>
            </div>
        </div>
        '''

    # =========================
    # HTML ORIGINAL (LIMPIO)
    # =========================

    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">

    <style>
    body {{
        font-family: Arial, Helvetica, sans-serif;
    }}

    .gantt-wrapper {{
        border: 1px solid #ccc;
        border-radius: 8px;
        overflow: auto;
    }}

    .gantt-header {{
        display: grid;
        grid-template-columns: 740px 1fr;
    }}

    .table-header {{
        display: grid;
        grid-template-columns: 220px 120px 90px 90px 65px 105px 70px;
    }}

    .table-header div {{
        padding: 8px;
        border-right: 1px solid #ccc;
    }}

    .timeline-header {{
        position: relative;
        height: 40px;
        border-left: 1px solid #ccc;
    }}

    .month-header {{
        position: absolute;
        height: 40px;
        text-align: center;
        font-size: 12px;
        border-right: 1px solid #ccc;
        background: #e5e7eb;
    }}

    .gantt-row {{
        display: grid;
        grid-template-columns: 740px 1fr;
    }}

    .task-table {{
        display: grid;
        grid-template-columns: 220px 120px 90px 90px 65px 105px 70px;
    }}

    .task-table > div {{
        padding: 6px;
        border-right: 1px solid #ddd;
    }}

    .timeline-cell {{
        position: relative;
        border-left: 1px solid #ccc;
    }}

    .bar {{
        position: absolute;
        top: 50%;
        transform: translateY(-50%);
        border-radius: 4px;
        height: 16px;
    }}
    </style>

    </head>

    <body>

    <div class="gantt-wrapper">
        <div class="gantt-header">
            <div class="table-header">
                <div>Proyecto / Tarea</div>
                <div>Responsable</div>
                <div>Inicio</div>
                <div>Fin</div>
                <div>Avance</div>
                <div>Estado</div>
                <div>Link</div>
            </div>
            <div class="timeline-header">
                {month_headers}
            </div>
        </div>

        {rows_html}

    </div>

    </body>
    </html>
    '''
    return html

def export_gantt_html(html: str, output_path: str | Path = "reports/gantt.html") -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
