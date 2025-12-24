from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field

# User schemas
class UserCreate(BaseModel):
    """Schema for user registration."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (min 8 characters)")
    full_name: str = Field(..., min_length=1, description="User full name")

class UserLogin(BaseModel):
    """Schema for user login."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

class User(BaseModel):
    """Schema for user response."""
    id: int = Field(..., description="User ID")
    email: str = Field(..., description="User email address")
    full_name: str = Field(..., description="User full name")
    created_at: datetime = Field(..., description="User creation timestamp")
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    """Schema for authentication token."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    user: User = Field(..., description="User information")

# Resume schemas
class ResumeUpload(BaseModel):
    """Schema for resume upload response."""
    id: int = Field(..., description="Resume ID")
    filename: str = Field(..., description="Original filename")
    file_path: str = Field(..., description="Stored file path")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    status: str = Field(default="uploaded", description="Processing status")

class Resume(BaseModel):
    """Schema for resume information."""
    id: int = Field(..., description="Resume ID")
    filename: str = Field(..., description="Original filename")
    uploaded_at: datetime = Field(..., description="Upload timestamp")
    status: str = Field(..., description="Processing status")
    user_id: int = Field(..., description="Owner user ID")
    
    class Config:
        from_attributes = True

# Analysis schemas
class AnalysisCreate(BaseModel):
    """Schema for triggering analysis."""
    resume_id: int = Field(..., description="Resume ID to analyze")

class AnalysisResult(BaseModel):
    """Schema for analysis results."""
    id: int = Field(..., description="Analysis ID")
    resume_id: int = Field(..., description="Analyzed resume ID")
    overall_score: float = Field(..., ge=0, le=100, description="Overall score (0-100)")
    strengths: List[str] = Field(..., description="List of identified strengths")
    weaknesses: List[str] = Field(..., description="List of identified weaknesses")
    recommendations: List[str] = Field(..., description="List of improvement recommendations")
    industry_benchmark: Optional[float] = Field(None, ge=0, le=100, description="Industry benchmark score")
    analyzed_at: datetime = Field(..., description="Analysis timestamp")
    
    class Config:
        from_attributes = True

class FeedbackSummary(BaseModel):
    """Schema for feedback summary."""
    total_resumes: int = Field(..., description="Total resumes uploaded")
    avg_score: Optional[float] = Field(None, description="Average score across all resumes")
    latest_analysis: Optional[AnalysisResult] = Field(None, description="Latest analysis result")
    improvement_trend: str = Field(..., description="Trend description (improving/declining/stable)")

# Response schemas
class SuccessResponse(BaseModel):
    """Schema for success response."""
    success: bool = Field(True, description="Operation success status")
    message: str = Field(..., description="Success message")
    data: Optional[dict] = Field(None, description="Additional response data")

class ErrorResponse(BaseModel):
    """Schema for error response."""
    success: bool = Field(False, description="Operation success status")
    error: str = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Additional error details")
