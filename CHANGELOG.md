# Changelog

## 2.0.0 — 2026-10-30

A full rewrite. The project is now **Booktures** (formerly "Lumina Reader"): one installable app you run with `booktures`, with no Redis, Celery or Docker required.

### New

- **Plugin system for models.** Story models (`TextProvider`) and illustrators (`ImageProvider`) are plugins that declare their own settings fields. They load from built-ins, from `pip` packages (the `booktures.plugins` entry point), and from drop-in `.py` folders. Each one gets a settings form and "Check connection" / "Try it" buttons. Plugin load errors are shown in the app instead of crashing it. See [docs/PLUGINS.md](docs/PLUGINS.md).
- **Built-in local image model.** SD-Turbo runs through diffusers on CUDA, Apple MPS or CPU. It takes about 2 seconds a picture on an Apple M4. There are presets for SDXL-Turbo, LCM Dreamshaper and SD 1.5, and `booktures download-model` fetches weights ahead of time.
- **Works with no model at all.** A rule-based story analyzer (finds characters and their appearance, detects genre, picks the most visual sentence) and the procedural Sketchbook painter.
- **12 built-in providers.**
  - Story models: Offline, OpenAI-compatible (with presets for OpenAI, OpenRouter, Groq, Together, DeepSeek, Mistral, LM Studio, llama.cpp, vLLM and Ollama /v1), Ollama, Anthropic Claude and Google Gemini.
  - Illustrators: Sketchbook, Local diffusion, Pollinations, OpenAI Images, Stability AI, SD WebUI and ComfyUI (including custom workflows).
- **Character bible and style lock.** Character descriptions and the art style go into every prompt. Both can be edited in the reader, along with 10 style presets or your own style.
- **New reader.**
  - Split view with scroll-synced pictures, and a full-screen cinema mode with a Ken Burns pan.
  - Night, sepia and paper themes, 5 text sizes, and keyboard navigation.
  - Live progress over server-sent events.
  - Per-page prompt editing and repaint.
- **Similar-scene reuse.** Consecutive pages that show the same scene share one picture.
- **Export** to a single self-contained HTML file.
- **CLI.** `booktures convert book.epub -o book.html` illustrates a book without the web app.
- **Better ingestion.**
  - PDFs: repeated headers, footers and page numbers are removed, and broken lines are rejoined into paragraphs. Scanned pages are OCR'd if Tesseract is installed.
  - EPUB support, plus TXT and Markdown.
- **Safety screen** before painting, using a keyword list plus the provider's own moderation when it has one.
- Docker image, docker-compose file, GitHub Actions CI, and 50 tests that run without network or GPU.

### Removed

- The Celery and Redis worker, the separate frontend and backend containers, and the hard dependency on one hosted LLM.

## 1.0.0

The first version, released as "Lumina Reader": a FastAPI, Celery and Redis backend with a React split reader.
