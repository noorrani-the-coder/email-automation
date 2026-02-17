import sys
from pathlib import Path
import threading
import time
from typing import List, Optional
from datetime import datetime, timezone
import json

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from sqlalchemy import desc

from email_agent import app as agent_app
from db.session import get_session, init_db
from db.models import EmailMemory, BehaviorLog, RetryQueue, User, UserCredentials
from api.auth import (
    hash_password,
    verify_password,
    create_jwt_token,
    extract_user_from_token,
)
from gmail.auth import store_credentials_for_user

app = FastAPI(title="Email Agent API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    gmail_email: str  # Gmail account email address


class SignupResponse(BaseModel):
    message: str
    user_id: int
    token: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    message: str
    token: str
    user_id: int
    gmail_email: str


class CredentialsUploadRequest(BaseModel):
    credentials_json: str  # JSON string of credentials.json


class CredentialsUploadResponse(BaseModel):
    message: str
    success: bool


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


# Dependency: Extract and validate JWT token
def get_current_user(authorization: Optional[str] = Header(None)):
    """Extract user from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format")
    
    token = parts[1]
    user_info = extract_user_from_token(token)
    
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user_info  # Returns {"user_id": int, "email": str}


@app.on_event("startup")
def startup_event():
    init_db()


# ============== AUTHENTICATION ENDPOINTS ==============

@app.post("/auth/signup", response_model=SignupResponse)
def signup(req: SignupRequest):
    """Register a new user."""
    session = get_session()
    try:
        # Check if email already exists
        existing_user = session.query(User).filter_by(email=req.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create new user
        now = datetime.now(tz=timezone.utc).isoformat()
        user = User(
            email=req.email,
            password_hash=hash_password(req.password),
            gmail_email=req.gmail_email,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(user)
        session.flush()  # Get the user ID
        user_id = user.id
        
        # Create JWT token
        token = create_jwt_token(user_id, req.email)
        
        session.commit()
        return SignupResponse(
            message="User registered successfully. Please upload your credentials.",
            user_id=user_id,
            token=token,
        )
    except Exception as e:
        session.rollback()
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@app.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    """Login user."""
    session = get_session()
    try:
        user = session.query(User).filter_by(email=req.email).first()
        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        if not user.is_active:
            raise HTTPException(status_code=403, detail="User account is inactive")
        
        # Create JWT token
        token = create_jwt_token(user.id, user.email)
        
        return LoginResponse(
            message="Login successful",
            token=token,
            user_id=user.id,
            gmail_email=user.gmail_email,
        )
    finally:
        session.close()


@app.post("/auth/upload-credentials", response_model=CredentialsUploadResponse)
def upload_credentials(
    req: CredentialsUploadRequest,
    current_user: dict = Depends(get_current_user),
):
    """Upload Gmail credentials (credentials.json content)."""
    try:
        user_id = current_user["user_id"]
        
        # Validate JSON
        try:
            creds_data = json.loads(req.credentials_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in credentials_json")
        
        # Store credentials
        success = store_credentials_for_user(
            user_id=user_id,
            credentials_json=req.credentials_json,
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to store credentials")
        
        return CredentialsUploadResponse(
            message="Credentials uploaded successfully",
            success=True,
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))


# ============== CONTROL ENDPOINTS ==============

@app.get("/control/status", response_model=AgentStatus)
def get_status(current_user: dict = Depends(get_current_user)):
    """Get agent status."""
    return AgentStatus(
        is_running=agent_app.is_running,
        uptime=time.time() - START_TIME if agent_app.is_running else 0,
    )


@app.post("/control/start")
def start_agent(current_user: dict = Depends(get_current_user)):
    """Start the agent for current user."""
    user_id = current_user["user_id"]
    if agent_app.is_running:
        return {"message": "Agent is already running"}
    
    # TODO: Start per-user agent instance
    agent_app.start_agent()
    return {"message": f"Agent started for user {user_id}"}


@app.post("/control/stop")
def stop_agent(current_user: dict = Depends(get_current_user)):
    """Stop the agent for current user."""
    user_id = current_user["user_id"]
    if not agent_app.is_running:
        return {"message": "Agent is not running"}
    
    # TODO: Stop per-user agent instance
    agent_app.stop_agent()
    return {"message": f"Agent stop signal sent for user {user_id}"}


# ============== DATA ENDPOINTS ==============

@app.get("/emails", response_model=List[EmailSchema])
def get_emails(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """Get emails for current user."""
    user_id = current_user["user_id"]
    session = get_session()
    try:
        emails = (
            session.query(EmailMemory)
            .filter_by(user_id=user_id)
            .order_by(EmailMemory.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
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
                task_status=e.task_status,
            )
            for e in emails
        ]
    finally:
        session.close()


@app.get("/logs")
def get_logs(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """Get behavior logs for current user."""
    user_id = current_user["user_id"]
    session = get_session()
    try:
        logs = (
            session.query(BehaviorLog)
            .filter_by(user_id=user_id)
            .order_by(BehaviorLog.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": l.id,
                "email_id": l.email_id,
                "intent": l.intent,
                "proposed_action": l.proposed_action,
                "agent_action": l.agent_action,
                "created_at": l.created_at,
            }
            for l in logs
        ]
    finally:
        session.close()


@app.get("/stats")
def get_stats(current_user: dict = Depends(get_current_user)):
    """Get statistics for current user."""
    user_id = current_user["user_id"]
    session = get_session()
    try:
        total_emails = session.query(EmailMemory).filter_by(user_id=user_id).count()
        total_logs = session.query(BehaviorLog).filter_by(user_id=user_id).count()
        pending_retries = (
            session.query(RetryQueue)
            .filter_by(user_id=user_id, status="pending")
            .count()
        )
        return {
            "total_emails": total_emails,
            "total_actions": total_logs,
            "pending_retries": pending_retries,
        }
    finally:
        session.close()


# Mount frontend
try:
    app.mount("/", StaticFiles(directory="web", html=True), name="static")
except Exception as e:
    print(f"Warning: Could not mount static files: {e}")
