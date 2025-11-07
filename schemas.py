"""
Database Schemas for PeerBazaar (Glitch Hub)

Each Pydantic model maps to a MongoDB collection named after the lowercase class name.
Example: Student -> "student", Listing -> "listing"
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List

class Student(BaseModel):
    """Student profiles (collection: student)"""
    name: str = Field(..., min_length=2, max_length=80, description="Full name")
    email: str = Field(..., description="Must be an @satiengg.in email")
    bio: Optional[str] = Field(None, max_length=280, description="Short intro")
    avatar_url: Optional[HttpUrl] = Field(None, description="Profile avatar URL")
    branch: Optional[str] = Field(None, description="Academic branch")
    year: Optional[int] = Field(None, ge=1, le=6, description="Academic year (1-6)")
    phone: Optional[str] = Field(None, description="Contact number")
    is_active: bool = Field(True, description="Active account flag")

class Listing(BaseModel):
    """Marketplace listings (collection: listing)"""
    title: str = Field(..., min_length=3, max_length=120, description="Listing title")
    description: Optional[str] = Field(None, max_length=2000, description="Details about the item")
    price: float = Field(..., ge=0, description="Price in INR")
    category: str = Field(..., description="Category e.g. Books, Electronics")
    location: str = Field(..., max_length=120, description="Meetup location on campus")
    images: List[HttpUrl] = Field(default_factory=list, description="Image URLs")
    seller_email: str = Field(..., description="Owner email (must be @satiengg.in)")
    status: str = Field("active", description="active | sold | hidden")
