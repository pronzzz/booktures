# Contributing to Booktures

Thanks for helping. Bug reports, new providers, parser fixes and UI polish are all welcome.

## Setup

```bash
git clone https://github.com/pronzzz/booktures && cd booktures
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # add ,local for the SD-Turbo provider
(cd frontend && npm ci && npm run build)
```

To work on the app, run the Python server and the Vite dev server side by side:

```bash
booktures serve --no-browser --data-dir ./.dev-library
cd frontend && npm run dev          # http://localhost:5173, forwards /api to :8765
```

## Layout

| Path | What's there |
| --- | --- |
| `booktures/plugins/` | The public plugin API (`TextProvider`, `ImageProvider`, `Field`, `register`) and the registry |
| `booktures/providers/` | Built-in story models (`text/`) and illustrators (`image/`) |
| `booktures/pipeline/` | Ingestion, prompts, styles, safety, text similarity |
| `booktures/engine.py` | The job runner that turns a book into pictures |
| `booktures/api.py`, `app.py`, `cli.py` | HTTP API, FastAPI app, command line |
| `frontend/` | The React + Tailwind web app (builds into `booktures/web/`) |
| `plugins/` | Example drop-in plugins |
| `tests/` | Pytest suite; providers are tested against a local mock server |

## Pull requests

1. Branch from `main`.
2. Add or update tests. `pytest` must pass with no network access and no GPU.
3. If you change the UI, run `npm run build` in `frontend/` and check it in a browser at desktop and phone widths.
4. Update `README.md`, `docs/PLUGINS.md` or `CHANGELOG.md` if behaviour changes.

### Adding a provider

Start with [docs/PLUGINS.md](docs/PLUGINS.md). Keep a new provider as a plugin, either a drop-in file or its own package, unless most people would use it. Built-in providers need a mock-server test in `tests/test_providers.py`, and any heavy dependency belongs in an optional extra.

## Reporting bugs

Open an [issue](https://github.com/pronzzz/booktures/issues) with:

- your OS and Python version;
- the story model and illustrator you used;
- the error from the reader's **Progress** tab or the terminal.

For parsing problems, a small sample file helps a lot.

By contributing you agree that your work is released under the [MIT License](LICENSE).
