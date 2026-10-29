"""REST API used by the web app (and handy for scripting)."""

from __future__ import annotations

import asyncio
import base64
import json
import re
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from booktures import __version__
from booktures.db import ACTIVE_STATES, Book, Page
from booktures.engine import Engine, image_ext
from booktures.export import export_html
from booktures.pipeline import prompts
from booktures.pipeline.ingest import UnsupportedFormat, detect_format
from booktures.pipeline.styles import STYLE_PRESETS
from booktures.plugins import ImageRequest, ProviderError, SceneContext

router = APIRouter()
media = APIRouter()

SAMPLE_PAGE = (
    "The storm broke just after midnight. Mara climbed the lighthouse stairs two at a time, "
    "her yellow oilskin streaming, and threw open the lamp room door. Far below, a fishing boat "
    "was fighting the waves, its single lantern swinging wildly."
)
SAMPLE_BIBLE = {"Mara": "a wiry young woman with cropped copper hair, freckles and a yellow oilskin coat"}


def engine(request: Request) -> Engine:
    return request.app.state.engine


def page_json(p: Page, book: Book) -> dict:
    return {
        "number": p.number,
        "text": p.text,
        "scene_summary": p.scene_summary,
        "visual": p.visual,
        "characters": p.characters or [],
        "mood": p.mood,
        "image_prompt": p.image_prompt,
        "prompt_override": p.prompt_override,
        "image_status": p.image_status,
        "image_url": f"/media/{book.id}/{p.image_file}?v={p.image_version}" if p.image_file else None,
        "reused_from": p.reused_from,
        "censored": p.censored,
        "error": p.error,
    }


def book_json(b: Book, with_pages: bool = False) -> dict:
    counts = {"pending": 0, "painting": 0, "done": 0, "reused": 0, "failed": 0}
    cover = None
    for p in b.pages:
        counts[p.image_status] = counts.get(p.image_status, 0) + 1
        if cover is None and p.image_file:
            cover = f"/media/{b.id}/{p.image_file}?v={p.image_version}"
    out = {
        "id": b.id,
        "title": b.title,
        "author": b.author,
        "format": b.format,
        "filename": b.filename,
        "status": b.status,
        "progress": round(b.progress or 0, 4),
        "message": b.message,
        "error": b.error,
        "warnings": b.warnings or [],
        "style_preset": b.style_preset,
        "custom_style": b.custom_style,
        "global_style": b.global_style,
        "genre": b.genre,
        "setting": b.setting,
        "character_bible": b.character_bible or {},
        "text_provider": b.text_provider,
        "image_provider": b.image_provider,
        "page_count": len(b.pages),
        "counts": counts,
        "cover_url": cover,
        "created_at": b.created_at.isoformat() if b.created_at else None,
        "updated_at": b.updated_at.isoformat() if b.updated_at else None,
    }
    if with_pages:
        out["pages"] = [page_json(p, b) for p in b.pages]
    return out


def _get_book(eng: Engine, s, book_id: str) -> Book:
    book = s.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")
    return book


# -- meta ------------------------------------------------------------------


@router.get("/health")
def health(request: Request):
    eng = engine(request)
    return {"status": "ok", "version": __version__, "data_dir": str(eng.home)}


@router.get("/styles")
def styles():
    return STYLE_PRESETS


@router.get("/providers")
def providers(request: Request):
    eng = engine(request)
    cat = eng.registry.catalog()
    data = eng.settings.get()
    cat["active"] = {"text": data["text"]["provider"], "image": data["image"]["provider"]}
    cat["plugin_dirs"] = [str(eng.home / "plugins")]
    return cat


class ProviderTest(BaseModel):
    config: dict = {}


@router.post("/providers/{kind}/{provider_id}/check")
def check_provider(kind: str, provider_id: str, body: ProviderTest, request: Request):
    eng = engine(request)
    try:
        provider = eng.provider(kind, provider_id, body.config)
        return {"ok": True, "message": provider.check()}
    except ProviderError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": f"{type(exc).__name__}: {exc}"}


@router.post("/providers/{kind}/{provider_id}/test")
def test_provider(kind: str, provider_id: str, body: ProviderTest, request: Request):
    """Run one real call: a sample scene for story models, a sample picture for illustrators."""
    eng = engine(request)
    try:
        provider = eng.provider(kind, provider_id, body.config)
        if kind == "text":
            ctx = SceneContext("The story begins.", SAMPLE_BIBLE, "watercolor illustration", "a stormy coast")
            scene = provider.describe_scene(SAMPLE_PAGE, ctx)
            return {"ok": True, "message": "The story model answered.", "scene": scene}
        prompt = prompts.compose_prompt(
            "a lighthouse on a cliff in a storm at night, a small boat with a lantern on huge waves",
            ["Mara"], SAMPLE_BIBLE, "atmospheric gouache book illustration",
        )
        data = provider.generate(ImageRequest(prompt=prompt, negative_prompt=prompts.NEGATIVE_PROMPT, width=768, height=512, seed=42))
        ext = image_ext(data)
        return {
            "ok": True,
            "message": "The illustrator painted a sample.",
            "image": f"data:image/{'jpeg' if ext == 'jpg' else ext};base64,{base64.b64encode(data).decode()}",
            "prompt": prompt,
        }
    except ProviderError as exc:
        return {"ok": False, "message": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": f"{type(exc).__name__}: {exc}"}


@router.get("/settings")
def get_settings(request: Request):
    eng = engine(request)
    return eng.settings.mask(eng.settings.get(), eng.secret_keys())


@router.put("/settings")
def put_settings(patch: dict, request: Request):
    eng = engine(request)
    for kind in ("text", "image"):
        pid = (patch.get(kind) or {}).get("provider")
        table = eng.registry.text if kind == "text" else eng.registry.image
        if pid and pid not in table:
            raise HTTPException(400, f"Unknown {kind} provider '{pid}'")
    data = eng.settings.update(patch, eng.secret_keys())
    return eng.settings.mask(data, eng.secret_keys())


# -- books -----------------------------------------------------------------


@router.get("/books")
def list_books(request: Request):
    eng = engine(request)
    with eng.db.Session() as s:
        books = s.query(Book).order_by(Book.created_at.desc()).all()
        return [book_json(b) for b in books]


@router.post("/books")
def create_book(
    request: Request,
    file: UploadFile = File(...),
    style_preset: str = Form("auto"),
    custom_style: str = Form(""),
    max_pages: int = Form(0),
    start: bool = Form(True),
):
    eng = engine(request)
    name = Path(file.filename or "book.pdf").name
    try:
        detect_format(name)
    except UnsupportedFormat as exc:
        raise HTTPException(400, str(exc)) from exc
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(name).suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        book = eng.create_book(tmp_path, name, style_preset, custom_style, max_pages or 0)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"Could not read this file: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)
    if start:
        eng.submit(book.id)
    with eng.db.Session() as s:
        return book_json(s.get(Book, book.id), with_pages=True)


SAMPLE_BOOK = Path(__file__).parent / "samples" / "the-lantern-keeper.md"


class SampleBody(BaseModel):
    style_preset: str = "auto"


@router.post("/books/sample")
def create_sample(body: SampleBody, request: Request):
    """Add the bundled short story so new users can see a result without finding a book."""
    eng = engine(request)
    # One paragraph per page, so the short story gets a picture for every scene.
    book = eng.create_book(SAMPLE_BOOK, SAMPLE_BOOK.name, body.style_preset, page_chars=600)
    eng.submit(book.id)
    with eng.db.Session() as s:
        return book_json(s.get(Book, book.id), with_pages=True)


@router.get("/books/{book_id}")
def get_book(book_id: str, request: Request):
    eng = engine(request)
    with eng.db.Session() as s:
        return book_json(_get_book(eng, s, book_id), with_pages=True)


class BookPatch(BaseModel):
    title: str | None = None
    author: str | None = None
    style_preset: str | None = None
    custom_style: str | None = None
    global_style: str | None = None
    character_bible: dict[str, str] | None = None


@router.patch("/books/{book_id}")
def patch_book(book_id: str, body: BookPatch, request: Request):
    eng = engine(request)
    with eng.db.Session() as s:
        book = _get_book(eng, s, book_id)
        for key, value in body.model_dump(exclude_none=True).items():
            if key == "character_bible":
                value = {k.strip(): v.strip() for k, v in value.items() if k.strip() and v.strip()}
            setattr(book, key, value)
        if body.style_preset is not None or body.custom_style is not None:
            from booktures.pipeline.styles import resolve_style

            book.global_style = resolve_style(book.style_preset, book.custom_style, book.global_style)
        s.commit()
        return book_json(book, with_pages=True)


@router.delete("/books/{book_id}")
def delete_book(book_id: str, request: Request):
    eng = engine(request)
    eng.delete_book(book_id)
    return {"ok": True}


class RunBody(BaseModel):
    mode: str = "resume"  # resume | repaint | reanalyze


@router.post("/books/{book_id}/run")
def run_book(book_id: str, body: RunBody, request: Request):
    eng = engine(request)
    if body.mode not in ("resume", "repaint", "reanalyze"):
        raise HTTPException(400, "mode must be resume, repaint or reanalyze")
    try:
        eng.submit(book_id, body.mode)
    except KeyError as exc:
        raise HTTPException(404, "Book not found") from exc
    return {"ok": True}


@router.post("/books/{book_id}/cancel")
def cancel_book(book_id: str, request: Request):
    engine(request).cancel(book_id)
    return {"ok": True}


class RegenerateBody(BaseModel):
    prompt_override: str | None = None


@router.post("/books/{book_id}/pages/{number}/regenerate")
def regenerate(book_id: str, number: int, body: RegenerateBody, request: Request):
    eng = engine(request)
    try:
        eng.regenerate_page(book_id, number, body.prompt_override)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(404, "Page not found") from exc
    return {"ok": True}


@router.get("/books/{book_id}/events")
async def events(book_id: str, request: Request):
    """Server-sent events: the book (with pages) every time something changes."""
    eng = engine(request)

    def snapshot() -> dict | None:
        with eng.db.Session() as s:
            book = s.get(Book, book_id)
            return book_json(book, with_pages=True) if book else None

    async def stream():
        last = ""
        idle = 0
        while not await request.is_disconnected():
            data = await asyncio.to_thread(snapshot)
            if data is None:
                yield "event: gone\ndata: {}\n\n"
                return
            payload = json.dumps(data)
            if payload != last:
                last, idle = payload, 0
                yield f"data: {payload}\n\n"
            else:
                idle += 1
                if idle % 30 == 0:
                    yield ": keep-alive\n\n"
            painting = any(p["image_status"] == "painting" for p in data["pages"])
            await asyncio.sleep(0.6 if data["status"] in ACTIVE_STATES or painting else 2.0)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/books/{book_id}/export")
def export(book_id: str, request: Request):
    eng = engine(request)
    with eng.db.Session() as s:
        book = _get_book(eng, s, book_id)
        markup = export_html(book, eng.book_dir(book.id) / "images")
        slug = re.sub(r"[^a-z0-9]+", "-", book.title.lower()).strip("-") or "book"
    return HTMLResponse(markup, headers={"Content-Disposition": f'attachment; filename="{slug}.html"'})


@media.get("/media/{book_id}/{filename}")
def media_file(book_id: str, filename: str, request: Request):
    eng = engine(request)
    if not re.fullmatch(r"[a-f0-9]{6,32}", book_id) or not re.fullmatch(r"[\w.\-]+", filename):
        raise HTTPException(404)
    path = eng.home / "books" / book_id / "images" / filename
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, headers={"Cache-Control": "public, max-age=31536000, immutable"})
