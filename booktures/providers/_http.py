"""HTTP helpers shared by the built-in providers."""

from __future__ import annotations

import httpx

from booktures import __version__
from booktures.plugins import ProviderError

USER_AGENT = f"Booktures/{__version__} (+https://github.com/pronzzz/booktures)"


def _error(name: str, resp: httpx.Response) -> ProviderError:
    detail = ""
    try:
        body = resp.json()
        err = body.get("error", body) if isinstance(body, dict) else body
        if isinstance(err, dict):
            detail = err.get("message") or err.get("detail") or str(err)
        else:
            detail = str(err)
    except ValueError:
        detail = resp.text
    detail = " ".join(str(detail).split())[:300]
    hint = {
        401: " Check the API key.",
        403: " The key is not allowed to use this model.",
        404: " Check the URL and model name.",
        429: " Rate limited or out of credit.",
    }.get(resp.status_code, "")
    return ProviderError(f"{name}: HTTP {resp.status_code}. {detail}{hint}".strip())


def request(
    name: str,
    method: str,
    url: str,
    *,
    timeout: float = 120.0,
    headers: dict | None = None,
    **kwargs,
) -> httpx.Response:
    hdrs = {"User-Agent": USER_AGENT, **(headers or {})}
    try:
        resp = httpx.request(method, url, headers=hdrs, timeout=timeout, follow_redirects=True, **kwargs)
    except httpx.ConnectError as exc:
        raise ProviderError(f"{name}: could not connect to {url}. Is the server running?") from exc
    except httpx.TimeoutException as exc:
        raise ProviderError(f"{name}: request to {url} timed out after {timeout:.0f}s.") from exc
    except httpx.HTTPError as exc:
        raise ProviderError(f"{name}: {exc}") from exc
    if resp.status_code >= 400:
        raise _error(name, resp)
    return resp


def join(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + path.lstrip("/")
