# KOSMA
[![smithery badge](https://smithery.ai/badge/@ansua79/kisti-mcp)](https://smithery.ai/server/@ansua79/kisti-mcp)
KISTI-Oriented Science&Mission-driven Agent

## *KISTI-MCP v0.1.7*

한국과학기술정보연구원(KISTI)가 서비스하는 다양한 플랫폼의 OpenAPI를 활용할 수 있는 MCP서버입니다. 현재 ScienceON 의 논문, 특허, 보고서 API를 사용할 수 있습니다(2025-07-22)

## 기능

- **논문 검색 및 분석**: KISTI ScienceON 데이터베이스에서 논문 검색 및 상세 정보 조회
- **특허 검색 및 분석**: 특허 검색, 상세 정보 조회, 인용/피인용 관계 분석
- **보고서 검색 및 분석**: R&D 보고서 검색 및 상세 정보 조회
- **MCP 호환**: Model Context Protocol을 통한 AI 모델과의 원활한 통합

## 사용 가능한 도구 (총 7개)

| 도구명                                 | 기능           | 매개변수                   |
| ----------------------------------- | ------------ | ---------------------- |
| `search_scienceon_papers`           | 논문 목록 검색     | `query`, `max_results` |
| `search_scienceon_paper_details`    | 논문 상세 정보     | `cn`                   |
| `search_scienceon_patents`          | 특허 목록 검색     | `query`, `max_results` |
| `search_scienceon_patent_details`   | 특허 상세 정보     | `cn`                   |
| `search_scienceon_patent_citations` | 특허 인용/피인용 관계 | `cn`                   |
| `search_scienceon_reports`          | 보고서 목록 검색    | `query`, `max_results` |
| `search_scienceon_report_details`   | 보고서 상세 정보    | `cn`                   |

## 설치

### Installing via Smithery

To install kisti-mcp for Claude Desktop automatically via [Smithery](https://smithery.ai/server/kisti-mcp):

```bash
npx -y @smithery/cli install @ansua79/kisti-mcp --client claude
```

### 요구사항

- [uv](https://github.com/astral-sh/uv) (권장) 또는 pip
    - Python 3.10 이상
- KISTI API 키 및 클라이언트 ID 필요

### 설치 방법

#### uv 사용 (권장)

0. 실행위치생성(예시 - C:\mcp\kisti-mcp)
```bash
cd c:\
mkdir mcp
cd mcp
```
   
1. 저장소 클론:

```bash
git clone https://github.com/ansua79/kisti-mcp.git
cd kisti-mcp
```

2. uv로 의존성 설치:

```bash
uv sync
```

3. 가상환경에서 실행:

```bash
uv run python kisti-mcp-server.py
```

#### 전통적인 pip 방법

1. 가상환경 생성 및 활성화:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows
```

2. 의존성 설치:

```bash
pip install -e .
# 또는 직접 설치
pip install fastmcp httpx pycryptodome
```

## 설정

### 환경변수 설정

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
```

### KISTI API 키 발급
#### KISTI ScienceON OpenAPI
1. https://scienceon.kisti.re.kr/por/oapi/openApi.do 사이트 방문
2. 회원가입 및 로그인
3. API 키 및 클라이언트 ID 발급
4. 위 설정 정보에 입력

## 사용법

### MCP 서버 실행(동작 확인)

#### uv 사용(권장):

```bash
uv run python kisti-mcp-server.py
```

```
INFO:__main__:.env 파일에서 3개의 환경변수를 로드했습니다.
INFO:__main__:KISTI API 인증 정보가 성공적으로 로드되었습니다.

╭─ FastMCP 2.0 ──────────────────────────────────────────────────────────────╮
│                                                                            │
│        _ __ ___ ______           __  __  _____________    ____    ____     │
│       _ __ ___ / ____/___ ______/ /_/  |/  / ____/ __ \  |___ \  / __ \    │
│      _ __ ___ / /_  / __ `/ ___/ __/ /|_/ / /   / /_/ /  ___/ / / / / /    │
│     _ __ ___ / __/ / /_/ (__  ) /_/ /  / / /___/ ____/  /  __/_/ /_/ /     │
│    _ __ ___ /_/    \__,_/____/\__/_/  /_/\____/_/      /_____(_)____/      │
│                                                                            │
│                                                                            │
│                                                                            │
│    🖥️  Server name:     KISTI-MCP Server                                    │
│    📦 Transport:       STDIO                                               │
│                                                                            │
│    📚 Docs:            https://gofastmcp.com                               │
│    🚀 Deploy:          https://fastmcp.cloud                               │
│                                                                            │
│    🏎️  FastMCP version: 2.10.6                                              │
│    🤝 MCP version:     1.12.2                                              │
│                                                                            │
╰────────────────────────────────────────────────────────────────────────────╯

[07/29/25 09:44:44] INFO     Starting MCP server 'KISTI-MCP Server' with transport 'stdio'                server.py:1371
```
#### 전통적인 방법:

```bash
python kisti-mcp-server.py
```

### 로그 확인

서버 실행 시 상세한 로그가 출력됩니다:

```bash
INFO:__main__:=== 논문 목록 검색 시작: 인공지능 (최대 결과: 5) ===
INFO:__main__:토큰 발급 요청 중...
INFO:__main__:토큰 발급 성공!
```

## 도구 등록

Claude Deskop(윈도우) 기준 %APPDATA%\Claude\claude_desktop_config.json 파일 수정
```
{
  "mcpServers": {
    "kisti": {
      "command": "uv", 
      "args": [
        "--directory",
        "설치디렉토리명", 
        "run",
        "kisti-mcp-server.py"
      ]
    }
  }
}
```
- 설치디렉토리명은 C:/mcp/kisti-mcp 등으로, 로컬 기준에 따라 수정

### 클라이언트 재시작

- Claude Desktop 기준
	- 작업관리자에서도 종료 후 재시작
	- 검색 및 도구 : kisti    ⑦ 확인
<img width="462" height="370" alt="Image" src="https://github.com/user-attachments/assets/73c5a059-7911-4f8a-8e0b-1c3f09ba5d35" />

### 도구 사용

Claude Desktop 등의 MCP 클라이언트에서 kisti-mcp 가 정상 등록되었다면, 다음과 같이 사용하실 수 있습니다.
```
일반 : 인공지능 멀티모달 관련 논문 5개 찾아 요약해줘
명시 : ScienceOn에서 인공지능 멀티모달 논문 검색해줘
```
<img width="461" height="369" alt="Image" src="https://github.com/user-attachments/assets/02e9d8f6-1807-47c6-a4fe-63cadcceca00" />

관련 도구는 다음과 같이 사용할 수 있습니다:

#### 논문 관련 도구

**`search_scienceon_papers`** - 논문 목록 검색

**매개변수:**

- `query` (str): 검색할 키워드
- `max_results` (int, 기본값: 10): 최대 결과 수

**예시:**

```python
# 인공지능 관련 논문 5개 검색
search_scienceon_papers(query="인공지능", max_results=5)

# 머신러닝 관련 논문 10개 검색
search_scienceon_papers(query="머신러닝", max_results=10)
```

**`search_scienceon_paper_details`** - 논문 상세 정보 조회

**매개변수:**

- `cn` (str): 논문 고유 식별번호 (검색 결과에서 얻은 CN 번호)

**예시:**

```python
# CN번호로 논문 상세 정보 조회
search_scienceon_paper_details(cn="JAKO202412345678901")
```

#### 특허 관련 도구

**`search_scienceon_patents`** - 특허 목록 검색

**매개변수:**

- `query` (str): 검색할 키워드
- `max_results` (int, 기본값: 10): 최대 결과 수

**`search_scienceon_patent_details`** - 특허 상세 정보 조회

**매개변수:**

- `cn` (str): 특허 고유 식별번호

**`search_scienceon_patent_citations`** - 특허 인용/피인용 관계 조회

**매개변수:**

- `cn` (str): 특허 고유 식별번호

**예시:**

```python
# 특허 검색
search_scienceon_patents(query="딥러닝", max_results=5)

# 특허 상세 정보
search_scienceon_patent_details(cn="KIPO202412345678901")

# 특허 인용/피인용 관계
search_scienceon_patent_citations(cn="KIPO202412345678901")
```

#### 보고서 관련 도구

**`search_scienceon_reports`** - 보고서 목록 검색

**매개변수:**

- `query` (str): 검색할 키워드
- `max_results` (int, 기본값: 10): 최대 결과 수

**`search_scienceon_report_details`** - 보고서 상세 정보 조회

**매개변수:**

- `cn` (str): 보고서 고유 식별번호

**예시:**

```python
# R&D 보고서 검색
search_scienceon_reports(query="바이오", max_results=5)

# 보고서 상세 정보
search_scienceon_report_details(cn="TRKO202412345678901")
```

## 검색 결과 예시

### 논문 검색 결과

```
🔍 **'인공지능' 논문 검색 결과** (총 1,234건 중 5건 표시):

📄 **Deep Learning for Natural Language Processing**
👤 저자: 김철수, 이영희
📅 연도: 2024
📖 저널: IEEE Transactions on Neural Networks
🔗 논문번호(CN): JAKO202412345678901
📝 초록: 자연어 처리를 위한 딥러닝 기법에 관한 연구...

💡 특정 논문의 상세정보를 원하면 CN번호를 이용해 논문상세보기를 사용하세요.
```

### 특허 상세 정보

```
📋 **특허 상세정보 (CN: KIPO202412345678901)**

🏛️ **특허제목**: 인공지능 기반 음성인식 시스템
👥 **출원인**: 삼성전자
📅 **출원일**: 2024-01-15
📰 **공개일**: 2024-07-15
📊 **특허상태**: 등록
🏷️ **IPC분류**: G10L15/08
```

## API 응답 형식

```json
{
  "success": true,
  "total_count": 1234,
  "papers": [
    {
      "Title": "논문 제목",
      "Author": "저자명",
      "Pubyear": "2024",
      "JournalName": "저널명",
      "Abstract": "논문 초록..."
    }
  ]
}
```

## 프로젝트 구조

```
kisti-mcp-server/
├── kisti-mcp-server.py    # 메인 서버 파일
├── pyproject.toml         # 프로젝트 설정
├── requirements.txt       # 의존성 목록
├── .env.example          # 환경변수 예시 파일
├── .env                  # 환경변수 파일 (사용자가 생성)
├── README.md             # 이 파일
├── LICENSE               # 라이선스
└── .gitignore           # Git 무시 파일
```

## 데이터 소스

- **KISTI ScienceON** : 한국과학기술정보연구원의 통합 과학기술 정보서비스
- **논문 데이터**: SCIE, SCOPUS, 한국과학기술논문 등 99.7% 포함
- **특허 데이터**: 국내외 특허 정보 포함
- **보고서 데이터**: 국가 R&D 보고서, 기술동향 보고서 등

## 라이선스

이 프로젝트는 **Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0)** 하에 배포됩니다.

- ✅ 개인적/학술/연구/교육 목적 사용, 비상업적 사용 허용
- ❌ 상업적 사용 금지
- 💼 상업적 사용을 원하시는 경우 별도 라이선스가 필요합니다. 문의: [raezero@kisti.re.kr]

자세한 내용은 [LICENSE](https://github.com/ansua79/kisti-mcp/blob/main/LICENSE) 파일을 참조하세요.

## 문제 해결

### 일반적인 문제(ScienceON)

1. **토큰 발급 실패**
    - API 키와 클라이언트 ID가 올바른지 확인
    - MAC 주소가 정확한지 확인
    - 네트워크 연결 상태 확인
2. **검색 결과 없음**
    - 검색 키워드를 다양하게 시도
    - 한글 키워드 사용 권장
3. **환경변수 확인**
    - `.env` 파일이 올바르게 설정되었는지 확인
    - 환경변수 값에 따옴표나 공백이 없는지 확인


## 관련 링크

- [KISTI ScienceON](https://scienceon.kisti.re.kr/)

## KISTI 초거대AI연구센터 AI플랫폼팀

KISTI의 초거대AI연구센터는 2023년 12월 KISTI는 생성형 거대 언어 모델 'KONI(KISTI Open Natural Intelligence)'의 첫선을 토대로 2024년 3월 정식 출범한 부서이며, **AI플랫폼팀은 AI모델 및 Agent 서비스 기술 개발**을 담당하고 있습니다.

## 지원

문제가 있거나 질문이 있으시면 [Issues](https://github.com/ansua79/kisti-mcp/issues)에서 문의해주세요.
