"""Library database: books and their pages (SQLite through SQLAlchemy)."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


ACTIVE_STATES = ("queued", "analyzing", "illustrating")


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    title: Mapped[str] = mapped_column(String, default="Untitled")
    author: Mapped[str] = mapped_column(String, default="")
    filename: Mapped[str] = mapped_column(String, default="")
    format: Mapped[str] = mapped_column(String, default="pdf")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # queued | analyzing | illustrating | done | failed | cancelled | interrupted
    status: Mapped[str] = mapped_column(String, default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    warnings: Mapped[list] = mapped_column(JSON, default=list)

    style_preset: Mapped[str] = mapped_column(String, default="auto")
    custom_style: Mapped[str] = mapped_column(Text, default="")
    global_style: Mapped[str] = mapped_column(Text, default="")
    genre: Mapped[str] = mapped_column(String, default="")
    setting: Mapped[str] = mapped_column(Text, default="")
    character_bible: Mapped[dict] = mapped_column(JSON, default=dict)
    seed: Mapped[int] = mapped_column(Integer, default=lambda: secrets.randbelow(2**31))

    text_provider: Mapped[str] = mapped_column(String, default="")
    image_provider: Mapped[str] = mapped_column(String, default="")

    pages: Mapped[list["Page"]] = relationship(
        back_populates="book", cascade="all, delete-orphan", order_by="Page.number"
    )


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    scene_summary: Mapped[str] = mapped_column(Text, default="")
    visual: Mapped[str] = mapped_column(Text, default="")
    characters: Mapped[list] = mapped_column(JSON, default=list)
    mood: Mapped[str] = mapped_column(String, default="")
    image_prompt: Mapped[str] = mapped_column(Text, default="")
    prompt_override: Mapped[str] = mapped_column(Text, default="")

    # pending | painting | done | reused | failed
    image_status: Mapped[str] = mapped_column(String, default="pending")
    image_file: Mapped[str] = mapped_column(String, default="")
    reused_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    censored: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str] = mapped_column(Text, default="")
    image_version: Mapped[int] = mapped_column(Integer, default=0)

    book: Mapped[Book] = relationship(back_populates="pages")


class Database:
    def __init__(self, path: Path):
        self.engine = create_engine(
            f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 30}
        )

        @event.listens_for(self.engine, "connect")
        def _pragmas(conn, _record):
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def mark_interrupted(self) -> int:
        """Books that were mid-run when the server stopped can be resumed later."""
        with self.Session() as s:
            books = s.query(Book).filter(Book.status.in_(ACTIVE_STATES)).all()
            for b in books:
                b.status = "interrupted"
                b.message = "Stopped when the server shut down. Press Resume to continue."
            for p in s.query(Page).filter(Page.image_status == "painting").all():
                p.image_status = "pending"
            s.commit()
            return len(books)
