# Lumina-Reader: Context-Aware PDF-to-Visual Novel Converter

![License](https://img.shields.io/badge/License-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-FastAPI-brightgreen)
![React](https://img.shields.io/badge/React-Vite-blue)
![Celery](https://img.shields.io/badge/Celery-Redis-orange)
![AI](https://img.shields.io/badge/AI-Stable%20Diffusion%20%7C%20OpenAI-blueviolet)

Lumina-Reader is a full-stack web application that transforms a static PDF book into an immersive "Visual Novel" experience. The system ingests a PDF, extracts text page-by-page, and generates a unique, contextually relevant illustration for each page.

## The "State of the Art" Improvement (USP)
**"Narrative Continuity & Style Locking"**
Existing tools generate images in isolation, leading to random art styles and character inconsistencies. Lumina-Reader maintains a "Context Vector" (a rolling summary of physical descriptions and settings) to ensure the protagonist and the visual style (e.g., "watercolor," "cyberpunk") remain consistent throughout the entire book. It runs a pre-processing step to create a "Character Bible" and a "Global Art Style" before processing pages.

## Features

- **Drag-and-Drop PDF Upload**: Simple UI for uploading any PDF book.
- **Context-Aware Visuals**: Uses LLM-powered context tracking to inject character traits into scene prompts (e.g., "Alice is blonde").
- **Smart Skipping**: Saves API costs and generation time by detecting if a scene hasn't visually changed from the previous page, reusing the image via Cosine Similarity checks.
- **Split-Screen Reader**: A sticky dynamic image container that updates via "Scroll Spy" as you read the book text.
- **Async Job Queue**: Celery and Redis handle slow image generation (5-20 seconds per image) in the background.
- **Real-time Progress**: WebSockets integration streams live processing updates to the UI.

## Architecture

- **Backend**: Python (FastAPI) for high-performance async APIs.
- **Frontend**: React with Tailwind CSS, managed by Zustand.
- **Database**: SQLite / SQLAlchemy.
- **Broker/Worker**: Redis & Celery for asynchronous image generation tasks.
- **AI Stack**: PyMuPDF for extraction, OpenAI (or Gemini) for LLM prompts, Stability AI (SDXL) for image generation.

## Installation & Setup

You need [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) installed.

1. **Clone the repository:**
   ```bash
   git clone https://github.com/pronzzz/booktures.git
   cd booktures/lumina-reader
   ```

2. **Configure Environment Variables:**
   Create a `.env` file in the `lumina-reader/backend/` directory based on the `.env.example`:
   ```bash
   OPENAI_API_KEY="your-openai-api-key"
   STABILITY_API_KEY="your-stability-api-key"
   REDIS_URL="redis://redis:6379/0"
   ```

3. **Run with Docker Compose:**
   ```bash
   docker-compose up --build
   ```

4. **Access the Application:**
   - Frontend: `http://localhost:3000`
   - Backend API Docs: `http://localhost:8000/docs`

## Usage

1. Open `http://localhost:3000` in your browser.
2. Upload a PDF file using the dropzone.
3. Wait for the processing to finish (you will see real-time updates via WebSockets).
4. Enjoy the visual novel experience in the split-screen reader!

## Walkthrough of Recent Improvements

During recent iterations, the following structural and logic fixes were made:
- **Celery Worker Configuration**: Removed the eager execution flags in `celery_app.py` to correctly implement the Producer-Consumer pattern using Redis as the message broker, preventing the main thread from blocking.
- **Frontend State Access**: Fixed a state access bug in `Uploader.jsx` allowing the frontend to smoothly transition to the reader view upon completion.
- **LLM Validation Test**: Implemented `test_llm_memory.py` to validate that the LLM successfully parses the character bible and accurately injects character appearances into Stable Diffusion prompts.

## Tags
`#ai` `#visual-novel` `#fastapi` `#react` `#stable-diffusion` `#pdf-parser` `#celery` `#redis` `#llm`

## License
MIT License. See `LICENSE` for more information.
