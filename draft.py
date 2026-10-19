"""2단계: 수집한 주요 뉴스 중 상위 N건을 Claude API로 한국어 브리핑 초안으로 바꿉니다.

사용법:
    export ANTHROPIC_API_KEY=sk-ant-...
    python draft.py              # 오늘 수집분에서 5건
    python draft.py --count 3
    python draft.py --mock       # API 없이 형식만 확인 (테스트용)
결과: drafts/YYYY-MM-DD.json  (사이트의 '초안 가져오기'나 publish_wp.py에 그대로 씁니다)

모든 초안은 status="draft"로 나옵니다. 사람이 원문과 대조해 검수한 뒤 발행하세요.
"""
import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
KST = timezone(timedelta(hours=9))
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
UA = "Mozilla/5.0 (compatible; chulgeun-ai-bot/1.0)"
CATEGORIES = {"politics", "economy", "policy", "society", "world", "tech", "life"}

PROMPT = """당신은 한국 직장인을 위한 아침 뉴스 브리핑 사이트 "출근길 브리핑"의 기자다.
아래 원문에서 사실(누가, 무엇을, 언제, 어디서, 숫자)만 추려 완전히 새 문장으로 한국어 기사 초안을 쓴다.

규칙:
- 원문 문장을 그대로 옮기거나 번역해 이어 붙이지 않는다. 사실만 가져와 우리 말로 다시 쓴다.
- 원문에 없는 사실·숫자·인용을 만들지 않는다. 확실하지 않으면 빼거나 "~로 알려졌습니다"라고 쓴다.
- 짧고 쉬운 존댓말 평서문(~습니다)으로 쓴다. 어려운 용어는 처음 나올 때 괄호로 풀어 쓴다.
- 정치·사회 쟁점은 중립을 지킨다. 어느 쪽 편도 들지 않고, 평가는 "누가 무엇이라고 했다"로 출처를 밝혀 쓴다. 의견이 갈리면 양쪽 입장을 모두 적는다.
- 사건·사고는 피해자 신상이나 자극적인 묘사를 넣지 않는다.
- 공식 발표·확인이 아니라 언론 보도·소문이거나 당사자가 확인하지 않은 내용이면 rumor를 true로 한다.
- 카테고리 id: politics(정치), economy(경제), policy(정책·제도), society(사회), world(국제), tech(IT·과학), life(생활·문화)
- 독자는 바쁜 직장인이다. tip에는 이 소식이 독자의 돈·일·일상에 어떤 영향을 주는지, 확인하거나 챙길 것이 있으면 무엇인지 쓴다. 영향이 거의 없으면 "당장 달라지는 점은 없지만 ~를 지켜볼 만합니다"처럼 솔직하게 쓴다.

다음 JSON 객체 하나로만 답한다:
{{"title": "40자 이내 제목", "category": "id", "date": "YYYY-MM-DD", "summary": ["요약1", "요약2", "요약3"], "why": "왜 중요한가 2문장", "tip": "나에게 미치는 영향 2문장", "rumor": false}}

출처 매체: {source}
원문 주소: {url}
발행 시각: {published}
제목: {title}
원문 내용:
{text}
"""


def fetch_text(url, limit=8000):
    """기사 페이지의 <p> 문단만 뽑아 모델에 줄 사실 자료로 씁니다. 저장·게시하지 않습니다."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode(r.headers.get_content_charset() or "utf-8", "replace")
    except Exception as e:
        print(f"  [본문 못 가져옴] {e}", file=sys.stderr)
        return ""
    raw = re.sub(r"(?is)<(script|style|nav|footer|header)[^>]*>.*?</\1>", " ", raw)
    paras = re.findall(r"(?is)<p[^>]*>(.*?)</p>", raw)
    text = " \n".join(re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", p))).strip() for p in paras)
    text = "\n".join(l for l in text.split("\n") if len(l.strip()) > 40)
    return text[:limit]


def call_claude(prompt, api_key, retries=2):
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(API_URL, data=body, headers={
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
            return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 500, 502, 503, 529) and attempt < retries:
                time.sleep(10 * (attempt + 1))
                continue
            raise RuntimeError(f"API 오류 {e.code}: {msg}")


def parse_json(text):
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("JSON을 찾지 못했습니다")
    return json.loads(text[start:end + 1])


def to_article(r, item, day):
    """모델 응답을 사이트 기사 형식으로 정리합니다. 빠진 값은 안전한 기본값으로 채웁니다."""
    summary = [str(s).strip() for s in (r.get("summary") or []) if str(s).strip()][:3]
    date = str(r.get("date") or "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        date = (item.get("published") or day)[:10]
    cat = r.get("category") if r.get("category") in CATEGORIES else "society"
    return {
        "title": str(r.get("title") or item["title"]).strip()[:80],
        "category": cat,
        "date": date,
        "summary": summary,
        "why": str(r.get("why") or "").strip(),
        "tip": str(r.get("tip") or "").strip(),
        "body": "",
        "sources": [{"name": item["source"], "url": item["url"]}] + [{"name": x["source"], "url": x["url"]} for x in item.get("also", [])[:2]],
        "rumor": bool(r.get("rumor")),
        "status": "draft",
        "originalTitle": item["title"],
    }


def mock_response(item):
    return json.dumps({
        "title": "[테스트] " + item["title"][:30], "category": "society", "date": "",
        "summary": ["테스트 요약 1", "테스트 요약 2", "테스트 요약 3"],
        "why": "테스트 문장입니다.", "tip": "테스트 문장입니다.", "rumor": False,
    }, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--day", help="YYYY-MM-DD (기본: 오늘, 한국 시간)")
    ap.add_argument("--mock", action="store_true", help="API를 부르지 않고 형식만 시험")
    ap.add_argument("--no-fetch", action="store_true", help="기사 본문을 가져오지 않고 RSS 요약만 사용")
    args = ap.parse_args()

    day = args.day or datetime.now(KST).strftime("%Y-%m-%d")
    raw_path = ROOT / "data" / "raw" / f"{day}.json"
    if not raw_path.exists():
        sys.exit(f"{raw_path} 가 없습니다. 먼저 python collect.py 를 실행하세요.")
    items = json.loads(raw_path.read_text(encoding="utf-8"))[: args.count]

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not args.mock and not api_key:
        sys.exit("ANTHROPIC_API_KEY 환경 변수가 필요합니다. (형식만 시험하려면 --mock)")

    drafts, failed = [], []
    for i, item in enumerate(items, 1):
        print(f"[{i}/{len(items)}] {item['source']} · {item['title'][:60]}")
        text = item.get("summary", "")
        if not args.no_fetch and not args.mock:
            body = fetch_text(item["url"])
            if body:
                text = body
        prompt = PROMPT.format(source=item["source"], url=item["url"], published=item.get("published") or "모름",
                               title=item["title"], text=text or "(본문 없음: 제목과 요약만으로 쓰고, 확인 안 된 내용은 빼세요)")
        try:
            reply = mock_response(item) if args.mock else call_claude(prompt, api_key)
            drafts.append(to_article(parse_json(reply), item, day))
        except Exception as e:
            print(f"  [실패] {e}", file=sys.stderr)
            failed.append(item["url"])

    out = ROOT / "drafts" / f"{day}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(drafts, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.mock:  # 다음 수집에서 같은 기사를 다시 고르지 않도록 기록
        seen_path = ROOT / "data" / "seen.json"
        seen = json.loads(seen_path.read_text(encoding="utf-8")) if seen_path.exists() else []
        seen = (seen + [d["sources"][0]["url"] for d in drafts])[-2000:]
        seen_path.write_text(json.dumps(seen, ensure_ascii=False), encoding="utf-8")

    print(f"초안 {len(drafts)}건 → {out}" + (f" (실패 {len(failed)}건)" if failed else ""))


if __name__ == "__main__":
    main()
