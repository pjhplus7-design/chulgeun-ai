"""3단계(선택): 초안을 워드프레스에 '임시글'로 올립니다. 검수 후 워드프레스 관리자 화면에서 발행하세요.

준비:
    워드프레스 관리자 > 사용자 > 프로필 > 애플리케이션 비밀번호 에서 비밀번호를 만듭니다.
    export WP_URL=https://내사이트.com
    export WP_USER=관리자아이디
    export WP_APP_PASSWORD="xxxx xxxx xxxx xxxx"
사용법:
    python publish_wp.py                  # 오늘 초안 업로드
    python publish_wp.py --dry-run        # 올리지 않고 HTML만 출력
"""
import argparse
import base64
import html
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
KST = timezone(timedelta(hours=9))
CAT_NAMES = {"politics": "정치", "economy": "경제", "policy": "정책·제도", "society": "사회",
             "world": "국제", "tech": "IT·과학", "life": "생활·문화"}


def to_html(a):
    e = html.escape
    parts = []
    if a.get("rumor"):
        parts.append('<p><strong>[보도·미확인]</strong> 공식 발표가 아닌 언론 보도를 바탕으로 한 기사입니다.</p>')
    parts.append("<h3>3줄 요약</h3><ul>" + "".join(f"<li>{e(s)}</li>" for s in a.get("summary", [])) + "</ul>")
    parts.append("<!-- 광고: 본문 중간 -->")
    if a.get("why"):
        parts.append(f"<h3>왜 중요한가</h3><p>{e(a['why'])}</p>")
    if a.get("tip"):
        parts.append(f"<h3>나에게 미치는 영향</h3><p>{e(a['tip'])}</p>")
    src = " · ".join(f'<a href="{e(s["url"])}" target="_blank" rel="noopener">{e(s["name"])}</a>' for s in a.get("sources", []))
    if src:
        parts.append(f"<p>출처: {src}</p>")
    return "\n".join(parts)


def wp_request(method, path, data=None):
    url = os.environ["WP_URL"].rstrip("/") + "/wp-json/wp/v2/" + path
    token = base64.b64encode(f'{os.environ["WP_USER"]}:{os.environ["WP_APP_PASSWORD"]}'.encode()).decode()
    req = urllib.request.Request(url, method=method, data=json.dumps(data).encode() if data else None,
                                 headers={"Authorization": "Basic " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def category_id(name, cache={}):
    if name in cache:
        return cache[name]
    found = wp_request("GET", "categories?search=" + urllib.request.quote(name))
    cid = next((c["id"] for c in found if c["name"] == name), None)
    if cid is None:
        cid = wp_request("POST", "categories", {"name": name})["id"]
    cache[name] = cid
    return cid


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    day = args.day or datetime.now(KST).strftime("%Y-%m-%d")
    path = ROOT / "drafts" / f"{day}.json"
    if not path.exists():
        sys.exit(f"{path} 가 없습니다. 먼저 python draft.py 를 실행하세요.")
    drafts = json.loads(path.read_text(encoding="utf-8"))
    if not args.dry_run:
        for k in ("WP_URL", "WP_USER", "WP_APP_PASSWORD"):
            if not os.environ.get(k):
                sys.exit(f"{k} 환경 변수가 필요합니다.")
    for a in drafts:
        content = to_html(a)
        if args.dry_run:
            print(f"--- {a['title']}\n{content}\n")
            continue
        post = wp_request("POST", "posts", {
            "title": a["title"], "content": content, "status": "draft",
            "categories": [category_id(CAT_NAMES.get(a["category"], "사회"))],
        })
        print(f"임시글 등록: {a['title']} (id {post['id']})")


if __name__ == "__main__":
    main()
