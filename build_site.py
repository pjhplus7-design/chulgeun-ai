"""4단계: 발행된 기사로 누구나 볼 수 있는 정적 웹사이트를 만듭니다.

어떤 기사가 들어가나:
    - content/articles.json 의 기사 전부
    - drafts/*.json 중 "status": "published" 로 바꾼 기사 (검수 후 직접 바꿉니다)
사용법:
    python build_site.py          # _site/ 폴더에 사이트 생성
    python -m http.server -d _site 8000   # 내 PC에서 http://localhost:8000 으로 미리 보기
외부 패키지 없이 파이썬 표준 라이브러리만 씁니다.
"""
import hashlib
import html
import json
import re
import shutil
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
KST = timezone(timedelta(hours=9))
CATS = [
    ("politics", "정치", "#2f6fd6"),
    ("economy", "경제", "#c98a0b"),
    ("policy", "정책·제도", "#1f9d55"),
    ("society", "사회", "#7a4fd0"),
    ("world", "국제", "#c0392b"),
    ("tech", "IT·과학", "#0e8a8a"),
    ("life", "생활·문화", "#d0548a"),
]
CAT = {c[0]: c for c in CATS}
e = html.escape


# assets/style.css 가 없을 때 쓰는 기본 디자인
DEFAULT_CSS = '/* 출근길 AI — 지하철 노선 색을 포인트로 쓰는 뉴스 레이아웃 */\n:root{\n  --paper:#f5f7f8; --surface:#ffffff; --ink:#15202b; --muted:#5a6772; --rule:#dde3e7;\n  --line:#1f9d55; --line-soft:#e3f4ea; --on-line:#ffffff; --warn:#b4570b; --ad:#eef1f3;\n  --f-display:"Gothic A1","Apple SD Gothic Neo","Malgun Gothic",sans-serif;\n  --f-body:"IBM Plex Sans KR","Apple SD Gothic Neo","Malgun Gothic",sans-serif;\n  --f-mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;\n  color-scheme:light;\n}\n@media (prefers-color-scheme: dark){:root{\n  --paper:#0f161c; --surface:#16212a; --ink:#e6edf2; --muted:#9aa8b3; --rule:#26343f;\n  --line:#3ccf7a; --line-soft:#173226; --on-line:#0f161c; --warn:#f0a35e; --ad:#1a2630; color-scheme:dark}}\n\n*{box-sizing:border-box}\nbody{margin:0;background:var(--paper);color:var(--ink);font-family:var(--f-body);font-size:16px;line-height:1.7;padding-inline:16px;padding-block:0 48px;-webkit-text-size-adjust:100%;word-break:keep-all;overflow-wrap:break-word}\n.wrap{max-width:1080px;margin:0 auto}\na{color:inherit}\nimg{max-width:100%}\n:focus-visible{outline:2px solid var(--line);outline-offset:2px;border-radius:4px}\n\n.mast{padding-block:24px 16px;display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center;justify-content:space-between}\n.brand{display:flex;align-items:center;gap:12px;text-decoration:none}\n.roundel{width:40px;height:40px;border-radius:50%;border:6px solid var(--line);flex:none}\n.brand .name{display:block;font-family:var(--f-display);font-weight:900;font-size:30px;line-height:1;letter-spacing:-.5px}\n.brand small{display:block;margin-top:4px;color:var(--muted);font-size:13px}\n.btn{display:inline-block;padding:8px 14px;border-radius:8px;border:1px solid var(--rule);background:var(--surface);color:var(--ink);font-size:14px;text-decoration:none}\n.btn.primary{background:var(--line);border-color:var(--line);color:var(--on-line);font-weight:700}\n\n.cats{display:flex;gap:6px;overflow-x:auto;padding-block:10px;border-block:1px solid var(--rule);scrollbar-width:thin}\n.cat{flex:none;padding:6px 14px;border-radius:999px;color:var(--muted);font-size:14px;display:inline-flex;align-items:center;gap:6px;white-space:nowrap;text-decoration:none}\n.cat i{width:8px;height:8px;border-radius:50%;background:var(--c,var(--line))}\n.cat:hover{color:var(--ink)}\n.cat[aria-current="page"]{background:var(--ink);color:var(--paper)}\n\n.ad{background:var(--ad);border:1px dashed var(--rule);border-radius:8px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:var(--muted);font-size:12.5px;text-align:center;padding:8px;gap:2px}\n.ad b{font-family:var(--f-mono);font-weight:500;letter-spacing:.08em;font-size:11px}\n.ad.leader{min-height:90px;margin-block:16px}\n.ad.rect{min-height:250px}\n.ad.rect.short{min-height:160px}\n.ad.infeed{min-height:110px;margin-block:12px}\n.ad-live{margin-block:16px}\n.ad-label{display:block;font-size:11px;color:var(--muted);margin-bottom:4px}\n\n.layout{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:32px;margin-top:8px}\n@media (max-width:860px){.layout{grid-template-columns:minmax(0,1fr)}}\nmain{min-width:0}\naside{display:flex;flex-direction:column;gap:24px;min-width:0}\n\n.listhead{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:8px;padding-block:16px 4px}\n.listhead h2{font-family:var(--f-display);font-weight:800;font-size:22px;margin:0}\n.listhead span{font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}\n.feed{display:flex;flex-direction:column}\n.item{display:grid;grid-template-columns:96px minmax(0,1fr);gap:16px;padding-block:18px;border-bottom:1px solid var(--rule);text-decoration:none}\n.item:hover h3{text-decoration:underline;text-underline-offset:3px}\n.txt{min-width:0}\n.when{font-family:var(--f-mono);font-size:12.5px;color:var(--muted);line-height:1.4;padding-top:4px}\n.when b{display:block;font-size:20px;color:var(--ink);font-weight:500}\n.item h3{font-family:var(--f-display);font-weight:800;font-size:19px;line-height:1.4;margin:4px 0 6px;text-wrap:balance}\n.item p{margin:0;color:var(--muted);font-size:15px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}\n@media (max-width:520px){.item{grid-template-columns:1fr;gap:4px}.when b{display:inline;font-size:13px;margin-right:6px}}\n\n.meta{display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:12.5px;color:var(--muted)}\n.tag{padding:1px 8px;border-radius:999px;background:var(--line-soft);color:var(--ink);display:inline-flex;align-items:center;gap:5px}\n.tag i{width:7px;height:7px;border-radius:50%;background:var(--c,var(--line))}\n.tag.rumor{background:transparent;border:1px solid var(--warn);color:var(--warn)}\n.tag.plain{background:transparent;border:1px dashed var(--muted)}\n.empty{padding:40px 16px;text-align:center;color:var(--muted);border:1px dashed var(--rule);border-radius:8px;margin-top:16px}\n\n.box{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:16px}\n.box h4{font-family:var(--f-display);font-weight:800;font-size:16px;margin:0 0 10px}\n.box p{margin:0 0 10px;font-size:14px;color:var(--muted)}\n.lines{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:8px;font-size:14px}\n.lines a{display:flex;align-items:center;gap:8px;text-decoration:none}\n.lines a:hover span:first-of-type{text-decoration:underline}\n.lines i{width:10px;height:10px;border-radius:50%;background:var(--c);flex:none}\n.lines .n{margin-left:auto;font-family:var(--f-mono);font-size:12px;color:var(--muted)}\n\n.article{max-width:680px;padding-block:16px 8px}\n.back{display:inline-block;color:var(--muted);font-size:14px;margin-bottom:12px;text-decoration:none}\n.article h1{font-family:var(--f-display);font-weight:900;font-size:clamp(24px,4.4vw,32px);line-height:1.35;margin:10px 0 16px;text-wrap:balance}\n.article h2{font-family:var(--f-display);font-weight:800;font-size:20px;margin:28px 0 8px}\n.article h5{font-size:12px;letter-spacing:.1em;color:var(--muted);font-weight:500;margin:24px 0 8px}\n.article ul.sum{margin:0;padding-left:20px}\n.article ul.sum li{margin-bottom:6px}\n.article .body p{margin:0 0 14px}\n.prose p,.prose li{max-width:65ch}\n.muted{color:var(--muted);font-size:14px}\n.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-top:20px}\n.cards div{background:var(--surface);border:1px solid var(--rule);border-radius:8px;padding:12px 14px;min-width:0}\n.cards b{display:block;font-size:12px;letter-spacing:.08em;color:var(--muted);font-weight:500;margin-bottom:4px}\n.cards p{margin:0;font-size:15px;line-height:1.6}\n.sources{font-size:14px;color:var(--muted);margin-top:20px;padding-top:12px;border-top:1px solid var(--rule);overflow-wrap:anywhere}\n.sources a{color:var(--muted)}\n\nfooter{font-size:12.5px;color:var(--muted);border-top:1px solid var(--rule);padding-top:20px;margin-top:40px}\nfooter p{margin:0 0 6px;max-width:70ch}\nfooter a{color:var(--muted)}\n'

# content/articles.json 이 없을 때 쓰는 첫 기사
SEED_ARTICLES = '[\n  {\n    "id": "energy-ceasefire",\n    "title": "트럼프 \\"러시아·우크라이나 에너지 시설 휴전 합의\\" 발표",\n    "category": "world",\n    "date": "2026-10-11",\n    "summary": [\n      "도널드 트럼프 미국 대통령이 소셜미디어에 러시아와 우크라이나가 \'에너지 휴전\'에 합의했고 즉시 효력이 생긴다고 밝혔습니다.",\n      "구체적인 조건은 공개되지 않았고, 발표 시점에 러시아와 우크라이나 정부는 합의 사실을 확인하지 않았습니다.",\n      "에너지 휴전은 서로의 발전소·송전망 같은 에너지 시설을 공격하지 않기로 하는 부분 휴전을 말합니다."\n    ],\n    "why": "전쟁 중 에너지 시설 공격은 겨울철 민간 피해와 국제 에너지 가격에 직접 영향을 줍니다. 실제로 지켜지면 전면 휴전 협상의 출발점이 될 수 있습니다.",\n    "tip": "당장 달라지는 점은 없지만, 휴전이 지켜지면 국제 유가와 가스 가격이 안정되는 쪽으로 움직일 수 있습니다. 양측 정부의 공식 확인 여부를 지켜볼 만합니다.",\n    "body": "",\n    "sources": [\n      {"name": "The Star (로이터 통신 배포)", "url": "https://www.thestar.com.my/news/world/2026/10/11/trump-says-russia-and-ukraine-reached-039energy-ceasefire039"},\n      {"name": "Al Jazeera", "url": "https://www.aljazeera.com/amp/news/2026/10/11/trump-says-ukraine-russia-agree-to-energy-ceasefire-2"}\n    ],\n    "rumor": true,\n    "status": "published"\n  },\n  {\n    "id": "riyadh-airport",\n    "title": "사우디 리야드 공항 여객터미널 미사일 피격, 공항 폐쇄",\n    "category": "world",\n    "date": "2026-10-10",\n    "summary": [\n      "사우디아라비아 수도 리야드의 킹칼리드 국제공항 여객터미널이 미사일 공격을 받아 12명이 숨지고 300명 넘게 다쳤습니다.",\n      "다음 날에도 같은 터미널이 다시 공격받아 1명이 숨지고 11명이 다쳤으며, 예멘의 후티 반군이 공격을 자신들이 했다고 밝혔습니다.",\n      "공항은 첫 공격 이후 폐쇄됐고, 일부 항공사는 사우디행 운항을 중단했습니다."\n    ],\n    "why": "중동 하늘길과 원유 수송로의 긴장이 커지고 있다는 신호입니다. 후티 반군이 홍해 입구 해협 주변을 장악하면서 원유 운송 차질 우려도 나옵니다.",\n    "tip": "중동을 경유하는 출장이나 여행 계획이 있다면 항공사 운항 공지와 외교부 해외안전여행 정보를 먼저 확인하세요. 유가가 오르면 국내 기름값에도 시차를 두고 반영됩니다.",\n    "body": "",\n    "sources": [\n      {"name": "NPR·AP 통신 (St. Louis Public Radio 게재)", "url": "https://www.stlpr.org/npr/2026-10-10/passenger-terminal-at-riyadh-airport-is-struck-again-a-day-after-12-were-killed"}\n    ],\n    "rumor": false,\n    "status": "published"\n  },\n  {\n    "id": "nobel-peace-pillay",\n    "title": "2026 노벨평화상에 나비 필레이 전 유엔 인권최고대표",\n    "category": "world",\n    "date": "2026-10-09",\n    "summary": [\n      "노르웨이 노벨위원회가 남아프리카공화국 출신 법률가 나비 필레이(85)에게 올해 노벨평화상을 준다고 발표했습니다.",\n      "위원회는 전쟁범죄와 집단학살 같은 국제범죄를 법정에서 처벌받게 하는 데 기여한 점을 수상 이유로 들었습니다.",\n      "필레이는 유엔 인권최고대표와 르완다 국제형사재판소 재판관 등을 지냈고, 시상식은 12월 10일 오슬로에서 열립니다."\n    ],\n    "why": "노벨위원회는 국제법 체계가 큰 압박을 받고 있다며 국제 사법의 역할을 강조했습니다. 반응은 엇갈렸는데, 유엔 사무총장과 남아공 대통령은 환영했고 이스라엘 외무부와 트럼프 미국 대통령은 비판했습니다.",\n    "tip": "생활에 직접 달라지는 점은 없습니다. 다만 국제형사재판소를 둘러싼 미국의 제재 등 국제 질서 갈등이 이어지고 있어 관련 뉴스를 이해하는 배경이 됩니다.",\n    "body": "",\n    "sources": [\n      {"name": "Al Jazeera", "url": "https://www.aljazeera.com/news/2026/10/9/2026-nobel-peace-prize-awarded-to-navi-pillay"}\n    ],\n    "rumor": false,\n    "status": "published"\n  },\n  {\n    "id": "youth-future-savings-2",\n    "title": "청년미래적금 2차 신청, 16일까지 은행 앱에서",\n    "category": "policy",\n    "date": "2026-10-06",\n    "summary": [\n      "만 19~34세 청년이 3년 동안 매달 최대 50만 원을 넣으면 정부가 납입액의 6% 또는 12%를 더 얹어 주는 청년미래적금 2차 신청이 10월 7일부터 16일까지 진행됩니다.",\n      "총급여 7,500만 원 이하 근로자나 연매출 3억 원 이하 소상공인 가운데 가구 중위소득 200% 이하면 신청할 수 있고, 이자소득세가 면제됩니다.",\n      "12~16일에는 출생연도와 관계없이 신청할 수 있으며, 심사 결과는 11월 12~13일에 나오고 계좌 개설은 11월 16~27일입니다."\n    ],\n    "why": "정부 기여금과 비과세를 합치면 일반 적금보다 수익이 크게 높아지는 청년 자산 형성 상품입니다. 기존 청년도약계좌 가입자도 이번에 갈아탈 수 있습니다.",\n    "tip": "1991년 11월 17일~2007년 11월 27일 출생이라면 대상인지 은행 앱에서 확인해 보세요. 청년도약계좌에서 갈아탈 경우, 새 계좌를 먼저 연 뒤 기존 계좌를 특별중도해지해야 혜택이 유지됩니다.",\n    "body": "",\n    "sources": [\n      {"name": "파이낸셜뉴스 (금융위원회·서민금융진흥원 발표 인용)", "url": "https://www.fnnews.com/news/202610061046004577"},\n      {"name": "토스뱅크 안내", "url": "https://www.tossbank.com/articles/youth-future-saving-2nd"}\n    ],\n    "rumor": false,\n    "status": "published"\n  },\n  {\n    "id": "national-audit-2026",\n    "title": "2026 국정감사 시작, 상임위별 쟁점은",\n    "category": "politics",\n    "date": "2026-10-06",\n    "summary": [\n      "국회가 10월 6일부터 정부 기관을 대상으로 한 국정감사에 들어갔습니다.",\n      "8일 하루에만 금융위원회, 법무부, 합동참모본부, 기상청 등 8개 상임위원회에서 감사가 진행됐습니다.",\n      "레버리지 ETF 도입 과정, 올해 처음 예산이 편성된 미래대응기금, 수사·기소 분리 제도 운영, 비무장지대(DMZ) 지뢰 폭발 사고 등이 쟁점으로 꼽힙니다."\n    ],\n    "why": "국정감사는 국회가 1년 동안의 정부 정책과 예산 집행을 점검하는 자리입니다. 여기서 드러난 문제가 다음 해 예산과 법 개정으로 이어지는 경우가 많습니다.",\n    "tip": "투자·금융 상품이나 관심 있는 제도가 있다면 해당 상임위 감사에서 어떤 지적이 나오는지 지켜볼 만합니다. 여야 주장이 엇갈리는 사안은 양쪽 설명을 함께 확인하는 것이 좋습니다.",\n    "body": "",\n    "sources": [\n      {"name": "위키트리", "url": "https://www.wikitree.co.kr/articles/1164725"}\n    ],\n    "rumor": false,\n    "status": "published"\n  },\n  {\n    "id": "exports-sep-2026",\n    "title": "9월 수출 1,209억 달러로 역대 최대, 반도체가 절반",\n    "category": "economy",\n    "date": "2026-10-01",\n    "summary": [\n      "산업통상부에 따르면 9월 수출액은 1,209억 4,000만 달러로 1년 전보다 83.5% 늘었습니다.",\n      "반도체 수출이 처음으로 한 달에 600억 달러를 넘으며 전체 수출의 절반가량을 차지했습니다.",\n      "수입은 710억 9,000만 달러로 26.0% 늘었고, 무역수지는 498억 5,000만 달러 흑자로 역대 최대를 기록했습니다."\n    ],\n    "why": "수출은 한국 경제 성장률과 기업 실적을 좌우하는 가장 큰 축입니다. 다만 반도체 한 품목 비중이 커질수록 반도체 경기에 따라 전체 경제가 흔들릴 위험도 커집니다.",\n    "tip": "반도체 관련 기업에 다니거나 투자하고 있다면 업황 흐름을 계속 확인하세요. 수출 호조가 이어지면 환율과 성과급, 채용 같은 분야에도 영향을 줄 수 있습니다.",\n    "body": "",\n    "sources": [\n      {"name": "KDI 경제정보센터 (산업통상부 보도자료)", "url": "https://eiec.kdi.re.kr/policy/materialView.do?num=287666"},\n      {"name": "머니투데이방송", "url": "https://news.mtn.co.kr/news-detail/2026100109075980661"}\n    ],\n    "rumor": false,\n    "status": "published"\n  }\n]\n'


# ---------- 데이터 ----------
def slug_for(a):
    basis = (a.get("sources") or [{}])[0].get("url") or a.get("title", "")
    return f'{a.get("date", "0000-00-00")}-{hashlib.sha1(basis.encode("utf-8")).hexdigest()[:6]}'


def load_articles():
    items = []
    # 폴더 없이 맨 위에 올린 경우(articles.json)도 찾습니다
    p = next((f for f in (ROOT / "content" / "articles.json", ROOT / "articles.json") if f.exists()), ROOT / "content" / "articles.json")
    if p.exists():
        items += json.loads(p.read_text(encoding="utf-8"))
    else:  # content 폴더가 없으면 파일에 내장된 첫 기사들을 씁니다
        items += json.loads(SEED_ARTICLES)
    for f in sorted((ROOT / "drafts").glob("*.json")):
        items += [a for a in json.loads(f.read_text(encoding="utf-8")) if a.get("status") == "published"]
    seen, out = set(), []
    for a in items:
        if a.get("status", "published") != "published" or not a.get("title"):
            continue
        a["id"] = re.sub(r"[^A-Za-z0-9_-]", "-", a.get("id") or slug_for(a))
        if a["id"] in seen:
            continue
        seen.add(a["id"])
        if a.get("category") not in CAT:
            a["category"] = "society"
        out.append(a)
    out.sort(key=lambda a: a.get("date", ""), reverse=True)
    return out


def safe_url(u):
    u = str(u or "").strip()
    return u if re.match(r"^https?://", u, re.I) else ""


def fmt_date(d):
    try:
        y, m, dd = d.split("-")
        return f"{int(m)}월 {int(dd)}일"
    except ValueError:
        return d


# ---------- 조각 ----------
def ad(cfg, kind, label, size, extra_cls=""):
    slot = (cfg.get("ad_slots") or {}).get(kind, "")
    client = cfg.get("adsense_client", "")
    if client and slot:
        return (f'<div class="ad-live {extra_cls}"><span class="ad-label">광고</span>'
                f'<ins class="adsbygoogle" style="display:block" data-ad-client="{e(client)}" data-ad-slot="{e(slot)}" '
                f'data-ad-format="auto" data-full-width-responsive="true"></ins>'
                f'<script>(adsbygoogle=window.adsbygoogle||[]).push({{}});</script></div>')
    if cfg.get("show_ad_placeholders"):
        return f'<div class="ad {extra_cls}"><b>광고 · {e(size)}</b><span>{e(label)}</span></div>'
    return ""


def cat_tag(cid):
    c = CAT[cid]
    return f'<span class="tag" style="--c:{c[2]}"><i></i>{e(c[1])}</span>'


def flags(a):
    s = ""
    if a.get("rumor"):
        s += '<span class="tag rumor">보도·미확인</span>'
    if a.get("example"):
        s += '<span class="tag plain">예시 글</span>'
    return s


def page(cfg, *, title, desc, path, body, prefix, active="all", canonical=None, og_type="website"):
    name = cfg["name"]
    full_title = name if title == name else f"{title} | {name}"
    base = cfg["base_url"].rstrip("/")
    canon = canonical or f"{base}/{path}"
    adsense = ""
    if cfg.get("adsense_client"):
        adsense = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={e(cfg["adsense_client"])}" '
                   'crossorigin="anonymous"></script>')
    cur_all = ' aria-current="page"' if active == "all" else ""
    nav = f'<a class="cat" href="{prefix}index.html"{cur_all}>전체</a>'
    for cid, cname, color in CATS:
        cur = ' aria-current="page"' if active == cid else ""
        nav += f'<a class="cat" href="{prefix}c/{cid}.html" style="--c:{color}"{cur}><i></i>{e(cname)}</a>'
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(full_title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(canon)}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{e(full_title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{e(canon)}">
<meta property="og:site_name" content="{e(name)}">
<link rel="alternate" type="application/rss+xml" title="{e(name)}" href="{prefix}feed.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;700&family=Gothic+A1:wght@800;900&family=IBM+Plex+Mono:wght@500&display=swap">
<link rel="stylesheet" href="{prefix}assets/style.css">
{adsense}
</head>
<body>
<div class="wrap">
<header class="mast">
  <a class="brand" href="{prefix}index.html"><span class="roundel" aria-hidden="true"></span><span><span class="name">{e(name)}</span><small>{e(cfg["tagline"])}</small></span></a>
  <a class="btn primary" href="{prefix}about.html#subscribe">아침 메일 받기</a>
</header>
<nav class="cats" aria-label="카테고리">{nav}</nav>
{ad(cfg, "top", "상단 배너 자리", "728×90", "leader")}
{body}
<footer>
  <p>{e(name)}의 기사는 AI가 초안을 쓰고 편집자가 사실관계를 확인한 해설입니다. 원문 문장은 옮기지 않으며, 자세한 내용은 출처 링크에서 확인하세요.</p>
  <p><a href="{prefix}about.html">소개·편집 원칙</a> · <a href="{prefix}privacy.html">개인정보처리방침</a> · <a href="{prefix}feed.xml">RSS</a></p>
</footer>
</div>
</body>
</html>
"""


def sidebar(cfg, prefix, counts):
    lines = "".join(
        f'<li><a href="{prefix}c/{cid}.html" style="--c:{color}"><i></i><span>{e(cname)}</span><span class="n">{counts.get(cid, 0)}</span></a></li>'
        for cid, cname, color in CATS)
    aff = cfg.get("affiliate_html") or ""
    aff_box = aff if aff else (ad(cfg, "sidebar", "도서·생활용품 제휴 링크 자리", "제휴 300×160", "rect short") if cfg.get("show_ad_placeholders") else "")
    return f"""<aside>
  {ad(cfg, "sidebar", "사이드바 배너 자리", "300×250", "rect")}
  <div class="box"><h4>카테고리</h4><ul class="lines">{lines}</ul></div>
  <div class="box"><h4>매일 아침 7시, 메일로 받기</h4><p>오늘의 다섯 소식과 금요일 주간 결산을 보내드립니다.</p><a class="btn primary" href="{prefix}about.html#subscribe">구독 안내</a></div>
  {aff_box}
</aside>"""


def list_items(cfg, items, prefix):
    out = []
    for i, a in enumerate(items):
        y, m, d = (a.get("date", "--").split("-") + ["", "", ""])[:3]
        first = (a.get("summary") or [""])[0]
        out.append(f"""<a class="item" href="{prefix}a/{a['id']}.html">
  <span class="when"><b>{e(d)}</b>{int(m) if m.isdigit() else ''}월</span>
  <span class="txt"><span class="meta">{cat_tag(a['category'])}{flags(a)}</span><h3>{e(a['title'])}</h3><p>{e(first)}</p></span>
</a>""")
        if (i + 1) % 4 == 0 and i < len(items) - 1:
            out.append(ad(cfg, "infeed", "목록 사이 광고 자리 (기사 4개마다)", "인피드", "infeed"))
    return "\n".join(out)


def article_body(cfg, a, prefix):
    summary = "".join(f"<li>{e(s)}</li>" for s in a.get("summary", []))
    body = ""
    if a.get("body"):
        body = '<h5>해설</h5><div class="body">' + "".join(f"<p>{e(p.strip())}</p>" for p in re.split(r"\n\s*\n", a["body"]) if p.strip()) + "</div>"
    cards = ""
    if a.get("why"):
        cards += f'<div><b>왜 중요한가</b><p>{e(a["why"])}</p></div>'
    if a.get("tip"):
        cards += f'<div><b>나에게 미치는 영향</b><p>{e(a["tip"])}</p></div>'
    srcs = [s for s in a.get("sources", []) if safe_url(s.get("url"))]
    src_html = ""
    if srcs:
        links = " · ".join(f'<a href="{e(safe_url(s["url"]))}" target="_blank" rel="noopener nofollow">{e(s.get("name") or s["url"])}</a>' for s in srcs)
        note = f' ({e(a["sourceNote"])})' if a.get("sourceNote") else ""
        src_html = f'<div class="sources">출처: {links}{note}</div>'
    return f"""<article class="article">
  <a class="back" href="{prefix}index.html">← 목록으로</a>
  <div class="meta">{cat_tag(a['category'])}{flags(a)}<span>{e(fmt_date(a.get('date', '')))}</span></div>
  <h1>{e(a['title'])}</h1>
  <h5>3줄 요약</h5><ul class="sum">{summary}</ul>
  {ad(cfg, "article", "기사 본문 중간 광고 자리", "본문 중간", "infeed")}
  {body}
  <div class="cards">{cards}</div>
  {src_html}
  {ad(cfg, "article", "기사 하단 배너 자리", "기사 하단", "leader")}
</article>"""


# ---------- 생성 ----------
def build():
    cfg_file = ROOT / "site.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8")) if cfg_file.exists() else {}
    for k, v in {"name": "출근길 브리핑", "tagline": "지하철 다섯 정거장 동안 읽는 오늘의 주요 뉴스",
                 "description": "바쁜 직장인을 위해 매일 아침 국내외 주요 뉴스를 3줄 요약과 생활 영향으로 정리합니다.",
                 "base_url": "https://pjhplus7-design.github.io/chulgeun-ai", "show_ad_placeholders": True}.items():
        cfg.setdefault(k, v)
    base = cfg["base_url"].rstrip("/")
    arts = load_articles()
    counts = {}
    for a in arts:
        counts[a["category"]] = counts.get(a["category"], 0) + 1

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "a").mkdir(parents=True)
    (OUT / "c").mkdir()
    (OUT / "assets").mkdir()
    css_file = next((f for f in (ROOT / "assets" / "style.css", ROOT / "style.css") if f.exists()), ROOT / "assets" / "style.css")
    (OUT / "assets" / "style.css").write_text(
        css_file.read_text(encoding="utf-8") if css_file.exists() else DEFAULT_CSS, encoding="utf-8")

    def write(rel, text):
        (OUT / rel).write_text(text, encoding="utf-8")

    # 첫 화면
    latest = arts[:40]
    empty = '<div class="empty">아직 발행된 기사가 없습니다.</div>'
    body = f"""<div class="layout"><main>
<div class="listhead"><h2>최신 기사</h2><span>{len(arts)}건</span></div>
<div class="feed">{list_items(cfg, latest, "") or empty}</div>
</main>{sidebar(cfg, "", counts)}</div>"""
    write("index.html", page(cfg, title=cfg["name"], desc=cfg["description"], path="", body=body, prefix=""))

    # 카테고리
    for cid, cname, _ in CATS:
        items = [a for a in arts if a["category"] == cid]
        empty_c = '<div class="empty">이 카테고리에는 아직 기사가 없습니다.</div>'
        body = f"""<div class="layout"><main>
<div class="listhead"><h2>{e(cname)}</h2><span>{len(items)}건</span></div>
<div class="feed">{list_items(cfg, items, "../") or empty_c}</div>
</main>{sidebar(cfg, "../", counts)}</div>"""
        write(f"c/{cid}.html", page(cfg, title=cname, desc=f"{cname} 분야 주요 뉴스 해설", path=f"c/{cid}.html", body=body, prefix="../", active=cid))

    # 기사
    for a in arts:
        body = f'<div class="layout"><main>{article_body(cfg, a, "../")}</main>{sidebar(cfg, "../", counts)}</div>'
        desc = (a.get("summary") or [cfg["description"]])[0][:150]
        write(f"a/{a['id']}.html", page(cfg, title=a["title"], desc=desc, path=f"a/{a['id']}.html", body=body,
                                        prefix="../", active=a["category"], og_type="article"))

    # 소개·정책 (애드센스 심사에 필요한 기본 페이지)
    contact = cfg.get("contact_email") or "(연락처를 site.json의 contact_email에 적어 주세요)"
    about = f"""<article class="article prose">
<h1>소개·편집 원칙</h1>
<p>{e(cfg["name"])}은 그날 꼭 알아야 할 국내외 주요 뉴스를 바쁜 직장인이 출근길 5분 안에 파악할 수 있도록 정리하는 브리핑입니다.</p>
<h2>이렇게 만듭니다</h2>
<ol><li>공식 발표, 보도자료, 신뢰할 수 있는 매체의 기사를 매일 아침 모읍니다.</li>
<li>AI가 사실만 추려 새 문장으로 초안을 씁니다. 원문 문장은 옮기지 않습니다.</li>
<li>편집자가 수치·이름·날짜를 원문과 대조하고, 해설과 생활 영향을 다듬은 뒤 발행합니다.</li></ol>
<h2>정치 기사 원칙</h2>
<p>정치·사회 쟁점은 특정 정당이나 진영의 입장을 대변하지 않습니다. 사실을 먼저 전하고, 의견이 갈리는 사안은 양쪽의 주장을 함께 소개합니다.</p>
<h2>표시 원칙</h2>
<ul><li>공식 발표가 아닌 보도는 <b>보도·미확인</b>으로 표시합니다.</li>
<li>모든 기사 하단에 원문 출처를 링크합니다.</li>
<li>광고와 제휴 링크는 '광고'로 표시하며, 기사 내용에 영향을 주지 않습니다.</li></ul>
<h2 id="subscribe">아침 메일 구독</h2>
<p>뉴스레터는 준비 중입니다. 오픈 소식은 이 페이지와 <a href="feed.xml">RSS</a>로 알려드립니다.</p>
<h2>정정·문의</h2>
<p>오류 제보와 정정 요청: {e(contact)}</p>
</article>"""
    write("about.html", page(cfg, title="소개·편집 원칙", desc=f"{cfg['name']}의 제작 방식과 편집 원칙", path="about.html",
                             body=f'<div class="layout"><main>{about}</main>{sidebar(cfg, "", counts)}</div>', prefix=""))
    privacy = f"""<article class="article prose">
<h1>개인정보처리방침</h1>
<p>{e(cfg["name"])}은 회원가입 없이 이용할 수 있으며, 이용자의 이름·연락처 등 개인정보를 직접 수집하지 않습니다.</p>
<h2>광고와 쿠키</h2>
<p>이 사이트는 Google 애드센스 등 제3자 광고를 게재할 수 있습니다. Google을 비롯한 제3자 광고 사업자는 쿠키를 사용해 이용자의 이전 방문 기록을 바탕으로 광고를 게재할 수 있습니다. 이용자는 <a href="https://adssettings.google.com" target="_blank" rel="noopener">Google 광고 설정</a>에서 맞춤 광고를 끌 수 있습니다.</p>
<h2>문의</h2>
<p>{e(contact)}</p>
<p class="muted">시행일: {datetime.now(KST).strftime("%Y년 %m월 %d일")}</p>
</article>"""
    write("privacy.html", page(cfg, title="개인정보처리방침", desc=f"{cfg['name']} 개인정보처리방침", path="privacy.html",
                               body=f'<div class="layout"><main>{privacy}</main>{sidebar(cfg, "", counts)}</div>', prefix=""))
    write("404.html", page(cfg, title="페이지를 찾을 수 없습니다", desc=cfg["description"], path="404.html", prefix="",
                           body='<div class="empty" style="margin-top:32px">찾는 페이지가 없습니다. <a href="index.html">첫 화면으로</a></div>'))

    # RSS, 사이트맵, robots, ads.txt
    now = datetime.now(KST)
    rss_items = ""
    for a in arts[:30]:
        try:
            pub = datetime.fromisoformat(a["date"]).replace(hour=7, tzinfo=KST)
        except ValueError:
            pub = now
        rss_items += (f"<item><title>{e(a['title'])}</title><link>{base}/a/{a['id']}.html</link>"
                      f"<guid>{base}/a/{a['id']}.html</guid><pubDate>{format_datetime(pub)}</pubDate>"
                      f"<description>{e(' '.join(a.get('summary', [])))}</description></item>")
    write("feed.xml", f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{e(cfg["name"])}</title>'
                      f'<link>{base}/</link><description>{e(cfg["description"])}</description><language>ko</language>'
                      f'<lastBuildDate>{format_datetime(now)}</lastBuildDate>{rss_items}</channel></rss>')
    urls = [f"{base}/", f"{base}/about.html"] + [f"{base}/c/{c[0]}.html" for c in CATS] + [f"{base}/a/{a['id']}.html" for a in arts]
    write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
          + "".join(f"<url><loc>{e(u)}</loc></url>" for u in urls) + "</urlset>")
    write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    if cfg.get("adsense_client"):
        pub = cfg["adsense_client"].replace("ca-", "")
        write("ads.txt", f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n")
    (OUT / ".nojekyll").write_text("")
    print(f"기사 {len(arts)}건으로 사이트 생성 → {OUT}")


if __name__ == "__main__":
    build()
