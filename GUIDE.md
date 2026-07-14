# Lumina-Reader Technical Guide

Welcome to the technical internals of Lumina-Reader! This guide explains the core architecture, the AI generation pipeline, and how the "Context-Aware Memory" functions to maintain visual novel continuity.

## Architecture Overview

Lumina-Reader uses a standard asynchronous task-queue architecture to decouple the web server from the heavy AI processing loads.

1. **FastAPI (Backend Server)**: Handles file uploads and API routing. It receives the PDF and instantly offloads it to Celery.
2. **Celery (Task Worker)**: The workhorse. It runs in the background and executes the PDF parsing, LLM calls, and image generation.
3. **Redis (Message Broker)**: Acts as the intermediary queue between FastAPI and Celery. It also handles WebSockets messages via pub-sub.
4. **React / Vite (Frontend)**: The UI. It displays a real-time progress bar (using WebSockets) and then transitions to the Split-Screen Reader view when the job completes.

## The Context-Aware Pipeline

The most critical innovation of Lumina-Reader is how it solves the "inconsistent generation" problem common in AI art generation.

### Phase 1: Pre-Processing (The "Brain")
Before generating any images, the system scans the first few pages of the PDF to establish the story's baseline.
- **Character Bible:** The LLM parses the intro to find main characters and their physical descriptions (e.g., "Alice: Tall, blonde, red scarf").
- **Global Style:** The LLM decides on an overarching art style (e.g., "Cyberpunk, neon lighting, gritty textures") based on the book's genre.

### Phase 2: Page-by-Page Processing
For each page, the text is extracted using PyMuPDF (`fitz`).
1. **Scene Summarization**: An LLM summarizes the page's action.
2. **Trait Injection**: The LLM automatically cross-references the characters mentioned in the scene with the Character Bible, injecting their physical traits into the final Stable Diffusion prompt.
3. **Image Generation**: The completed prompt (Action + Character Traits + Global Style) is sent to Stability AI.

### Phase 3: Smart Skipping Optimization
To save time and API costs, the system compares the current page's scene description with the previous page's scene description. If the scene hasn't visually changed (e.g., a long internal monologue or extended dialogue in the same room), the system skips image generation and simply reuses the previous image. 

## Running Tests

To validate the LLM Memory and trait injection:
```bash
python3 lumina-reader/backend/tests/test_llm_memory.py
```
This script mocks the LLM responses to ensure the prompt engineering logic correctly extracts and injects traits.

## Extending the Project

If you wish to contribute, consider the following areas:
- **Local LLMs**: Swap out OpenAI for a local Ollama model to run the entire pipeline offline.
- **Local Diffusion**: Integrate ComfyUI or a local Stable Diffusion instance instead of the Stability API.
- **EPUB Support**: Extend the document parser to handle EPUBs, which are often cleaner to parse than PDFs.
