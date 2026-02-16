import sys
from pathlib import Path
import threading
import time
from typing import List, Optional

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import desc

from email_agent import app as agent_app
from db.session import get_session, init_db
from db.models import EmailMemory, BehaviorLog, RetryQueue

app = FastAPI(title="Email Agent API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class AgentStatus(BaseModel):
    is_running: bool
    uptime: float

class EmailSchema(BaseModel):
    id: int
    email_id: str
    sender: str
    subject: str
    timestamp: str
    priority_score: int
    priority_label: str
    next_action: str
    task_status: str

class LogSchema(BaseModel):
    id: int
    email_id: str
    intent: str
    agent_action: str
    timestamp: str

# Global state
START_TIME = time.time()


@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/control/status")
def get_status():
    return {
        "is_running": agent_app.is_running,
        "uptime": time.time() - START_TIME if agent_app.is_running else 0
    }

@app.post("/control/start")
def start_agent():
    if agent_app.is_running:
        return {"message": "Agent is already running"}
    
    agent_app.start_agent()
    return {"message": "Agent started"}

@app.post("/control/stop")
def stop_agent():
    if not agent_app.is_running:
        return {"message": "Agent is not running"}
    
    agent_app.stop_agent()
    return {"message": "Agent stop signal sent"}

@app.get("/emails", response_model=List[EmailSchema])
def get_emails(limit: int = 50, offset: int = 0):
    session = get_session()
    try:
        emails = session.query(EmailMemory).order_by(desc(EmailMemory.id)).offset(offset).limit(limit).all()
        return [
            EmailSchema(
                id=e.id,
                email_id=e.email_id,
                sender=e.sender,
                subject=e.subject,
                timestamp=e.timestamp,
                priority_score=e.priority_score,
                priority_label=e.priority_label,
                next_action=e.next_action,
                task_status=e.task_status
            ) for e in emails
        ]
    finally:
        session.close()

@app.get("/logs")
def get_logs(limit: int = 50, offset: int = 0):
    session = get_session()
    try:
        logs = session.query(BehaviorLog).order_by(desc(BehaviorLog.id)).offset(offset).limit(limit).all()
        return [
            {
                "id": l.id,
                "email_id": l.email_id,
                "intent": l.intent,
                "proposed_action": l.proposed_action,
                "agent_action": l.agent_action,
                "created_at": l.created_at
            } for l in logs
        ]
    finally:
        session.close()

@app.get("/stats")
def get_stats():
    session = get_session()
    try:
        total_emails = session.query(EmailMemory).count()
        total_logs = session.query(BehaviorLog).count()
        pending_retries = session.query(RetryQueue).filter_by(status="pending").count()
        return {
            "total_emails": total_emails,
            "total_actions": total_logs,
            "pending_retries": pending_retries
        }
    finally:
        session.close()

# Mount frontend
app.mount("/", StaticFiles(directory="web", html=True), name="static")
