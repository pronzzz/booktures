"""The engine: owns the database, settings and providers, and runs illustration jobs.

A job reads the book's opening once to build the art style and character bible,
then walks the pages in order. For each page it asks the story model for a
scene, injects the traits of every character on screen, screens the prompt,
skips the paint step when the scene matches the previous one, and saves the
image. Pages are committed one at a time, so the reader can show pictures as
they arrive, and a stopped job resumes where it left off.
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from booktures.config import SettingsStore, data_dir
from booktures.db import ACTIVE_STATES, Book, Database, Page
from booktures.pipeline import prompts, safety
from booktures.pipeline.ingest import TARGET_PAGE_CHARS, parse_book
from booktures.pipeline.styles import resolve_style
from booktures.pipeline.text_utils import similarity
from booktures.plugins import ImageProvider, ImageRequest, ProviderError, SceneContext, TextProvider
from booktures.plugins.registry import Registry, load_all

log = logging.getLogger("booktures")

MAGIC = [(b"\x89PNG", "png"), (b"\xff\xd8", "jpg"), (b"RIFF", "webp"), (b"GIF8", "gif")]


def image_ext(data: bytes) -> str:
    for magic, ext in MAGIC:
        if data.startswith(magic):
            return ext
    raise ProviderError("The illustrator returned data that is not an image.")


class Cancelled(Exception):
    pass


class Engine:
    def __init__(self, home: str | Path | None = None, plugin_dirs: list[Path] | None = None):
        self.home = data_dir(home)
        self.settings = SettingsStore(self.home / "settings.json")
        self.db = Database(self.home / "booktures.db")
        dirs = [self.home / "plugins", *(plugin_dirs or [])]
        self.registry: Registry = load_all(dirs)
        self._books = ThreadPoolExecutor(max_workers=1, thread_name_prefix="book")
        self._pages = ThreadPoolExecutor(max_workers=1, thread_name_prefix="page")
        self._cancel: dict[str, threading.Event] = {}
        self.db.mark_interrupted()

    # -- providers -----------------------------------------------------
    def secret_keys(self) -> dict[tuple[str, str], set[str]]:
        keys: dict[tuple[str, str], set[str]] = {}
        for kind, table in (("text", self.registry.text), ("image", self.registry.image)):
            for pid, cls in table.items():
                keys[(kind, pid)] = {f.key for f in cls.fields if f.type == "secret"}
        return keys

    def provider(self, kind: str, provider_id: str | None = None, overrides: dict | None = None):
        pid, cfg = self.settings.provider_config(kind, provider_id)
        if overrides:
            secrets = self.secret_keys().get((kind, pid), set())
            for key, value in overrides.items():
                if key in secrets and isinstance(value, str) and value.startswith("••"):
                    continue
                cfg[key] = value
        try:
            return self.registry.create(kind, pid, cfg)
        except KeyError as exc:
            raise ProviderError(f"The {kind} provider '{pid}' is not installed.") from exc

    # -- paths -----------------------------------------------------------
    def book_dir(self, book_id: str) -> Path:
        path = self.home / "books" / book_id
        (path / "images").mkdir(parents=True, exist_ok=True)
        return path

    # -- books -----------------------------------------------------------
    def create_book(
        self,
        upload_path: Path,
        filename: str,
        style_preset: str = "auto",
        custom_style: str = "",
        max_pages: int | None = None,
        page_chars: int | None = None,
    ) -> Book:
        pipe = self.settings.get()["pipeline"]
        limit = int(max_pages if max_pages is not None else pipe.get("max_pages") or 0)
        parsed = parse_book(upload_path, filename, max_pages=limit, page_chars=page_chars or TARGET_PAGE_CHARS)
        with self.db.Session() as s:
            book = Book(
                title=parsed.title[:200], author=parsed.author[:200], filename=filename, format=parsed.format,
                style_preset=style_preset or "auto", custom_style=custom_style or "", warnings=parsed.warnings,
                message="Waiting to start…",
            )
            s.add(book)
            s.flush()
            for i, text in enumerate(parsed.pages, start=1):
                s.add(Page(book_id=book.id, number=i, text=text))
            s.commit()
            dest = self.book_dir(book.id) / f"source{Path(filename).suffix.lower()}"
            shutil.copyfile(upload_path, dest)
            return book

    def delete_book(self, book_id: str) -> None:
        self.cancel(book_id)
        with self.db.Session() as s:
            book = s.get(Book, book_id)
            if book:
                s.delete(book)
                s.commit()
        shutil.rmtree(self.home / "books" / book_id, ignore_errors=True)

    def submit(self, book_id: str, mode: str = "resume") -> None:
        with self.db.Session() as s:
            book = s.get(Book, book_id)
            if not book:
                raise KeyError(book_id)
            if book.status in ACTIVE_STATES and book_id in self._cancel:
                return  # already queued or running
            if mode in ("repaint", "reanalyze"):
                for p in book.pages:
                    p.image_status, p.reused_from, p.error = "pending", None, ""
                if mode == "reanalyze":
                    book.global_style, book.character_bible, book.genre, book.setting = "", {}, "", ""
                    for p in book.pages:
                        p.scene_summary = p.visual = p.image_prompt = ""
            book.status, book.error, book.message = "queued", "", "Queued…"
            s.commit()
        self._cancel[book_id] = threading.Event()
        self._books.submit(self._safe_run, book_id)

    def cancel(self, book_id: str) -> None:
        event = self._cancel.get(book_id)
        if event:
            event.set()

    def regenerate_page(self, book_id: str, number: int, prompt_override: str | None = None) -> None:
        with self.db.Session() as s:
            page = s.query(Page).filter_by(book_id=book_id, number=number).one()
            if prompt_override is not None:
                page.prompt_override = prompt_override.strip()
            page.image_status, page.error = "painting", ""
            s.commit()
        self._pages.submit(self._safe_page, book_id, number)

    # -- job bodies ------------------------------------------------------
    def _safe_run(self, book_id: str) -> None:
        try:
            self.run_book(book_id, self._cancel.get(book_id) or threading.Event())
        except Cancelled:
            pass
        except Exception as exc:  # noqa: BLE001
            log.exception("Book %s failed", book_id)
            self._set(book_id, status="failed", error=str(exc), message="Stopped with an error.")
        finally:
            self._cancel.pop(book_id, None)

    def _safe_page(self, book_id: str, number: int) -> None:
        try:
            self.illustrate_single(book_id, number)
        except Exception as exc:  # noqa: BLE001
            log.exception("Page %s/%s failed", book_id, number)
            with self.db.Session() as s:
                page = s.query(Page).filter_by(book_id=book_id, number=number).one_or_none()
                if page:
                    page.image_status, page.error = "failed", str(exc)
                    s.commit()

    def _set(self, book_id: str, **fields) -> None:
        with self.db.Session() as s:
            book = s.get(Book, book_id)
            if book:
                for k, v in fields.items():
                    setattr(book, k, v)
                s.commit()

    def _fallback(self) -> TextProvider:
        return self.registry.create("text", "offline", {})

    def analyze(self, book: Book, pages: list[Page], text: TextProvider, pipe: dict) -> list[str]:
        """Fill in style, genre, setting and character bible. Returns warnings."""
        warnings: list[str] = []
        limit = int(pipe.get("excerpt_chars") or 14000)
        excerpt, size = [], 0
        for p in pages:
            excerpt.append(p.text)
            size += len(p.text)
            if size >= limit:
                break
        excerpt_text = "\n\n".join(excerpt)[:limit]
        try:
            analysis = text.analyze_book(excerpt_text)
        except Exception as exc:  # noqa: BLE001
            if not pipe.get("fallback_to_offline", True) or text.id == "offline":
                raise
            warnings.append(f"Story model failed while reading the opening ({exc}); used the offline analyzer.")
            analysis = self._fallback().analyze_book(excerpt_text)
        book.genre = analysis.get("genre", "")
        book.setting = analysis.get("setting", "")
        book.character_bible = analysis.get("character_bible", {}) or {}
        if not book.author and analysis.get("author"):
            book.author = analysis["author"]
        book.global_style = resolve_style(book.style_preset, book.custom_style, analysis.get("global_art_style", ""))
        return warnings

    def describe(self, page: Page, book: Book, ctx: SceneContext, text: TextProvider, pipe: dict) -> tuple[dict, str]:
        try:
            return text.describe_scene(page.text, ctx), ""
        except Exception as exc:  # noqa: BLE001
            if not pipe.get("fallback_to_offline", True) or text.id == "offline":
                raise
            return self._fallback().describe_scene(page.text, ctx), f"Story model failed ({exc}); used offline analyzer."

    def paint(self, book: Book, page: Page, image: ImageProvider, pipe: dict, attempt_seed: int) -> str:
        req = ImageRequest(
            prompt=page.image_prompt,
            negative_prompt=prompts.NEGATIVE_PROMPT,
            width=int(pipe.get("width") or 768),
            height=int(pipe.get("height") or 512),
            seed=attempt_seed,
            style=book.global_style,
            hints={"characters": page.characters, "mood": page.mood, "page": page.number},
        )
        last: Exception | None = None
        for attempt in range(2):
            try:
                data = image.generate(req)
                ext = image_ext(data)
                page.image_version = (page.image_version or 0) + 1
                name = f"p{page.number:04d}-v{page.image_version}.{ext}"
                (self.book_dir(book.id) / "images" / name).write_bytes(data)
                return name
            except ProviderError as exc:
                last = exc
                if attempt == 0:
                    time.sleep(1.5)
        raise last or ProviderError("Image generation failed")

    def prepare_page(self, book: Book, page: Page, prev_summary: str, total: int, text: TextProvider, pipe: dict) -> str:
        """Describe the scene and build the final prompt. Returns a warning or ''."""
        warning = ""
        if page.prompt_override:
            page.image_prompt = page.prompt_override
            page.censored = False
            return ""
        ctx = SceneContext(
            previous_summary=prev_summary, character_bible=dict(book.character_bible or {}),
            global_style=book.global_style, setting=book.setting, page_number=page.number, total_pages=total,
        )
        scene, warning = self.describe(page, book, ctx, text, pipe)
        if scene.get("new_characters"):
            bible = dict(book.character_bible or {})
            for name, desc in scene["new_characters"].items():
                if name not in bible and len(bible) < 12:
                    bible[name] = desc
                    if name not in scene["characters"]:
                        scene["characters"].append(name)
            book.character_bible = bible
        page.scene_summary = scene["scene_summary"]
        page.visual = scene["visual_description"]
        page.characters = scene["characters"]
        page.mood = scene["mood"]
        prompt = prompts.compose_prompt(page.visual, page.characters, book.character_bible or {}, book.global_style, page.mood)
        if safety.is_safe(prompt, pipe.get("safety", "standard"), text):
            page.image_prompt, page.censored = prompt, False
        else:
            page.image_prompt = prompts.compose_prompt(safety.SAFE_PLACEHOLDER, [], {}, book.global_style)
            page.censored = True
        return warning

    def run_book(self, book_id: str, cancel: threading.Event, on_progress: Callable[[Book], None] | None = None) -> None:
        pipe = self.settings.get()["pipeline"]
        text: TextProvider = self.provider("text")
        image: ImageProvider = self.provider("image")
        threshold = float(pipe.get("similarity_threshold") or 0)

        with self.db.Session() as s:
            book = s.get(Book, book_id)
            pages = list(book.pages)
            total = len(pages)
            book.text_provider, book.image_provider = text.id, image.id
            warnings = [w for w in (book.warnings or []) if not w.startswith("Story model")]

            if not book.global_style:
                book.status, book.message, book.progress = "analyzing", f"Reading the opening with {text.name}…", 0.02
                s.commit()
                warnings += self.analyze(book, pages, text, pipe)
            book.warnings = warnings
            book.status = "illustrating"
            s.commit()

            prev_done: Page | None = None
            prev_summary = "The story begins."
            failures_in_a_row = 0
            for i, page in enumerate(pages):
                if cancel.is_set():
                    book.status, book.message = "cancelled", f"Paused at page {page.number} of {total}."
                    s.commit()
                    raise Cancelled()
                if page.image_status in ("done", "reused") and page.image_file:
                    prev_done, prev_summary = page, page.scene_summary or prev_summary
                    continue

                book.progress = 0.05 + 0.95 * i / max(1, total)
                book.message = f"Page {page.number} of {total}: writing the scene…"
                page.image_status = "painting"
                s.commit()
                if on_progress:
                    on_progress(book)

                warning = self.prepare_page(book, page, prev_summary, total, text, pipe)
                if warning and warning not in book.warnings:
                    book.warnings = [*book.warnings, warning]

                sim = 0.0
                if prev_done is not None and prev_done.image_file and not page.censored and not page.prompt_override:
                    sim = similarity(page.visual, prev_done.visual)
                if threshold and sim >= threshold:
                    page.image_status = "reused"
                    page.image_file = prev_done.image_file
                    page.reused_from = prev_done.reused_from or prev_done.number
                    page.error = ""
                    book.message = f"Page {page.number} of {total}: same scene as before, reusing the picture."
                else:
                    book.message = f"Page {page.number} of {total}: painting with {image.name}…"
                    s.commit()
                    try:
                        page.image_file = self.paint(book, page, image, pipe, book.seed + page.number)
                        page.image_status, page.reused_from, page.error = "done", None, ""
                        failures_in_a_row = 0
                    except ProviderError as exc:
                        page.image_status, page.error = "failed", str(exc)
                        failures_in_a_row += 1
                        if failures_in_a_row >= 3:
                            book.status = "failed"
                            book.error = f"The illustrator failed three pages in a row: {exc}"
                            book.message = "Stopped. Fix the illustrator in Settings, then press Resume."
                            s.commit()
                            return
                if page.image_status in ("done", "reused"):
                    prev_done = page
                prev_summary = page.scene_summary or prev_summary
                s.commit()

            counts = {"done": 0, "reused": 0, "failed": 0}
            for p in pages:
                if p.image_status in counts:
                    counts[p.image_status] += 1
            book.status, book.progress = "done", 1.0
            book.message = (
                f"Illustrated {counts['done'] + counts['reused']} of {total} pages"
                + (f" ({counts['reused']} reused a matching scene)" if counts["reused"] else "")
                + (f", {counts['failed']} failed" if counts["failed"] else "")
                + "."
            )
            s.commit()
            if on_progress:
                on_progress(book)

    def illustrate_single(self, book_id: str, number: int) -> None:
        pipe = self.settings.get()["pipeline"]
        text = self.provider("text")
        image = self.provider("image")
        with self.db.Session() as s:
            book = s.get(Book, book_id)
            pages = list(book.pages)
            idx = next(i for i, p in enumerate(pages) if p.number == number)
            page = pages[idx]
            if not book.global_style:
                self.analyze(book, pages, text, pipe)
            prev = pages[idx - 1].scene_summary if idx > 0 else "The story begins."
            self.prepare_page(book, page, prev, len(pages), text, pipe)
            s.commit()
            seed = book.seed + number + 7919 * ((page.image_version or 0) + 1)
            page.image_file = self.paint(book, page, image, pipe, seed)
            page.image_status, page.reused_from, page.error = "done", None, ""
            s.commit()

    def shutdown(self) -> None:
        for event in self._cancel.values():
            event.set()
        self._books.shutdown(wait=False, cancel_futures=True)
        self._pages.shutdown(wait=False, cancel_futures=True)
