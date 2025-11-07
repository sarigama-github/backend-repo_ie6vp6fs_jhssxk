import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from schemas import Student, Listing, OTPRequest, OTPVerify, OTPRecord
from database import db, create_document, get_documents
from datetime import datetime, timezone
import random
import requests

EMAIL_DOMAIN = "satiengg.in"
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM = os.getenv("RESEND_FROM", f"PeerBazaar <no-reply@{EMAIL_DOMAIN}>")

app = FastAPI(title="PeerBazaar API", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AuthRequest(BaseModel):
    email: EmailStr
    name: str

class AuthResponse(BaseModel):
    email: EmailStr
    name: str
    allowed: bool
    reason: Optional[str] = None

@app.get("/")
async def root():
    return {"service": "PeerBazaar Backend", "team": "Glitch Hub"}

@app.get("/test")
def test_database():
    """Test endpoint to verify DB connectivity and envs"""
    response = {
        "backend": "running",
        "database": "not_connected",
        "database_url": bool(os.getenv("DATABASE_URL")),
        "database_name": bool(os.getenv("DATABASE_NAME")),
        "collections": [],
        "email_delivery": bool(RESEND_API_KEY),
    }
    try:
        if db is not None:
            response["database"] = "connected"
            response["collections"] = db.list_collection_names()[:10]
    except Exception as e:
        response["database"] = f"error: {str(e)[:80]}"
    return response

@app.post("/auth/validate", response_model=AuthResponse)
async def validate_email(payload: AuthRequest):
    email = payload.email.lower().strip()
    if not email.endswith(f"@{EMAIL_DOMAIN}"):
        return AuthResponse(email=email, name=payload.name, allowed=False, reason=f"Only @{EMAIL_DOMAIN} allowed")
    return AuthResponse(email=email, name=payload.name, allowed=True)

# --- OTP Email Verification Flow ---

def _generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


def _send_email(to_email: str, code: str, name: str) -> bool:
    """Send OTP using Resend if configured. Returns True if attempted successfully."""
    if not RESEND_API_KEY:
        return False
    try:
        subject = "Your PeerBazaar verification code"
        text = f"Hi {name or to_email},\n\nYour verification code is: {code}\nIt expires in 10 minutes.\n\nIf you didn't request this, you can ignore this email.\n\n— PeerBazaar"
        html = f"""
        <div style='font-family:Inter,Segoe UI,Arial,sans-serif;font-size:14px;color:#0f172a;'>
          <p>Hi {name or to_email},</p>
          <p>Your verification code is:</p>
          <p style='font-size:24px;font-weight:700;letter-spacing:4px;margin:16px 0;'>
            {code}
          </p>
          <p>This code expires in 10 minutes.</p>
          <p>If you didn't request this, you can ignore this email.</p>
          <p style='color:#64748b;'>— PeerBazaar</p>
        </div>
        """
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM,
                "to": [to_email],
                "subject": subject,
                "text": text,
                "html": html,
            },
            timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False


@app.post("/auth/otp/request")
async def request_otp(payload: OTPRequest):
    email = payload.email.lower().strip()
    if not email.endswith(f"@{EMAIL_DOMAIN}"):
        raise HTTPException(status_code=400, detail=f"Only @{EMAIL_DOMAIN} emails allowed")
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Invalidate any previous OTPs for this email
    db["otp"].delete_many({"email": email})

    code = _generate_code()
    record = OTPRecord.new(email=email, code=code)
    create_document("otp", record)

    delivered = _send_email(to_email=email, code=code, name=payload.name)

    # In development/sandbox we also return the code if email not configured
    response = {"sent": True, "email": email}
    if not delivered:
        response["dev_code"] = code
        response["delivery"] = "dev"
    else:
        response["delivery"] = "email"
    return response

@app.post("/auth/otp/verify", response_model=AuthResponse)
async def verify_otp(payload: OTPVerify):
    email = payload.email.lower().strip()
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    rec = db["otp"].find_one({"email": email, "code": payload.code, "consumed": False})
    if not rec:
        raise HTTPException(status_code=400, detail="Invalid code")

    expires_at = rec.get("expires_at")
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except Exception:
            pass
    if expires_at and datetime.now(timezone.utc) > expires_at:
        db["otp"].update_one({"_id": rec["_id"]}, {"$set": {"consumed": True, "updated_at": datetime.now(timezone.utc)}})
        raise HTTPException(status_code=400, detail="Code expired")

    db["otp"].update_one({"_id": rec["_id"]}, {"$set": {"consumed": True, "updated_at": datetime.now(timezone.utc)}})

    allowed = email.endswith(f"@{EMAIL_DOMAIN}")
    return AuthResponse(email=email, name=email.split("@")[0], allowed=allowed, reason=(None if allowed else f"Only @{EMAIL_DOMAIN} allowed"))

@app.post("/students", status_code=201)
async def create_student(student: Student):
    email = student.email.lower().strip()
    if not email.endswith(f"@{EMAIL_DOMAIN}"):
        raise HTTPException(status_code=400, detail=f"Only @{EMAIL_DOMAIN} emails allowed")
    _id = create_document("student", student)
    return {"id": _id}

@app.get("/students")
async def list_students(limit: int = 20):
    docs = get_documents("student", {}, limit)
    for d in docs:
        d["_id"] = str(d.get("_id"))
    return docs

@app.post("/listings", status_code=201)
async def create_listing(listing: Listing):
    email = listing.seller_email.lower().strip()
    if not email.endswith(f"@{EMAIL_DOMAIN}"):
        raise HTTPException(status_code=400, detail=f"Only @{EMAIL_DOMAIN} sellers allowed")
    _id = create_document("listing", listing)
    return {"id": _id}

@app.get("/listings")
async def get_listings(category: Optional[str] = None, limit: int = 24):
    filt = {"status": "active"}
    if category:
        filt["category"] = category
    docs = get_documents("listing", filt, limit)
    for d in docs:
        d["_id"] = str(d.get("_id"))
    return docs

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
