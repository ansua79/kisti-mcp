# *KISTI-MCP v0.3.12a*

한국과학기술정보연구원(KISTI)가 서비스하는 다양한 플랫폼의 OpenAPI를 활용할 수 있는 MCP서버입니다. 
현재 ScienceON, NTIS, DataON의 논문, 특허, 보고서, 국가R&D과제, 연구데이터 관련 API를 사용할 수 있습니다.
Model Context Protocol 기반 사용하는 AI 모델과 KISTI가 제공하는 서비스 간 원활한 통합을 지원합니다. 

## 기능

- **ScienceON**: 논문, 특허, R&D연구보고서 검색 및 상세검색, 특허 인용/피인용 관계 분석 등 총 7종 기능
- **NTIS**: 국가R&D 연구과제 검색 및 상세검색, 분류코드 추천 등 총 3종 기능
- **DataON**: 국가R&D 연구데이터 검색 및 메타데이터 상세 정보 조회 등 총 2종 기능

## 주요 기능

| #   | 기능       | 설명                                               |
|-----|----------|--------------------------------------------------|
| 1   | 논문 검색    | ScienceON에서 키워드로 논문을 검색하고 제목, 저자, 초록, CN번호 제공    |
| 2   | 논문 상세정보  | CN번호로 특정 논문의 상세정보, DOI, 키워드, 관련논문 조회             |
| 3   | 특허 검색    | ScienceON에서 키워드로 특허를 검색하고 출원인, 출원일, CN번호 제공      |
| 4   | 특허 상세정보  | CN번호로 특정 특허의 상세정보, IPC분류, 특허상태 조회                |
| 5   | 특허 인용정보  | CN번호로 특허의 인용/피인용 관계 분석                           |
| 6   | 보고서 검색   | ScienceON에서 키워드로 R&D 보고서를 검색하고 저자, 발행기관, CN번호 제공 |
| 7   | 보고서 상세정보 | CN번호로 특정 보고서의 상세정보, 인용논문/특허 조회                   |
| 8   | 국가R&D 과제 검색  | NTIS에서 키워드로 국가R&D 과제를 검색하고 수행기관, 연구비, 과제번호 제공 |
| 9   | 과학기술 분류코드 추천 | 연구과제 초록으로 적합한 분류코드를 AI 기반 매칭점수와 함께 추천         |
| 10  | 과제 연관콘텐츠 추천  | 과제번호로 연관된 논문, 특허, 보고서, 관련과제 추천                |
| 11  | 연구데이터 검색   | DataON에서 키워드로 공개 연구데이터를 검색하고 제목, 작성자, svcId 제공 |
| 12  | 연구데이터 상세정보 | svcId로 특정 연구데이터의 메타데이터, 포맷, 권리정보 조회            |



## History

| 버전     | 날짜         | 주요 사항                                                                             |
| ------ | ---------- | --------------------------------------------------------------------------------- |
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
  - **국가R&D 과제**: 정부 R&D 사업 및 과제 정보
  - **분류코드 추천**: 연구 초록 기반 과학기술 분류 추천
  - **연관 콘텐츠**: 과제 관련 논문, 특허, 보고서 추천

- **DataON**: 국가연구데이터플랫폼
  - **연구데이터**: 공공 연구데이터, 데이터셋, AI 모델 등
  - **메타데이터**: 데이터셋 상세 정보, DOI, 라이선스 정보


## 설치

### 요구사항

- uv 설치 (https://github.com/astral-sh/uv) 
  - Python 3.10 이상
- 플랫폼 별 API 관련 정보
	- ScienceON - API Key, Client ID, MAC Address
		- https://scienceon.kisti.re.kr/por/oapi/openApi.do 사이트 방문
		- 회원가입 및 로그인
		- API Key 및 Client ID 발급 신청
	- NTIS - API Key
		- https://www.ntis.go.kr/rndopen/api/mng/apiMain.do 사이트 방문
		- 회원가입 및 로그인
		- 데이터활용 > OpenAPI > API 별 활용신청
			- 1) 국가R&D 과제검색 서비스(대국민용) 2021-02-09
			- 2) 과학기술표준분류 추천 서비스(기관용) 2019-12-31
			- 3) 연관콘텐츠 추천 서비스(전체용) 2023-11-27
	- DataON - 서비스 별 API Key
      - https://dataon.kisti.re.kr/openApi/openApiList_R.do 사이트 방문(데이터온 > 서비스 > API 활용 > OpenAPI)
      - 회원가입 및 로그인
      - API 키 발급 (데이터온은 검색 API와 상세조회 API 키 별도 발급 필요)
        - 연구데이터 검색 API 활용신청
        - 연구데이터 메타정보 상세 조회 API 활용신청

- MCP 지원 LLM 클라이언트 설정
	- Claude Desktop 

### 설치 방법

#### uv 사용 (권장)

1. 저장소 클론

```bash
git clone https://github.com/ansua79/kisti-mcp.git
cd kisti-mcp
```

2. uv로 의존성 설치

```bash
uv sync
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
# ScienceON API 키
SCIENCEON_API_KEY=your_actual_api_key
SCIENCEON_CLIENT_ID=your_actual_client_id
SCIENCEON_MAC_ADDRESS=your_actual_mac_address

# NTIS API 키 (모든 NTIS 서비스에 공통 사용)
NTIS_API_KEY=your_ntis_api_key

# DataON API 키 (데이터온은 API마다 Key값이 다름)
DataON_ResearchData_API_KEY=your_dataon_search_api_key
DataON_ResearchDataMetadata_API_KEY=your_dataon_detail_api_key
```

## 사용법

### MCP 서버 실행(동작 확인)

#### uv 사용(권장)

```bash
uv run python kisti-mcp-server.py
```

```
INFO:__main__:.env 파일에서 6개의 환경변수를 로드했습니다.
INFO:__main__:KISTI API 인증 정보가 성공적으로 로드되었습니다.
INFO:__main__:NTIS API 인증 정보가 성공적으로 로드되었습니다.
INFO:__main__:DataON API 인증 정보가 성공적으로 로드되었습니다.

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


[11/05/25 11:26:29] INFO     Starting MCP server 'KISTI-MCP Server' with transport 'stdio'                server.py:1371
```
#### 전통적인 방법

```bash
python kisti-mcp-server.py
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
  - 메뉴 > 파일 > 종료
  - 또는 작업관리자에서 종료후
- 재시작
  - 검색 및 도구 : kisti    ⑫ 확인
![[Pasted image 20250729101543.png]]

### 도구 사용

Claude Desktop 등의 MCP 클라이언트에서 kisti-mcp 가 정상 등록되었다면, 다음과 같이 사용하실 수 있습니다.
```
일반 : 인공지능 멀티모달 관련 논문 5개 찾아 요약해줘
명시 : ScienceOn에서 인공지능 멀티모달 논문 검색해줘
```

![[Pasted image 20250729101952.png]]

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
    - `.env` 파일이 올바르게 설정되었는지 확인
    - 환경변수 값에 따옴표나 공백이 없는지 확인


## KISTI 초거대AI연구센터 AI플랫폼팀

KISTI의 초거대AI연구센터는 2023년 12월 KISTI는 생성형 거대 언어 모델 'KONI(KISTI Open Natural Intelligence)'의 첫선을 토대로 2024년 3월 정식 출범한 부서이며, 
**AI플랫폼팀은 AI모델 관련 플랫폼 기술 및 Agent 서비스 개발**을 담당하고 있습니다.

## 지원

문제가 있거나 질문이 있으시면 이메일(raezero@kisti.re.kr)을 보내주시거나 [Issues](https://github.com/ansua79/kisti-mcp/issues)에서 문의해주세요.

## 관련 링크
- [KONI:KISTI Open Neural Intelligence](https://huggingface.co/KISTI-KONI) - KISTI 과학기술정보 특화 거대언어생성모델
- [KISTI AI Platform Team](https://github.com/KISTI-AI-Platform-Team/BlueSkyNova) - KISTI 초거대AI연구센터 AI플랫폼팀
- [DOREA:Document-Oriented Reasoning and Exploration Assistant](https://github.com/Byun11/Dorea-pdf-ai) 
- [SpectraBench](https://github.com/gwleee/SpectraBench) - Intelligent Scheduling System for Large Language Model Benchmarking
- [KISTI ScienceON](https://scienceon.kisti.re.kr/)
- [NTIS 국가과학기술지식정보서비스](https://www.ntis.go.kr/)
- [DataON 국가연구데이터플랫폼](https://dataon.kisti.re.kr/)