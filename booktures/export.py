"""Export a finished book as one self-contained HTML file (images embedded)."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from booktures import __version__
from booktures.db import Book

MIME = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Booktures</title>
<style>
:root{--bg:#0f0d0b;--panel:#17140f;--ink:#efe6d6;--muted:#a3977f;--accent:#e2a65a;--line:#2c271f}
@media (prefers-color-scheme: light){:root{--bg:#f6f0e4;--panel:#ede4d3;--ink:#2b2318;--muted:#6f6350;--accent:#9a5a12;--line:#d8ccb5}}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink)}
body{font:18px/1.75 "Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}
.wrap{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);min-height:100vh}
.text{padding:8vh 6vw 50vh}.pic{position:sticky;top:0;height:100vh;background:#000;overflow:hidden}
.pic img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:0;transition:opacity .9s ease}
.pic img.on{opacity:1}.cap{position:absolute;left:0;right:0;bottom:0;padding:32px;font:italic 14px/1.5 system-ui,sans-serif;color:#d9cfbd;background:linear-gradient(transparent,rgba(0,0,0,.85))}
h1{font-size:2.6rem;line-height:1.1;margin:0 0 .3em}.by{color:var(--muted);margin:0 0 2em}
.page{margin:0 0 5rem;max-width:38rem}.num{font:600 11px/1 system-ui,sans-serif;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);display:flex;gap:12px;align-items:center;margin-bottom:1rem}
.num:after{content:"";flex:1;height:1px;background:var(--line)}.page p{margin:0 0 1em}
.cast{border:1px solid var(--line);background:var(--panel);border-radius:14px;padding:18px 22px;margin:0 0 4rem;font:14px/1.6 system-ui,sans-serif}
.cast b{color:var(--accent)}.mobile-pic{display:none}
footer{font:12px system-ui,sans-serif;color:var(--muted);margin-top:4rem}
@media (max-width:860px){.wrap{display:block}.pic{display:none}.mobile-pic{display:block;width:100%;border-radius:12px;margin:0 0 1rem}.text{padding:24px 16px 20vh}}
</style></head><body>
<div class="wrap"><main class="text">
<h1>__TITLE__</h1><p class="by">__BYLINE__</p>
__CAST__
__PAGES__
<footer>Illustrated with Booktures __VERSION__ · style: __STYLE__</footer>
</main><aside class="pic" id="pic">__IMAGES__<div class="cap" id="cap"></div></aside></div>
<script>
const caps=__CAPTIONS__;const imgs=[...document.querySelectorAll('#pic img')];
function show(k){imgs.forEach(i=>i.classList.toggle('on',i.dataset.key===k));const c=caps[k];document.getElementById('cap').textContent=c||'';}
const io=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting&&e.target.dataset.key)show(e.target.dataset.key)})},{rootMargin:'-45% 0px -45% 0px'});
document.querySelectorAll('.page').forEach(p=>io.observe(p));if(imgs[0])show(imgs[0].dataset.key);
</script></body></html>"""


def export_html(book: Book, image_dir: Path) -> str:
    images: dict[str, str] = {}
    captions: dict[str, str] = {}
    page_html = []
    for p in book.pages:
        key = ""
        if p.image_file and (image_dir / p.image_file).exists():
            key = p.image_file
            if key not in images:
                ext = key.rsplit(".", 1)[-1]
                data = base64.b64encode((image_dir / key).read_bytes()).decode()
                images[key] = f"data:{MIME.get(ext, 'image/png')};base64,{data}"
                captions[key] = p.scene_summary or ""
        paras = "".join(f"<p>{html.escape(t)}</p>" for t in p.text.split("\n\n") if t.strip())
        mobile = f'<img class="mobile-pic" src="{images[key]}" alt="">' if key else ""
        page_html.append(
            f'<section class="page" data-key="{html.escape(key)}"><div class="num">Page {p.number}</div>{mobile}{paras}</section>'
        )
    cast = ""
    if book.character_bible:
        rows = "".join(
            f"<div><b>{html.escape(n)}</b> — {html.escape(d)}</div>" for n, d in book.character_bible.items()
        )
        cast = f'<div class="cast">{rows}</div>'
    tags = "".join(f'<img data-key="{html.escape(k)}" src="{v}" alt="">' for k, v in images.items())
    byline = html.escape(book.author or (book.genre.title() if book.genre else "An illustrated edition"))
    return (
        TEMPLATE.replace("__TITLE__", html.escape(book.title))
        .replace("__BYLINE__", byline)
        .replace("__CAST__", cast)
        .replace("__PAGES__", "\n".join(page_html))
        .replace("__IMAGES__", tags)
        .replace("__CAPTIONS__", json.dumps(captions).replace("</", "<\\/"))
        .replace("__STYLE__", html.escape(book.global_style))
        .replace("__VERSION__", __version__)
    )
