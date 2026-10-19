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


# ---------- 데이터 ----------
def slug_for(a):
    basis = (a.get("sources") or [{}])[0].get("url") or a.get("title", "")
    return f'{a.get("date", "0000-00-00")}-{hashlib.sha1(basis.encode("utf-8")).hexdigest()[:6]}'


def load_articles():
    items = []
    p = ROOT / "content" / "articles.json"
    if p.exists():
        items += json.loads(p.read_text(encoding="utf-8"))
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
    cfg = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
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
    shutil.copy(ROOT / "assets" / "style.css", OUT / "assets" / "style.css")

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
