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

    # ✅ meses
    months = pd.date_range(min_date, max_date, freq="MS")

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


    # ✅ filas completas (PRO)
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

        rows_html += f'''
        <div class="gantt-row">

            <div class="task-table">

                <div class="task-name" style="padding-left:{style["indent"]}px; font-weight:{style["font_weight"]};">
                    <span class="tree-icon">{style["icon"]}</span>
                    {escape(str(row["item_name"]))}
                </div>

                <div>{escape(str(row["responsible"]))}</div>

                <div>{row["start_date"].strftime("%d/%m/%Y")}</div>

                <div>{row["end_date"].strftime("%d/%m/%Y")}</div>

                <div>{int(row["progress"])}%</div>

                <div class="task-status">
                    <span class="status-pill" style="background:{color};">
                        {escape(str(row["timeline_status"]))}
                    </span>
                </div>

                <div></div>

            </div>

            <div class="timeline-cell">
                <div class="bar"
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
        <style>
        .gantt-wrapper {
            border: 1px solid #d1d5db;
            border-radius: 6px;
            overflow: auto;
            background: #ffffff;
        }

        /* HEADER */
        .gantt-header {
            display: grid;
            grid-template-columns: 740px 1fr;   /* 👈 más compacto */
            background: #e5e7eb;                /* 👈 más contraste */
        }

        .table-header {
            display: grid;
            grid-template-columns: 220px 120px 90px 90px 65px 105px 70px;
            font-weight: bold;
            font-size: 13px;
        }

        .table-header div {
            padding: 8px;
            border-right: 1px solid #ccc;
        }

        /* FILAS */
        .gantt-row {
            display: grid;
            grid-template-columns: 740px 1fr;
            min-height: 34px;                  /* 👈 más compacto */
            align-items: center;
            border-bottom: 1px solid #e5e7eb;
        }

        /* zebra */
        .gantt-row:nth-child(even) {
            background: #fafafa;
        }

        /* TABLA */
        .task-table {
            display: grid;
            grid-template-columns: 220px 120px 90px 90px 65px 105px 70px;
            font-size: 12px;
        }

        .task-table > div {
            padding: 5px 8px;
            border-right: 1px solid #eee;
        }

        /* TIMELINE HEADER */
        .timeline-header {
            position: relative;
            height: 34px;

            /* 👇 ESTO ES LO QUE TE FALTABA (grid vertical) */
            background: repeating-linear-gradient(
                to right,
                #ffffff 0px,
                #ffffff 79px,
                #e5e7eb 80px
            );
        }

        /* MESES */
        .month-header {
            position: absolute;
            height: 34px;
            text-align: center;
            font-size: 12px;
            font-weight: bold;
            border-right: 1px solid #ccc;
        }

        /* TIMELINE CELDA */
        .timeline-cell {
            position: relative;
            height: 34px;

            background: repeating-linear-gradient(
                to right,
                #ffffff 0px,
                #ffffff 79px,
                #f3f4f6 80px
            );
        }

        /* BARRAS */
        .bar {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            height: 16px;                     /* 👈 más fino */
            border-radius: 4px;

            box-shadow: 0 1px 2px rgba(0,0,0,0.25);  /* 👈 profundidad */
        }

        .tree-icon {
            display: inline-block;
            width: 16px;
            color: #666;
        }

        .task-name {
            color: #111;
        }

        .status-pill {
            color: white;
            border-radius: 999px;
            padding: 3px 8px;
            font-size: 11px;
            font-weight: bold;
        }

        .bar-progress {
            height: 100%;
            background: rgba(255,255,255,0.35);
        }

        
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