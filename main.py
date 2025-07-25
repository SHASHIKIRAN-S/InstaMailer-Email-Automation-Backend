# backend/main.py
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Body
from .sqlmodel import SQLModel, Session, create_engine, select
from .models import Draft
from .email_generator import EmailGenerator
from .mailer import send_email
from .config import get_settings
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from datetime import datetime, timedelta, timezone
from collections import Counter
from typing import List, Dict, Any, Optional
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the backend directory path
backend_dir = os.path.dirname(os.path.abspath(__file__))
database_path = os.path.join(backend_dir, "database.db")
engine = create_engine(f"sqlite:///{database_path}")

def ensure_aware(dt):
    if dt is None:
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    masked_key = settings.email_api_key[:10] + "..." if settings.email_api_key else "MISSING"
    logger.info(f"Email API loaded: {masked_key}")
    SQLModel.metadata.create_all(engine)
    print("Loaded API key:", settings.email_api_key[:8] + "...")
    yield

app = FastAPI(lifespan=lifespan)

email_generator = EmailGenerator()

# Allow frontend origins
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5137",
    "http://127.0.0.1:5137",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GenerateRequest(BaseModel):
    prompt: str
    recipient: str
    tone: str = "friendly"
    type: str = "general"

class EmailDraftResponse(BaseModel):
    id: int
    prompt: str
    content: str
    recipient: str
    tone: str
    status: str
    type: str
    created_at: datetime
    sent_at: Optional[datetime] = None
    subject: Optional[str] = None

@app.post("/generate")
async def generate(
    prompt: str = Form(...),
    recipient: str = Form(...),
    tone: str = Form("friendly"),
    type: str = Form("general")
):
    try:
        email_data = email_generator.generate_email_with_subject(prompt, tone)
        draft = Draft(
            prompt=prompt,
            content=email_data["content"],
            recipient=recipient,
            tone=tone,
            type=type,
            subject=email_data.get("subject")
        )
        with Session(engine) as session:
            session.add(draft)
            session.commit()
            session.refresh(draft)
        return {
            "content": email_data["content"],
            "subject": email_data["subject"],
            "draft_id": draft.id
        }
    except Exception as e:
        logger.error(f"Error generating email: {e}")
        raise HTTPException(status_code=500, detail="Error generating email")

@app.post("/send/{draft_id}")
def send(draft_id: int):
    try:
        with Session(engine) as session:
            draft = session.get(Draft, draft_id)
            if not draft:
                raise HTTPException(status_code=404, detail="Draft not found")

            subject = draft.subject or draft.content.split('\n')[0][:50] if draft.content else "Email"

            success = send_email(
                to_email=draft.recipient,
                subject=subject,
                content=draft.content
            )

            if success:
                # Update draft status to sent
                draft.status = "sent"
                draft.sent_at = datetime.now(timezone.utc)
                session.commit()
                return {"status": "sent", "message": "Email sent successfully"}
            else:
                draft.status = "failed"
                session.commit()
                raise HTTPException(status_code=500, detail="Failed to send email")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/emails", response_model=List[EmailDraftResponse])
def get_emails():
    """Get all email drafts"""
    try:
        with Session(engine) as session:
            statement = select(Draft).order_by(Draft.created_at.desc())
            drafts = session.exec(statement).all()
            return drafts
    except Exception as e:
        logger.error(f"Error fetching emails: {e}")
        raise HTTPException(status_code=500, detail="Error fetching emails")

@app.get("/stats")
def get_stats():
    """Get email statistics"""
    try:
        with Session(engine) as session:
            # Get all drafts
            statement = select(Draft)
            drafts = session.exec(statement).all()
            
            # Calculate stats
            total_sent = len([d for d in drafts if d.status == "sent"])
            total_drafts = len([d for d in drafts if d.status == "draft"])
            total_failed = len([d for d in drafts if d.status == "failed"])
            total_emails = len(drafts)
            
            success_rate = (total_sent / total_emails * 100) if total_emails > 0 else 0
            
            # Recent activity (last 7 days)
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            recent_activity = len([d for d in drafts if ensure_aware(d.created_at) >= week_ago])
            
            # Popular tones
            tone_counter = Counter(d.tone for d in drafts)
            popular_tones = dict(tone_counter.most_common())
            
            # Monthly stats (last 6 months)
            monthly_stats = []
            for i in range(6):
                month_start = datetime.now(timezone.utc).replace(day=1) - timedelta(days=30*i)
                month_end = month_start.replace(day=1) + timedelta(days=32)
                month_end = month_end.replace(day=1) - timedelta(days=1)
                
                month_drafts = [d for d in drafts if month_start <= ensure_aware(d.created_at) <= month_end]
                month_sent = len([d for d in month_drafts if d.status == "sent"])
                month_draft_count = len([d for d in month_drafts if d.status == "draft"])
                
                monthly_stats.append({
                    "month": month_start.strftime("%b"),
                    "sent": month_sent,
                    "drafts": month_draft_count
                })
            
            monthly_stats.reverse()  # Show oldest to newest
            
            return {
                "total_sent": total_sent,
                "total_drafts": total_drafts,
                "total_failed": total_failed,
                "success_rate": round(success_rate, 1),
                "recent_activity": recent_activity,
                "popular_tones": popular_tones,
                "monthly_stats": monthly_stats
            }
            
    except Exception as e:
        logger.error(f"Error calculating stats: {e}")
        raise HTTPException(status_code=500, detail="Error calculating stats")

@app.delete("/emails/{draft_id}")
def delete_email(draft_id: int):
    """Delete an email draft"""
    try:
        with Session(engine) as session:
            draft = session.get(Draft, draft_id)
            if not draft:
                raise HTTPException(status_code=404, detail="Draft not found")
            
            session.delete(draft)
            session.commit()
            return {"message": "Email deleted successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting email: {e}")
        raise HTTPException(status_code=500, detail="Error deleting email")

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.post("/update_draft/{draft_id}")
def update_draft(draft_id: int, content: str = Body(...)):
    with Session(engine) as session:
        draft = session.get(Draft, draft_id)
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")
        draft.content = content
        session.commit()
        return {"message": "Draft updated"}
