# ppt-craft 사용 가이드

[English](USAGE.md)

- [설치](#설치)
- [빠르게 시작하기](#빠르게-시작하기)
- [작업 흐름](#작업-흐름)
- [레퍼런스 주기](#레퍼런스-주기)
- [내용 입력 방식과 활용 예](#내용-입력-방식과-활용-예)
- [폰트](#폰트)
- [이미지와 배치](#이미지와-배치)
- [기존 자료 검수하기](#기존-자료-검수하기)
- [나중에 고치기](#나중에-고치기)
- [예시](#예시)
- [자주 묻는 질문과 문제 해결](#자주-묻는-질문과-문제-해결)

## 설치

### 터미널에서

```bash
claude plugin marketplace add rrrr66254/ppt-craft
claude plugin install ppt-craft@ppt-craft
```

기본으로 현재 사용자 범위(scope `user`)에 설치됩니다.

### Claude Code 세션 안에서

```
/plugin marketplace add rrrr66254/ppt-craft
/plugin install ppt-craft@ppt-craft
```

두 번째 명령을 실행하면 `/plugin` 패널에 플러그인 상세 정보가 열리고, 거기서 설치를 확정합니다.

설치한 뒤에는 `/reload-plugins`를 실행하거나 Claude Code를 다시 시작하세요.

### 설치 확인

```bash
claude plugin list
claude plugin details ppt-craft
```

`claude plugin list`에 `ppt-craft@ppt-craft`가 Status `enabled`로 나오면 됩니다. `claude plugin details ppt-craft`에는 Skills (5) `deck`, `deck-brief`, `deck-build`, `deck-review`, `deck-style`과 Agents (1) `deck-reviewer`가 표시됩니다.

### 특정 버전으로 고정

git 태그를 붙여 마켓플레이스를 추가합니다.

```bash
claude plugin marketplace add rrrr66254/ppt-craft#v0.2.0
```

### 팀이나 저장소 전체에 설치

저장소에서 한 번만 실행합니다.

```bash
claude plugin marketplace add rrrr66254/ppt-craft --scope project
```

이 명령이 `.claude/settings.json`을 만들어 줍니다. 이 파일을 커밋하세요. 팀원은 Claude Code에서 해당 폴더를 신뢰(trust)하면 마켓플레이스를 받게 됩니다.

### 업데이트

이 플러그인처럼 서드파티 마켓플레이스는 백그라운드 자동 업데이트가 기본으로 꺼져 있습니다. 둘 중 하나를 고르세요.

- 자동 업데이트 켜기: `/plugin` → Marketplaces → ppt-craft → Enable auto-update
- 직접 업데이트: 세션에서는 `/plugin marketplace update ppt-craft`, 터미널에서는 `claude plugin update ppt-craft@ppt-craft`

플러그인 버전 번호가 바뀌었을 때만 새 사본을 받습니다. 업데이트한 뒤에는 Claude Code를 다시 시작하세요.

### 설치하지 않고 클론으로 써 보기

```bash
git clone https://github.com/rrrr66254/ppt-craft
claude --plugin-dir ./ppt-craft
```

### 제거

```bash
claude plugin uninstall ppt-craft@ppt-craft
claude plugin marketplace remove ppt-craft
```

첫 번째는 플러그인만 제거합니다. 두 번째는 마켓플레이스를 지우고 그 마켓플레이스의 플러그인도 함께 제거합니다. 제거하면 플러그인 데이터 폴더(기억해 둔 폰트, 저장한 스타일. [폰트](#폰트) 참고)도 지워집니다. 남기고 싶으면 `uninstall`에 `--keep-data`를 붙이세요.

### 필요한 것

- **Python 3.10 이상.** 스킬은 `python`을, 없으면 `python3`를 실행합니다.
- **Python 패키지:** python-pptx, Pillow, resvg-py (`requirements.txt`). 스크립트가 `ModuleNotFoundError`로 멈추면 Claude가 동의를 받은 뒤 `pip install -r "<플러그인 폴더>/requirements.txt"`를 실행합니다. 직접 설치하려면 `python`이 가리키는 그 Python에 설치하세요.

  ```bash
  python -m pip install -r ~/.claude/plugins/cache/ppt-craft/ppt-craft/0.2.0/requirements.txt
  ```

  설치된 사본은 `~/.claude/plugins/cache/<마켓플레이스>/<플러그인>/<버전>/`에 있습니다(Windows에서는 `%USERPROFILE%\.claude\plugins\cache\ppt-craft\ppt-craft\0.2.0\`). 클론으로 쓰는 경우에는 클론 폴더의 `requirements.txt`를 쓰면 됩니다.
- **렌더러.** 스타일 후보 비교와 검수에는 슬라이드를 이미지로 렌더링해야 합니다. 새 자료를 만들 때 인터뷰 전에 먼저 확인하고, 렌더러가 없으면 설치 방법을 알려 주고 멈춥니다.
  - Windows: Microsoft PowerPoint가 설치되어 있으면 자동으로 씁니다.
  - 그 밖의 경우(macOS, Linux 포함): LibreOffice와 PDF→PNG 변환기(poppler의 `pdftoppm` 또는 `pip install pymupdf`)가 필요합니다.
    - macOS: `brew install --cask libreoffice && brew install poppler`
    - Linux: `sudo apt install libreoffice poppler-utils`

  `python "<플러그인 폴더>/scripts/render.py" --check`로 확인할 수 있습니다. `powerpoint`나 `libreoffice`가 출력되면 정상이고, 없으면 종료 코드 2와 함께 설치 안내가 나옵니다.

### 설치 문제 해결

- 마켓플레이스는 사용자의 `git`으로 클론됩니다. `owner/repo` 형식이면 SSH를 먼저 시도하고 실패하면 HTTPS로 넘어갑니다. `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`을 설정하면 SSH 시도를 건너뜁니다(GitHub SSH 접속이 막혀 있거나 멈출 때 유용).
- 설치 후 스킬이 보이지 않으면 `/reload-plugins`를 실행하거나 다시 시작한 뒤 `claude plugin details ppt-craft`로 확인하세요.

## 빠르게 시작하기

`/ppt-craft:deck` 명령으로 시작하거나 그냥 요청하면 됩니다. 예를 들면 이렇습니다.

**주제만 있을 때**

```
/ppt-craft:deck 신입 개발자 대상 사내 코드 리뷰 문화 소개, 15분
```
```
/ppt-craft:deck a 10-minute internal talk on why we moved session storage to Redis
```

**문서에서 만들 때**

```
./연구노트.md 내용으로 랩미팅 발표자료 만들어줘. 20분.
```
```
/ppt-craft:deck make a 12-slide board update from ./q3-report.pdf
```

**직접 쓴 목차가 있을 때**

```
이 목차대로 PPT 만들어줘: 1) 현황 2) 문제 3) 원인 4) 제안 5) 일정
```
```
Build a deck from this outline, keep my order:
1. Checkout p99 doubled after the September release
2. The cause is the new fraud check running inline
3. Moving it async brings p99 back to 410ms
4. Ask: approve two days of work next sprint
```

Claude는 사용자가 쓴 언어로 답하고, 자료는 자료의 언어(한국어 또는 영어)로 만듭니다.

## 작업 흐름

모든 작업은 현재 폴더 아래 `decks/<slug>/`에서 이루어집니다. slug는 주제를 짧은 영어 kebab-case로 줄인 이름입니다(예: `decks/redis-sessions/`). 단계마다 이 폴더의 파일을 읽고 쓰기 때문에 언제든 멈출 수 있습니다.

### 1. 브리프

Claude는 처음 요청에서 알 수 없었던 것만 묻습니다.

- 청중과 목표(발표가 끝난 뒤 청중이 무엇을 해야 하는지)
- 분량(슬라이드 수 또는 발표 시간. 시간으로 답하면 1분에 약 1장으로 환산)
- 내용 출처: 주제만 / 자료 있음(경로) / 목차 있음
- 레퍼런스와 이미지(로고 포함)
- 선택: 발표 날짜, 행사 이름, 발표자 이름, 말투, 직접 쓴 글 샘플

주제만 주면 슬라이드에 쓸 사실(수치, 날짜, 고유명사, 실제 사례)을 묻습니다. 없다고 하면 브리프에 `lack of factual material`이 기록되고, 이후 단계에서 빈자리를 채우려고 사실을 지어내지 않습니다.

파일: `brief.md`

### 2. 스타일

Claude가 스타일 후보 세 개를 만들고, 브리프의 실제 내용으로 각각 샘플 슬라이드를 렌더링해 비교 이미지 한 장(`candidates/compare.png`)으로 보여 줍니다. 하나를 고르거나 "A의 색에 B의 레이아웃"처럼 섞어 달라고 하면 네 번째 후보를 렌더링해 보여 줍니다.

그다음 세부 사항을 정합니다. 바꿀 때마다 샘플을 다시 렌더링해 보여 줍니다.

1. **폰트.** 후보 2~3개를 나란히 렌더링해 비교합니다. [폰트](#폰트) 참고.
2. **색, 표지, 구조.** 바꾸고 싶을 때만: 표지 유형(type, band, image), 구조(주장형 제목, 또는 보고서처럼 제목 아래 거버닝 메시지를 두는 governing), 본문 기본 구성(split, statement, figure).
3. **로고와 푸터.** 푸터에는 기본으로 행사 이름과 쪽 번호가 들어갑니다.
4. **이미지 톤과 배치**(사진을 쓰는 경우만). 사용자의 사진 한 장으로 비교 이미지를 만듭니다. 톤 처리 네 가지(none, harmonize, gray, duotone)와 배치 세 가지(bleed-panel, bleed-scrim, split). [이미지와 배치](#이미지와-배치) 참고.

이 단계에서 생기는 파일: `candidates/A`, `B`, `C`(각각 `style.json`, `sample.pptx`, `renders/`), `candidates/sample.json`, `candidates/compare.png`, 폰트 비교용 `candidates/F1`, `F2`, ..., `candidates/imagery/`. 스타일이 확정되면 `style.json`을 저장하고 `candidates/`는 지웁니다.

`style.json` 원문은 보여 주지 않습니다. 모든 선택은 렌더링된 이미지를 보고 합니다.

### 3. 목차와 제작

먼저 스토리보드를 씁니다. 한 줄 논지와 슬라이드 제목만 나열한 것입니다. 제목은 주장 문장이고, 순서대로 읽으면 그 자체로 논리가 이어져야 합니다. 주제만 받았다면 스토리보드를 보여 주고 확인을 받습니다. 목차를 받았다면 순서를 그대로 따르고, 제목을 주장 문장으로 다듬은 곳이 있으면 알려 줍니다.

그다음 `outline.md`에 슬라이드별 표를 씁니다. 제목, 근거 내용, 시각화 유형(한 문장, 큰 숫자, 차트, 비교표, 2×2, 프로세스, 전면 이미지, 인용, 다이어그램, 주석 단 스크린샷), 에셋, 이미지 배치와 이유, 발표자 노트, 수치 출처가 들어갑니다.

이어서 내장 라이브러리 `deckkit`으로 `build.py`를 작성해 실행하고, 빌드 경고(텍스트 넘침, 단어 중간 줄바꿈, 미설치 폰트, 낮은 이미지 해상도 등)를 모두 해결합니다.

파일: `outline.md`, `assets/`(정리된 이미지, `images.json`, `treated/`, `icons/`, `credits.json`), `build.py`, `out.pptx`

### 4. 린트와 검수

1. `lint.py`가 텍스트와 XML에서 AI 티를 찾습니다(`lint.json` 생성).
2. `render.py`가 모든 슬라이드를 렌더링합니다(`renders/slide-01.png`, ..., `renders/sheet.png`).
3. 별도의 `deck-reviewer` 에이전트가 렌더링 이미지, 브리프, 스타일, 목차만 보고 판정합니다. `build.py`나 이전 검수 결과는 보지 않습니다.
4. 결과는 `review-N.md`입니다. 첫 줄이 `RESULT: PASS` 또는 `RESULT: FAIL`입니다.

FAIL이면 Claude가 `build.py`에서 blocker와 major를 모두 고치고, 고친 내용을 해당 검수 파일의 `## Applied` 아래에 적은 뒤 다시 빌드하고 다시 검수합니다. 검수는 최대 3번입니다. 세 번째도 FAIL이면 그대로 받기, 문제 슬라이드 빼기, 직접 지시하기 중에서 고르게 됩니다.

### 5. 마무리

PASS가 나오면 Claude가 파일 경로와 슬라이드 수, 고른 스타일, 남은 minor 문제, 아직 `[출처 필요]`(영어 자료는 `[source needed]`)가 남은 슬라이드 번호를 알려 줍니다. 작업용 파일(`renders/`, `candidates/`, `assets/_cand/`, `lint.json`)은 지우고 `brief.md`, `style.json`, `outline.md`, `build.py`, `out.pptx`, `assets/`, `review-*.md`는 남깁니다.

### 이어서 하기

```
/ppt-craft:deck decks/<slug>
```

폴더에 어떤 파일이 있는지 보고 다음 단계부터 이어서 진행합니다. PASS 이후에 수정을 요청하면 제작과 검수를 다시 거칩니다.

### 단계만 따로 실행하기

단계별 스킬은 자료 폴더를 인자로 받습니다.

```
/ppt-craft:deck-brief decks/<slug>
/ppt-craft:deck-style decks/<slug>
/ppt-craft:deck-build decks/<slug>
/ppt-craft:deck-review decks/<slug>
```

`deck-style`에는 `brief.md`가, `deck-build`에는 `brief.md`와 `style.json`이 있어야 합니다. 보통은 `/ppt-craft:deck`이 순서대로 실행합니다.

## 레퍼런스 주기

Claude가 물을 때 알려 주거나 처음 요청에 함께 적으면 됩니다. 가져오는 것은 색, 타이포그래피, 그리드, 여백, 모티프 같은 시각 속성뿐입니다. 로고, 일러스트, 사진, 템플릿 파일은 가져오지 않습니다.

| 레퍼런스 | 처리 방식 |
|---|---|
| `.pptx` 파일 | 파일에서 색, 폰트, 크기, 여백을 읽고, 슬라이드를 렌더링해 레이아웃과 모티프를 직접 봅니다 |
| 이미지(스크린샷, 슬라이드 사진) | Claude가 보고 색(추정 hex), 서체 계열, 그리드, 여백, 모티프를 정리합니다 |
| URL | 브라우저 도구가 있으면 캡처해서 보고, 없으면 페이지 HTML/CSS에서 색과 폰트를 읽습니다 |
| SlidesCarnival, Slidesgo, Microsoft Create 테마 페이지 | 사용자가 준 그 한 페이지만 엽니다. 검색, 목록 탐색, 다운로드는 하지 않습니다 |
| Canva, 미리캔버스, 망고보드, Google Slides 템플릿 | 이용 약관 때문에 자동으로 접근하지 않습니다. 스크린샷을 보내 주세요 |
| "웹에서 찾아줘" | 웹 검색을 하되 위 사이트만 엽니다. 실패하면 프리셋으로 대신합니다 |

레퍼런스가 있으면 후보 세 개는 A 충실한 재현, B 레퍼런스의 AI 티와 약점을 걷어 낸 정제판, C 인상은 같되 레이아웃과 대비를 바꾼 과감한 변형입니다.

레퍼런스가 없으면 내장 프리셋 세 개에서 출발해 브리프에 맞게 조정합니다.

| 프리셋 | 용도 |
|---|---|
| `report-grid` | 한국 기업 보고서 관례(제목 / 거버닝 메시지 / 본문). 사업, 내부 보고, 제안서 |
| `keynote-type` | 큰 글씨로 한 장에 한 문장. 기술 발표, 컨퍼런스, 키노트 |
| `academic-figure` | 그림과 표가 주인공. 연구 발표, 논문 발표, 랩미팅 |

내려받은 템플릿 파일을 직접 쓸 생각이라면 조건을 지켜야 합니다. Slidesgo 무료판은 크레딧 슬라이드를 유지해야 하고, SlidesCarnival은 출처 표기와 링크가 필요하며, 망고보드 무료판은 워터마크를 유지해야 합니다.

스타일을 다시 쓰고 싶으면 "이 스타일 저장해줘"라고 하세요. 플러그인 데이터 폴더에 저장되고 다음부터 후보로 나옵니다.

## 내용 입력 방식과 활용 예

| 주는 것 | Claude가 하는 일 |
|---|---|
| 주제만 | 슬라이드별로 쓸 사실을 묻고, 스토리보드를 제안해 확인받습니다 |
| 문서(PDF, Markdown, 메모) | 읽고 나서 주장, 수치와 그 출처(파일, 쪽, URL), 고유명사, 사례를 정리합니다 |
| 직접 쓴 목차 | 순서와 구조를 그대로 두고, 제목만 주장 문장으로 다듬은 뒤 그 사실을 알려 줍니다 |

수치는 자료에 있는 그대로 옮깁니다. 출처가 없는 수치는 슬라이드에 `[출처 필요]`로 남겨 나중에 채울 수 있게 하고, 지어내지 않습니다. 수치가 있는 슬라이드에는 작은 출처 줄도 들어갑니다.

활용 예:

- **기술 발표, 컨퍼런스:** `keynote-type`. 슬라이드마다 주장 하나, 핵심 숫자는 크게 키워 리듬을 깨고, 기기 목업 대신 주석 단 스크린샷을 씁니다.
- **학회, 랩미팅:** `academic-figure`. 번호 붙은 그림과 캡션, 축과 단위, 표본 수(`n`, 자료에 있을 때만)가 있는 차트.
- **사업 보고, 제안:** `report-grid`에 `governing` 구조. 슬라이드마다 제목과 거버닝 문장 하나, 마지막은 결정이나 요청으로 끝납니다.
- **강의, 교육:** 어떤 프리셋이든 됩니다. 빽빽한 참고 슬라이드와 한 문장 슬라이드를 섞고, 말할 내용은 발표자 노트에 둡니다.

## 폰트

- 한 번 묻고, 고른 폰트를 플러그인 데이터 폴더(`~/.claude/plugins/data/ppt-craft-ppt-craft/`)의 `prefs.json`에 기억합니다. 다음에는 같은 폰트를 먼저 제안합니다.
- 후보 폰트는 사용자의 샘플 슬라이드에 나란히 렌더링해 비교합니다. 너무 흔한 기본 폰트(Inter, Roboto, Arial, Poppins, Montserrat, Calibri, 맑은 고딕 등)는 사용자가 직접 말하지 않는 한 후보에서 뺍니다.
- 한국어 자료에는 한글 글리프가 있는 폰트만 후보로 나옵니다.
- 무료 폰트 카탈로그(`data/fonts.json`)에서 설치된 것과 안 된 것을 섞어 제안합니다. 예: Pretendard, Wanted Sans, SUIT, IBM Plex Sans KR, 나눔명조(Nanum Myeongjo), 고운바탕(Gowun Batang), JetBrains Mono, Source Serif 4. 설치되지 않은 폰트는 동의를 받아 내려받고 **관리자 권한 없이 현재 사용자에게만** 설치합니다.
  - Windows: `%LOCALAPPDATA%\Microsoft\Windows\Fonts`
  - macOS: `~/Library/Fonts`
  - Linux: `~/.local/share/fonts`
- 폰트를 설치한 뒤에는 PowerPoint를 다시 시작하세요.
- 카탈로그의 일부 폰트(Gmarket Sans, LINE Seed Sans KR, Paperlogy, NanumSquare Neo)는 `manual`로 표시되어 있습니다. 이 경우 공식 다운로드 페이지를 알려 드립니다.
- 폰트는 자동으로 포함(embed)되지 않습니다. 받는 사람 PC에 폰트가 없을 수 있다면 PowerPoint에서 파일 > 옵션 > 저장 > "파일의 글꼴 포함"을 켜고 저장하세요.

## 이미지와 배치

### 이미지를 어디서 가져오나

1. 사용자의 이미지가 먼저입니다(사진, 스크린샷, 다이어그램, 로고). 로고는 브리프에 표시해 두면 모든 본문 슬라이드의 같은 자리에 들어갑니다.
2. 선택 사항으로, 동의를 받으면 무료 사진이나 AI 생성 이미지를 씁니다. 둘은 동등한 선택지입니다.
3. 그 밖에는 이미지를 넣지 않습니다. 이미지 없는 슬라이드는 언제나 허용되고, 이미지는 슬라이드의 주장을 뒷받침할 때만 넣습니다.

원본은 건드리지 않습니다. EXIF 회전을 적용하고 긴 변을 3000px 이하로 줄인 사본을 `assets/`에 만듭니다.

### 배치 패턴

이미지가 들어가는 슬라이드는 내용과 이미지를 보고 패턴 하나를 고르고, 그 이유를 목차에 적습니다.

| 패턴 | 쓰는 곳 |
|---|---|
| `bleed-panel` | 전면 사진 위에 단색 패널을 두고 글을 얹음 |
| `bleed-scrim` | 전면 사진 위에 대비를 검사한 반투명 단색 띠. 대비가 부족하거나 15단어를 넘으면 `bleed-panel`로 바뀜 |
| `split` | 사진을 슬라이드 끝까지 반만 채우고 옆에 글(기본 사진:글 5:7, 사진이 핵심이면 7:5) |
| `inset` | 본문 영역 안에 캡션 달린 사진 |
| `strip` | 파노라마 띠(3:1 이상) |
| `gallery` | 비교할 이미지 2~4장, 큰 "히어로" 이미지 하나도 가능 |
| `figure` | 다이어그램이나 로고를 잘리지 않게 넣고 캡션 |
| `annotated` | 스크린샷에 중요한 곳을 가리키는 주석 |
| `type-only` | 이미지 없음 |

공통 규칙: 전면 사진 슬라이드는 최대 `max_bleed`장(기본 3장), 같은 패턴은 3장 연속 금지, 글은 이미지 초점의 반대편에, 스크림은 단색만(그라데이션 금지), 가짜 기기 프레임이나 도형 마스크 금지.

### 톤 처리와 텍스처

- 자료 안의 모든 사진은 같은 톤 처리를 씁니다: `none`, `gray`, `duotone`(스타일의 잉크색과 배경색 사용). 출처가 다른 사진이 어울리도록 채도를 살짝 낮추는 `harmonize`는 기본으로 켜져 있습니다. 렌더링 비교를 보고 고릅니다.
- 텍스처(paper, grain, dots, grid)는 요청할 때만, 불투명도 0.1 이하로, 표지나 섹션 슬라이드 한 장에만 넣습니다.

### 초점, 캡션, 출처 표기

- Claude가 이미지마다 초점(꼭 보여야 하는 영역)과 잘리면 안 되는 부분(얼굴, 글자)을 표시하고, 그에 맞춰 자릅니다.
- 모든 사진과 그림에는 출처(출처, 날짜, 장소)가 있는 캡션이 붙습니다. 없으면 슬라이드에 `[출처 필요]`가 표시됩니다.
- 내려받은 이미지의 라이선스는 `assets/credits.json`에 기록됩니다. 크레딧 문구는 그 이미지를 쓰는 슬라이드의 발표자 노트에 들어가고, 출처 표기 의무가 있거나 동일조건변경허락(share-alike)이거나 AI 생성인 이미지는 마지막의 작은 크레딧 슬라이드에도 나열됩니다.

### 선택 사항: 무료 에셋

동의하기 전에는 아무것도 내려받지 않습니다. 세션마다 한 번, 무엇이 어디로 가는지 알려 주고 묻습니다.

- 사진: Openverse, Wikimedia Commons(키 불필요), Pexels, Pixabay(무료 키)
- AI 이미지: Cloudflare Workers AI, Pollinations, Hugging Face(키 필요). 키가 없으면 자원봉사로 운영되는 AI Horde(키 불필요, 576px 이하 작은 이미지)
- 아이콘: Iconify, 허용적 라이선스(MIT, ISC, Apache-2.0)만, 자료 하나에 아이콘 세트 하나
- 폰트: Google Fonts, GitHub

거절하면 사용자의 이미지와 이미 설치된 폰트만 쓰고 아이콘은 넣지 않습니다.

### API 키

모든 키는 선택 사항이고 무료로 받을 수 있습니다. 환경 변수로 설정한 뒤 Claude Code를 다시 시작하세요.

| 변수 | 용도 |
|---|---|
| `PEXELS_API_KEY` | Pexels 사진 검색 |
| `PIXABAY_API_KEY` | Pixabay 사진 검색 |
| `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` | FLUX.1-schnell 이미지 생성(무료 사용량, AI Horde보다 큰 이미지) |
| `POLLINATIONS_API_KEY` | 이미지 생성 |
| `HF_TOKEN` | Hugging Face 이미지 생성(소액 무료 크레딧) |

키를 채팅에 붙여 넣지 마세요. 스크립트는 키를 찾았는지만 알려 주고 값은 출력하지 않습니다.

### 개인정보

네트워크 사용을 허락하면 검색어와 이미지 생성 프롬프트가 위 서비스로 전송됩니다. Claude는 브리프의 기밀 내용을 여기에 넣지 않지만, 주제 자체가 민감하다면 동의하기 전에 한 번 더 생각해 보세요. 키가 없으면 프롬프트는 자원봉사자가 운영하는 AI Horde로 갑니다.

## 기존 자료 검수하기

```
/ppt-craft:deck-review path/to/file.pptx
```

"PPT 검수해줘", "AI 티 나는지 봐줘"라고 해도 됩니다. 결과는 파일 옆의 `<파일 이름>-review/` 폴더에 `lint.json`, `renders/`, `review-1.md`로 생깁니다. 임시 사본을 렌더링하므로 PowerPoint에서 파일을 열어 둔 채로 해도 안전합니다. 원본 파일은 고치지 않습니다. 다시 만들고 싶다면 그 파일을 레퍼런스로 삼아 `/ppt-craft:deck`으로 새로 만들 수 있습니다.

**린트**(텍스트와 XML 자동 검사):

- 텍스트: 남은 자리표시자, 이모지, 상투적인 AI 문구와 번역투(영어·한국어 단어 목록), 엠 대시, 콜론 제목과 Title Case 제목, "감사합니다"·"Q&A" 같은 제목, 출처 없는 수치, 가짜 이름(John Doe, Acme), 영어 자료의 곧은 따옴표, 셋씩 맞춘 글머리표, 한 목록에 5개 넘는 글머리표
- 폰트: 한글에 동아시아(ea) 폰트 미지정(대체 폰트로 바뀜), `lang="ko-KR"`이 없는 한글 런(단어 중간 줄바꿈), 흔한 기본 폰트
- 도형과 색: 그라데이션, 그림자, 제목 아래 강조선, 카드의 색 띠, 도형으로 그린 가짜 막대 차트, 순수 검정 글자, 한 슬라이드에 너무 많은 색
- 이미지: `max_bleed`를 넘는 전면 사진 슬라이드, 같은 레이아웃·패턴 3장 연속, 요소가 너무 많은 이미지 슬라이드, 여러 장에 쓴 텍스처

**검수 에이전트**(렌더링 이미지로 판단): 잘리거나 겹친 글자, 폰트 대체, 레이아웃 반복과 리듬, 카드 그리드, 전부 가운데 정렬, 대비와 글자 크기, 제목만 읽어도 논리가 이어지는지, 수치 출처가 보이는지, 차트 축과 단위, 발표자 노트, 자르기와 이미지 품질, 사진 위 글자의 가독성, 사진 톤 일관성, 캡션, 그리고 사람이 만든 신호(구체적 사실, 실명, 주석, 밀도 변화).

규칙 ID와 설명은 [`rules/tells.md`](../rules/tells.md)에 있습니다.

| 등급 | 의미 |
|---|---|
| blocker | 그대로 내보내면 안 됨(예: 남은 자리표시자, 이모지, 동아시아 폰트 미지정) |
| major | 분명한 AI 티이거나 가독성 문제 |
| minor | 다듬으면 좋은 것 |

`RESULT: PASS`는 blocker와 major가 하나도 없다는 뜻입니다. 모든 지적에는 규칙 ID와 구체적인 수정 방법(어느 열, 어느 문장)이 붙습니다.

## 나중에 고치기

`out.pptx`의 모든 요소는 PowerPoint 기본 개체라서 직접 편집할 수 있습니다.

- **텍스트**는 일반 텍스트 상자와 제목 개체 틀에 있고, 글머리표도 실제 단락 글머리표입니다.
- **차트**는 PowerPoint 기본 차트입니다. 마우스 오른쪽 > 데이터 편집으로 숫자를 바꿀 수 있습니다.
- **사진**은 기본 자르기 기능을 씁니다. 원본 전체가 파일 안에 남아 있으니 그림 서식 > 자르기로 다시 자를 수 있습니다.
- **아이콘**은 SVG입니다. PowerPoint 2019와 365에서는 편집 가능한 벡터이고, 이전 버전에서는 PNG로 대신 표시됩니다.
- **스크림과 패널**은 단색 채우기에 투명도를 준 일반 도형입니다.
- **발표자 노트**도 채워져 있습니다.

고치는 방법은 두 가지입니다.

- Claude에게 맡기기: `/ppt-craft:deck decks/<slug>`와 함께 바꿀 내용을 말하면 `build.py`를 고쳐 다시 빌드하고 다시 검수합니다.
- PowerPoint에서 직접 고치기: `build.py`로 다시 빌드하면 `out.pptx`를 덮어쓰므로, 직접 고친 파일은 다른 이름으로 저장하거나 Claude와의 작업을 마친 뒤에 고치세요.

## 예시

예시는 가상의 샘플 내용이고, 사진은 포함되어 있지 않습니다. 폴더마다 컨택트 시트를 만든 `build.py`와 `style.json`이 들어 있습니다.

| 예시 | 컨택트 시트 | 소스 |
|---|---|---|
| 사업 보고 | [sheet.jpg](../examples/business-report/sheet.jpg) | [build.py](../examples/business-report/build.py), [style.json](../examples/business-report/style.json) |
| 컨퍼런스 발표 | [sheet.jpg](../examples/conference-talk/sheet.jpg) | [build.py](../examples/conference-talk/build.py), [style.json](../examples/conference-talk/style.json) |
| 연구 발표 | [sheet.jpg](../examples/research-talk/sheet.jpg) | [build.py](../examples/research-talk/build.py), [style.json](../examples/research-talk/style.json) |

스타일 단계에서 보게 되는 [스타일 후보 비교](../examples/style-candidates.jpg)와 [이미지 배치 패턴](../examples/image-patterns.jpg)도 있습니다.

## 자주 묻는 질문과 문제 해결

**"렌더러 없음" / 렌더가 종료 코드 2로 끝남**
PowerPoint(Windows) 또는 LibreOffice와 poppler나 pymupdf를 설치한 뒤([필요한 것](#필요한-것) 참고) `render.py --check`로 확인하세요. 렌더링 없이는 검수를 하지 않습니다. LibreOffice는 변환할 때 숨긴 슬라이드를 빼 버린다는 점도 알아 두세요.

**`ModuleNotFoundError`**
`python`이 가리키는 Python에 패키지가 없는 것입니다. Claude에게 설치를 맡기거나 `python -m pip install -r "<플러그인 폴더>/requirements.txt"`를 실행하세요.

**폰트가 설치되어 있지 않음 / 글자가 맑은 고딕이나 굴림으로 보임**
빌드할 때 `Font '…' is not installed` 경고가 나오면 설치할지 다른 폰트로 바꿀지 묻고 멈춥니다. 설치한 뒤에는 PowerPoint를 다시 시작하세요. Microsoft Store에서 설치한 Python은 폰트를 쓸 수 없어서 `fonts.py install`이 실패합니다. 이때는 Claude가 알려 주는 공식 링크에서 폰트 파일을 받아 직접 설치하세요. 받는 사람을 위해서는 폰트를 포함해 저장하세요(파일 > 옵션 > 저장).

**PowerPoint가 바쁘거나 렌더가 멈춤**
Windows에서는 PowerPoint를 백그라운드로 돌려 렌더링합니다. 임시 사본을 열고, 직접 띄운 PowerPoint이면서 열린 창이 없을 때만 종료합니다. PowerPoint에 대화 상자(저장 확인, 로그인, 업데이트)가 떠 있으면 내보내기가 막힐 수 있으니 닫고 다시 시도하세요. 15분이 넘으면 렌더를 중단합니다. PowerPoint가 계속 방해된다면 LibreOffice를 설치하고 `render.py`에 `--backend libreoffice`를 주세요.

**한글 단어가 줄 중간에서 끊김**
PowerPoint는 텍스트가 한국어로 지정되지 않으면 한글 단어를 중간에서 끊습니다. ppt-craft는 모든 한글 런에 `lang="ko-KR"`을 넣고, 빠진 런은 린트가 잡아냅니다(T11). PowerPoint에서 직접 추가한 텍스트는 선택한 뒤 검토 > 언어에서 한국어로 지정하세요.

**네트워크 사용을 거절했는데 이미지를 쓸 수 있나요?**
네, 사용자의 이미지는 쓸 수 있습니다. 브리프에 경로를 적거나 Claude에게 알려 주세요. 아이콘과 카탈로그 폰트는 네트워크가 필요합니다.

**내려받은 이미지가 너무 작음**
`photo get`은 폭이 좁은 이미지에 경고(`low_res`)를 내고, 그 이미지는 작은 자리에만 씁니다. 키 없이 쓰는 AI Horde 이미지는 최대 576px입니다. 더 큰 생성 이미지가 필요하면 `CLOUDFLARE_ACCOUNT_ID`와 `CLOUDFLARE_API_TOKEN`을 설정하세요.

**중간에 멈춰도 되나요?**
네. 모든 것이 `decks/<slug>/`에 있습니다. `/ppt-craft:deck decks/<slug>`로 이어서 하면 됩니다.
