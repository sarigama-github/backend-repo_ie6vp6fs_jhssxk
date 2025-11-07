import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from schemas import Student, Listing
from database import db, create_document, get_documents

EMAIL_DOMAIN = "satiengg.in"

app = FastAPI(title="PeerBazaar API", version="1.0.0")

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
