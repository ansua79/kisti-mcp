# *KISTI-MCP v0.3.32.2*

KISTI-MCP는 한국과학기술정보연구원(KISTI)에서 서비스하는 ScienceON(과학기술 지식인프라), NTIS(국가과학기술지식정보서비스), DataON(국가연구데이터플랫폼) 등 다양한 플랫폼의 OpenAPI를 활용할 수 있는 MCP 서버입니다. 
ScienceON, NTIS, DataON의 논문, 특허, 보고서, 국가R&D과제·성과, 연구데이터 등 **총 32종 도구**를 제공합니다.
MCP(Model Context Protocol)를 이용하여 거대언어모델과 KISTI가 제공하는 서비스 간 원활한 통합을 지원합니다.

> **빠른 시작 (권장)**: 별도 설치 없이 PyPI에서 바로 실행 — `uvx kisti-mcp`
> ([설치](#설치) · [도구 등록](#도구-등록) 참고)
> 
> 🧑‍💻 **설치가 어려운 초보자라면?**
> 명령줄(uvx)·JSON 설정이 부담스럽다면 GUI 설치 관리 도구 **[STIMCP-Manager](https://github.com/ansua79/stimcp-manager)** 를 사용해 보세요.
> 카탈로그에서 kisti-mcp를 골라 **원클릭으로 Claude Desktop·VS Code에 등록**할 수 있습니다. (Windows 10/11 전용) 

![KISTI-MCP 데모](media/KISTI-MCP-demo.gif)

## 도구

- **ScienceON** (17종): 논문·특허·보고서 검색/상세/인용, 과학기술 동향, 과학향기 칼럼, 연구자, 연구기관, 기술트렌드, 금주의 과학기술뉴스
- **NTIS** (13종): 국가R&D 과제·성과·연구보고서 검색, 수행기관 R&D현황, 이슈로보는R&D, 용어사전, 분류/중점기술 코드, 분류코드 추천, 연관콘텐츠 추천, 위탁/공동연구, 과제참여정보, 통합검색, 출연(연) 연구자정보
- **DataON** (2종): 국가R&D 연구데이터 검색 및 메타데이터 상세 정보 조회

### NTIS 권한별 자동 폴백

NTIS의 **국가R&D 과제검색**과 **성과검색**은 이용자격(전체용·기관용·전문기관용)에 따라
엔드포인트와 제공 필드가 다릅니다. 본 서버는 이를 **하나의 도구로 통합**하고,
내부에서 **전문기관용 → 기관용 → 전체용** 순으로 자동 호출하여 발급키 권한이 닿는
가장 풍부한 응답을 반환합니다. 사용자/LLM은 이용자격을 구분할 필요가 없습니다.

- 과제검색: `projectAllSearch`(전문기관) → `public_project`(전체)
- 성과검색: `natRnDAllSearch`(전문기관) → `natRnDSearch`(기관) → `public_result`(전체)

> 기관용/전문기관용 API는 NTIS에서 해당 자격으로 활용신청·승인된 발급키가 있어야
> 상위 레벨 응답을 받을 수 있으며, 권한이 없으면 자동으로 하위 레벨(전체용)로 폴백됩니다.

## 주요 기능

### ScienceON (17종, 전체기능대응완료)

| 도구 | 설명 |
|------|------|
| 논문 검색 / 상세 | 키워드 검색, DOI·소속·발행기관·페이지·ISSN·키워드·초록 전문·원문URL 반환 |
| 특허 검색 / 상세 / 인용 | 키워드 검색, 출원/공개/등록번호·상태·IPC 상세, 인용/피인용 특허 관계 |
| 보고서 검색 / 상세 | R&D 보고서 검색, 주관/공동연구기관·기여자·표준분류·초록 전문 반환 |
| 과학기술 동향 검색 / 상세 | 국내외 과학기술 동향 기사 |
| 과학향기 검색 / 상세 | 발행연도(YYYY)로 대중과학 칼럼 검색 및 본문 |
| 연구자 검색 / 상세 | 국내 식별 연구자 (소속, 논문/특허/보고서 실적) |
| 연구기관 검색 / 상세 | 국내 식별 연구기관 (한글 기관명 권장) |
| 기술트렌드 검색 | 신기술 토픽 정의·연관키워드·PDF |
| 금주의 과학기술뉴스 | 날짜(YYYYMMDD)로 주차별 뉴스 조회 |

### NTIS (13종, 전체기능대응완료)

| 도구 | 설명 |
|------|------|
| 국가R&D 과제 검색 | 키워드 검색 (전문기관용→전체용 자동 폴백) |
| 국가R&D 성과 검색 | 논문/특허/연구시설장비/보고서 (전문→기관→전체 폴백) |
| 국가R&D 연구보고서 검색 | 연구보고서 메타정보·원문 URL |
| 수행기관 R&D현황 조회 | 기관명/사업자번호로 연도별 과제·논문·특허 현황 |
| 이슈로보는R&D | 최신 과학기술 이슈 키워드·연관과제 |
| 용어사전 조회 | 국가R&D 용어 검색 (한/영, 설명, 연관어) |
| 분류/중점기술 코드 검색 | 과학기술표준분류·국가중점기술 코드 |
| 과학기술 분류코드 추천 | 연구초록으로 분류코드 AI 추천 |
| 과제 연관콘텐츠 추천 | 과제번호로 연관 논문/특허/보고서/과제 |
| 위탁/공동연구 과제 정보 | 주관과제번호로 위탁/공동 과제 조회 |
| 과제참여정보 | 연구자 성명+국가연구자번호로 참여기간·인건비계상률 |
| 통합검색 | 과제/논문/특허/보고서/장비 통합 검색 |
| 출연(연) 연구자정보 | 연구자명+번호로 실적 종합 조회 |

### DataON (2종)

| 도구 | 설명 |
|------|------|
| 연구데이터 검색 | 키워드로 공개 연구데이터 검색 (제목, 작성자, svcId) |
| 연구데이터 상세정보 | svcId로 메타데이터, 포맷, 권리정보 조회 |



## History

| 버전     | 날짜         | 주요 사항                                                                             |
| ------ | ---------- | --------------------------------------------------------------------------------- |
| 0.3.32.2 | 2026-06-23 | - **ScienceON 검색/상세 출력 대폭 보강** — API가 제공하는 서지정보를 최대한 반환. 논문에 **DOI**·소속·발행기관·페이지·ISSN·DB구분·원문URL·ScienceON링크 추가, 특허에 출원/공개/등록번호·공고일 추가, 보고서에 주관/연구관리/공동연구/협력기관·기여자·표준분류 추가, 동향/과학향기/연구자/연구기관/트렌드/뉴스도 항목 보강<br>- **초록·본문·정의 등 긴 텍스트를 전문(全文)으로 반환** (기존 300자 절단 → LLM이 온전한 내용으로 판단 가능)<br>- **일반검색 ↔ 상세검색 출력 필드 일치** (상세가 목록보다 빈약하던 문제 해소)<br>- **`include_body` 옵션 추가** — `False`로 호출 시 긴 텍스트를 제외하고 서지·DOI·링크만 반환(컨텍스트가 작은 로컬 소형 모델·목록 훑기용, 논문 10건 기준 출력 ~60% 감소)<br>- **특허 인용/피인용 정보 보강** (인용구분·발명자·IPC·국가·CN 추가)<br>- 응답에 오지 않는 필드를 참조하던 코드 정리(논문/보고서 상세의 미제공 인용·참고문헌 출력부 제거) |
| 0.3.32.1 | 2026-06-23 | - **버그 수정: 서비스별 독립 활성화** — NTIS/DataON도 키 누락 시 해당 서비스만 비활성화되도록 검증 로직을 ScienceON과 일관되게 수정(키가 없는 서비스가 '활성'으로 잘못 동작하던 문제 해결)<br>- DataON OpenAPI 신청 정책 변경 안내 반영(2026년 3월부터 기관사용자만 신규 신청/연장 가능) |
| 0.3.32 | 2026-06-15 | - **총 32종 도구로 대폭 확장** (ScienceON 17 + NTIS 13 + DataON 2)<br>- ScienceON 7→17종: 동향·과학향기·연구자·연구기관·기술트렌드·금주뉴스 추가<br>- NTIS 3→13종: 성과검색·연구보고서·수행기관현황·이슈로보는R&D·용어사전·분류코드·위탁공동·과제참여·통합검색·연구자정보 추가<br>- NTIS 과제/성과검색 권한별 자동 폴백(전문기관→기관→전체)<br>- 토큰 캐싱, HTML 엔티티 정제 개선(가독성↑)<br>- DataON: OpenAPI 서비스 점검/이용제한 안내 표기 |
| 0.3.12b0 | 2026-03-04 | - PyPI 정식 배포<br>- uvx 설치 방식 지원<br>- README 업데이트 |
| 0.3.12a | 2025-11-11 | - 버그 수정:  get_paper_details 메서드 수정<br>- 기능 개선: 논문/특허/보고서 상세정보에 ScienceON 웹 링크 추가<br>- 기능 개선: 특허 검색 결과에 CN 번호 표시 및 안내 문구 추가 |
| 0.3.12 | 2025-11-05 | - DataON 연구데이터 및 메타정보 검색 기능 지원 등 총 12종 도구 지원 |
| 0.2.10a | 2025-10-29 | - NTIS API Key 통합 및 내부 프로세스 개선 |
| 0.2.10 | 2025-08-13 | - NTIS 과제 검색 도구 기능 지원<br>- NTIS 과학기술분류 추천 도구 기능 지원<br>- NTIS 과제 연관콘텐츠 추천 도구 기능 지원 등 총 10종 도구 지원 |
| 0.1.7  | 2025-07-22 | - 첫 번째 릴리즈<br>- ScienceON 의 논문, 특허, 보고서 등 총 7종의 API 사용 지원                         |


## 데이터 소스

- **ScienceON**: 한국과학기술정보연구원의 통합 과학기술 정보서비스
  - **논문 데이터**: SCIE, SCOPUS, 한국과학기술논문 등 99.7% 포함
  - **특허 데이터**: 국내외 특허 정보 포함
  - **보고서 데이터**: 국가 R&D 보고서, 기술동향 보고서 등

- **NTIS**: 국가과학기술지식정보서비스
  - **국가R&D 과제/성과/연구보고서**: 정부 R&D 사업·과제·논문·특허·시설장비·보고서 정보
  - **수행기관 R&D현황·이슈로보는R&D·용어사전·분류코드**: 기관 현황, 최신 이슈, 용어, 분류/중점기술 코드
  - **분류코드 추천·연관콘텐츠·위탁공동·과제참여·통합검색·연구자정보**
  - ⚠️ NTIS는 **API마다 활용신청 별도, 유효기간 1년, IP 제한 가능** (아래 [요구사항](#요구사항) 참고)

- **DataON**: 국가연구데이터플랫폼
  - **연구데이터/메타데이터**: 공공 연구데이터, 데이터셋, DOI, 라이선스 정보
  - ⚠️ **현재 OpenAPI 서비스 점검/이용제한 상태로 확인됨** (도구는 제공되나 정상 응답이 오지 않을 수 있음)


## 설치

> 🧑‍💻 **설치가 어려운 초보자라면?**
> 명령줄(uvx)·JSON 설정이 부담스럽다면 GUI 설치 관리 도구 **[STIMCP-Manager](https://github.com/ansua79/stimcp-manager)** 를 사용해 보세요.
> 카탈로그에서 kisti-mcp를 골라 **원클릭으로 Claude Desktop·VS Code에 등록**할 수 있습니다. (Windows 10/11 전용)

### 요구사항

- 플랫폼 별 API Key 발급 관련 정보
	- ScienceON - API Key, Client ID, MAC Address **(1세트로 17개 API 모두 사용 가능 — 가장 편리)**
		- https://scienceon.kisti.re.kr/por/oapi/openApi.do 사이트 방문
		- 회원가입 및 로그인
		- API Key 및 Client ID 발급 신청
		- ✅ 한 번 발급받은 인증정보로 ScienceON의 모든 도구를 사용할 수 있습니다.
	- NTIS - API Key **(⚠️ API마다 활용신청 별도 + 유효기간 1년 + IP 제한 가능)**
		- https://www.ntis.go.kr/rndopen/api/mng/apiMain.do 사이트 방문
		- 회원가입 및 로그인
		- ⚠️ **NTIS 운영 특성**: 키는 하나지만 **사용하려는 API마다 개별 활용신청**이 필요하며(미신청 API는 같은 키로도 `유효한 인증키가 아닙니다` 오류), **유효기간은 승인일로부터 1년**, **신청 시 IP 등록 항목이 있어 환경에 따라 `접근 허용 IP가 아닙니다` 오류**가 날 수 있습니다.
		- 데이터활용 > OpenAPI > 사용하려는 API별 활용신청 (전체용 우선)
			- 국가R&D 과제검색(대국민용) → search_ntis_rnd_projects
			- 국가R&D 성과검색(전체용) → search_ntis_rnd_outcomes
			- 국가R&D 연구보고서 검색(전체용) → search_ntis_research_reports
			- 국가R&D 수행기관 R&D현황조회(전체용) → search_ntis_institution_status
			- 이슈로보는R&D(전체용) → search_ntis_rnd_issues
			- 국가R&D 용어사전 조회(전체용) → search_ntis_terminology
			- 과학기술표준분류코드/국가중점기술코드 검색(전체용) → search_ntis_classification_codes
			- 과학기술표준분류 추천(기관용) → search_ntis_science_tech_classifications
			- 연관콘텐츠 추천(전체용) → search_ntis_related_content_recommendations
			- 위탁/공동연구·과제참여·통합검색·출연(연)연구자정보(기관/전문기관용) → search_ntis_commission_projects, search_ntis_participation, search_ntis_total, search_ntis_researcher_info
	- DataON - 서비스 별 API Key **(⚠️ OpenAPI 신청 정책 변경 — 2026년 3월부터 기관사용자만 신규 신청 및 권한 관리가 가능합니다)**
      - **OpenAPI 신청 대상 변경 안내**
        - 기존: 일반사용자 + 기관사용자 → 변경: **기관사용자만 신청 가능**
        - 일반사용자로 접속 시 OpenAPI 신청 메뉴 접근이 제한될 수 있습니다.
        - 기존에 발급받아 이용 중인 API는 **신청 당시 승인된 이용 기간 내에서는 정상 사용 가능**합니다.
        - **신규 신청 또는 이용 기간 연장 시에는 기관사용자 권한이 필요**합니다.
      - https://dataon.kisti.re.kr/openApi/openApiList_R.do 사이트 방문(데이터온 > 서비스 > API 활용 > OpenAPI)
      - 회원가입 및 로그인 (※ API 발급은 기관사용자 권한 필요)
      - API 키 발급 (데이터온은 검색 API와 상세조회 API 키 별도 발급 필요)
        - 연구데이터 검색 API 활용신청
        - 연구데이터 메타정보 상세 조회 API 활용신청
- uvx 방식 설치 권장
- 또는 uv 설치 (https://github.com/astral-sh/uv) 
  - Python 3.10 이상
- MCP 지원 LLM 클라이언트 설정
	- Claude Desktop 

### 설치 방법

#### uvx 사용 (권장)

별도 설치 없이 PyPI에서 자동으로 받아 실행:

```bash
uvx kisti-mcp
```

#### uv 사용 (개발자)

1. 저장소 클론

```bash
git clone https://github.com/ansua79/kisti-mcp.git
cd kisti-mcp
```

2. 의존성 설치

```bash
uv sync
```

## 설정

### 환경변수 설정

UVX 방식 설치 시 API 키는 MCP 클라이언트 설정(JSON)의 `env` 항목에 직접 지정하는 방식을 **권장**합니다.
`.env` 파일은 로컬 개발(`uv run`) 시 편의용 fallback으로만 사용됩니다.

#### 필요한 환경변수

| 변수명 | 서비스 | 설명 |
|--------|--------|------|
| `SCIENCEON_API_KEY` | ScienceON | API 키 |
| `SCIENCEON_CLIENT_ID` | ScienceON | 클라이언트 ID |
| `SCIENCEON_MAC_ADDRESS` | ScienceON | MAC 주소 (XX-XX-XX-XX-XX-XX) |
| `NTIS_API_KEY` | NTIS | API 키 (키는 하나지만 **API마다 활용신청 별도 필요**, 유효기간 1년) |
| `DataON_ResearchData_API_KEY` | DataON | 연구데이터 검색 API 키 |
| `DataON_ResearchDataMetadata_API_KEY` | DataON | 메타데이터 상세조회 API 키 |

> **참고**: 키가 없는 서비스는 자동으로 비활성화되며, 나머지 서비스는 정상 동작합니다.

Claude Desktop 등 MCP 클라이언트에서는 JSON 설정의 `env` 항목으로 환경변수를 주입합니다.
구체적인 설정 방법은 아래 [도구 등록](#도구-등록) 섹션을 참고하세요.

#### .env 파일 (로컬 개발용/uv 설치 시)

1. `.env.example` 파일을 `.env`로 복사:

```bash
cp .env.example .env
```

2. `.env` 파일을 편집하여 실제 값으로 변경:

```bash
# .env 파일 내용
SCIENCEON_API_KEY=your_actual_api_key
SCIENCEON_CLIENT_ID=your_actual_client_id
SCIENCEON_MAC_ADDRESS=your_actual_mac_address
NTIS_API_KEY=your_ntis_api_key
DataON_ResearchData_API_KEY=your_dataon_search_api_key
DataON_ResearchDataMetadata_API_KEY=your_dataon_detail_api_key
```

## 사용법

### MCP 서버 실행(동작 확인)

#### uvx 사용 (가장 간단, 권장)

```bash
uvx kisti-mcp
```

> MCP 클라이언트(Claude Desktop 등)에서는 JSON 설정의 `env` 항목으로 환경변수를 주입합니다.
> CLI에서 직접 실행할 때는 OS 환경변수를 설정한 후 위 명령을 실행하세요.

#### uv 사용 (개발자용)

```bash
uv run python kisti_mcp.py
```

> 프로젝트 루트의 `.env` 파일을 자동으로 읽습니다.



## 도구 등록

Claude Desktop(윈도우) 기준 `%APPDATA%\Claude\claude_desktop_config.json` 파일을 수정합니다.

#### 방법 1: uvx 사용 (권장)

uvx가 자동으로 패키지를 다운로드·실행합니다. API 키는 `env` 항목에 직접 지정합니다.

```json
{
  "mcpServers": {
    "kisti": {
      "command": "uvx",
      "args": ["kisti-mcp"],
      "env": {
        "SCIENCEON_API_KEY": "your_api_key",
        "SCIENCEON_CLIENT_ID": "your_client_id",
        "SCIENCEON_MAC_ADDRESS": "XX-XX-XX-XX-XX-XX",
        "NTIS_API_KEY": "your_ntis_api_key",
        "DataON_ResearchData_API_KEY": "your_dataon_search_api_key",
        "DataON_ResearchDataMetadata_API_KEY": "your_dataon_detail_api_key"
      }
    }
  }
}
```

- 키가 없는 서비스는 자동 비활성화되며, 나머지 서비스는 정상 동작합니다.

#### 방법 2: uv run 사용 (개발자용)

저장소를 직접 클론한 경우 사용합니다. 이 방식에서는 프로젝트 루트의 `.env` 파일을 자동으로 읽습니다.

`claude_desktop_config.json`의 `"kisti"` 항목을 아래와 같이 변경하세요:

```json
{
  "mcpServers": {
    "kisti": {
      "command": "uv",
      "args": [
        "--directory", 
        "C:/mcp/kisti-mcp",
        "run",
        "python",
        "kisti_mcp.py"
      ]
    }
  }
}
```

- `--directory` 값은 `git clone`한 로컬 경로로 변경하세요.

### 클라이언트 재시작

- Claude Desktop 기준
  - 메뉴 > 파일 > 종료
  - 또는 작업관리자에서 종료후
- 재시작
  - 검색 및 도구 : kisti    ⑫ 확인

### 도구 사용

Claude Desktop 등의 MCP 클라이언트에서 kisti-mcp 가 정상 등록되었다면, 다음과 같이 사용하실 수 있습니다.
```
일반 : 인공지능 멀티모달 관련 논문 5개 찾아 요약해줘
명시 : ScienceOn에서 인공지능 멀티모달 논문 검색해줘
개수 : 관련 논문 3건만 찾아줘   (자연어로 결과 수를 지정하면 그대로 반영됩니다)
```

#### 초록/본문 제외 옵션 (`include_body`)

기본적으로 검색 결과에는 초록·본문·정의 등 **긴 텍스트가 전문(全文)으로 포함**됩니다. 이는 Claude 등
컨텍스트 창이 큰 모델에 이상적이지만, **컨텍스트가 작은 로컬 소형 모델**(예: Gemma·Llama 등)이나
단순히 목록만 빠르게 훑고 싶을 때는 부담이 될 수 있습니다.

이때 검색 도구의 `include_body` 인자를 `False`로 주면 **긴 텍스트를 제외**하고
제목·저자·서지정보·DOI·링크만 반환합니다. (논문 10건 기준 출력량 약 60% 감소)

```
초록 빼고 논문 10개 목록만 보여줘
→ LLM이 search_scienceon_papers(query=..., max_results=10, include_body=False) 로 호출
```

관심 있는 항목이 나오면 CN번호로 상세조회하면 됩니다. 별도 설정 파일(.env) 변경 없이
호출할 때마다 자연어로 제어됩니다.

## 검색 결과 예시

### 논문 검색 결과 (기본: 초록 전문 포함)

```
**'멀티모달 인공지능' 논문 검색 결과** (총 1,234건 중 1건 표시):

**멀티모달 인공지능을 이용한 교통사고 유형 예측**
  - 저자: 한헌탁;장수은;
  - 연도: 2025
🏢 소속: 서울대학교 환경대학원 교통학전공;
📖 저널: 韓國ITS學會 論文誌
  - 발행기관: 한국ITS학회
  - 페이지: pp.102-120
  - ISSN: 1738-0774;2384-1729;
  - DB구분: JAKO
🔗 논문번호(CN): JAKO202507239665561
🔗 DOI: https://doi.org/10.12815/kits.2025.24.6.102
  - 키워드: 멀티모달 인공지능 . 교통사고 유형 . 도로 기하구조 . 교통안전
📝 초록: (초록 전문 — 절단 없이 그대로 반환)
📄 원문 URL: http://click.ndsl.kr/...
🔗 ScienceON 링크: http://click.ndsl.kr/...
```

### 논문 검색 결과 (`include_body=False` — 초록 제외)

```
**멀티모달 인공지능을 이용한 교통사고 유형 예측**
  - 저자: 한헌탁;장수은;
  - 연도: 2025
🏢 소속: 서울대학교 환경대학원 교통학전공;
📖 저널: 韓國ITS學會 論文誌
  - 발행기관: 한국ITS학회
  - 페이지: pp.102-120
  - DB구분: JAKO
🔗 논문번호(CN): JAKO202507239665561
🔗 DOI: https://doi.org/10.12815/kits.2025.24.6.102
  - 키워드: 멀티모달 인공지능 . 교통사고 유형 . 교통안전
📄 원문 URL: http://click.ndsl.kr/...
🔗 ScienceON 링크: http://click.ndsl.kr/...
        ↑ 초록만 빠지고 서지·DOI·링크는 유지됩니다.
```

### 특허 인용/피인용 정보

```
**특허 인용/피인용 정보 (CN: KOR1020057009529)**

**SEMICONDUCTOR DEVICE**  [인용특허]
  - 출원인: TOSHIBA CORP
  - 출원일: 19960529
  - 발명자: USUDA KOJI; IMAI KIYOSHI; ...
  - 특허상태: 공개
  - IPC분류: H01L-029/786; ...
  - 국가: 일본(JP)
  - CN: JPA1997120321307
```



## 프로젝트 구조

```
kisti-mcp/
├── kisti_mcp.py                  # 메인 서버 파일 (32종 도구)
├── pyproject.toml                # 프로젝트 설정
├── uv.lock                       # 의존성 잠금
├── .env.example                  # 환경변수 예시 (로컬 개발용 fallback)
├── .github/workflows/publish.yml # PyPI 자동 배포 워크플로
├── README.md                     # 이 파일
├── LICENSE                       # 라이선스
└── .gitignore
```

## 라이선스

이 프로젝트는 **Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0)** 하에 배포됩니다.

- ✅ 개인적/학술/연구/교육 목적 사용, 비상업적 사용 허용
- ❌ 상업적 사용 금지
- 💼 상업적 사용을 원하시는 경우 별도 라이선스가 필요합니다. 문의: [raezero@kisti.re.kr]

자세한 내용은 [LICENSE](https://github.com/ansua79/kisti-mcp/LICENSE) 파일을 참조하세요.

## 문제 해결

### 일반적인 문제

#### ScienceON
1. **토큰 발급 실패**
    - API 키와 클라이언트 ID가 올바른지 확인
    - MAC 주소가 정확한지 확인 (형식: XX-XX-XX-XX-XX-XX)
    - 네트워크 연결 상태 확인
2. **검색 결과 없음**
    - 검색 키워드를 다양하게 시도
    - 한글 키워드 사용 권장

#### NTIS
1. **API 키 오류**
    - NTIS_API_KEY가 올바르게 설정되었는지 확인
    - 모든 NTIS 서비스에 동일한 API 키 사용
2. **분류코드 추천 실패**
    - 연구 초록이 최소 128바이트 이상인지 확인
    - 분류체계 이름이 정확한지 확인

#### DataON
1. **API 키 오류**
    - 검색 API와 상세조회 API 키가 각각 올바르게 설정되었는지 확인
    - DataON_ResearchData_API_KEY와 DataON_ResearchDataMetadata_API_KEY 확인

#### 공통
1. **환경변수 확인**
    - MCP 클라이언트 JSON 설정의 `env` 항목에 필요한 키가 올바르게 설정되었는지 확인
    - 환경변수 값에 따옴표나 공백이 없는지 확인
    - 로컬 개발 시 `.env` 파일을 사용하는 경우, 프로젝트 루트에 파일이 있는지 확인


## KISTI 연구지능화센터

KISTI의 연구지능화센터는 **과학기술 지식인프라 ScienceON**를 통해 국가  과학기술정보, 연구데이터, 정보분석서비스 및 연구인프라를 연계·융합하여 연구자가 필요로 하는 지식인프라를 한곳에서 제공하는 업무를 수행하고 있습니다.

## 지원

문제가 있거나 질문이 있으시면 이메일(raezero@kisti.re.kr)을 보내주시거나 [Issues](https://github.com/ansua79/kisti-mcp/issues)에서 문의해주세요.

## 관련 링크

- [STIMCP-Manager](https://github.com/ansua79/stimcp-manager) - MCP 서버를 GUI로 손쉽게 설치·등록하는 관리 도구 (초보자 권장, Windows)
- [ScienceON-MCP](https://github.com/ansua79/scienceon-mcp) - ScienceON 전용 MCP 서버
- [DOREA-X](https://github.com/leeryong/DOREA-X) - 문서 이해부터 보고서 작성까지 전 과정을 함께하는 문서 작업 AI 에이전트

![alt text](media/image.png)
- [ScienceON](https://scienceon.kisti.re.kr/) - 국가 과학기술 지식인프라 플랫폼
- [NTIS](https://www.ntis.go.kr/) - 국가과학기술지식정보서비스
- [DataON](https://dataon.kisti.re.kr/) - 국가연구데이터플랫폼
- [(OLD) KISTI AI Platform Team (BLUESKY)](https://github.com/KISTI-AI-Platform-Team/KISTI_BLUESKY)
- [(OLD) DOREA Initial](https://github.com/Byun11/Dorea-pdf-ai)