import os
import uuid
from typing import Tuple
from fastapi import UploadFile, HTTPException

# Configuration
UPLOAD_DIRECTORY = "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}

def create_upload_directory():
    """Create upload directory if it doesn't exist."""
    os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

def validate_file(file: UploadFile) -> None:
    """
    Validate uploaded file.
    
    Args:
        file: Uploaded file
        
    Raises:
        HTTPException: If file is invalid
    """
    # Check file extension
    if file.filename:
        _, ext = os.path.splitext(file.filename.lower())
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Supported formats: {', '.join(ALLOWED_EXTENSIONS)}"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="No filename provided"
        )

def generate_unique_filename(original_filename: str) -> str:
    """
    Generate unique filename while preserving extension.
    
    Args:
        original_filename: Original filename
        
    Returns:
        str: Unique filename
    """
    name, ext = os.path.splitext(original_filename)
    unique_id = str(uuid.uuid4())
    return f"{unique_id}{ext}"

async def save_upload_file(file: UploadFile) -> Tuple[str, str, int]:
    """
    Save uploaded file to disk.
    
    Args:
        file: Uploaded file
        
    Returns:
        tuple: (file_path, filename, file_size)
        
    Raises:
        HTTPException: If file cannot be saved
    """
    # Validate file
    validate_file(file)
    
    # Create upload directory
    create_upload_directory()
    
    # Generate unique filename
    unique_filename = generate_unique_filename(file.filename)
    file_path = os.path.join(UPLOAD_DIRECTORY, unique_filename)
    
    try:
        # Read and save file
        contents = await file.read()
        file_size = len(contents)
        
        # Check file size
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Save file
        with open(file_path, "wb") as f:
            f.write(contents)
        
        return file_path, unique_filename, file_size
        
    except Exception as e:
        # Clean up file if it was partially created
        if os.path.exists(file_path):
            os.remove(file_path)
        
        raise HTTPException(
            status_code=500,
            detail=f"Could not save file: {str(e)}"
        )
    finally:
        # Reset file position for any future reads
        await file.seek(0)

def delete_file(file_path: str) -> None:
    """
    Delete file from disk.
    
    Args:
        file_path: Path to file to delete
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        # Log error but don't raise - file deletion is not critical
        pass
