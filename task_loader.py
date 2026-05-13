import json
from pathlib import Path
from datetime import date
import pandas as pd


def load_tasks(json_path: str | Path) -> dict:
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {json_path}")

    with open(json_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if "projects" not in data:
        raise ValueError("El JSON debe contener la clave raíz 'projects'.")

    return data


def save_tasks(data: dict, json_path: str | Path) -> None:
    json_path = Path(json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    with open(json_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def get_timeline_status(row: pd.Series) -> str:
    today = pd.Timestamp(date.today())
    end_date = pd.to_datetime(row["end_date"])
    progress = float(row.get("progress", 0))

    if progress >= 100 or row.get("status") == "Completado":
        return "Completado"

    if end_date < today:
        return "Vencido"

    days_left = (end_date - today).days
    if days_left <= 7 and progress < 80:
        return "En riesgo"

    return "En plazo"


def flatten_tasks(data: dict) -> pd.DataFrame:
    rows = []

    for project in data.get("projects", []):
        rows.append({
            "level": "Proyecto",
            "level_order": 0,
            "project_id": project["project_id"],
            "project_name": project["project_name"],
            "item_id": project["project_id"],
            "item_name": project["project_name"],
            "parent_id": "",
            "responsible": project.get("owner", ""),
            "start_date": project["start_date"],
            "end_date": project["end_date"],
            "progress": project.get("progress", 0),
            "status": project.get("status", "En curso"),
            "document_url": project.get("document_url", "")
        })

        for task in project.get("tasks", []):
            rows.append({
                "level": "Tarea",
                "level_order": 1,
                "project_id": project["project_id"],
                "project_name": project["project_name"],
                "item_id": task["task_id"],
                "item_name": task["task_name"],
                "parent_id": project["project_id"],
                "responsible": task.get("responsible", ""),
                "start_date": task["start_date"],
                "end_date": task["end_date"],
                "progress": task.get("progress", 0),
                "status": task.get("status", "No iniciado"),
                "document_url": task.get("document_url", "")
            })

            for subtask in task.get("subtasks", []):
                rows.append({
                    "level": "Subtarea",
                    "level_order": 2,
                    "project_id": project["project_id"],
                    "project_name": project["project_name"],
                    "item_id": subtask["subtask_id"],
                    "item_name": subtask["subtask_name"],
                    "parent_id": task["task_id"],
                    "responsible": subtask.get("responsible", ""),
                    "start_date": subtask["start_date"],
                    "end_date": subtask["end_date"],
                    "progress": subtask.get("progress", 0),
                    "status": subtask.get("status", "No iniciado"),
                    "document_url": subtask.get("document_url", "")
                })

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])
    df["progress"] = pd.to_numeric(df["progress"], errors="coerce").fillna(0).clip(0, 100)
    df["timeline_status"] = df.apply(get_timeline_status, axis=1)

    return df


def dataframe_to_nested_json(df: pd.DataFrame) -> dict:
    df = df.copy()
    df["start_date"] = pd.to_datetime(df["start_date"]).dt.strftime("%Y-%m-%d")
    df["end_date"] = pd.to_datetime(df["end_date"]).dt.strftime("%Y-%m-%d")

    projects = []
    project_rows = df[df["level"] == "Proyecto"]

    for _, p in project_rows.iterrows():
        project = {
            "project_id": p["item_id"],
            "project_name": p["item_name"],
            "owner": p["responsible"],
            "status": p["status"],
            "start_date": p["start_date"],
            "end_date": p["end_date"],
            "progress": int(p["progress"]),
            "document_url": p.get("document_url", ""),
            "tasks": []
        }

        task_rows = df[
            (df["level"] == "Tarea") &
            (df["project_id"] == p["project_id"]) &
            (df["parent_id"] == p["item_id"])
        ]

        for _, t in task_rows.iterrows():
            task = {
                "task_id": t["item_id"],
                "task_name": t["item_name"],
                "responsible": t["responsible"],
                "start_date": t["start_date"],
                "end_date": t["end_date"],
                "progress": int(t["progress"]),
                "status": t["status"],
                "document_url": t.get("document_url", ""),
                "subtasks": []
            }

            subtask_rows = df[
                (df["level"] == "Subtarea") &
                (df["project_id"] == p["project_id"]) &
                (df["parent_id"] == t["item_id"])
            ]

            for _, s in subtask_rows.iterrows():
                task["subtasks"].append({
                    "subtask_id": s["item_id"],
                    "subtask_name": s["item_name"],
                    "responsible": s["responsible"],
                    "start_date": s["start_date"],
                    "end_date": s["end_date"],
                    "progress": int(s["progress"]),
                    "status": s["status"],
                    "document_url": s.get("document_url", "")
                })

            project["tasks"].append(task)

        projects.append(project)

    return {"projects": projects}
