from pydantic import BaseModel
from typing import List, Optional, Dict

class ProjectCreate(BaseModel):
    title: str

class ProjectResponse(BaseModel):
    id: str
    title: str
    global_art_style: Optional[str] = None
    character_bible: Optional[Dict] = None

# Fixed PageResponse using int instead of Integer
class PageResponse(BaseModel):
    page_number: int
    raw_text: str
    scene_summary: Optional[str] = None
    image_prompt: Optional[str] = None
    image_url: Optional[str] = None
    censored: bool = False
    
    class Config:
        from_attributes = True


class ProjectBookResponse(BaseModel):
    project_title: str
    global_style: Optional[str]
    pages: List[PageResponse]
