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


def build_ms_project_gantt_html(df: pd.DataFrame, title: str = "Gantt de Seguimiento", zoom: str = "Proyecto completo") -> str:
    if df.empty:
        return "<p>No existen datos para construir el Gantt.</p>"

    data = df.copy()
# --- DEFINIR RANGO BASE ---
    data["start_date"] = pd.to_datetime(data["start_date"])
    data["end_date"] = pd.to_datetime(data["end_date"])

    base_min = data["start_date"].min()
    base_max = data["end_date"].max()

    # DEFAULT
    min_date = base_min
    max_date = base_max

    # APPLY ZOOM
    if zoom == "30 días":
        max_date = base_min + pd.Timedelta(days=30)

    elif zoom == "60 días":
        max_date = base_min + pd.Timedelta(days=60)


# Recortar tareas al rango visible
        data = data[data["end_date"] >= min_date]
        data = data[data["start_date"] <= max_date]


        total_days = max((max_date - min_date).days, 1)
        # FILTRAR datos dentro del rango visible
        data = data[data["start_date"] <= max_date]
        data = data[data["end_date"] >= min_date]

        months = _date_range_months(min_date, max_date)
        if not months:
            months = [min_date]


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
                     title="{escape(str(row['item_name']))} | {escape(str(row['timeline_status']))} | {int(row['progress'])}%"
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

    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: Arial, Helvetica, sans-serif;
            background: #ffffff;
            color: #1f2937;
        }}

        .gantt-wrapper {{
            border: 1px solid #d1d5db;
            border-radius: 8px;
            overflow: auto;
            background: #ffffff;
        }}

        .gantt-title {{
            font-size: 20px;
            font-weight: 700;
            padding: 14px 16px;
            border-bottom: 1px solid #d1d5db;
            background: #f9fafb;
        }}

        .gantt-header {{
            display: grid;
            grid-template-columns: 740px minmax(900px, 1fr);
            position: sticky;
            top: 0;
            z-index: 10;
            background: #f3f4f6;
            border-bottom: 1px solid #d1d5db;
        }}

        .table-header {{
            display: grid;
            grid-template-columns: 220px 120px 90px 90px 65px 105px 70px;
            font-size: 12px;
            font-weight: 700;
            color: #374151;
        }}

        .table-header div {{
            padding: 10px 8px;
            border-right: 1px solid #d1d5db;
        }}

        .timeline-header {{
            position: relative;
            min-height: 38px;
            border-left: 1px solid #d1d5db;
            background: repeating-linear-gradient(to right, #f9fafb 0px, #f9fafb 79px, #e5e7eb 80px);
        }}

        .month-header {{
            position: absolute;
            top: 0;
            height: 38px;
            padding: 10px 4px;
            font-size: 12px;
            font-weight: 700;
            text-align: center;
            border-right: 1px solid #d1d5db;
            box-sizing: border-box;
            color: #374151;
        }}

        .gantt-row {{
            display: grid;
            grid-template-columns: 740px minmax(900px, 1fr);
            min-height: 38px;
            border-bottom: 1px solid #e5e7eb;
        }}

        .gantt-row.proyecto {{
            background: #eef2ff;
        }}

        .gantt-row.tarea {{
            background: #ffffff;
        }}

        .gantt-row.subtarea {{
            background: #fafafa;
        }}

        .task-table {{
            display: grid;
            grid-template-columns: 220px 120px 90px 90px 65px 105px 70px;
            align-items: center;
            font-size: 12px;
        }}

        .task-table > div {{
            padding: 7px 8px;
            border-right: 1px solid #e5e7eb;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .task-name {{
            color: #111827;
        }}

        .tree-icon {{
            display: inline-block;
            width: 16px;
            color: #4b5563;
        }}

        .task-link a {{
            color: #1d4ed8;
            text-decoration: none;
            font-weight: 600;
        }}

        .status-pill {{
            display: inline-block;
            color: white;
            border-radius: 999px;
            padding: 3px 8px;
            font-size: 11px;
            font-weight: 700;
        }}

        .timeline-cell {{
            position: relative;
            min-height: 38px;
            border-left: 1px solid #d1d5db;
            background: repeating-linear-gradient(to right, #ffffff 0px, #ffffff 79px, #f3f4f6 80px);
        }}

        .bar {{
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            border-radius: 4px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.25);
            min-width: 8px;
            overflow: hidden;
        }}

        .bar-progress {{
            height: 100%;
            background: rgba(255,255,255,0.38);
        }}

        .legend {{
            display: flex;
            gap: 14px;
            padding: 12px 16px;
            font-size: 12px;
            border-top: 1px solid #d1d5db;
            background: #f9fafb;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .legend-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }}
    </style>
    </head>

    <body>
        <div class="gantt-wrapper">
            <div class="gantt-title">{escape(title)}</div>

            <div class="gantt-header">
                <div class="table-header">
                    <div>Proyecto / Tarea</div>
                    <div>Responsable</div>
                    <div>Inicio</div>
                    <div>Fin</div>
                    <div>Avance</div>
                    <div>Estado plazo</div>
                    <div>Link</div>
                </div>
                <div class="timeline-header">
                    {month_headers}
                </div>
            </div>

            {rows_html}

            <div class="legend">
                <div class="legend-item"><span class="legend-dot" style="background:#2E7D32;"></span>Completado</div>
                <div class="legend-item"><span class="legend-dot" style="background:#1976D2;"></span>En plazo</div>
                <div class="legend-item"><span class="legend-dot" style="background:#F9A825;"></span>En riesgo</div>
                <div class="legend-item"><span class="legend-dot" style="background:#C62828;"></span>Vencido</div>
            </div>
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
