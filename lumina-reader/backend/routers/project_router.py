from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import shutil
import os
from core.database import get_db
from models import Project, Page
from schemas import ProjectResponse, ProjectBookResponse, PageResponse
from tasks import process_book_task
from core.celery_app import celery_app
from celery.result import AsyncResult

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=ProjectResponse)
def upload_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Create Project
    project = Project(title=file.filename)
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Save File
    file_path = os.path.join(UPLOAD_DIR, f"{project.id}.pdf")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return project

@router.post("/process/{project_id}")
def process_project(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    file_path = os.path.join(UPLOAD_DIR, f"{project.id}.pdf")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Trigger Celery Task
    task = process_book_task.delay(project_id, file_path)
    
    return {"message": "Processing started", "task_id": task.id}

@router.get("/status/{task_id}")
def get_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": task_result.status,
        "result": task_result.result,
        "info": task_result.info # Progress meta
    }

@router.get("/book/{project_id}", response_model=ProjectBookResponse)
def get_book(project_id: str, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {
        "project_title": project.title,
        "global_style": project.global_art_style,
        "pages": project.pages
    }
