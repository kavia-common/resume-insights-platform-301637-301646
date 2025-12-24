from datetime import timedelta
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.database import get_db, engine
from src import models, schemas, auth, file_utils
from src.ai_service import ai_service

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="Resume Insights Platform API",
    description="Backend API for AI-driven resume analysis and feedback platform",
    version="1.0.0",
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User registration and authentication endpoints"
        },
        {
            "name": "Resumes",
            "description": "Resume upload and management endpoints"
        },
        {
            "name": "Analysis",
            "description": "AI analysis and feedback endpoints"
        },
        {
            "name": "Health",
            "description": "Health check and system status endpoints"
        }
    ]
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/", tags=["Health"], summary="Health Check")
def health_check():
    """
    Health check endpoint to verify API is running.
    
    Returns:
        dict: Health status message
    """
    return {"message": "Resume Insights Platform API is healthy", "version": "1.0.0"}

# Authentication endpoints
@app.post("/auth/register", response_model=schemas.Token, tags=["Authentication"], 
         summary="Register New User")
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account.
    
    Creates a new user with encrypted password and returns authentication token.
    
    Args:
        user: User registration data
        db: Database session
        
    Returns:
        Token: Authentication token and user information
        
    Raises:
        HTTPException: If email already exists
    """
    # Check if user already exists
    db_user = auth.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create access token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": db_user.id}, expires_delta=access_token_expires
    )
    
    # Convert to response schema
    user_schema = schemas.User.from_orm(db_user)
    
    return schemas.Token(
        access_token=access_token,
        token_type="bearer",
        user=user_schema
    )

@app.post("/auth/login", response_model=schemas.Token, tags=["Authentication"], 
         summary="User Login")
def login_user(user: schemas.UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user and return access token.
    
    Validates user credentials and returns authentication token.
    
    Args:
        user: User login credentials
        db: Database session
        
    Returns:
        Token: Authentication token and user information
        
    Raises:
        HTTPException: If credentials are invalid
    """
    # Authenticate user
    db_user = auth.authenticate_user(db, user.email, user.password)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": db_user.id}, expires_delta=access_token_expires
    )
    
    # Convert to response schema
    user_schema = schemas.User.from_orm(db_user)
    
    return schemas.Token(
        access_token=access_token,
        token_type="bearer",
        user=user_schema
    )

@app.get("/auth/me", response_model=schemas.User, tags=["Authentication"], 
        summary="Get Current User")
def get_current_user_info(current_user: models.User = Depends(auth.get_current_user)):
    """
    Get current authenticated user information.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User: Current user information
    """
    return schemas.User.from_orm(current_user)

# Resume endpoints
@app.post("/resumes/upload", response_model=schemas.ResumeUpload, tags=["Resumes"], 
         summary="Upload Resume")
async def upload_resume(
    file: UploadFile = File(..., description="Resume file (PDF, DOC, DOCX, TXT)"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a resume file for analysis.
    
    Accepts resume files in PDF, DOC, DOCX, or TXT format.
    
    Args:
        file: Resume file to upload
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        ResumeUpload: Upload confirmation with resume ID
    """
    # Save uploaded file
    file_path, filename, file_size = await file_utils.save_upload_file(file)
    
    # Create resume record
    db_resume = models.Resume(
        filename=filename,
        original_filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        content_type=file.content_type,
        user_id=current_user.id
    )
    db.add(db_resume)
    db.commit()
    db.refresh(db_resume)
    
    return schemas.ResumeUpload(
        id=db_resume.id,
        filename=db_resume.original_filename,
        file_path=db_resume.file_path,
        uploaded_at=db_resume.uploaded_at,
        status=db_resume.status
    )

@app.get("/resumes", response_model=List[schemas.Resume], tags=["Resumes"], 
        summary="List User Resumes")
def list_user_resumes(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get list of resumes uploaded by current user.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List[Resume]: List of user's resumes
    """
    resumes = db.query(models.Resume).filter(
        models.Resume.user_id == current_user.id
    ).order_by(desc(models.Resume.uploaded_at)).all()
    
    return [schemas.Resume.from_orm(resume) for resume in resumes]

@app.get("/resumes/{resume_id}", response_model=schemas.Resume, tags=["Resumes"], 
        summary="Get Resume Details")
def get_resume(
    resume_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific resume.
    
    Args:
        resume_id: Resume ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Resume: Resume details
        
    Raises:
        HTTPException: If resume not found or access denied
    """
    resume = db.query(models.Resume).filter(
        models.Resume.id == resume_id,
        models.Resume.user_id == current_user.id
    ).first()
    
    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found"
        )
    
    return schemas.Resume.from_orm(resume)

@app.delete("/resumes/{resume_id}", tags=["Resumes"], summary="Delete Resume")
def delete_resume(
    resume_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a resume and its associated files.
    
    Args:
        resume_id: Resume ID to delete
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        dict: Deletion confirmation
        
    Raises:
        HTTPException: If resume not found or access denied
    """
    resume = db.query(models.Resume).filter(
        models.Resume.id == resume_id,
        models.Resume.user_id == current_user.id
    ).first()
    
    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found"
        )
    
    # Delete file from disk
    file_utils.delete_file(resume.file_path)
    
    # Delete from database
    db.delete(resume)
    db.commit()
    
    return {"message": "Resume deleted successfully"}

# Analysis endpoints
def run_analysis_background(resume_id: int, db: Session):
    """
    Background task to run AI analysis on resume.
    
    Args:
        resume_id: Resume ID to analyze
        db: Database session
    """
    # Get resume
    resume = db.query(models.Resume).filter(models.Resume.id == resume_id).first()
    if not resume:
        return
    
    try:
        # Update status to processing
        resume.status = "processing"
        db.commit()
        
        # Run AI analysis
        analysis_data = ai_service.analyze_resume(
            resume.file_path, 
            resume.user_id, 
            resume.id
        )
        
        # Save analysis results
        db_analysis = models.AnalysisResult(
            resume_id=resume.id,
            overall_score=analysis_data["overall_score"],
            strengths=analysis_data["strengths"],
            weaknesses=analysis_data["weaknesses"],
            recommendations=analysis_data["recommendations"],
            industry_benchmark=analysis_data["industry_benchmark"],
            detailed_feedback=analysis_data["detailed_feedback"],
            analysis_version=analysis_data["analysis_version"]
        )
        db.add(db_analysis)
        
        # Update resume status
        resume.status = "analyzed"
        db.commit()
        
    except Exception as e:
        # Update status to error
        resume.status = "error"
        db.commit()
        # In production, log the error
        print(f"Analysis error for resume {resume_id}: {str(e)}")

@app.post("/analysis/trigger", tags=["Analysis"], summary="Trigger Resume Analysis")
def trigger_analysis(
    analysis_request: schemas.AnalysisCreate,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Trigger AI analysis for a resume.
    
    Starts background analysis process for the specified resume.
    
    Args:
        analysis_request: Analysis request data
        background_tasks: FastAPI background tasks
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        dict: Analysis initiation confirmation
        
    Raises:
        HTTPException: If resume not found or access denied
    """
    # Verify resume exists and belongs to user
    resume = db.query(models.Resume).filter(
        models.Resume.id == analysis_request.resume_id,
        models.Resume.user_id == current_user.id
    ).first()
    
    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found"
        )
    
    if resume.status == "processing":
        raise HTTPException(
            status_code=400,
            detail="Analysis already in progress"
        )
    
    # Add background task for analysis
    background_tasks.add_task(run_analysis_background, analysis_request.resume_id, db)
    
    return {"message": "Analysis started", "resume_id": analysis_request.resume_id}

@app.get("/analysis/{resume_id}", response_model=schemas.AnalysisResult, tags=["Analysis"], 
        summary="Get Analysis Results")
def get_analysis_results(
    resume_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get analysis results for a resume.
    
    Args:
        resume_id: Resume ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        AnalysisResult: Analysis results and feedback
        
    Raises:
        HTTPException: If resume not found, access denied, or no analysis available
    """
    # Verify resume exists and belongs to user
    resume = db.query(models.Resume).filter(
        models.Resume.id == resume_id,
        models.Resume.user_id == current_user.id
    ).first()
    
    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found"
        )
    
    # Get latest analysis result
    analysis = db.query(models.AnalysisResult).filter(
        models.AnalysisResult.resume_id == resume_id
    ).order_by(desc(models.AnalysisResult.analyzed_at)).first()
    
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="No analysis results found for this resume"
        )
    
    return schemas.AnalysisResult.from_orm(analysis)

@app.get("/feedback/summary", response_model=schemas.FeedbackSummary, tags=["Analysis"], 
        summary="Get Feedback Summary")
def get_feedback_summary(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get summary of feedback across all user's resumes.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        FeedbackSummary: Summary of feedback and trends
    """
    # Get user's resumes
    resumes = db.query(models.Resume).filter(
        models.Resume.user_id == current_user.id
    ).all()
    
    total_resumes = len(resumes)
    
    if total_resumes == 0:
        return schemas.FeedbackSummary(
            total_resumes=0,
            avg_score=None,
            latest_analysis=None,
            improvement_trend="No data available"
        )
    
    # Get all analysis results for user's resumes
    resume_ids = [r.id for r in resumes]
    analyses = db.query(models.AnalysisResult).filter(
        models.AnalysisResult.resume_id.in_(resume_ids)
    ).order_by(desc(models.AnalysisResult.analyzed_at)).all()
    
    if not analyses:
        return schemas.FeedbackSummary(
            total_resumes=total_resumes,
            avg_score=None,
            latest_analysis=None,
            improvement_trend="No analysis data available"
        )
    
    # Calculate average score
    scores = [a.overall_score for a in analyses]
    avg_score = round(sum(scores) / len(scores), 1)
    
    # Get latest analysis
    latest_analysis = schemas.AnalysisResult.from_orm(analyses[0])
    
    # Determine improvement trend
    if len(analyses) >= 2:
        recent_avg = sum(scores[:min(3, len(scores))]) / min(3, len(scores))
        older_avg = sum(scores[-min(3, len(scores)):]) / min(3, len(scores))
        
        if recent_avg > older_avg + 2:
            trend = "Improving - your recent resumes show better scores"
        elif recent_avg < older_avg - 2:
            trend = "Declining - consider reviewing recent feedback"
        else:
            trend = "Stable - consistent performance across resumes"
    else:
        trend = "Insufficient data for trend analysis"
    
    return schemas.FeedbackSummary(
        total_resumes=total_resumes,
        avg_score=avg_score,
        latest_analysis=latest_analysis,
        improvement_trend=trend
    )

# PUBLIC_INTERFACE
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
