from pathlib import Path
import pandas as pd

STATUS_COLORS = {
    "Completado": "#2E7D32",
    "En plazo": "#1976D2",
    "En riesgo": "#F9A825",
    "Vencido": "#C62828"
}

def build_ms_project_gantt_html(df, zoom="Proyecto completo"):

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

    # meses
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

    # filas
    rows_html = ""
    for _, row in data.iterrows():

        start = max(row["start_date"], min_date)
        end = min(row["end_date"], max_date)

        left = ((start - min_date).days / total_days) * 100
        width = max(((end - start).days / total_days) * 100, 1)

        color = STATUS_COLORS.get(row["timeline_status"], "#607D8B")

        rows_html += f'''
        <div class="gantt-row">

            <div class="task-table">
                <div>{row["item_name"]}</div>
                <div>{row["responsible"]}</div>
                <div>{row["start_date"].strftime("%d/%m/%Y")}</div>
                <div>{row["end_date"].strftime("%d/%m/%Y")}</div>
                <div>{int(row["progress"])}%</div>
                <div>{row["timeline_status"]}</div>
                <div></div>
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

    html = f'''
    <style>
    .gantt-header {{
        display: grid;
        grid-template-columns: 700px 1fr;
        background: #eee;
    }}

    .table-header {{
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        font-weight: bold;
    }}

    .gantt-row {{
        display: grid;
        grid-template-columns: 700px 1fr;
        border-bottom: 1px solid #ddd;
    }}

    .task-table {{
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        font-size: 12px;
    }}

    .task-table > div {{
        padding: 6px;
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

    .timeline-header {{
        position: relative;
        height: 40px;
        border-left: 1px solid #ccc;
    }}

    .month-header {{
        position: absolute;
        font-size: 12px;
        text-align: center;
    }}
    </style>

    <div>

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


def export_gantt_html(html, output_path="reports/gantt.html"):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path