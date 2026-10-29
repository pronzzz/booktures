# Writing a Booktures plugin

Booktures uses two kinds of model, and you can plug in your own version of either:

| Kind | Base class | You implement | What it does |
| --- | --- | --- | --- |
| **Story model** | `TextProvider` | `complete_json(system, user) -> dict` | Reads the book, builds the character bible, and writes a picture brief for every page |
| **Illustrator** | `ImageProvider` | `generate(request) -> bytes` | Turns a brief into a PNG, JPEG or WebP |

A plugin is one Python class. Booktures builds its settings form, its "Check connection" and "Try it" buttons, retries, safety screening and progress reporting for you.

- [Quick start](#quick-start)
- [A story model](#a-story-model)
- [An illustrator](#an-illustrator)
- [Settings fields](#settings-fields)
- [Errors, checks and dependencies](#errors-checks-and-dependencies)
- [Where plugins are loaded from](#where-plugins-are-loaded-from)
- [Publishing a plugin as a package](#publishing-a-plugin-as-a-package)
- [Testing your plugin](#testing-your-plugin)

## Quick start

1. Make the plugin folder (Booktures creates it on first run):

   ```bash
   mkdir -p ~/.booktures/plugins
   ```

2. Save this as `~/.booktures/plugins/my_llm.py`:

   ```python
   import json
   import httpx
   from booktures.plugins import Field, TextProvider, register

   @register
   class MyLLM(TextProvider):
       id = "my-llm"
       name = "My LLM"
       description = "My company's internal model."
       fields = [
           Field("url", "Endpoint", type="url", default="http://localhost:9000/generate"),
           Field("api_key", "API key", type="secret", env="MY_LLM_KEY"),
       ]

       def complete_json(self, system: str, user: str) -> dict:
           resp = httpx.post(
               self.config["url"],
               headers={"Authorization": f"Bearer {self.config['api_key']}"},
               json={"system": system, "prompt": user, "format": "json"},
               timeout=120,
           )
           resp.raise_for_status()
           return json.loads(resp.json()["text"])
   ```

3. Restart Booktures. "My LLM" now appears under **Models & plugins → Story model**, with a form for the endpoint and key.

The repo has a complete working example in [`plugins/hf_inference.py`](../plugins/hf_inference.py), an illustrator for Hugging Face Inference Providers.

## A story model

Subclass `TextProvider` and implement one method:

```python
def complete_json(self, system: str, user: str) -> dict:
    """Send a system prompt and a user message; return the model's reply parsed as a JSON object."""
```

Booktures writes the prompts and checks the replies. It calls `complete_json` in two ways.

**1. Once per book, to analyze it.** The user message holds the opening of the book (14,000 characters by default). Return a dict with:

```json
{
  "title": "The Lantern Keeper of Gull Point",
  "author": "",
  "genre": "sea adventure",
  "setting": "a lighthouse on a stormy northern coast, 19th century",
  "global_art_style": "atmospheric gouache book illustration, textured paper",
  "character_bible": {
    "Mara": "wiry girl of twelve, cropped copper hair, freckles, yellow oilskin coat",
    "Tobias": "old man, long white beard, brass spectacles, navy peacoat"
  }
}
```

**2. Once per page, to describe the scene.** The system prompt includes the character bible, the art style and a summary of the previous page. Return:

```json
{
  "scene_summary": "Mara signals a boat away from the rocks with a lantern.",
  "visual_description": "a girl in a yellow oilskin holding a brass lantern up to the lighthouse glass, storm waves below",
  "characters": ["Mara"],
  "new_characters": {"Elias": "young man, dark braid, black cloak"},
  "mood": "tense"
}
```

You don't have to get the shape exactly right. Booktures accepts common alternatives (`summary`, `image_prompt`, `characters` as a comma-separated string), trims long values, matches character names regardless of case, and ignores keys it doesn't know. If the model wraps its JSON in code fences or `<think>` tags, use `booktures.pipeline.prompts.parse_json_loose(text)` to extract it.

### Going further

- **Override `analyze_book(excerpt)` or `describe_scene(page_text, ctx)`** if your model needs its own prompts, or isn't an LLM at all. `ctx` is a `SceneContext` with `previous_summary`, `character_bible`, `global_style`, `setting`, `page_number` and `total_pages`. Return the dicts shown above.
- **Override `moderate(text) -> bool | None`** if your service has a moderation endpoint. Return `False` to block a scene, `True` to allow it, or `None` (the default) to rely on Booktures' built-in keyword screen.

## An illustrator

Subclass `ImageProvider` and implement:

```python
def generate(self, request: ImageRequest) -> bytes:
    """Return the encoded image (PNG, JPEG or WebP)."""
```

`ImageRequest` has these fields:

| Field | Meaning |
| --- | --- |
| `prompt` | The full prompt: style, scene, then the bible traits of the characters in it, then mood |
| `negative_prompt` | Things to avoid (text, watermarks, extra limbs…). Ignore it if your model doesn't take one |
| `width`, `height` | Requested size from Settings → Pipeline. Round or clamp them to what your model supports |
| `seed` | Book seed + page number, so re-runs are repeatable |
| `style` | The art style on its own, for APIs that take style separately |
| `hints` | `{"characters": [...], "mood": "..."}`, for providers that can use them |

Example:

```python
import httpx
from booktures.plugins import Field, ImageProvider, ImageRequest, register

@register
class MyPainter(ImageProvider):
    id = "my-painter"
    name = "My painter"
    local = True  # never sends book text off this machine
    fields = [Field("url", "Server URL", type="url", default="http://127.0.0.1:7000")]

    def generate(self, request: ImageRequest) -> bytes:
        resp = httpx.post(
            f"{self.config['url']}/txt2img",
            json={"prompt": request.prompt, "seed": request.seed,
                  "width": request.width // 64 * 64, "height": request.height // 64 * 64},
            timeout=300,
        )
        resp.raise_for_status()
        return resp.content
```

Booktures detects the file type from the bytes, saves the image, retries failed pages, and skips repeated scenes.

## Settings fields

Each `Field` becomes one control in the settings form. Values are saved to `~/.booktures/settings.json` (readable only by you) and are available as `self.config[key]`.

```python
Field(
    key="model",                 # self.config["model"]
    label="Model",               # shown above the control
    type="string",               # string | secret | url | number | boolean | select | textarea
    default="gpt-5-mini",        # used when the user leaves it empty
    help="Shown under the field.",
    placeholder="Shown in the empty input.",
    options=["a", "b"],          # for type="select"
    env="MY_MODEL",              # read from this environment variable when the field is empty
    required=False,
    sets={"a": {"url": "https://a.example/v1"}},  # for selects: picking "a" fills in other fields
)
```

- **`secret`** values are never sent back to the browser in full: the UI shows `••••••abcd`. Sending that mask back leaves the stored key unchanged.
- **`number`** values arrive as `int` or `float`; **`boolean`** values arrive as `bool`.
- Call **`self.require("api_key")`** to get a value or raise a clear "'API key' is not set" error.

## Errors, checks and dependencies

- **Raise `ProviderError("message")`** for failures the user should see. The message appears in the reader's Progress tab and next to the failed page. Other exceptions are caught too, but with less helpful text.
- **Override `check(self) -> str`** to back the "Check connection" button. Do something cheap (list models, read the account), then return a short success message or raise `ProviderError`. Call `super().check()` first so missing packages are reported.
- **Declare optional packages** with `requires = ["torch", "diffusers"]` and `install_hint = 'pip install "booktures[local]"'`. If they're missing, the provider still appears in Settings, marked "Needs install", with that hint, instead of breaking the app.
- **Set `local = True`** when book text never leaves the machine. The UI labels your plugin Local or Cloud based on this.
- **Calls are blocking and run in a worker thread.** Plain `httpx` or `requests` is fine; you don't need asyncio. One book is processed at a time, so you don't need to worry about concurrency limits.

## Where plugins are loaded from

When Booktures starts, it loads providers in this order. A later provider with the same `kind` and `id` replaces an earlier one, so you can override a built-in.

1. Built-in providers.
2. Installed packages that declare a `booktures.plugins` entry point.
3. `.py` files in `~/.booktures/plugins/` (or `$BOOKTURES_HOME/plugins/`). Files whose name starts with `_` are skipped.
4. Every folder passed with `--plugins DIR` or listed in `$BOOKTURES_PLUGINS` (separated by `:`, or `;` on Windows).

A plugin that fails to import doesn't stop the app. Its error and traceback appear under **Models & plugins → Plugins → Load errors**, and in the terminal output of `booktures providers`.

## Publishing a plugin as a package

To share a plugin with `pip install`, add an entry point to its `pyproject.toml`:

```toml
[project]
name = "booktures-myllm"
dependencies = ["booktures>=2.0"]

[project.entry-points."booktures.plugins"]
my-llm = "booktures_myllm:MyLLM"   # a provider class, or a module whose classes use @register
```

## Testing your plugin

```bash
booktures --plugins ./my-plugins providers          # is it listed? any load errors?
booktures --plugins ./my-plugins convert book.epub --text my-llm --image sketchbook --max-pages 3 -o out.html
```

In the web app, **Try it** runs one real call: story models describe a sample scene, and illustrators paint a sample picture.

For unit tests, instantiate the class with a config dict and call it directly:

```python
from booktures.plugins import ImageRequest
from my_plugin import MyPainter

def test_paints():
    data = MyPainter({"url": "http://127.0.0.1:7000"}).generate(ImageRequest(prompt="a red fox"))
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
```
