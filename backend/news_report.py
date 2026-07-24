"""
news_report.py — OX-NEWS-REPORT-1
=================================
Deterministic news gathering + report generation, SEPARATED from the agent loop.
The agent (or the API/UI) only decides the topics; this module does the rest in
CODE — gather real headlines (Google News RSS), rank by IMPORTANCE (reputable
source tier + recency), de-duplicate, and render a clean readable HTML report
from a fixed template. Output quality is constant — no model freestyle.

Priority: news quality + importance, not visual flair.
Dependency-free (stdlib only).
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import html
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

# Source-importance tiers (substring match on source/title, case-insensitive).
# Higher = more authoritative → ranked first.
_SOURCE_TIER: Dict[str, int] = {
    # global tier-1 financial / wire
    "reuters": 4, "bloomberg": 4, "financial times": 4, "ft.com": 4,
    "wall street journal": 4, "wsj": 4, "the economist": 4,
    "cnbc": 3, "associated press": 3, "ap news": 3, "bbc": 3, "the guardian": 3,
    "cnn": 3, "forbes": 3, "nikkei": 3, "marketwatch": 3, "yahoo finance": 2,
    "coindesk": 3, "cointelegraph": 2, "coinbase": 2, "binance": 2, "the block": 3,
    # thai tier-1 (general + financial)
    "thairath": 4, "ไทยรัฐ": 4, "bangkok post": 4, "กรุงเทพธุรกิจ": 4,
    "ฐานเศรษฐกิจ": 3, "ประชาชาติ": 3, "the standard": 3, "มติชน": 3, "ข่าวสด": 3,
    "posttoday": 3, "ผู้จัดการ": 3, "infoquest": 3, "อินโฟเควสท์": 3,
    "set.or.th": 3, "ตลาดหลักทรัพย์": 3, "efinancethai": 3, "ทันหุ้น": 2,
    "line today": 2, "sanook": 1, "kapook": 1,
}


def _tier(item: Dict[str, Any]) -> int:
    s = (str(item.get("source", "")) + " " + str(item.get("title", ""))).lower()
    return max((w for k, w in _SOURCE_TIER.items() if k in s), default=0)


def _ts(pub: str) -> float:
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z",
                "%a, %d %b %Y %H:%M:%S"):
        try:
            return time.mktime(time.strptime(pub.strip(), fmt))
        except Exception:
            continue
    return 0.0


def importance(item: Dict[str, Any]) -> float:
    """Higher = more important: reputable source dominates, recency breaks ties."""
    tier = _tier(item)
    ts = _ts(item.get("date", ""))
    age_days = (time.time() - ts) / 86400 if ts else 5.0
    recency = max(0.0, 4.0 - age_days)        # full credit < 1 day, fades over ~4 days
    return tier * 3.0 + recency


def _gnews(topic: str, lang: str = "th", n: int = 16) -> List[Dict[str, Any]]:
    hl, gl, ceid = (("en", "US", "US:en") if lang.startswith("en")
                    else ("th", "TH", "TH:th"))
    url = (f"https://news.google.com/rss/search?q={urllib.parse.quote(topic)}"
           f"&hl={hl}&gl={gl}&ceid={ceid}")
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=14) as r:
        root = ET.fromstring(r.read().decode("utf-8", "replace"))
    out: List[Dict[str, Any]] = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        if not title:
            continue
        src_el = it.find("source")
        out.append({
            "title": title,
            "link": (it.findtext("link") or "").strip(),
            "date": (it.findtext("pubDate") or "").strip(),
            "source": (src_el.text.strip() if src_el is not None and src_el.text else ""),
            "summary": re.sub(r"<[^>]+>", "", it.findtext("description") or "").strip(),
            "topic": topic,
        })
        if len(out) >= n:
            break
    return out


def gather(topics: List[str], lang: str = "th", per_topic: int = 6) -> List[Dict[str, Any]]:
    """Per topic: fetch → de-dupe → rank by importance → keep top N."""
    sections = []
    for t in topics:
        try:
            items = _gnews(t, lang, per_topic * 3)
        except Exception as e:
            sections.append({"topic": t, "items": [], "error": str(e)[:80]})
            continue
        seen, uniq = set(), []
        for it in items:
            key = re.sub(r"\W+", "", it["title"].lower())[:48]
            if key in seen:
                continue
            seen.add(key)
            uniq.append(it)
        uniq.sort(key=importance, reverse=True)
        sections.append({"topic": t, "items": uniq[:per_topic]})
    return sections


def build_html(title: str, sections: List[Dict[str, Any]]) -> str:
    esc = html.escape
    parts: List[str] = []
    for sec in sections:
        parts.append(f"<h2>{esc(sec['topic'])}</h2>")
        items = sec.get("items", [])
        if not items:
            parts.append(f"<p class='empty'>— ไม่พบข่าว{' ('+esc(sec['error'])+')' if sec.get('error') else ''} —</p>")
            continue
        parts.append("<ol>")
        for it in items:
            meta = " · ".join(x for x in [esc(it.get("source", "")),
                                          esc(it.get("date", "")[:25]),
                                          f"★{_tier(it)}" if _tier(it) else ""] if x)
            summ = f"<div class='sum'>{esc(it['summary'][:260])}</div>" if it.get("summary") else ""
            link = esc(it.get("link", "") or "#")
            parts.append(f"<li><a href='{link}' target='_blank' rel='noopener'>{esc(it['title'])}</a>"
                         f"<div class='meta'>{meta}</div>{summ}</li>")
        parts.append("</ol>")
    n = sum(len(s.get("items", [])) for s in sections)
    body = "\n".join(parts)
    return f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<style>
body{{font-family:system-ui,'Segoe UI',sans-serif;max-width:880px;margin:24px auto;padding:0 18px;line-height:1.65;color:#1a1a1a}}
h1{{font-size:23px;margin:0 0 4px}}
h2{{font-size:16px;margin:30px 0 8px;border-bottom:2px solid #d4ac60;padding-bottom:5px}}
a{{color:#0b5fff;text-decoration:none;font-weight:600}}a:hover{{text-decoration:underline}}
ol{{padding-left:22px}}li{{margin-bottom:13px}}
.meta{{color:#666;font-size:12px;margin:2px 0}}.sum{{color:#333;font-size:13px;margin:4px 0 0}}
.empty{{color:#999}}.gen{{color:#888;font-size:12px;margin-bottom:6px}}
@media(prefers-color-scheme:dark){{body{{background:#13151a;color:#e8e6e0}}a{{color:#7db1ff}}.sum{{color:#cfcfcf}}.meta{{color:#9a9a9a}}}}
</style></head><body>
<h1>{esc(title)}</h1>
<div class="gen">อัปเดต {time.strftime('%Y-%m-%d %H:%M')} · {n} ข่าว · {len(sections)} หัวข้อ · แหล่ง: Google News — จัดอันดับตามความสำคัญของแหล่ง (★) + ความใหม่</div>
{body}
</body></html>"""


def make_report(topics: List[str], title: str = "สรุปข่าวสำคัญ", lang: str = "th",
                per_topic: int = 6, out_path: str = None) -> Dict[str, Any]:
    if isinstance(topics, str):
        topics = [t.strip() for t in re.split(r"[,\n;|]", topics) if t.strip()]
    topics = [t for t in (topics or []) if t][:10] or ["ข่าวเศรษฐกิจ"]
    sections = gather(topics, lang=lang, per_topic=per_topic)
    h = build_html(title, sections)
    if out_path:
        d = os.path.dirname(out_path)
        if d:
            os.makedirs(d, exist_ok=True)
        open(out_path, "w", encoding="utf-8").write(h)
    return {"title": title, "topics": topics, "path": out_path,
            "count": sum(len(s.get("items", [])) for s in sections),
            "sections": [{"topic": s["topic"], "n": len(s.get("items", [])),
                          "top": [{"title": i["title"], "source": i["source"],
                                   "tier": _tier(i), "link": i["link"]}
                                  for i in s.get("items", [])[:3]]} for s in sections]}


if __name__ == "__main__":
    import json
    r = make_report(["ราคาทองคำ", "bitcoin", "ข่าวเศรษฐกิจไทย"],
                    title="สรุปข่าวการเงิน", out_path="news_test.html")
    print(json.dumps(r, ensure_ascii=False, indent=2)[:1500])
