from core.celery_app import celery_app
from sqlalchemy.orm import Session
from core.database import SessionLocal, engine
from models import Project, Page
from services.pdf_parser import extract_text_from_pdf, clean_text, extract_text_with_ocr
from services.llm_engine import analyze_style_and_characters, generate_page_prompt, check_safety
from services.image_gen import generate_image
import fitz
import os
import redis
import json
from core.config import settings
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

redis_client = redis.from_url(settings.REDIS_URL)

def calculate_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.0
    vectorizer = TfidfVectorizer()
    try:
        tfidf = vectorizer.fit_transform([text1, text2])
        return cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
    except Exception:
        return 0.0

def update_progress(self_task, task_id, progress, message, status="PROCESSING"):
    self_task.update_state(state=status, meta={'progress': progress, 'message': message})
    try:
        redis_client.publish(f"task_progress:{task_id}", json.dumps({
            "progress": progress, 
            "message": message, 
            "status": status
        }))
    except Exception as e:
        print(f"Redis publish error: {e}")

@celery_app.task(bind=True)
def process_book_task(self, project_id: str, file_path: str):
    task_id = self.request.id
    update_progress(self, task_id, 0, 'Starting...')
    
    db: Session = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return {"status": "failed", "reason": "Project not found"}

        # 1. Extract Text
        update_progress(self, task_id, 5, 'Extracting text...')
        doc = fitz.open(file_path)
        total_pages = len(doc)
        
        full_text_start = ""
        
        # Save pages to DB first
        for page_num, page in enumerate(doc):
            text = page.get_text()
            if len(text.strip()) < 50:
                text = extract_text_with_ocr(page)
            cleaned = clean_text(text)
            if page_num < 10:
                full_text_start += cleaned + "\n"
            
            db_page = Page(id=None, project_id=project_id, page_number=page_num+1, raw_text=cleaned)
            db.add(db_page)
        
        db.commit()
        
        # 2. Analyze Style
        update_progress(self, task_id, 10, 'Analyzing style...')
        analysis = analyze_style_and_characters(full_text_start)
        project.global_art_style = analysis.get("global_art_style", "")
        project.character_bible = analysis.get("character_bible", {})
        db.commit()
        
        # 3. Generate Scene Summaries & Images
        prev_summary = "Start of the book."
        
        pages = db.query(Page).filter(Page.project_id == project_id).order_by(Page.page_number).all()
        
        for i, page in enumerate(pages):
            progress = 10 + int((i / total_pages) * 80)
            update_progress(self, task_id, progress, f'Processing page {page.page_number}/{total_pages} (LLM)...')
            
            # Generate Prompt
            prompt_data = generate_page_prompt(
                page.raw_text, 
                prev_summary, 
                project.character_bible, 
                project.global_art_style
            )
            
            page.scene_summary = prompt_data.get("scene_summary", "")
            raw_prompt = prompt_data.get("image_prompt", "")

            # Safety Check
            if not check_safety(raw_prompt):
                page.image_prompt = "A closed book resting on a table, dimly lit, safe content placeholder"
                page.censored = True
            else:
                page.image_prompt = raw_prompt
                page.censored = False

            # Smart Skipping using Cosine Similarity
            similarity = calculate_similarity(page.scene_summary, prev_summary)
            if similarity > 0.85 and i > 0 and not page.censored:
                scene_changed = False
            else:
                scene_changed = True

            prev_summary = page.scene_summary
            
            # Smart Skipping
            if not scene_changed and i > 0:
                # Reuse previous image
                update_progress(self, task_id, progress, f'Processing page {page.page_number}/{total_pages} (Skipping Gen - Sim {similarity:.2f})...')
                page.image_url = pages[i-1].image_url
            else:
                # Generate Image
                update_progress(self, task_id, progress, f'Processing page {page.page_number}/{total_pages} (Painting)...')
                image_url = generate_image(page.image_prompt)
                page.image_url = image_url
            
            db.commit()
            
    except Exception as e:
        update_progress(self, task_id, 0, str(e), status="FAILURE")
        raise e
    finally:
        db.close()
        # Cleanup file if needed
        if os.path.exists(file_path):
            os.remove(file_path)

    # Final success update
    update_progress(self, task_id, 100, "Completed", status="SUCCESS")
    return {"status": "completed", "project_id": project_id}
