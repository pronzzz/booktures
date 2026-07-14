from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
import uuid
from core.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String, index=True)
    global_art_style = Column(Text, nullable=True)
    character_bible = Column(JSON, nullable=True)
    
    pages = relationship("Page", back_populates="project", cascade="all, delete-orphan")

class Page(Base):
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String, ForeignKey("projects.id"))
    page_number = Column(Integer)
    raw_text = Column(Text)
    scene_summary = Column(Text, nullable=True)
    image_prompt = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)
    censored = Column(Boolean, default=False)

    project = relationship("Project", back_populates="pages")
