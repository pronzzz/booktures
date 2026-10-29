"""Command line: ``booktures`` starts the app; other subcommands help with setup and scripting."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import webbrowser
from pathlib import Path

from booktures import __version__


def _plugin_dirs(args) -> list[Path]:
    dirs = [Path(p) for p in (args.plugins or [])]
    env = os.environ.get("BOOKTURES_PLUGINS")
    if env:
        dirs += [Path(p) for p in env.split(os.pathsep) if p]
    return dirs


def cmd_serve(args) -> None:
    import uvicorn

    from booktures.app import create_app

    app = create_app(args.data_dir, _plugin_dirs(args))
    url = f"http://{'localhost' if args.host in ('0.0.0.0', '127.0.0.1') else args.host}:{args.port}"
    print(f"\n  Booktures {__version__} is running at {url}\n  Library: {app.state.engine.home}\n")
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def cmd_providers(args) -> None:
    from booktures.engine import Engine

    eng = Engine(args.data_dir, _plugin_dirs(args))
    cat = eng.registry.catalog()
    active = eng.settings.get()
    for kind, title in (("text", "Story models"), ("image", "Illustrators")):
        print(f"\n{title}:")
        for p in cat[kind]:
            mark = "●" if active[kind]["provider"] == p["id"] else " "
            flag = "" if p["available"] else f"  (unavailable: {p['unavailable_reason']})"
            local = "local" if p["local"] else "cloud"
            print(f"  {mark} {p['id']:<20} {local:<6} {p['name']}  [{p['origin']}]{flag}")
    if cat["errors"]:
        print("\nPlugins that failed to load:")
        for e in cat["errors"]:
            print(f"  {e['source']}: {e['error']}")
    print(f"\nDrop-in plugin folder: {eng.home / 'plugins'}")


def cmd_convert(args) -> None:
    """Illustrate a book from the command line and write a standalone HTML file."""
    from booktures.db import Book
    from booktures.engine import Engine
    from booktures.export import export_html

    eng = Engine(args.data_dir, _plugin_dirs(args))
    patch: dict = {}
    if args.text:
        patch["text"] = {"provider": args.text}
    if args.image:
        patch["image"] = {"provider": args.image}
    if patch:
        eng.settings.update(patch, eng.secret_keys())
    src = Path(args.book)
    book = eng.create_book(src, src.name, args.style, args.custom_style or "", args.max_pages)
    with eng.db.Session() as s:
        count = len(s.get(Book, book.id).pages)
    print(f"Illustrating '{book.title}' ({count} pages)…")

    last = [""]

    def progress(b: Book) -> None:
        if b.message != last[0]:
            last[0] = b.message
            print(f"  [{b.progress * 100:5.1f}%] {b.message}")

    eng.run_book(book.id, threading.Event(), on_progress=progress)
    with eng.db.Session() as s:
        b = s.get(Book, book.id)
        for w in b.warnings or []:
            print(f"  note: {w}")
        out = Path(args.output or f"{src.stem}.illustrated.html")
        out.write_text(export_html(b, eng.book_dir(b.id) / "images"))
        print(f"{b.message}\nSaved {out}")


def cmd_download_model(args) -> None:
    from huggingface_hub import snapshot_download

    print(f"Downloading {args.model} (fp16 weights)…")
    path = snapshot_download(args.model, allow_patterns=["*.json", "*.txt", "*fp16.safetensors", "*.model"])
    print(f"Cached at {path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="booktures", description="Turn any book into an illustrated visual novel.")
    parser.add_argument("--version", action="version", version=f"booktures {__version__}")
    parser.add_argument("--data-dir", help="Library folder (default ~/.booktures or $BOOKTURES_HOME)")
    parser.add_argument("--plugins", action="append", help="Extra folder of drop-in plugins (repeatable)")
    sub = parser.add_subparsers(dest="cmd")

    serve = sub.add_parser("serve", help="Start the web app (default)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=int(os.environ.get("BOOKTURES_PORT", 8765)))
    serve.add_argument("--no-browser", action="store_true")
    serve.set_defaults(func=cmd_serve)

    sub.add_parser("providers", help="List story models and illustrators").set_defaults(func=cmd_providers)

    conv = sub.add_parser("convert", help="Illustrate a book and save a standalone HTML file")
    conv.add_argument("book")
    conv.add_argument("-o", "--output")
    conv.add_argument("--text", help="Story model id (e.g. offline, ollama, anthropic)")
    conv.add_argument("--image", help="Illustrator id (e.g. sketchbook, diffusers, pollinations)")
    conv.add_argument("--style", default="auto", help="Style preset id (watercolor, ink, oil, …)")
    conv.add_argument("--custom-style", help="Free-text style that overrides the preset")
    conv.add_argument("--max-pages", type=int, default=0)
    conv.set_defaults(func=cmd_convert)

    dl = sub.add_parser("download-model", help="Pre-download a local diffusion model")
    dl.add_argument("model", nargs="?", default="stabilityai/sd-turbo")
    dl.set_defaults(func=cmd_download_model)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if not getattr(args, "func", None):
        args = parser.parse_args([*(argv or sys.argv[1:]), "serve"])
    args.func(args)
