# 출근길 브리핑

매일 아침 국내외 주요 뉴스를 모아 Claude로 한국어 브리핑 초안을 만들고, 검수한 기사를 누구나 볼 수 있는 웹사이트로 게시합니다.

```
collect.py → draft.py → (사람 검수: status를 published로) → build_site.py → GitHub Pages
RSS 수집      AI 초안          하루 30분                         사이트 생성     무료 주소로 공개
```

파이썬 3.9 이상만 있으면 되고, 따로 설치할 패키지는 없습니다.

---

## 1. 사이트를 무료 주소로 공개하기 (처음 한 번, 약 15분)

결과 주소: `https://pjhplus7-design.github.io/chulgeun-ai/`

1. **GitHub 가입**: github.com 에서 계정을 만듭니다. 아이디가 주소에 들어갑니다.
2. **저장소 만들기**: 오른쪽 위 **+** > **New repository**
   - Repository name: `chulgeun-ai`
   - **Public** 선택 (무료 계정에서 Pages를 쓰려면 공개 저장소여야 합니다)
   - **Create repository**
3. **파일 올리기**: 새 저장소 화면의 **uploading an existing file** 링크를 눌러, 이 폴더 안의 파일과 폴더를 전부 끌어다 놓고 **Commit changes**.
   - `.github` 폴더는 숨김 폴더라 탐색기에서 안 보일 수 있습니다. 보이지 않으면 아래 "숨김 폴더 올리기"를 참고하세요.
4. **Pages 켜기**: 저장소 **Settings** > 왼쪽 **Pages** > Build and deployment의 Source를 **GitHub Actions**로 바꿉니다.
5. **주소 적기**: 저장소에서 `site.json`을 열어 연필 아이콘으로 수정합니다.
   - `"base_url": "https://pjhplus7-design.github.io/chulgeun-ai"`
   - `"contact_email": "연락받을 메일"`
   - **Commit changes**를 누르면 사이트가 자동으로 다시 만들어집니다.
6. 1~2분 뒤 **Actions** 탭에 초록 체크가 뜨면 위 주소로 접속해 보세요.

**숨김 폴더 올리기**: 업로드 화면에서 **Add file > Create new file**을 누르고 파일 이름 칸에 `.github/workflows/pages.yml`을 입력한 뒤, 이 폴더의 같은 파일 내용을 붙여넣어 저장합니다. `daily.yml`도 같은 방법으로 만듭니다.

## 2. 매일 자동으로 초안 받기

1. console.anthropic.com 에서 API 키를 만듭니다.
2. 저장소 **Settings > Secrets and variables > Actions > New repository secret**
   - Name: `ANTHROPIC_API_KEY`, Secret: 발급받은 키
3. 매일 오전 6시(한국 시간)에 `drafts/날짜.json`이 새로 생깁니다. 바로 시험하려면 **Actions** 탭 > daily-briefing > **Run workflow**.

## 3. 매일 아침 검수하고 발행하기 (하루 30분)

1. 저장소에서 `drafts/오늘날짜.json`을 열고 연필 아이콘을 누릅니다.
2. 기사마다 출처 링크를 열어 숫자·이름·날짜를 대조하고 문장을 고칩니다.
3. 발행할 기사의 `"status": "draft"`를 `"status": "published"`로 바꿉니다.
4. **Commit changes**를 누르면 1~2분 뒤 사이트에 올라갑니다.

발행하지 않을 기사는 `draft`로 두면 사이트에 나오지 않습니다.

## 4. 내 도메인 연결하기 (선택, 연 1만~3만 원대)

1. 가비아, 카페24, Cloudflare, Namecheap 같은 등록업체에서 도메인을 삽니다. 예: `chulgeun-ai.com`, `chulgeunai.kr`
   - 이름이 이미 쓰였는지는 등록업체 검색창에서 바로 확인됩니다.
2. 저장소 **Settings > Pages > Custom domain**에 산 도메인을 입력하고 **Save**.
3. 등록업체의 DNS 설정에 아래를 추가합니다.

   | 종류 | 이름(호스트) | 값 |
   | --- | --- | --- |
   | A | @ | 185.199.108.153 |
   | A | @ | 185.199.109.153 |
   | A | @ | 185.199.110.153 |
   | A | @ | 185.199.111.153 |
   | CNAME | www | 내아이디.github.io |

4. 몇 분~몇 시간 뒤 GitHub Pages 화면에 체크가 뜨면 **Enforce HTTPS**를 켭니다.
5. `site.json`의 `base_url`을 `https://chulgeun-ai.com`처럼 새 주소로 바꿉니다.

IP 주소는 GitHub가 바꿀 수 있으니, 연결 전에 GitHub 공식 문서 "Managing a custom domain for your GitHub Pages site"에서 최신 값을 확인하세요.

## 5. 광고 붙이기

1. 기사를 20~30편 쌓고, 소개·개인정보처리방침 페이지(자동 생성됨)에 연락처가 들어갔는지 확인합니다.
2. adsense.google.com 에서 사이트 주소로 신청합니다. 심사용 코드는 `site.json`의 `adsense_client`에 `ca-pub-...`를 넣으면 모든 페이지에 들어가고, `ads.txt`도 자동으로 만들어집니다.
3. 승인되면 광고 단위를 만들고 ID를 `ad_slots`에 넣습니다. 비워 둔 자리는 회색 "광고 자리" 상자로 보입니다.
4. 정식 공개 전에 회색 상자를 숨기려면 `"show_ad_placeholders": false`로 바꾸세요.

## 내 PC에서 미리 보기

```bash
python collect.py              # 뉴스 수집
python draft.py --mock         # API 없이 형식만 시험
python draft.py --count 5      # 실제 초안 (ANTHROPIC_API_KEY 필요)
python build_site.py           # _site 폴더에 사이트 생성
python -m http.server -d _site 8000   # http://localhost:8000
```

## 바꾸고 싶을 때

| 바꿀 것 | 위치 |
| --- | --- |
| 사이트 이름·소개·주소 | `site.json` |
| 디자인 | `assets/style.css` |
| 뉴스 소스 | `feeds.json`의 `feeds` |
| 우선순위 키워드 / 걸러낼 단어 | `feeds.json`의 `keywords` / `block_words` |
| 하루 초안 수 | `.github/workflows/daily.yml`의 `--count 5` |
| 문체·규칙 | `draft.py`의 `PROMPT` |
| 사용할 모델 | 환경 변수 `CLAUDE_MODEL` (기본 `claude-sonnet-4-5`) |
| 이미 발행한 기사 고치기 | `content/articles.json` 또는 해당 `drafts/날짜.json` |

## 지켜야 할 것

- **언론사 기사 저작권**: 연합뉴스 등 언론사 기사는 저작물입니다. 기사 본문은 초안 작성 때 사실 확인용으로만 쓰고, 사이트에는 우리 문장으로 쓴 요약과 출처 링크만 올립니다. 정부 정책브리핑(korea.kr) 자료는 공공누리 표시를 확인하면 더 자유롭게 쓸 수 있습니다.
- **정치 기사 중립**: 초안 프롬프트에 중립 원칙을 넣었지만, 발행 전에 한쪽 주장만 담기지 않았는지 꼭 확인하세요.

- 초안은 반드시 사람이 원문과 대조한 뒤 발행합니다. AI가 숫자나 이름을 틀릴 수 있습니다.
- 기사 본문은 모델에 사실 자료로만 넘기고 저장하거나 게시하지 않습니다. 원문 문장을 그대로 쓰지 않고 출처를 링크합니다.
- 사이트별 이용약관에서 자동 수집을 금지하는지 확인하고, 금지한 곳은 `feeds.json`에서 빼세요.
- 회사 취업규칙의 겸업 조항을 먼저 확인하고, 수익이 생기면 세금 신고를 챙기세요.
- 워드프레스로 옮기고 싶다면 `publish_wp.py`를 쓰면 됩니다 (파일 안 설명 참고).
