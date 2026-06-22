import os
import sys
import json

# Force UTF-8 output on Windows to avoid charmap encode errors in logs
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from typing import Optional, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from orchestrator import tasks, start_analysis_task, start_discovery_task, OLLAMA_MODEL

app = FastAPI(title="Accenture V&A Company Intelligence Platform")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup_event():
    os.makedirs("projects", exist_ok=True)
    for fn in os.listdir("projects"):
        if fn.endswith(".json"):
            try:
                with open(os.path.join("projects", fn)) as f:
                    d = json.load(f)
                    if d.get("task_id"):
                        tasks[d["task_id"]] = d
            except Exception as e:
                print(f"Load failed for {fn}: {e}")


class ProfileRequest(BaseModel):
    company: str
    model: Optional[str] = None
    simulate: bool = False


class DiscoveryRequest(BaseModel):
    acquirer: str
    sector: Optional[str] = None
    geography: Optional[str] = None
    capability_gap: Optional[str] = None
    revenue_range: Optional[str] = None
    model: Optional[str] = None
    simulate: bool = False


@app.post("/api/analyze")
def analyze(payload: ProfileRequest):
    if not payload.company.strip():
        raise HTTPException(400, "Company name or URL is required.")
    task_id = start_analysis_task(
        company=payload.company, model=payload.model, simulate=payload.simulate,
    )
    return {"task_id": task_id}


@app.post("/api/discover")
def discover(payload: DiscoveryRequest):
    if not payload.acquirer.strip():
        raise HTTPException(400, "Acquirer name is required.")
    thesis = {
        "sector":          payload.sector or "",
        "geography":       payload.geography or "",
        "capability_gap":  payload.capability_gap or "",
        "revenue_range":   payload.revenue_range or "$50M–$500M",
    }
    task_id = start_discovery_task(
        acquirer=payload.acquirer, thesis=thesis, model=payload.model, simulate=payload.simulate,
    )
    return {"task_id": task_id}


@app.get("/api/projects")
def get_projects():
    pl = [
        {"task_id": tid, "company": t.get("company"), "mode": t.get("mode", "profile"),
         "status": t.get("status"), "progress": t.get("progress"),
         "created_at": t.get("created_at"), "model": t.get("model", OLLAMA_MODEL), "simulate": t.get("simulate", False)}
        for tid, t in tasks.items()
    ]
    pl.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return pl


@app.get("/api/status/{task_id}")
def get_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(404, "Task not found.")
    t = tasks[task_id]
    return {
        "task_id": task_id, "company": t.get("company"), "mode": t.get("mode", "profile"),
        "status": t.get("status"), "current_agent": t.get("current_agent"),
        "progress": t.get("progress"), "logs": t.get("logs", []),
        "created_at": t.get("created_at"), "model": t.get("model", OLLAMA_MODEL),
        "simulate": t.get("simulate", False),
    }


@app.get("/api/report/{task_id}")
def get_report(task_id: str):
    if task_id not in tasks:
        raise HTTPException(404, "Task not found.")
    t = tasks[task_id]
    if t.get("status") != "completed":
        raise HTTPException(400, f"Report not ready. Status: {t.get('status')}")
    return t.get("results")


@app.delete("/api/projects/{task_id}")
def delete_project(task_id: str):
    tasks.pop(task_id, None)
    fp = os.path.join("projects", f"{task_id}.json")
    if os.path.exists(fp):
        try:
            os.remove(fp)
        except Exception as e:
            raise HTTPException(500, str(e))
    return {"message": "Deleted."}


os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    p = os.path.join("static", "index.html")
    return FileResponse(p) if os.path.exists(p) else {"message": "Static assets not found."}
