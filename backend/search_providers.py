"""
search_providers.py — the Search Provider Layer (ADR-0013 pattern, applied to search)
=====================================================================================
**Operational Infrastructure, not Cognitive Logic.** `web_search`'s public interface and
semantics are unchanged; only the *External Provider Layer* behind it is factored into
swappable `SearchProvider`s — exactly as models are swappable Capability Providers under
ADR-0013. A keyed provider (Brave / Tavily / Serper), when its API key is present in the
environment, is tried FIRST for reliable, deterministic results; the free providers keep
their EXACT prior order, so with NO key configured the behaviour is byte-identical to before.

Change class (Commander ruling 2026-07-21, under Standing Order 007): Operational
Infrastructure Maintenance — Interface unchanged · Semantics unchanged · Evidence unchanged
· Determinism improved. Not an architectural change; no ADR required.

Keys are set by the operator (never hard-coded, never handled by an agent):
    BRAVE_SEARCH_API_KEY · TAVILY_API_KEY · SERPER_API_KEY
A provider with no key is silently skipped (not an error) — so the failure evidence with no
keys is identical to the pre-refactor behaviour.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request as ureq
from typing import Dict, List, Tuple

_UA_CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
_UA_FIREFOX = ("Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0")

Item = Dict[str, str]   # {"title","url","snippet", optional "tag"}

_SEARCH_KEYS = ("BRAVE_SEARCH_API_KEY", "TAVILY_API_KEY", "SERPER_API_KEY")


def _load_search_keys_from_dotenv() -> None:
    """Best-effort: the main.py process does not call load_dotenv, so pull ONLY the three
    search keys from the repo .env if they are not already set. Dependency-free; never
    overrides an existing env value; silent on any error. Scope: search keys only."""
    if all(os.environ.get(k) for k in _SEARCH_KEYS):
        return
    for base in (os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # repo root
                 os.path.dirname(os.path.abspath(__file__))):                  # backend/
        path = os.path.join(base, ".env")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k in _SEARCH_KEYS and v and not os.environ.get(k):
                        os.environ[k] = v
        except Exception:
            pass


_load_search_keys_from_dotenv()


# ── transport ─────────────────────────────────────────────────────────────────
def _fetch_html(url: str, headers=None, timeout=10) -> str:
    hdr = {"User-Agent": _UA_CHROME, "Accept": "text/html,*/*",
           "Accept-Language": "en-US,en;q=0.9,th;q=0.8"}
    if headers:
        hdr.update(headers)
    with ureq.urlopen(ureq.Request(url, headers=hdr), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _fetch_json(url: str, headers=None, timeout=10, data: bytes = None):
    hdr = {"User-Agent": _UA_CHROME, "Accept": "application/json"}
    if headers:
        hdr.update(headers)
    req = ureq.Request(url, headers=hdr, data=data, method=("POST" if data else "GET"))
    with ureq.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _strip(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


# ── the exact output format web_search has always produced ─────────────────────
def format_results(items: List[Item]) -> List[str]:
    out: List[str] = []
    for i, it in enumerate(items):
        tag = f" [{it['tag']}]" if it.get("tag") else ""
        out.append(f"{i+1}. **{it.get('title','')}**{tag}\n"
                   f"   🔗 {it.get('url','')[:140]}\n   {it.get('snippet','')[:240]}")
    return out


# ── provider base ──────────────────────────────────────────────────────────────
class SearchProvider:
    name = "provider"      # label shown as the winning source
    short = "provider"     # error prefix
    def available(self) -> bool:
        return True
    def search(self, query: str, n: int, q_enc: str) -> Tuple[List[Item], str]:
        raise NotImplementedError


# ── keyed providers (tried first when configured — reliable + deterministic) ────
class BraveApiProvider(SearchProvider):
    name = "Brave API"; short = "BraveAPI"
    def available(self) -> bool:
        return bool(os.environ.get("BRAVE_SEARCH_API_KEY"))
    def search(self, query, n, q_enc):
        key = os.environ["BRAVE_SEARCH_API_KEY"]
        url = f"https://api.search.brave.com/res/v1/web/search?q={q_enc}&count={min(n,20)}"
        d = _fetch_json(url, headers={"X-Subscription-Token": key,
                                      "Accept": "application/json"}, timeout=10)
        items = [{"title": r.get("title", ""), "url": r.get("url", ""),
                  "snippet": r.get("description", "")}
                 for r in (d.get("web", {}).get("results", []) or [])[:n]]
        return items, self.name


class TavilyProvider(SearchProvider):
    name = "Tavily"; short = "Tavily"
    def available(self) -> bool:
        return bool(os.environ.get("TAVILY_API_KEY"))
    def search(self, query, n, q_enc):
        body = json.dumps({"api_key": os.environ["TAVILY_API_KEY"], "query": query,
                           "max_results": min(n, 10)}).encode()
        d = _fetch_json("https://api.tavily.com/search",
                        headers={"Content-Type": "application/json"}, timeout=15, data=body)
        items = [{"title": r.get("title", ""), "url": r.get("url", ""),
                  "snippet": r.get("content", "")}
                 for r in (d.get("results", []) or [])[:n]]
        return items, self.name


class SerperProvider(SearchProvider):
    name = "Serper"; short = "Serper"
    def available(self) -> bool:
        return bool(os.environ.get("SERPER_API_KEY"))
    def search(self, query, n, q_enc):
        body = json.dumps({"q": query, "num": min(n, 10)}).encode()
        d = _fetch_json("https://google.serper.dev/search",
                        headers={"X-API-KEY": os.environ["SERPER_API_KEY"],
                                 "Content-Type": "application/json"}, timeout=15, data=body)
        items = [{"title": r.get("title", ""), "url": r.get("link", ""),
                  "snippet": r.get("snippet", "")}
                 for r in (d.get("organic", []) or [])[:n]]
        return items, self.name


# ── free providers (keyless fallback — kept in EXACT prior order) ───────────────
class DuckDuckGoLiteProvider(SearchProvider):
    name = "DuckDuckGo Lite"; short = "DDG-Lite"
    def search(self, query, n, q_enc):
        html = _fetch_html(f"https://lite.duckduckgo.com/lite/?q={q_enc}", timeout=10)
        links = re.findall(r'<a[^>]+class="result-link"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                           html, re.DOTALL)
        snips = re.findall(r'class="result-snippet"[^>]*>(.*?)</td>', html, re.DOTALL)
        items = []
        for i, (href, title) in enumerate(links[:n]):
            t = _strip(title)
            if t:
                items.append({"title": t, "url": href,
                              "snippet": _strip(snips[i] if i < len(snips) else "")})
        return items, self.name


class DuckDuckGoHtmlProvider(SearchProvider):
    name = "DuckDuckGo HTML"; short = "DDG-HTML"
    def search(self, query, n, q_enc):
        html = _fetch_html(f"https://html.duckduckgo.com/html/?q={q_enc}",
                           headers={"User-Agent": _UA_FIREFOX}, timeout=10)
        titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)
        snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|span)', html, re.DOTALL)
        hrefs = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]*)"', html)
        items = []
        for i, t in enumerate(titles[:n]):
            tc = _strip(t)
            if tc:
                items.append({"title": tc, "url": hrefs[i] if i < len(hrefs) else "",
                              "snippet": _strip(snips[i] if i < len(snips) else "")})
        return items, self.name


class SearxngProvider(SearchProvider):
    name = "SearXNG"; short = "SearXNG"
    # public instances go up/down/rate-limit constantly — this is exactly why the
    # keyed providers exist above; kept only as a best-effort keyless fallback.
    endpoints = [
        "https://searx.be/search",
        "https://search.inetol.net/search",
        "https://baresearch.org/search",
        "https://priv.au/search",
        "https://searx.tiekoetter.com/search",
    ]
    def search(self, query, n, q_enc):
        errs = []
        for endpoint in self.endpoints:
            try:
                url = f"{endpoint}?q={q_enc}&format=json&language=auto"
                data = _fetch_json(url, timeout=8)
                items = [{"title": (it.get("title") or "").strip(),
                          "url": (it.get("url") or "").strip(),
                          "snippet": (it.get("content") or "").strip()}
                         for it in (data.get("results", []) or [])[:n]]
                items = [it for it in items if it["title"]]
                if items:
                    return items, f"SearXNG ({endpoint.split('/')[2]})"
            except Exception as e:
                errs.append(f"{endpoint.split('/')[2]} {type(e).__name__}")
        raise RuntimeError(f"{len(self.endpoints)} instances failed [{'; '.join(errs[:4])}]")


class WikipediaProvider(SearchProvider):
    name = "Wikipedia"; short = "Wiki"
    def search(self, query, n, q_enc):
        langs = ["th", "en"] if re.search(r"[฀-๿]", query) else ["en", "th"]
        for lang in langs:
            try:
                url = (f"https://{lang}.wikipedia.org/w/api.php?action=opensearch"
                       f"&search={q_enc}&limit={n}&namespace=0&format=json")
                d = _fetch_json(url, timeout=8)
                if isinstance(d, list) and len(d) == 4:
                    titles, descs, urls = d[1], d[2], d[3]
                    items = []
                    for i in range(min(len(titles), n)):
                        if titles[i]:
                            items.append({"title": titles[i], "tag": f"Wikipedia {lang.upper()}",
                                          "url": urls[i] if i < len(urls) else "",
                                          "snippet": descs[i] if i < len(descs) else ""})
                    if items:
                        return items, f"Wikipedia {lang.upper()}"
            except Exception:
                continue
        return [], self.name


class BraveScrapeProvider(SearchProvider):
    name = "Brave Search"; short = "Brave"
    def search(self, query, n, q_enc):
        html = _fetch_html(f"https://search.brave.com/search?q={q_enc}",
                           headers={"User-Agent": _UA_FIREFOX}, timeout=10)
        blocks = re.findall(
            r'<a[^>]+href="(https?://[^"]+)"[^>]*>\s*.*?<div[^>]*class="[^"]*title[^"]*"[^>]*>'
            r'(.*?)</div>.*?<(?:div|p)[^>]*class="[^"]*snippet-content[^"]*"[^>]*>(.*?)</(?:div|p)>',
            html, re.DOTALL)
        items = []
        for href, title, snip in blocks[:n]:
            t = _strip(title)
            if t and href.startswith("http"):
                items.append({"title": t, "url": href, "snippet": _strip(snip)})
        return items, self.name


class DdgInstantAnswerProvider(SearchProvider):
    name = "DDG Instant Answer"; short = "DDG-API"
    def search(self, query, n, q_enc):
        d = _fetch_json(f"https://api.duckduckgo.com/?q={q_enc}&format=json"
                        f"&no_html=1&skip_disambig=1", timeout=10)
        items = []
        if d.get("Abstract"):
            items.append({"title": d.get("Heading", query),
                          "url": d.get("AbstractURL", ""), "snippet": d["Abstract"]})
        for rel in (d.get("RelatedTopics", []) or [])[:n - len(items)]:
            if isinstance(rel, dict) and rel.get("Text"):
                items.append({"title": rel["Text"][:60], "url": rel.get("FirstURL", ""),
                              "snippet": rel["Text"]})
        return items, self.name


# ── the registry (fixed, deterministic order: keyed first, then prior free order) ─
PROVIDERS: List[SearchProvider] = [
    BraveApiProvider(), TavilyProvider(), SerperProvider(),   # keyed — reliable
    DuckDuckGoLiteProvider(), DuckDuckGoHtmlProvider(),        # free — prior order preserved
    SearxngProvider(), WikipediaProvider(),
    BraveScrapeProvider(), DdgInstantAnswerProvider(),
]


def configured() -> List[str]:
    """Which keyed providers are active (for diagnostics / the UI)."""
    return [p.name for p in PROVIDERS if p.short in ("BraveAPI", "Tavily", "Serper")
            and p.available()]


def search(query: str, n: int) -> Tuple[List[str], str, List[str]]:
    """Router: try each available provider in order; return the first non-empty result set
    as formatted strings, plus the winning source label and the list of provider errors.
    Unconfigured keyed providers are skipped silently (not counted as errors)."""
    q_enc = urllib.parse.quote(query)
    errors: List[str] = []
    for p in PROVIDERS:
        try:
            if not p.available():
                continue
            items, label = p.search(query, n, q_enc)
            items = [it for it in items if it.get("title")][:n]
            if items:
                return format_results(items), label, errors
        except Exception as e:
            errors.append(f"{p.short}: {type(e).__name__}: {str(e)[:60]}")
    return [], "", errors
