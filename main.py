import os
import json
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from orchestrator import tasks, start_analysis_task, OLLAMA_MODEL

app = FastAPI(title="M&A Target Discovery and Synergy Evaluation System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    os.makedirs("projects", exist_ok=True)
    for filename in os.listdir("projects"):
        if filename.endswith(".json"):
            filepath = os.path.join("projects", filename)
            try:
                with open(filepath, "r") as f:
                    task_data = json.load(f)
                    task_id = task_data.get("task_id")
                    if task_id:
                        tasks[task_id] = task_data
            except Exception as e:
                print(f"Failed to load project {filename}: {e}")


class AnalyzeRequest(BaseModel):
    acquirer: str
    industry_focus: Optional[str] = None
    geography_preference: Optional[str] = None
    revenue_range: Optional[str] = None
    acquisition_budget: Optional[str] = None
    strategic_goals: Optional[str] = None
    technology_areas: Optional[str] = None
    risk_appetite: Optional[str] = None
    time_horizon: Optional[str] = None
    model: Optional[str] = None   # Ollama model override
    simulate: bool = False


@app.post("/api/analyze")
def analyze(payload: AnalyzeRequest):
    if not payload.acquirer.strip():
        raise HTTPException(status_code=400, detail="Acquiring company name is required.")

    inputs = {
        "industry_focus": payload.industry_focus,
        "geography_preference": payload.geography_preference,
        "revenue_range": payload.revenue_range,
        "acquisition_budget": payload.acquisition_budget,
        "strategic_goals": payload.strategic_goals,
        "technology_areas": payload.technology_areas,
        "risk_appetite": payload.risk_appetite,
        "time_horizon": payload.time_horizon,
    }

    task_id = start_analysis_task(
        acquirer=payload.acquirer,
        inputs=inputs,
        model=payload.model,
        simulate=payload.simulate,
    )

    return {"task_id": task_id, "message": "Analysis started successfully."}


@app.get("/api/projects")
def get_projects():
    project_list = [
        {
            "task_id": tid,
            "acquirer": t.get("acquirer"),
            "status": t.get("status"),
            "progress": t.get("progress"),
            "created_at": t.get("created_at"),
            "model": t.get("model", OLLAMA_MODEL),
            "simulate": t.get("simulate", False),
        }
        for tid, t in tasks.items()
    ]
    project_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return project_list


@app.get("/api/status/{task_id}")
def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task ID not found.")
    t = tasks[task_id]
    return {
        "task_id": task_id,
        "acquirer": t.get("acquirer"),
        "status": t.get("status"),
        "current_agent": t.get("current_agent"),
        "progress": t.get("progress"),
        "logs": t.get("logs", []),
        "created_at": t.get("created_at"),
        "model": t.get("model", OLLAMA_MODEL),
        "simulate": t.get("simulate", False),
    }


@app.get("/api/report/{task_id}")
def get_report(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task ID not found.")
    t = tasks[task_id]
    if t.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail="Report not ready. Status: " + t.get("status"),
        )
    return t.get("results")


@app.delete("/api/projects/{task_id}")
def delete_project(task_id: str):
    if task_id in tasks:
        del tasks[task_id]
    filepath = os.path.join("projects", f"{task_id}.json")
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete: {e}")
    return {"message": "Project deleted successfully."}


os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def get_index():
    index_path = os.path.join("static", "index.html")
    if not os.path.exists(index_path):
        return {"message": "FastAPI running. Static assets not found."}
    return FileResponse(index_path)
