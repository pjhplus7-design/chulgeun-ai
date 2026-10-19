"""1단계: RSS에서 최근 주요 뉴스를 모아 점수순으로 저장합니다.
여러 언론사가 함께 다룬 사건일수록 점수가 높아집니다.

사용법:
    python collect.py                 # 최근 36시간 기사 수집
    python collect.py --hours 72      # 기간 바꾸기
결과: data/raw/YYYY-MM-DD.json
외부 패키지 없이 파이썬 표준 라이브러리만 씁니다.
"""
import argparse
import email.utils
import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
KST = timezone(timedelta(hours=9))
UA = "Mozilla/5.0 (compatible; chulgeun-ai-bot/1.0; +https://example.com/bot)"
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def strip_tags(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = email.utils.parsedate_to_datetime(s)  # RSS: Tue, 07 Oct 2026 10:00:00 GMT
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))  # Atom: 2026-10-07T10:00:00Z
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def parse_feed(xml_bytes, source):
    """RSS 2.0과 Atom을 모두 읽어 [{title, url, summary, published, source}]를 돌려줍니다."""
    root = ET.fromstring(xml_bytes)
    items = []
    for it in root.iter("item"):  # RSS
        items.append({
            "title": strip_tags(it.findtext("title")),
            "url": (it.findtext("link") or "").strip(),
            "summary": strip_tags(it.findtext("description"))[:800],
            "published": parse_date(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")),
            "source": source,
        })
    for it in root.iter(ATOM + "entry"):  # Atom
        link = ""
        for l in it.findall(ATOM + "link"):
            if l.get("rel", "alternate") == "alternate":
                link = l.get("href", "")
                break
        items.append({
            "title": strip_tags(it.findtext(ATOM + "title")),
            "url": link.strip(),
            "summary": strip_tags(it.findtext(ATOM + "summary") or it.findtext(ATOM + "content"))[:800],
            "published": parse_date(it.findtext(ATOM + "published") or it.findtext(ATOM + "updated")),
            "source": source,
        })
    return [i for i in items if i["title"] and i["url"]]


def score(item, keywords, block_words):
    text = (item["title"] + " " + item["summary"]).lower()
    if any(b.lower() in text for b in block_words):
        return -1
    s = 0
    for k, w in keywords.items():
        if k.startswith("_"):
            continue
        if k.lower() in text:
            s += w
    if any(k.lower() in item["title"].lower() for k in keywords if not k.startswith("_")):
        s += 1  # 제목에 들어 있으면 가산점
    return s


def norm_title(t):
    return re.sub(r"[^0-9a-z가-힣]", "", t.lower())[:60]


STOP = {"the", "and", "for", "with", "from", "that", "this", "says", "said", "after", "over", "into",
        "있다", "했다", "한다", "위해", "대한", "관련", "오늘", "내일", "속보", "단독", "종합"}


def tokens(title):
    words = re.findall(r"[0-9A-Za-z]{3,}|[가-힣]{2,}", title.lower())
    return {w for w in words if w not in STOP}


def merge_coverage(items):
    """같은 사건을 다룬 기사를 하나로 묶고, 다룬 언론사가 많을수록 점수를 더합니다."""
    groups = []
    for it in sorted(items, key=lambda x: x["score"], reverse=True):
        tk = tokens(it["title"])
        for g in groups:
            inter = len(tk & g["tokens"])
            if inter >= 3 or (inter >= 2 and inter / max(1, min(len(tk), len(g["tokens"]))) >= 0.5):
                g["sources"].add(it["source"])
                g["also"].append({"source": it["source"], "url": it["url"], "title": it["title"]})
                break
        else:
            groups.append({"lead": it, "tokens": tk, "sources": {it["source"]}, "also": []})
    out = []
    for g in groups:
        lead = g["lead"]
        extra = len(g["sources"]) - 1
        lead["score"] += min(extra * 2, 8)
        lead["coverage"] = len(g["sources"])
        lead["also"] = g["also"][:5]  # 초안 작성 때 사실 대조용으로 함께 넘깁니다
        out.append(lead)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=36)
    ap.add_argument("--config", default=str(ROOT / "feeds.json"))
    ap.add_argument("--from-file", help="테스트용: 네트워크 대신 로컬 RSS 파일을 읽습니다 (이름=경로, 여러 개는 쉼표)")
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=args.hours)

    seen_path = ROOT / "data" / "seen.json"
    seen = set(json.loads(seen_path.read_text(encoding="utf-8"))) if seen_path.exists() else set()

    sources = []
    if args.from_file:
        for pair in args.from_file.split(","):
            name, path = pair.split("=", 1)
            sources.append((name, Path(path).read_bytes()))
    else:
        for f in cfg["feeds"]:
            try:
                sources.append((f["name"], fetch(f["url"])))
            except Exception as e:  # 한 피드가 실패해도 나머지는 계속
                print(f"[건너뜀] {f['name']}: {e}", file=sys.stderr)

    picked, titles = [], set()
    for name, raw in sources:
        try:
            items = parse_feed(raw, name)
        except ET.ParseError as e:
            print(f"[읽기 실패] {name}: {e}", file=sys.stderr)
            continue
        for it in items:
            if it["published"] and it["published"] < since:
                continue
            if it["url"] in seen:
                continue
            key = norm_title(it["title"])
            if key in titles:
                continue
            sc = score(it, cfg.get("keywords", {}), cfg.get("block_words", []))
            if sc < 0:
                continue
            titles.add(key)
            it["score"] = sc
            it["published"] = it["published"].astimezone(KST).isoformat() if it["published"] else None
            picked.append(it)

    picked = merge_coverage(picked)
    picked.sort(key=lambda x: (x["score"], x["published"] or ""), reverse=True)
    day = now.astimezone(KST).strftime("%Y-%m-%d")
    out = ROOT / "data" / "raw" / f"{day}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(picked, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(sources)}개 피드에서 {len(picked)}건 수집 → {out}")


if __name__ == "__main__":
    main()
