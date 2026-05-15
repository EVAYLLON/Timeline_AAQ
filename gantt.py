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


def build_ms_project_gantt_html(df, title="Gantt", zoom="Proyecto completo"):

    if df.empty:
        return "<p>No existen datos</p>"

    data = df.copy()

    data["start_date"] = pd.to_datetime(data["start_date"])
    data["end_date"] = pd.to_datetime(data["end_date"])

    base_min = data["start_date"].min()
    base_max = data["end_date"].max()

    min_date = base_min
    max_date = base_max

    if zoom == "30 días":
        max_date = base_min + pd.Timedelta(days=30)
    elif zoom == "60 días":
        max_date = base_min + pd.Timedelta(days=60)

    data = data[(data["end_date"] >= min_date) & (data["start_date"] <= max_date)]

    total_days = max((max_date - min_date).days, 1)

    months = _date_range_months(min_date, max_date)

    # ✅ HEADER
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

    # ✅ FILAS
    rows_html = ""

    for _, row in data.iterrows():
        style = LEVEL_STYLES.get(row["level"], LEVEL_STYLES["Subtarea"])
        color = STATUS_COLORS.get(row["timeline_status"], "#607D8B")

        start = max(row["start_date"], min_date)
        end = min(row["end_date"], max_date)

        left = ((start - min_date).days / total_days) * 100
        width = ((end - start).days / total_days) * 100

        rows_html += f'''
        <div class="gantt-row">

            <div class="task-table">
                <div style="padding-left:{style["indent"]}px;">{row["item_name"]}</div>
                <div>{row["responsible"]}</div>
                <div>{row["start_date"].strftime("%d/%m/%Y")}</div>
                <div>{row["end_date"].strftime("%d/%m/%Y")}</div>
                <div>{int(row["progress"])}%</div>
                <div>{row["timeline_status"]}</div>
                <div>{_safe_link(row.get("document_url",""))}</div>
            </div>

            <div class="timeline-cell">
                <div class="bar" style="
                    left:{left:.2f}%;
                    width:{width:.2f}%;
                    background:{color};
                "></div>
            </div>

        </div>
        '''

    # ✅ HTML CORRECTO PARA STREAMLIT
    html = f'''
    <style>
    .gantt-wrapper {{
        border: 1px solid #ccc;
        overflow: auto;
    }}

    .gantt-header {{
        display: grid;
        grid-template-columns: 740px 1fr;
        background: #eee;
    }}

    .table-header {{
        display: grid;
        grid-template-columns: 220px 120px 90px 90px 65px 105px 70px;
        font-weight: bold;
    }}

    .timeline-header {{
        position: relative;
        height: 40px;
    }}

    .month-header {{
        position: absolute;
        font-size: 12px;
    }}

    .gantt-row {{
        display: grid;
        grid-template-columns: 740px 1fr;
    }}

    .task-table {{
        display: grid;
        grid-template-columns: 220px 120px 90px 90px 65px 105px 70px;
    }}

    .timeline-cell {{
        position: relative;
        height: 40px;
    }}

    .bar {{
        position: absolute;
        top: 10px;
        height: 18px;
        border-radius: 4px;
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
            </div>
        </div>

        {rows_html}

    </div>
    '''

    return html