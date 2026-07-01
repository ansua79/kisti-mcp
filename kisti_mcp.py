#!/usr/bin/env python3
"""
KOSMA
(KISTI-Oriented Science&Mission-driven Agent)
KISTI가 서비스하는 다양한 플랫폼의 OpenAPI를 활용할 수 있습니다.
KISTI-MCP Server
v0.3.12 - ScienceON + NTIS + DataON 통합 검색 서비스 (DataON 연구데이터 검색 추가)
"""
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import httpx
from fastmcp import FastMCP
import json
import re
import html
import base64
from Crypto.Cipher import AES
from urllib.parse import quote
import xml.etree.ElementTree as ET
from pathlib import Path
from abc import ABC, abstractmethod
# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User-Agent (KISTI 서버 로그에서 kisti-mcp발 호출을 식별할 수 있도록 모든 API 호출에 부착)
try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("kisti-mcp")
except Exception:
    __version__ = "0.0.0"
USER_AGENT = f"kisti-mcp/{__version__}"
# MCP 서버 초기화
mcp = FastMCP("KISTI-MCP Server")
# 환경변수 캐시 (중복 로딩 방지)
_env_cache = None
_env_loaded = False

def _load_env_file_fallback(env_file_path: str = ".env") -> Dict[str, str]:
    """
    .env 파일에서 환경변수를 로드합니다. (내부 fallback용, 캐시 사용)
    프로세스 환경변수(os.getenv)가 우선이며, .env는 보조 수단입니다.

    Args:
        env_file_path: .env 파일 경로

    Returns:
        환경변수 딕셔너리
    """
    global _env_cache, _env_loaded

    if _env_loaded:
        return _env_cache or {}

    env_vars = {}
    env_path = Path(env_file_path)

    if env_path.exists():
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            env_vars[key.strip()] = value.strip()
            logger.info(f".env 파일에서 {len(env_vars)}개의 환경변수를 로드했습니다. (fallback)")
        except Exception as e:
            logger.warning(f".env 파일 로드 중 오류: {str(e)}")
    else:
        logger.debug(f".env 파일 없음 (정상 — 환경변수로 설정 가능): {env_path}")

    _env_cache = env_vars
    _env_loaded = True

    return env_vars


def get_env(key: str, default: str = "") -> str:
    """
    환경변수를 조회합니다.
    1순위: 프로세스 환경변수 (os.environ / Claude Desktop JSON env)
    2순위: .env 파일 (개발용 fallback)

    Args:
        key: 환경변수 키
        default: 기본값

    Returns:
        환경변수 값
    """
    value = os.getenv(key)
    if value:
        return value
    env_vars = _load_env_file_fallback()
    return env_vars.get(key, default)


def clean_text(text, max_len: int = 300) -> str:
    """HTML 태그/엔티티를 제거하고 LLM 가독성 좋게 정리한다.

    1) XML 이스케이프 디코딩(&lt;→<) → 2) 태그 제거 → 3) HTML 엔티티 전체 디코딩
    (&nbsp; &#37; &lsquo; 등) → 4) 연속 공백 정리 → 5) max_len 초과 시 절단.
    max_len=0 이면 절단하지 않는다.
    """
    if not text:
        return ""
    clean = str(text).replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    clean = re.sub(r'<[^>]+>', '', clean)        # 태그 제거
    # KISTI/NTIS가 비표준으로 내보내는 엔티티 보정 (&quo;→", &apos;→')
    clean = clean.replace('&quo;', '"').replace('&apos;', "'")
    clean = html.unescape(clean)                  # &nbsp; &#37; &lsquo; 등 디코딩
    clean = re.sub(r'\s+', ' ', clean).strip()    # 연속 공백 정리
    if max_len and len(clean) > max_len:
        clean = clean[:max_len] + "..."
    return clean


class AESTestClass:
    """ScienceON사용을 위한 AES 암호화 클래스"""
    
    def __init__(self, plain_txt, key):
        self.iv = 'jvHJ1EFA0IXBrxxz'
        self.block_size = 16
        self.plain_txt = plain_txt
        self.key = key
    
    def pad(self):
        number_of_bytes_to_pad = self.block_size - len(self.plain_txt) % self.block_size
        ascii_str = chr(number_of_bytes_to_pad)
        padding_str = number_of_bytes_to_pad * ascii_str
        padded_plain_text = self.plain_txt + padding_str
        return padded_plain_text
    
    def encrypt(self):
        cipher = AES.new(self.key.encode('utf-8'), AES.MODE_CBC, self.iv.encode('utf-8'))
        padded_txt = self.pad()
        encrypted_bytes = cipher.encrypt(padded_txt.encode('utf-8'))
        encrypted_str = base64.urlsafe_b64encode(encrypted_bytes).decode("utf-8")
        return quote(encrypted_str)
# 추상 기본 클래스들
class BaseAPIClient(ABC):
    """API 클라이언트 기본 클래스"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.access_token = None
    
    @abstractmethod
    async def get_token(self) -> bool:
        """토큰 발급"""
        pass
    
    @abstractmethod
    async def search(self, query: str, target: str, max_results: int = 10) -> Dict[str, Any]:
        """검색 수행"""
        pass
class BaseResultFormatter(ABC):
    """결과 포맷터 기본 클래스"""
    
    @abstractmethod
    def format_search_results(self, results: List[Dict], query: str, total_count: int, result_type: str) -> str:
        """검색 결과 포맷팅"""
        pass
    
    @abstractmethod
    def format_detail_result(self, result: Dict, identifier: str) -> str:
        """상세 결과 포맷팅"""
        pass
# NTIS 전용 구현  
class NTISClient(BaseAPIClient):
    """NTIS OpenAPI 클라이언트"""
    
    def __init__(self):
        super().__init__("https://www.ntis.go.kr")

        # 환경변수에서 인증 정보 읽기 (통합 API 키)
        self.api_key = get_env("NTIS_API_KEY")

        # 필수 정보 검증
        self._validate_credentials()

    def _validate_credentials(self):
        """인증 정보 검증"""
        if not self.api_key:
            logger.warning("NTIS API KEY가 설정되지 않았습니다: NTIS_API_KEY")
            logger.info("NTIS 서비스가 비활성화됩니다.")
            raise ValueError("필수 환경변수 누락: NTIS_API_KEY")
        else:
            logger.info("NTIS API 인증 정보가 성공적으로 로드되었습니다.")

    def _get_api_key(self, target: str) -> str:
        """API KEY 반환 (모든 서비스에서 동일한 키 사용)"""
        return self.api_key
    
    async def get_token(self) -> bool:
        """NTIS는 토큰 발급이 필요하지 않음"""
        return True
    
    async def search(self, query: str, target: str, max_results: int = 10) -> Dict[str, Any]:
        """NTIS 검색 수행"""
        
        api_key = self._get_api_key(target)
        if not api_key:
            return {"error": True, "message": f"{target} 서비스에 대한 NTIS API KEY가 설정되지 않았습니다"}
        
        # target에 따른 엔드포인트 결정
        if target in ("PROJECT", "PROJECT_SPECIAL"):
            # 전체용=public_project, 전문기관용=projectAllSearch (자동 폴백용)
            endpoint = ("/rndopen/openApi/projectAllSearch"
                        if target == "PROJECT_SPECIAL"
                        else "/rndopen/openApi/public_project")
            params = {
                "apprvKey": api_key,
                "userId": "",
                "collection": "project",
                "SRWR": query,
                "searchFd": "",
                "addQuery": "",
                "searchRnkn": "",
                "startPosition": 1,
                "displayCnt": min(max_results, 100)
            }
        elif target == "CLASSIFICATION":
            # 분류 타입별 엔드포인트와 컬렉션 결정
            # query가 튜플 형태로 (실제_쿼리, 분류_타입) 전달될 것으로 가정
            if isinstance(query, tuple):
                actual_query, classification_type = query
            else:
                actual_query, classification_type = query, "standard"
            
            classification_configs = {
                "standard": {
                    "endpoint": "/rndopen/openApi/rcmncls",
                    "collection": "rcmncls"
                },
                "health": {
                    "endpoint": "/rndopen/openApi/rcmncls", 
                    "collection": "rcmnhtcls"
                },
                "industry": {
                    "endpoint": "/rndopen/openApi/rcmncls",
                    "collection": "rcmnitcls"
                }
            }
            
            config = classification_configs.get(classification_type, classification_configs["standard"])
            endpoint = config["endpoint"]
            params = {
                "apprvKey": api_key,
                "collection": config["collection"],
                "rqstDes": actual_query
            }
        elif target == "CLASSIFICATION_DETAILED":
            # 항목별 세부 추천 모드
            # query가 튜플 형태로 (research_goal, research_content, expected_effect, korean_keywords, english_keywords, classification_type) 전달
            if isinstance(query, tuple) and len(query) == 6:
                research_goal, research_content, expected_effect, korean_keywords, english_keywords, classification_type = query
            else:
                return {"error": True, "message": "CLASSIFICATION_DETAILED 타입에는 6개 파라미터가 필요합니다"}
            
            classification_configs = {
                "standard": {
                    "endpoint": "/rndopen/openApi/rcmncls",
                    "collection": "rcmnclsdtl"
                },
                "health": {
                    "endpoint": "/rndopen/openApi/rcmncls", 
                    "collection": "rcmnhtclsdtl"
                },
                "industry": {
                    "endpoint": "/rndopen/openApi/rcmncls",
                    "collection": "rcmnitclsdtl"
                }
            }
            
            config = classification_configs.get(classification_type, classification_configs["standard"])
            endpoint = config["endpoint"]
            params = {
                "apprvKey": api_key,
                "collection": config["collection"],
                "rschGoalAbstract": research_goal,
                "rschAbstract": research_content,
                "expEfctAbstract": expected_effect,
                "korKywd": korean_keywords,
                "engKywd": english_keywords
            }
        elif target == "RECOMMENDATION":
            endpoint = "/rndopen/openApi/public_recommend"
            params = {
                "apprvKey": api_key,
                "userId": "",
                "collection": "recommend",
                "SRWR": query,
                "searchFd": "",
                "addQuery": "",
                "searchRnkn": "",
                "startPosition": 1,
                "displayCnt": min(max_results, 100)
            }
        elif target == "RELATED_CONTENT":
            # 연관콘텐츠 검색 (pjtId, collection 기반)
            # query가 튜플 형태로 (pjtId, collection_type) 전달될 것으로 가정
            if isinstance(query, tuple):
                pjt_id, collection_type = query
            else:
                pjt_id, collection_type = query, "researchreport"
                
            endpoint = "/rndopen/openApi/ConnectionContent"
            params = {
                "apprvKey": api_key,
                "pjtId": pjt_id,
                "collection": collection_type
            }
        elif target == "OUTCOME":
            # 성과검색 (논문/특허/연구시설장비/보고서) - query=(검색어, collection, level)
            # level: "all"(전문기관용 natRnDAllSearch) / "org"(기관용 natRnDSearch) / "public"(전체용 public_result)
            if isinstance(query, tuple) and len(query) == 3:
                srwr, collection_type, level = query
            elif isinstance(query, tuple):
                srwr, collection_type = query
                level = "public"
            else:
                srwr, collection_type, level = query, "rpaper", "public"

            outcome_endpoints = {
                "all": "/rndopen/openApi/natRnDAllSearch",
                "org": "/rndopen/openApi/natRnDSearch",
                "public": "/rndopen/openApi/public_result",
            }
            endpoint = outcome_endpoints.get(level, outcome_endpoints["public"])
            # collection별 DBT값 (addQuery에 필수)
            dbt_map = {"rpaper": "PAP", "rpatent": "PAT", "requip": "EQU",
                       "rresearch": "TRKO"}
            dbt = dbt_map.get(collection_type, "PAP")
            params = {
                "apprvKey": api_key,
                "userId": "",
                "collection": collection_type,
                "SRWR": srwr,
                "searchFd": "BI",
                "addQuery": f"DBT={dbt}",
                "startPosition": 1,
                "displayCnt": min(max_results, 100),
            }
        elif target == "REPORT_SEARCH":
            # 국가R&D 연구보고서 검색
            endpoint = "/rndopen/openApi/rresearchpdf/"
            params = {
                "apprvKey": api_key,
                "userId": "",
                "collection": "researchpdf",
                "query": query,
                "searchField": "BI",
                "startPosition": 1,
                "displayCount": min(max_results, 100),
                "returnType": "xml",
            }
        elif target == "TERMINOLOGY":
            # 국가R&D 용어사전 조회
            endpoint = "/rndopen/openApi/ntisDic"
            params = {
                "apprvKey": api_key,
                "userId": "",
                "query": query,
                "searchField": "BI",
                "startPosition": 1,
                "displayCount": min(max_results, 100),
            }
        elif target == "ORG_STATUS":
            # 수행기관 R&D현황조회 - query=(값, mode) mode: "bno" 또는 "nm"
            if isinstance(query, tuple):
                org_value, mode = query
            else:
                org_value, mode = query, "nm"
            endpoint = "/rndopen/openApi/orgRndInfo"
            params = {"apprvKey": api_key}
            if mode == "bno":
                params["reqOrgBno"] = org_value
            else:
                params["reqOrgNm"] = org_value
        elif target == "ISSUE":
            # 이슈로보는R&D (SRWR 선택, 미입력시 최신 5개)
            endpoint = "/rndopen/openApi/issue"
            params = {"apprvKey": api_key}
            if query:
                params["SRWR"] = query
        elif target == "CLASS_CODE":
            # 표준분류/중점기술 코드검색 (POST) - query=(rqstSlctCd, rqstSearchCd)
            if isinstance(query, tuple):
                slct_cd, search_cd = query
            else:
                slct_cd, search_cd = query, ""
            endpoint = "/rndopen/openApi/targetSearch"
            params = {"apprvKey": api_key, "rqstSlctCd": slct_cd}
            if search_cd:
                params["rqstSearchCd"] = search_cd
        elif target == "COMMISSION":
            # 위탁/공동연구 과제 정보 (기관용) - query=pjtId
            endpoint = "/rndopen/openApi/projectuOrg"
            params = {"apprvKey": api_key, "pjtId": query}
        elif target == "PARTICIPATION":
            # 과제참여정보 (전문기관용) - query=(psnNm, rrNo)
            if isinstance(query, tuple):
                psn_nm, rr_no = query
            else:
                psn_nm, rr_no = query, ""
            endpoint = "/rndopen/openApi/prtcpProdRt"
            params = {"apprvKey": api_key, "psnNm": psn_nm, "rrNo": rr_no}
        elif target == "TOTAL_SEARCH":
            # 국가R&D 통합검색 (기관용) - query=(검색어, collection)
            if isinstance(query, tuple):
                srwr, collection_type = query
            else:
                srwr, collection_type = query, "project"
            endpoint = "/rndopen/openApi/totalRstSearch"
            params = {
                "apprvKey": api_key,
                "userId": "",
                "collection": collection_type,
                "SRWR": srwr,
                "searchFd": "BI",
                "startPosition": 1,
                "displayCnt": min(max_results, 100),
            }
            if collection_type in ("rpaper", "rpatent", "rresearch", "requip"):
                dbt_map = {"rpaper": "PAP", "rpatent": "PAT",
                           "rresearch": "TRKO", "requip": "EQU"}
                params["addQuery"] = f"DBT={dbt_map[collection_type]}"
        elif target == "RESEARCHER_INFO":
            # 출연(연) 연구자정보검색 (기관용) - query=(nm, rrno, brthdt)
            if isinstance(query, tuple) and len(query) == 3:
                nm, rrno, brthdt = query
            elif isinstance(query, tuple):
                nm, rrno = query
                brthdt = ""
            else:
                nm, rrno, brthdt = query, "", ""
            endpoint = "/rndopen/openApi/rsrcInfo"
            params = {"apprvKey": api_key, "nm": nm}
            if rrno:
                params["rrno"] = rrno
            if brthdt:
                params["brthdt"] = brthdt
        else:
            return {"error": True, "message": f"지원되지 않는 검색 타입: {target}"}

        url = f"{self.base_url}{endpoint}"

        logger.info(f"NTIS 요청 URL: {url}")
        logger.info(f"파라미터: {params}")

        async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
            # 분류/중점기술 코드검색은 POST 방식
            if target == "CLASS_CODE":
                response = await client.post(url, data=params)
            else:
                response = await client.get(url, params=params)

            logger.info(f"NTIS 응답 상태코드: {response.status_code}")
            logger.info(f"NTIS 응답 내용: {response.text[:500]}...")

            if response.status_code == 200:
                # 연관콘텐츠 검색은 JSON 형태로 응답
                if target == "RELATED_CONTENT":
                    return self._parse_json_response(response.text, target)
                else:
                    return self._parse_xml_response(response.text, target)
            else:
                return {"error": True, "message": f"NTIS API 요청 실패: {response.status_code}, 응답: {response.text[:200]}"}
    
    def _parse_json_response(self, json_result: str, target: str) -> Dict[str, Any]:
        """NTIS JSON 응답 파싱 (연관콘텐츠 전용)"""
        try:
            import json
            data = json.loads(json_result)
            
            if not data.get("exist", False):
                return {
                    "success": True,
                    "total_count": 0,
                    "results": []
                }
            
            items = data.get("items", [])
            results = []
            
            for item in items:
                # 각 collection 타입별로 필드명이 다름
                result = {}
                
                # 공통 필드
                result['similarity_score'] = item.get('similarity_score', 0)
                result['rank'] = item.get('rank', 0)
                result['creat_dt'] = item.get('creat_dt', '')
                
                # collection 타입별 특화 필드
                if 'PJT_ID' in item:
                    result['id'] = item['PJT_ID']
                    result['title'] = item.get('KOR_PJT_NM', '')
                    result['type'] = 'project'
                elif 'RST_ID' in item:
                    result['id'] = item['RST_ID']
                    if 'PAPER_NM' in item:
                        result['title'] = item['PAPER_NM']
                        result['type'] = 'paper'
                    elif 'IPR_INVENTION_NM' in item:
                        result['title'] = item['IPR_INVENTION_NM']
                        result['type'] = 'patent'
                    elif 'KOR_RPT_TITLE_NM' in item:
                        result['title'] = item['KOR_RPT_TITLE_NM']
                        result['type'] = 'researchreport'
                else:
                    # 알 수 없는 타입은 일반적으로 처리
                    result['id'] = str(item)
                    result['title'] = str(item)
                    result['type'] = 'unknown'
                
                results.append(result)
            
            return {
                "success": True,
                "total_count": len(results),
                "results": results,
                "project_info": {
                    "pjt_id": data.get("PJT_ID", ""),
                    "title": data.get("KOR_PJT_NM", "")
                }
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"NTIS JSON 파싱 오류: {str(e)}")
            logger.error(f"원본 JSON: {json_result[:500]}...")
            return {
                "error": True,
                "message": f"JSON 파싱 오류: {str(e)}",
                "raw_result": json_result[:200]
            }
        except Exception as e:
            logger.error(f"NTIS JSON 처리 오류: {str(e)}")
            return {
                "error": True,
                "message": f"JSON 처리 오류: {str(e)}",
                "raw_result": json_result[:200]
            }
    
    def _parse_xml_response(self, xml_result: str, target: str) -> Dict[str, Any]:
        """NTIS XML 응답 파싱"""
        try:
            root = ET.fromstring(xml_result)
            
            # 분류 추천 서비스는 다른 XML 구조를 사용
            if target == "CLASSIFICATION":
                return self._parse_classification_response(root)

            # 신규 전체용 서비스는 응답 래퍼가 제각각이라 전용 파서 사용
            if target in ("OUTCOME", "REPORT_SEARCH", "TERMINOLOGY",
                          "COMMISSION", "TOTAL_SEARCH"):
                return self._parse_resultset_response(root)
            if target == "ORG_STATUS":
                return self._parse_org_status_response(root)
            if target == "ISSUE":
                return self._parse_issue_response(root)
            if target == "CLASS_CODE":
                return self._parse_class_code_response(root)
            if target == "PARTICIPATION":
                return self._parse_participation_response(root)
            if target == "RESEARCHER_INFO":
                return self._parse_researcher_info_response(root)

            # 기존 PROJECT, RECOMMENDATION 서비스용 파싱
            # NTIS 응답 구조: RESULT 루트 엘리먼트
            total_hits = root.find('TOTALHITS')
            if total_hits is None:
                return {"error": True, "message": "TOTALHITS를 찾을 수 없습니다"}
            
            total_count = int(total_hits.text) if total_hits.text else 0
            
            # RESULTSET에서 HIT 요소들 파싱
            resultset = root.find('RESULTSET')
            if resultset is None:
                return {"error": True, "message": "RESULTSET을 찾을 수 없습니다"}
            
            hits = resultset.findall('HIT')
            results = []
            
            for hit in hits:
                # PDF 매뉴얼 page 8-9 구조에 맞게 전체 XML 구조를 그대로 파싱
                result = {}
                
                # 기본 정보
                project_number = hit.find('ProjectNumber')
                if project_number is not None:
                    result['ProjectNumber'] = project_number.text
                
                # 과제명 (한국어/영어)
                project_title_korean = hit.find('.//ProjectTitle/Korean')
                project_title_english = hit.find('.//ProjectTitle/English')
                project_title = {}
                if project_title_korean is not None:
                    project_title['Korean'] = project_title_korean.text or ""
                if project_title_english is not None:
                    project_title['English'] = project_title_english.text or ""
                if project_title:
                    result['ProjectTitle'] = project_title
                
                # 연구책임자
                manager_name = hit.find('.//Manager/Name')
                if manager_name is not None:
                    result['Manager'] = {'Name': manager_name.text or ""}
                
                # 참여연구원
                researchers_name = hit.find('.//Researchers/Name')
                man_count = hit.find('.//Researchers/ManCount')
                woman_count = hit.find('.//Researchers/WomanCount')
                researchers = {}
                if researchers_name is not None:
                    researchers['Name'] = researchers_name.text or ""
                if man_count is not None:
                    researchers['ManCount'] = man_count.text or ""
                if woman_count is not None:
                    researchers['WomanCount'] = woman_count.text or ""
                if researchers:
                    result['Researchers'] = researchers
                
                # 연구기관
                research_agency_name = hit.find('.//ResearchAgency/Name')
                if research_agency_name is not None:
                    result['ResearchAgency'] = {'Name': research_agency_name.text or ""}
                
                order_agency_name = hit.find('.//OrderAgency/Name')
                if order_agency_name is not None:
                    result['OrderAgency'] = {'Name': order_agency_name.text or ""}
                
                # 예산 사업
                budget_project_name = hit.find('.//BudgetProject/Name')
                if budget_project_name is not None:
                    result['BudgetProject'] = {'Name': budget_project_name.text or ""}
                
                # 부처
                ministry_name = hit.find('.//Ministry/Name')
                if ministry_name is not None:
                    result['Ministry'] = {'Name': ministry_name.text or ""}
                
                # 과제 연도
                project_year = hit.find('ProjectYear')
                if project_year is not None:
                    result['ProjectYear'] = project_year.text or ""
                
                # 과제 기간
                period_start = hit.find('.//ProjectPeriod/Start')
                period_end = hit.find('.//ProjectPeriod/End')
                total_start = hit.find('.//ProjectPeriod/TotalStart')
                total_end = hit.find('.//ProjectPeriod/TotalEnd')
                period = {}
                if period_start is not None:
                    period['Start'] = period_start.text or ""
                if period_end is not None:
                    period['End'] = period_end.text or ""
                if total_start is not None:
                    period['TotalStart'] = total_start.text or ""
                if total_end is not None:
                    period['TotalEnd'] = total_end.text or ""
                if period:
                    result['ProjectPeriod'] = period
                
                # 예산 정보
                gov_funds = hit.find('GovernmentFunds')
                if gov_funds is not None:
                    result['GovernmentFunds'] = gov_funds.text or ""
                
                total_funds = hit.find('TotalFunds')
                if total_funds is not None:
                    result['TotalFunds'] = total_funds.text or ""
                
                # 연구 목표/내용/효과 (핵심!)
                goal_full = hit.find('.//Goal/Full')
                goal_teaser = hit.find('.//Goal/Teaser')
                goal = {}
                if goal_full is not None:
                    goal['Full'] = goal_full.text or ""
                if goal_teaser is not None:
                    goal['Teaser'] = goal_teaser.text or ""
                if goal:
                    result['Goal'] = goal
                
                abstract_full = hit.find('.//Abstract/Full')
                abstract_teaser = hit.find('.//Abstract/Teaser')
                abstract = {}
                if abstract_full is not None:
                    abstract['Full'] = abstract_full.text or ""
                if abstract_teaser is not None:
                    abstract['Teaser'] = abstract_teaser.text or ""
                if abstract:
                    result['Abstract'] = abstract
                
                effect_full = hit.find('.//Effect/Full')
                effect_teaser = hit.find('.//Effect/Teaser')
                effect = {}
                if effect_full is not None:
                    effect['Full'] = effect_full.text or ""
                if effect_teaser is not None:
                    effect['Teaser'] = effect_teaser.text or ""
                if effect:
                    result['Effect'] = effect
                
                # 키워드
                keyword_korean = hit.find('.//Keyword/Korean')
                keyword_english = hit.find('.//Keyword/English')
                keyword = {}
                if keyword_korean is not None:
                    keyword['Korean'] = keyword_korean.text or ""
                if keyword_english is not None:
                    keyword['English'] = keyword_english.text or ""
                if keyword:
                    result['Keyword'] = keyword
                
                # 하위 호환성을 위한 기존 필드명들
                if 'ProjectNumber' in result:
                    result['pjtNo'] = result['ProjectNumber']
                    result['pjtId'] = result['ProjectNumber']  # 연관콘텐츠 검색용 pjtId 추가
                if 'ProjectTitle' in result and 'Korean' in result['ProjectTitle']:
                    result['pjtName'] = result['ProjectTitle']['Korean']
                    result['title'] = result['ProjectTitle']['Korean']  # 연관콘텐츠 검색용 title 추가
                if 'Manager' in result and 'Name' in result['Manager']:
                    result['researchManager'] = result['Manager']['Name']
                if 'ResearchAgency' in result and 'Name' in result['ResearchAgency']:
                    result['instName'] = result['ResearchAgency']['Name']
                if 'ProjectPeriod' in result:
                    if 'Start' in result['ProjectPeriod'] and 'End' in result['ProjectPeriod']:
                        start_date = result['ProjectPeriod']['Start']
                        end_date = result['ProjectPeriod']['End']
                        start_year = start_date[:4] if start_date and len(start_date) >= 4 else ""
                        end_year = end_date[:4] if end_date and len(end_date) >= 4 else ""
                        if start_year and end_year:
                            result['pjtPeriod'] = f"{start_year}~{end_year}"
                
                # 연구분야
                science_class = hit.find('.//ScienceClass[@type="new"][@sequence="1"]/Large')
                if science_class is not None:
                    result['researchArea'] = science_class.text
                
                # 총 연구비
                total_funds = hit.find('TotalFunds')
                if total_funds is not None and total_funds.text:
                    try:
                        funds_amount = int(total_funds.text)
                        result['totalExpense'] = f"{funds_amount:,}원"
                    except:
                        result['totalExpense'] = total_funds.text
                
                # 정부지원금
                govt_funds = hit.find('GovernmentFunds')
                if govt_funds is not None and govt_funds.text:
                    try:
                        govt_amount = int(govt_funds.text)
                        result['govtExpense'] = f"{govt_amount:,}원"
                    except:
                        result['govtExpense'] = govt_funds.text
                
                # 과제요약 (목표)
                goal = hit.find('.//Goal/Full')
                if goal is not None:
                    clean_goal = re.sub(r'<[^>]+>', '', goal.text) if goal.text else ""
                    result['abstract'] = clean_goal[:500] + "..." if len(clean_goal) > 500 else clean_goal
                
                # 키워드
                keyword = hit.find('.//Keyword/Korean')
                if keyword is not None:
                    clean_keyword = re.sub(r'<[^>]+>', '', keyword.text) if keyword.text else ""
                    result['keyword'] = clean_keyword
                
                results.append(result)
            
            return {
                "success": True,
                "total_count": total_count,
                "results": results
            }
            
        except ET.ParseError as e:
            logger.error(f"NTIS XML 파싱 오류: {str(e)}")
            logger.error(f"원본 XML: {xml_result[:500]}...")
            return {
                "error": True,
                "message": f"XML 파싱 오류: {str(e)}",
                "raw_result": xml_result[:200]
            }
    
    def _flatten_element(self, elem) -> Dict[str, Any]:
        """XML 엘리먼트를 평면 dict로 변환.
        - 자식 텍스트는 태그명을 키로
        - 중첩(Korean/English, Full/Teaser 등)은 부모태그+자식태그 결합 또는 부모태그에 우선값
        - 같은 태그 반복은 ';'로 결합
        """
        result: Dict[str, Any] = {}

        def put(key, value):
            if value is None:
                return
            value = value.strip() if isinstance(value, str) else value
            if not value:
                return
            if key in result and result[key]:
                result[key] = f"{result[key]};{value}"
            else:
                result[key] = value

        for child in elem:
            tag = child.tag
            children = list(child)
            if children:
                # 중첩 구조: Korean/English/Full/Teaser/Name 등
                # 한국어/대표값 우선으로 부모 태그에 매핑
                kor = child.find('Korean')
                full = child.find('Full')
                name = child.find('Name')
                if kor is not None:
                    put(tag, kor.text)
                    eng = child.find('English')
                    if eng is not None and eng.text:
                        put(tag + 'Eng', eng.text)
                elif full is not None:
                    put(tag, full.text)
                elif name is not None:
                    put(tag, name.text)
                else:
                    # 그 외 중첩은 자식 텍스트들을 펼침
                    for sub in children:
                        if sub.text and sub.text.strip():
                            put(tag + sub.tag, sub.text)
            else:
                put(tag, child.text)
        return result

    def _parse_resultset_response(self, root) -> Dict[str, Any]:
        """RESULT>RESULTSET>HIT 구조 파싱 (성과검색/연구보고서/용어사전)"""
        total_hits = root.find('TOTALHITS')
        total_count = int(total_hits.text) if total_hits is not None and total_hits.text else 0
        resultset = root.find('RESULTSET')
        results = []
        if resultset is not None:
            for hit in resultset.findall('HIT'):
                results.append(self._flatten_element(hit))
        if total_count == 0:
            total_count = len(results)
        return {"success": True, "total_count": total_count, "results": results}

    def _parse_org_status_response(self, root) -> Dict[str, Any]:
        """response>header+body 구조 파싱 (수행기관 R&D현황조회)"""
        header = root.find('header')
        result_code = header.findtext('resultCode') if header is not None else None
        result_msg = header.findtext('resultMsg') if header is not None else None
        if result_code is not None and result_code != "00":
            return {"error": True, "status_code": result_code,
                    "error_message": result_msg or "수행기관 정보 조회 오류"}
        body = root.find('body')
        results = []
        if body is not None:
            results.append(self._flatten_element(body))
        return {"success": True, "total_count": len(results), "results": results}

    def _parse_issue_response(self, root) -> Dict[str, Any]:
        """NewestIssue>list 구조 파싱 (이슈로보는R&D). 오류 시 RESULT 래퍼"""
        if root.tag == 'RESULT':
            return {"error": True,
                    "error_message": root.findtext('resMsg') or "이슈 조회 오류"}
        results = []
        for item in root.findall('list'):
            results.append(self._flatten_element(item))
        cnt = root.findtext('selectListCnt') or root.findtext('searchListCnt')
        total_count = int(cnt) if cnt and cnt.isdigit() else len(results)
        return {"success": True, "total_count": total_count, "results": results}

    def _parse_class_code_response(self, root) -> Dict[str, Any]:
        """ntis>status+contents>dataset 구조 파싱 (분류/중점기술 코드검색)"""
        status = root.find('status')
        recode = status.findtext('recode') if status is not None else None
        if recode is not None and recode != "100":
            remsg = status.findtext('remsg') if status is not None else None
            return {"error": True, "status_code": recode,
                    "error_message": remsg or "코드 검색 오류"}
        contents = root.find('contents')
        results = []
        if contents is not None:
            for ds in contents.findall('dataset'):
                results.append(self._flatten_element(ds))
        return {"success": True, "total_count": len(results), "results": results}

    def _parse_participation_response(self, root) -> Dict[str, Any]:
        """RESULT_SET>RESULT_LIST>RESULT 구조 파싱 (과제참여정보)"""
        err = root.findtext('ERR_MSG')
        if err and err.strip():
            return {"error": True, "error_message": err}
        total = root.findtext('TOTAL_CNT')
        result_list = root.find('RESULT_LIST')
        results = []
        if result_list is not None:
            for rec in result_list.findall('RESULT'):
                results.append(self._flatten_element(rec))
        total_count = int(total) if total and total.isdigit() else len(results)
        return {"success": True, "total_count": total_count, "results": results}

    def _parse_researcher_info_response(self, root) -> Dict[str, Any]:
        """ResultList>Result 구조 파싱 (출연연 연구자정보)"""
        results = []
        # 루트가 ResultList이거나 그 하위에 Result들이 있음
        for rec in root.findall('.//Result'):
            results.append(self._flatten_element(rec))
        cnt = root.get('Count')
        total_count = int(cnt) if cnt and cnt.isdigit() else len(results)
        return {"success": True, "total_count": total_count, "results": results}

    def _parse_classification_response(self, root) -> Dict[str, Any]:
        """과학기술표준분류 추천 응답 파싱"""
        try:
            # STATUS 확인
            status = root.find('STATUS')
            if status is not None:
                result_code = status.find('ResultCode')
                result_msg = status.find('ResultMsg')
                
                if result_code is not None and result_code.text != "0":
                    error_msg = result_msg.text if result_msg is not None else "알 수 없는 오류"
                    return {"error": True, "message": f"API 오류 (코드: {result_code.text}): {error_msg}"}
            
            # RESULT 요소 파싱
            result_element = root.find('RESULT')
            if result_element is None:
                return {"error": True, "message": "RESULT 요소를 찾을 수 없습니다"}
            
            classifications = []
            
            # RESULT TYPE 확인 (1: 표준분류, 4: 보건의료분류, 6: 산업기술분류 등)
            result_type = result_element.get('TYPE', '1')
            
            if result_type == '4':
                # 보건의료기술분류: MOHWR, MOHWD, MOTIE 섹션들 처리
                for section in result_element:
                    section_name = section.tag
                    for result_item in section:
                        classification = self._parse_health_classification_item(result_item, section_name)
                        if classification:
                            classifications.append(classification)
            elif result_type == '6':
                # 산업기술분류: 단일 구조
                for result_item in result_element:
                    classification = {}
                    attrs = result_item.attrib
                    
                    # 산업기술분류 특수 필드들 처리
                    for key, value in attrs.items():
                        if value and value.strip():  # 빈 값 제외
                            classification[key.lower()] = value
                    
                    # 매칭 점수 찾기
                    for weight_key in ['SCLS_WEIGHT', 'MCLS_WEIGHT', 'LCLS_WEIGHT']:
                        if weight_key in attrs and attrs[weight_key]:
                            classification['matching_score'] = attrs[weight_key]
                            break
                    
                    classification['section'] = 'INDUSTRY'
                    classifications.append(classification)
            else:
                # 표준분류 및 기타: 기존 방식
                for result_item in result_element:
                    classification = {}
                    
                    # 속성에서 분류 정보 추출
                    attrs = result_item.attrib
                    
                    # 대분류
                    if 'LCLS_CD' in attrs:
                        classification['lcls_code'] = attrs['LCLS_CD']
                    if 'LCLS_NM' in attrs:
                        classification['lcls_name'] = attrs['LCLS_NM']
                    
                    # 중분류
                    if 'MCLS_CD' in attrs:
                        classification['mcls_code'] = attrs['MCLS_CD']
                    if 'MCLS_NM' in attrs:
                        classification['mcls_name'] = attrs['MCLS_NM']
                    
                    # 소분류
                    if 'SCLS_CD' in attrs:
                        classification['scls_code'] = attrs['SCLS_CD']
                    if 'SCLS_NM' in attrs:
                        classification['scls_name'] = attrs['SCLS_NM']
                    
                    # 매칭 점수
                    if 'SCLS_WEIGHT' in attrs:
                        classification['matching_score'] = attrs['SCLS_WEIGHT']
                    elif 'MCLS_WEIGHT' in attrs:
                        classification['matching_score'] = attrs['MCLS_WEIGHT']
                    elif 'DCLS_WEIGHT' in attrs:
                        classification['matching_score'] = attrs['DCLS_WEIGHT']
                    
                    classifications.append(classification)
            
            return {
                "success": True,
                "total_count": len(classifications),
                "classifications": classifications
            }
            
        except Exception as e:
            logger.error(f"분류 추천 XML 파싱 오류: {str(e)}")
            return {
                "error": True,
                "message": f"분류 추천 XML 파싱 오류: {str(e)}"
            }
    
    def _parse_health_classification_item(self, result_item, section_name: str) -> Dict[str, Any]:
        """보건의료기술분류 개별 항목 파싱"""
        classification = {}
        attrs = result_item.attrib
        
        # 섹션별로 다른 구조 처리
        if section_name == "MOHWR":
            # 보건복지부 분류
            if 'LCLS_CD' in attrs:
                classification['lcls_code'] = attrs['LCLS_CD']
            if 'LCLS_NM' in attrs:
                classification['lcls_name'] = attrs['LCLS_NM']
            if 'MCLS_CD' in attrs:
                classification['mcls_code'] = attrs['MCLS_CD']
            if 'MCLS_NM' in attrs:
                classification['mcls_name'] = attrs['MCLS_NM']
            if 'MCLS_WEIGHT' in attrs:
                classification['matching_score'] = attrs['MCLS_WEIGHT']
                
        elif section_name == "MOHWD":
            # 질병분류
            if 'DCLS_CD' in attrs:
                classification['disease_code'] = attrs['DCLS_CD']
            if 'DCLS_NM' in attrs:
                classification['disease_name'] = attrs['DCLS_NM'] 
            if 'DCLS_WEIGHT' in attrs:
                classification['matching_score'] = attrs['DCLS_WEIGHT']
                
        elif section_name == "MOTIE":
            # 산업통상자원부 분류
            if 'LCLS_CD' in attrs:
                classification['lcls_code'] = attrs['LCLS_CD']
            if 'LCLS_NM' in attrs:
                classification['lcls_name'] = attrs['LCLS_NM']
            if 'MCLS_CD' in attrs:
                classification['mcls_code'] = attrs['MCLS_CD']
            if 'MCLS_NM' in attrs:
                classification['mcls_name'] = attrs['MCLS_NM']
            if 'SCLS_CD' in attrs:
                classification['scls_code'] = attrs['SCLS_CD']
            if 'SCLS_NM' in attrs:
                classification['scls_name'] = attrs['SCLS_NM']
            if 'SCLS_WEIGHT' in attrs:
                classification['matching_score'] = attrs['SCLS_WEIGHT']
        
        # 섹션 정보 추가
        classification['section'] = section_name
        return classification
# ScienceON 전용 구현
class ScienceONClient(BaseAPIClient):
    """KISTI ScienceON API 클라이언트"""
    
    def __init__(self):
        super().__init__("https://apigateway.kisti.re.kr")

        # 환경변수에서 인증 정보 읽기
        self.api_key = get_env("SCIENCEON_API_KEY")
        self.client_id = get_env("SCIENCEON_CLIENT_ID")
        self.mac_address = get_env("SCIENCEON_MAC_ADDRESS")

        # 필수 정보 검증
        self._validate_credentials()

        self.refresh_token = None
        # 토큰 캐싱 (TTL 1시간)
        self._token_issued_at = None
        self._TOKEN_TTL_SECONDS = 3600
    
    def _validate_credentials(self):
        """인증 정보 검증"""
        if not all([self.api_key, self.client_id, self.mac_address]):
            missing = []
            if not self.api_key:
                missing.append("SCIENCEON_API_KEY")
            if not self.client_id:
                missing.append("SCIENCEON_CLIENT_ID")
            if not self.mac_address:
                missing.append("SCIENCEON_MAC_ADDRESS")
            
            logger.error(f"필수 환경변수가 설정되지 않았습니다: {', '.join(missing)}")
            raise ValueError(f"필수 환경변수 누락: {', '.join(missing)}")
        
        logger.info("KISTI API 인증 정보가 성공적으로 로드되었습니다.")
    
    def _create_token_request_url(self):
        """토큰 요청 URL 생성"""
        try:
            # 현재 시간을 숫자만 추출
            time_str = ''.join(re.findall(r"\d", datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            
            # accounts 파라미터 생성
            plain_data = {
                "datetime": time_str,
                "mac_address": self.mac_address
            }
            plain_txt = json.dumps(plain_data, separators=(',', ':'))
            
            logger.info(f"암호화할 데이터: {plain_txt}")
            
            # AES 암호화
            encryption = AESTestClass(plain_txt, self.api_key)
            encrypted_txt = encryption.encrypt()
            
            logger.info(f"암호화된 데이터: {encrypted_txt[:50]}...")
            
            # URL 생성
            url = f"{self.base_url}/tokenrequest.do?client_id={self.client_id}&accounts={encrypted_txt}"
            return url
            
        except Exception as e:
            logger.error(f"토큰 URL 생성 실패: {str(e)}")
            return ""
    
    async def get_token(self) -> bool:
        """토큰 발급 (TTL 내에서는 캐시된 토큰 재사용)"""
        # 유효한 토큰이 캐시돼 있으면 재발급 생략
        if self.access_token and self._token_issued_at is not None:
            age = (datetime.now() - self._token_issued_at).total_seconds()
            if age < self._TOKEN_TTL_SECONDS:
                return True

        logger.info("토큰 발급 요청 중...")

        try:
            url = self._create_token_request_url()
            if not url:
                return False
            
            logger.info(f"요청 URL: {url[:100]}...")
            
            async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
                response = await client.get(url)
                
                logger.info(f"응답 상태: {response.status_code}")
                logger.info(f"응답 내용: {response.text}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        self.access_token = data.get('access_token')
                        self.refresh_token = data.get('refresh_token')
                        self._token_issued_at = datetime.now()

                        logger.info(f"토큰 발급 성공!")
                        return True
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 파싱 실패: {str(e)}")
                        return False
                else:
                    logger.error(f"토큰 발급 실패: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"토큰 발급 중 오류: {str(e)}")
            return False
    
    async def search(self, query, target: str, max_results: int = 5,
                     query_field: str = "BI") -> Dict[str, Any]:
        """검색 수행

        query: 검색어 문자열, 또는 이미 구성된 searchQuery dict
        query_field: 검색 필드 키 (BI=서지통합, PY=발행연도, RD=날짜 등)
        """
        # JSON 형식으로 검색 쿼리 생성
        if isinstance(query, dict):
            search_dict = query
        else:
            search_dict = {query_field: query}
        search_query = json.dumps(search_dict, ensure_ascii=False)
        encoded_query = quote(search_query)
        
        # URL 생성
        url = (f"{self.base_url}/openapicall.do?"
               f"client_id={self.client_id}&"
               f"token={self.access_token}&"
               f"version=1.0&"
               f"action=search&"
               f"target={target}&"
               f"searchQuery={encoded_query}&"
               f"curPage=1&"
               f"rowCount={min(max_results, 100)}")
        
        logger.info(f"요청 URL: {url[:150]}...")
        
        async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                return self._parse_xml_response(response.text)
            else:
                return {"error": True, "message": f"API 요청 실패: {response.status_code}"}
    
    async def get_details(self, cn: str, target: str = "ARTI") -> Dict[str, Any]:
        """상세 정보 조회"""
        url = (f"{self.base_url}/openapicall.do?"
               f"client_id={self.client_id}&"
               f"token={self.access_token}&"
               f"version=1.0&"
               f"action=browse&"
               f"target={target}&"
               f"cn={cn}")
        
        logger.info(f"상세보기 요청 URL: {url[:150]}...")
        
        async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                return self._parse_xml_response(response.text)
            else:
                return {"error": True, "message": f"API 요청 실패: {response.status_code}"}
    
    async def get_citations(self, cn: str, target: str = "PATENT") -> Dict[str, Any]:
        """인용/피인용 정보 조회"""
        url = (f"{self.base_url}/openapicall.do?"
               f"client_id={self.client_id}&"
               f"token={self.access_token}&"
               f"version=1.0&"
               f"action=citation&"
               f"target={target}&"
               f"cn={cn}")
        
        logger.info(f"인용정보 요청 URL: {url[:150]}...")
        
        async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                return self._parse_xml_response(response.text)
            else:
                return {"error": True, "message": f"API 요청 실패: {response.status_code}"}
    
    def _parse_xml_response(self, xml_result: str) -> Dict[str, Any]:
        """XML 응답 파싱"""
        try:
            root = ET.fromstring(xml_result)
            
            # 상태 확인
            status_code = root.find('.//statusCode')
            if status_code is not None and status_code.text != "200":
                error_code = root.find('.//errorCode')
                error_message = root.find('.//errorMessage')
                return {
                    "error": True,
                    "status_code": status_code.text,
                    "error_code": error_code.text if error_code is not None else None,
                    "error_message": error_message.text if error_message is not None else None
                }
            
            # 정상 결과 파싱
            total_count = root.find('.//TotalCount')
            records = root.findall('.//record')
            
            papers = []
            for record in records:
                paper = {}
                for item in record.findall('item'):
                    meta_code = item.get('metaCode')
                    value = item.text if item.text else ""
                    paper[meta_code] = value
                papers.append(paper)
            
            return {
                "success": True,
                "total_count": int(total_count.text) if total_count is not None else 0,
                "papers": papers,   # 레거시 키 (기존 7개 메서드 호환)
                "records": papers   # 신규 일반화 키 (신규 도구가 사용)
            }
            
        except ET.ParseError as e:
            return {
                "error": True,
                "message": f"XML 파싱 오류: {str(e)}",
                "raw_result": xml_result
            }

# DataON 전용 구현
class DataONClient(BaseAPIClient):
    """KISTI DataON API 클라이언트"""

    def __init__(self):
        super().__init__("https://dataon.kisti.re.kr")

        # 환경변수에서 인증 정보 읽기
        self.research_data_api_key = get_env("DataON_ResearchData_API_KEY")
        self.research_data_metadata_api_key = get_env("DataON_ResearchDataMetadata_API_KEY")

        # 필수 정보 검증
        self._validate_credentials()

    def _validate_credentials(self):
        """인증 정보 검증"""
        missing = []
        if not self.research_data_api_key:
            missing.append("DataON_ResearchData_API_KEY")
        if not self.research_data_metadata_api_key:
            missing.append("DataON_ResearchDataMetadata_API_KEY")

        if missing:
            logger.warning(f"DataON API KEY가 설정되지 않았습니다: {', '.join(missing)}")
            logger.info("DataON 서비스가 비활성화됩니다.")
            raise ValueError(f"필수 환경변수 누락: {', '.join(missing)}")
        else:
            logger.info("DataON API 인증 정보가 성공적으로 로드되었습니다.")

    async def get_token(self) -> bool:
        """DataON은 토큰 발급이 필요하지 않음 (API KEY 직접 사용)"""
        return True

    async def search(self, query: str, target: str = "RESEARCH_DATA", max_results: int = 10,
                    from_pos: int = 0, sort_con: str = "", sort_arr: str = "desc") -> Dict[str, Any]:
        """
        DataON 연구데이터 검색

        Args:
            query: 검색 키워드
            target: 검색 대상 (RESEARCH_DATA 또는 RESEARCH_DATA_DETAIL)
            max_results: 최대 결과 수 (기본 10)
            from_pos: 시작 위치 (기본 0)
            sort_con: 정렬 조건 (date, title 등)
            sort_arr: 정렬 방향 (asc, desc)
        """
        if target == "RESEARCH_DATA":
            api_key = self.research_data_api_key
        else:
            api_key = self.research_data_metadata_api_key

        if not api_key:
            return {"error": True, "message": f"DataON API KEY가 설정되지 않았습니다: {target}"}

        endpoint = "/rest/api/search/dataset/"
        url = f"{self.base_url}{endpoint}"

        params = {
            "key": api_key,
            "query": query,
            "from": from_pos,
            "size": min(max_results, 100)
        }

        # 선택적 파라미터 추가
        if sort_con:
            params["sortCon"] = sort_con
        if sort_arr:
            params["sortArr"] = sort_arr

        logger.info(f"DataON 요청 URL: {url}")
        logger.info(f"파라미터: {params}")

        try:
            async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
                response = await client.get(url, params=params)

                logger.info(f"DataON 응답 상태코드: {response.status_code}")
                logger.info(f"DataON 응답 내용: {response.text[:500]}...")

                if response.status_code == 200:
                    return self._parse_json_response(response.text, target)
                else:
                    return {"error": True, "message": f"DataON API 요청 실패: {response.status_code}, 응답: {response.text[:200]}"}
        except Exception as e:
            logger.error(f"DataON API 요청 중 오류: {str(e)}")
            return {"error": True, "message": f"DataON API 요청 중 오류: {str(e)}"}

    async def get_details(self, svc_id: str) -> Dict[str, Any]:
        """
        DataON 연구데이터 상세 정보 조회

        Args:
            svc_id: 서비스 ID (데이터셋 고유 식별자)
        """
        if not self.research_data_metadata_api_key:
            return {"error": True, "message": "DataON_ResearchDataMetadata_API_KEY가 설정되지 않았습니다"}

        # PDF 매뉴얼에 따르면 svcId를 URL 경로에 포함
        endpoint = f"/rest/api/search/dataset/{svc_id}"
        url = f"{self.base_url}{endpoint}"

        # key만 query parameter로 전달
        params = {
            "key": self.research_data_metadata_api_key
        }

        logger.info(f"DataON 상세조회 URL: {url}")
        logger.info(f"파라미터: {params}")

        try:
            async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": USER_AGENT}) as client:
                response = await client.get(url, params=params)

                logger.info(f"DataON 응답 상태코드: {response.status_code}")
                logger.info(f"DataON 응답 내용: {response.text[:500]}...")

                if response.status_code == 200:
                    return self._parse_json_response(response.text, "DETAIL")
                else:
                    return {"error": True, "message": f"DataON API 요청 실패: {response.status_code}, 응답: {response.text[:200]}"}
        except Exception as e:
            logger.error(f"DataON API 요청 중 오류: {str(e)}")
            return {"error": True, "message": f"DataON API 요청 중 오류: {str(e)}"}

    def _parse_json_response(self, json_result: str, target: str) -> Dict[str, Any]:
        """DataON JSON 응답 파싱"""
        try:
            data = json.loads(json_result)

            # 에러 응답 체크
            response_info = data.get("response", {})
            if response_info.get("status") == "error":
                return {
                    "error": True,
                    "message": response_info.get("message", "알 수 없는 오류")
                }

            # 검색 결과인 경우
            if target == "RESEARCH_DATA":
                total_count = response_info.get("total count", 0)
                records = data.get("records", [])

                results = []
                for record in records:
                    # DataON API의 실제 필드명 사용
                    # 작성자와 발행기관은 배열로 제공됨
                    creators = record.get("dataset_creator_kor", [])
                    creator_str = ", ".join(creators) if creators else ""

                    publishers = record.get("dataset_pblshr", [])
                    publisher_str = ", ".join(publishers) if publishers else ""

                    result = {
                        "svcId": record.get("svc_id", ""),
                        "score": 0,  # DataON API는 score를 직접 제공하지 않음
                        "title": record.get("dataset_title_kor", ""),
                        "creator": creator_str,
                        "publisher": publisher_str,
                        "date": record.get("dataset_pub_dt_pc", ""),
                        "description": record.get("dataset_expl_kor", ""),
                        "subject": record.get("dataset_kywd_kor", ""),
                        "type": record.get("dataset_type_pc", ""),
                        "format": record.get("file_frmt_pc", []),
                        "rights": record.get("dataset_cc_license_pc", ""),
                        "coverage": record.get("dataset_data_loc", ""),
                        "landing_page": record.get("dataset_lndgpg", ""),
                        "doi": record.get("dataset_doi", "")
                    }
                    results.append(result)

                return {
                    "success": True,
                    "total_count": total_count,
                    "results": results
                }

            # 상세 정보인 경우
            elif target == "DETAIL":
                # 상세조회 API는 records가 단일 객체로 반환됨 (배열 아님)
                records = data.get("records", {})

                # records가 dict가 아니거나 비어있으면 에러
                if not isinstance(records, dict) or not records:
                    return {
                        "error": True,
                        "message": "해당 svcId의 데이터를 찾을 수 없습니다"
                    }

                record = records

                # 작성자, 기여자, 발행기관은 배열로 제공됨
                creators = record.get("dataset_creator_kor", [])
                creator_str = ", ".join(creators) if creators else ""

                contributors = record.get("dataset_cntrbtr_kor", [])
                contributor_str = ", ".join(contributors) if contributors else ""

                publishers = record.get("dataset_pblshr", [])
                publisher_str = ", ".join(publishers) if publishers else ""

                return {
                    "success": True,
                    "result": {
                        "svcId": record.get("svc_id", ""),
                        "title": record.get("dataset_title_kor", ""),
                        "creator": creator_str,
                        "publisher": publisher_str,
                        "date": record.get("dataset_pub_dt_pc", ""),
                        "description": record.get("dataset_expl_kor", ""),
                        "subject": record.get("dataset_kywd_kor", ""),
                        "type": record.get("dataset_type_pc", ""),
                        "format": record.get("file_frmt_pc", []),
                        "rights": record.get("dataset_cc_license_pc", ""),
                        "coverage": record.get("dataset_data_loc", ""),
                        "relation": record.get("pjt_nm_kor", []),
                        "language": record.get("dataset_main_lang_pc", ""),
                        "identifier": record.get("dataset_doi", ""),
                        "contributor": contributor_str,
                        "landing_page": record.get("dataset_lndgpg", ""),
                        "platform": record.get("cltfm_kor", "")
                    }
                }
            else:
                return {"error": True, "message": f"지원되지 않는 target 타입: {target}"}

        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {str(e)}")
            return {
                "error": True,
                "message": f"JSON 파싱 오류: {str(e)}",
                "raw_result": json_result[:500]
            }
        except Exception as e:
            logger.error(f"응답 처리 중 오류: {str(e)}")
            return {
                "error": True,
                "message": f"응답 처리 중 오류: {str(e)}"
            }

class NTISFormatter(BaseResultFormatter):
    """NTIS 결과 포매터"""
    
    def format_search_results(self, results: List[Dict], query: str, total_count: int, result_type: str) -> str:
        """NTIS 검색 결과 포맷팅"""
        if result_type == "project":
            return self._format_project_results(results, query, total_count)
        elif result_type.startswith("classification"):
            # classification_standard, classification_health, classification_industry 등 처리
            classification_type = result_type.split("_")[1] if "_" in result_type else "standard"
            return self._format_classification_results(results, query, total_count, classification_type)
        elif result_type == "recommendation":
            return self._format_recommendation_results(results, query, total_count)
        elif result_type.startswith("related_"):
            # related_project, related_paper, related_patent, related_researchreport 처리
            collection_type = result_type.split("_")[1] if "_" in result_type else "researchreport"
            return self._format_related_content_results(results, query, total_count, collection_type)
        elif result_type == "outcome":
            return self._format_outcome_results(results, query, total_count)
        elif result_type == "report_search":
            return self._format_report_search_results(results, query, total_count)
        elif result_type == "terminology":
            return self._format_terminology_results(results, query, total_count)
        elif result_type == "org_status":
            return self._format_org_status_results(results, query, total_count)
        elif result_type == "issue":
            return self._format_issue_results(results, query, total_count)
        elif result_type == "class_code":
            return self._format_class_code_results(results, query, total_count)
        elif result_type == "commission":
            return self._format_commission_results(results, query, total_count)
        elif result_type == "participation":
            return self._format_participation_results(results, query, total_count)
        elif result_type == "total_search":
            return self._format_outcome_results(results, query, total_count)
        elif result_type == "researcher_info":
            return self._format_researcher_info_results(results, query, total_count)
        else:
            return f"지원되지 않는 결과 타입: {result_type}"

    def _ntis_clean(self, text: str, max_len: int = 250) -> str:
        return clean_text(text, max_len)

    def _format_outcome_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """국가R&D 성과검색 결과 포맷팅 (논문/특허/시설장비 공통)"""
        lines = []
        for r in items:
            title = r.get("ResultTitle") or r.get("Title") or "제목 없음"
            lines.append(f"**{title}**")
            if r.get("Author"):
                lines.append(f"  - 저자/출원인: {r['Author']}")
            if r.get("Registrant"):
                lines.append(f"  - 출원/등록인: {r['Registrant']}")
            if r.get("JournalName"):
                lines.append(f"📖 학술지: {r['JournalName']}")
            if r.get("RegistNumber"):
                lines.append(f"  - 출원/등록번호: {r['RegistNumber']}")
            if r.get("KeepOrganization"):
                lines.append(f"🏢 보유기관: {r['KeepOrganization']}")
            if r.get("PerformAgency"):
                lines.append(f"🏢 수행기관: {r['PerformAgency']}")
            if r.get("PubYear") or r.get("Year") or r.get("ProjectYear"):
                lines.append(f"  - 연도: {r.get('PubYear') or r.get('Year') or r.get('ProjectYear')}")
            if r.get("ProjectTitle"):
                lines.append(f"  - 관련 과제: {self._ntis_clean(r['ProjectTitle'], 100)}")
            if r.get("Abstract"):
                lines.append(f"📝 초록: {self._ntis_clean(r['Abstract'])}")
            if r.get("ResultID"):
                lines.append(f"🔗 성과ID: {r['ResultID']}")
            lines.append("")
        return (f"**'{query}' 국가R&D 성과검색 결과** "
                f"(총 {total_count:,}건 중 {len(items)}건 표시):\n\n" + "\n".join(lines))

    def _format_report_search_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """국가R&D 연구보고서 검색 결과 포맷팅"""
        lines = []
        for r in items:
            title = r.get("ResultTitle") or "보고서명 없음"
            lines.append(f"**{title}**")
            if r.get("PublicationAgency"):
                lines.append(f"🏢 발행기관: {r['PublicationAgency']}")
            if r.get("PublicationYear"):
                lines.append(f"  - 발행년도: {r['PublicationYear']}")
            if r.get("ProjectTitle"):
                lines.append(f"  - 과제명: {self._ntis_clean(r['ProjectTitle'], 100)}")
            if r.get("ManagerName") or r.get("Manager"):
                lines.append(f"👤 연구책임자: {r.get('ManagerName') or r.get('Manager')}")
            if r.get("Abstract"):
                lines.append(f"📝 초록: {self._ntis_clean(r['Abstract'])}")
            if r.get("DocUrl"):
                lines.append(f"📄 원문: {r['DocUrl']}")
            if r.get("TermSn"):
                lines.append(f"🔗 성과번호: {r['TermSn']}")
            lines.append("")
        return (f"**'{query}' 국가R&D 연구보고서 검색 결과** "
                f"(총 {total_count:,}건 중 {len(items)}건 표시):\n\n" + "\n".join(lines))

    def _format_terminology_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """국가R&D 용어사전 조회 결과 포맷팅"""
        lines = []
        for r in items:
            kor = r.get("KorWord", "용어 없음")
            eng = r.get("EngWord", "")
            lines.append(f"**{kor}**" + (f" ({eng})" if eng else ""))
            if r.get("MainAbrv"):
                lines.append(f"  - 주약어: {r['MainAbrv']}")
            if r.get("TermDctn"):
                lines.append(f"📝 설명: {self._ntis_clean(r['TermDctn'])}")
            if r.get("RelWord"):
                lines.append(f"🔗 연관어: {self._ntis_clean(r['RelWord'], 150)}")
            lines.append("")
        return (f"**'{query}' 국가R&D 용어사전 조회 결과** "
                f"(총 {total_count:,}건 중 {len(items)}건 표시):\n\n" + "\n".join(lines))

    def _format_org_status_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """수행기관 R&D현황조회 결과 포맷팅 (외부용 허용필드만)"""
        if not items:
            return f"'{query}'에 대한 수행기관 R&D현황 정보가 없습니다."
        lines = []
        for r in items:
            lines.append(f"**{r.get('orgName', query)}**")
            if r.get("rndKorKeyword") or r.get("rndKorKeword"):
                lines.append(f"  - 국문 연구키워드: {r.get('rndKorKeyword') or r.get('rndKorKeword')}")
            if r.get("rndCategory"):
                lines.append(f"  - 연구분야: {r['rndCategory']}")
            if r.get("year"):
                lines.append(f"  - 연도: {r['year']} / 과제 {r.get('pjtCnt','0')}건 / "
                             f"논문 {r.get('paperCnt','0')}건 / 특허 {r.get('patentCnt','0')}건 / "
                             f"보고서 {r.get('reportCnt') or r.get('reportcnt','0')}건")
            if r.get("orgPageInfo"):
                lines.append(f"🔗 NTIS 기관 링크: {r['orgPageInfo']}")
            lines.append("")
        return (f"**'{query}' 수행기관 R&D현황** "
                f"({len(items)}건):\n\n" + "\n".join(lines))

    def _format_issue_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """이슈로보는R&D 결과 포맷팅"""
        if not items:
            return "이슈 정보가 없습니다."
        lines = []
        for r in items:
            lines.append(f"**{r.get('topicNm', '이슈명 없음')}**")
            if r.get("rltdPjtCnt"):
                lines.append(f"  - 연관과제: {r['rltdPjtCnt']}건")
            if r.get("kywd"):
                lines.append(f"  - 관련키워드: {self._ntis_clean(r['kywd'], 150)}")
            if r.get("extrDt"):
                lines.append(f"  - 추출일자: {r['extrDt']}")
            if r.get("topicNo"):
                lines.append(f"🔗 바로가기: http://www.ntis.go.kr/issuernd/sns/{r['topicNo']}")
            lines.append("")
        header = f"**이슈로보는R&D" + (f" ('{query}')" if query else " (최신)") + f"** ({len(items)}건):\n\n"
        return header + "\n".join(lines)

    def _format_class_code_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """표준분류/중점기술 코드검색 결과 포맷팅"""
        if not items:
            return f"'{query}'에 대한 코드 검색 결과가 없습니다."
        lines = []
        for r in items:
            # NTIS001: classCd/classCdNm/upperClassCd, NTIS002: cd/cdNm/upperCd
            code = r.get("classCd") or r.get("cd") or ""
            name = r.get("classCdNm") or r.get("cdNm") or "코드명 없음"
            lines.append(f"**[{code}] {name}**")
            eng = r.get("classCdNmEng") or r.get("cdNmEng")
            if eng:
                lines.append(f"  - 영문명: {eng}")
            explain = r.get("classCdExplan") or r.get("cdExplan")
            if explain:
                lines.append(f"📝 설명: {self._ntis_clean(explain)}")
            upper = r.get("upperClassCd") or r.get("upperCd")
            if upper:
                lines.append(f"  - 상위코드: {upper}")
            lines.append("")
        return (f"**'{query}' 분류/기술 코드 검색 결과** "
                f"({len(items)}건):\n\n" + "\n".join(lines))

    def _format_commission_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """위탁/공동연구 과제 정보 결과 포맷팅"""
        if not items:
            return f"과제번호 '{query}'에 대한 위탁/공동연구 정보가 없습니다."
        lines = []
        for r in items:
            title = r.get("ProjectTitle") or r.get("ConsignmentProjectTitle") or "과제명 없음"
            lines.append(f"**{title}**")
            if r.get("ProjectNumber"):
                lines.append(f"  - 주관과제번호: {r['ProjectNumber']}")
            if r.get("CommissionNumber"):
                lines.append(f"  - 위탁과제번호: {r['CommissionNumber']}")
            if r.get("ConsignmentCollaborativeResearchType"):
                lines.append(f"  - 구분: {r['ConsignmentCollaborativeResearchType']}")
            if r.get("ConsignmentCollaborativeOrderAgency"):
                lines.append(f"🏢 위탁/공동 수행기관: {r['ConsignmentCollaborativeOrderAgency']}")
            if r.get("ConsignmentResearchManagerName"):
                lines.append(f"👤 위탁 연구책임자: {r['ConsignmentResearchManagerName']}")
            if r.get("ConsignmentProjectResearchFunds"):
                lines.append(f"💰 위탁과제 연구비: {r['ConsignmentProjectResearchFunds']}")
            lines.append("")
        return (f"**위탁/공동연구 과제 정보 (과제번호: {query})** "
                f"({len(items)}건):\n\n" + "\n".join(lines))

    def _format_participation_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """과제참여정보 결과 포맷팅"""
        if not items:
            return f"'{query}'에 대한 과제참여정보가 없습니다."
        lines = []
        for r in items:
            lines.append(f"**{r.get('KOR_PJT_NM', '과제명 없음')}**")
            if r.get("HM_NM"):
                lines.append(f"👤 연구자: {r['HM_NM']}")
            if r.get("ROLE_SLCT"):
                lines.append(f"  - 참여구분: {r['ROLE_SLCT']}")
            if r.get("ORG_NM"):
                lines.append(f"🏢 수행기관: {r['ORG_NM']}")
            if r.get("STAN_YR"):
                lines.append(f"  - 기준년도: {r['STAN_YR']}")
            if r.get("PRTCP_START_DT") or r.get("PRTCP_RT"):
                lines.append(f"  - 참여: {r.get('PRTCP_START_DT','')}~{r.get('PRTCP_END_DT','')} "
                             f"(인건비계상률 {r.get('PRTCP_RT','-')})")
            if r.get("PJT_ID"):
                lines.append(f"🔗 과제고유번호: {r['PJT_ID']}")
            lines.append("")
        return (f"**'{query}' 과제참여정보** "
                f"({len(items)}건):\n\n" + "\n".join(lines))

    def _format_researcher_info_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """출연(연) 연구자정보 결과 포맷팅"""
        if not items:
            return f"'{query}'에 대한 연구자정보가 없습니다."
        lines = []
        for r in items:
            lines.append(f"**{r.get('Nm', '이름 없음')}**")
            if r.get("BlngorNm"):
                lines.append(f"🏢 소속: {r['BlngorNm']}")
            if r.get("Keyword"):
                lines.append(f"  - 키워드: {self._ntis_clean(r['Keyword'], 150)}")
            if r.get("Rrno"):
                lines.append(f"  - 국가연구자번호: {r['Rrno']}")
            lines.append("")
        return (f"**'{query}' 출연(연) 연구자정보** "
                f"({len(items)}건):\n\n" + "\n".join(lines))

    def _format_classification_results(self, classifications: List[Dict], query: str, total_count: int, classification_type: str = "standard") -> str:
        """분류 추천 결과 포맷팅"""
        formatted_results = []
        
        for cls in classifications:
            section = cls.get("section", "")
            
            # 섹션별로 다른 처리
            if section == "MOHWD":
                # 질병분류
                disease_code = cls.get("disease_code", "")
                disease_name = cls.get("disease_name", "")
                matching_score = cls.get("matching_score", "")
                
                result_text = f"**{disease_name}** ({disease_code})"
                if matching_score:
                    result_text += f"\n  - 매칭점수: {matching_score}"
                result_text += f"\n  - 분류: 질병분류 (MOHWD)"
                
            elif section == "INDUSTRY":
                # 산업기술분류
                matching_score = cls.get("matching_score", "")
                
                # 모든 필드를 확인해서 분류명과 코드 찾기
                name_fields = [k for k in cls.keys() if k.endswith('_nm') or 'name' in k.lower()]
                code_fields = [k for k in cls.keys() if k.endswith('_cd') or 'code' in k.lower()]
                
                # 가장 구체적인 분류 우선 (소분류 > 중분류 > 대분류)
                name = ""
                code = ""
                for field in ['scls_nm', 'mcls_nm', 'lcls_nm'] + name_fields:
                    if field in cls and cls[field]:
                        name = cls[field]
                        break
                        
                for field in ['scls_cd', 'mcls_cd', 'lcls_cd'] + code_fields:
                    if field in cls and cls[field]:
                        code = cls[field]
                        break
                
                if not name and not code:
                    # 필드가 없으면 모든 값 표시
                    all_values = [f"{k}:{v}" for k, v in cls.items() if k not in ['section', 'matching_score'] and v]
                    result_text = f"**산업기술분류** ({', '.join(all_values[:3])})"
                else:
                    result_text = f"**{name or '산업기술분류'}** ({code})"
                
                if matching_score:
                    result_text += f"\n  - 매칭점수: {matching_score}"
                result_text += f"\n  - 분류: 산업기술분류 (INDUSTRY)"
                
            else:
                # 표준 분류 구조 (MOHWR, MOTIE 등)
                lcls_code = cls.get("lcls_code", "")
                lcls_name = cls.get("lcls_name", "")
                mcls_code = cls.get("mcls_code", "")
                mcls_name = cls.get("mcls_name", "")
                scls_code = cls.get("scls_code", "")
                scls_name = cls.get("scls_name", "")
                matching_score = cls.get("matching_score", "")
                
                # 메인 분류명과 코드 (소분류 우선)
                main_code = scls_code if scls_code else mcls_code if mcls_code else lcls_code
                main_name = scls_name if scls_name else mcls_name if mcls_name else lcls_name
                
                result_text = f"**{main_name}** ({main_code})"
                
                if matching_score and matching_score.strip():
                    result_text += f"\n  - 매칭점수: {matching_score}"
                
                # 계층 구조 표시
                hierarchy = []
                if lcls_name and lcls_code:
                    hierarchy.append(f"{lcls_name}({lcls_code})")
                if mcls_name and mcls_code and mcls_code != lcls_code:
                    hierarchy.append(f"{mcls_name}({mcls_code})")
                if scls_name and scls_code and scls_code != mcls_code:
                    hierarchy.append(f"{scls_name}({scls_code})")
                
                if len(hierarchy) > 1:
                    result_text += f"\n  - 분류체계: {' > '.join(hierarchy)}"
                
                # 섹션 정보 추가
                if section:
                    section_names = {
                        "MOHWR": "보건복지부",
                        "MOTIE": "산업통상자원부"
                    }
                    section_name = section_names.get(section, section)
                    result_text += f"\n  - 분류: {section_name} ({section})"
            
            formatted_results.append(result_text + "\n")
        
        # 분류 타입별 제목 설정
        classification_names = {
            "standard": "과학기술표준분류",
            "health": "보건의료기술분류",
            "industry": "산업기술분류"
        }
        classification_name = classification_names.get(classification_type, "분류")
        
        return (f"**{classification_name} 추천 결과** "
                f"(총 {total_count:,}건 추천):\n\n"
                f"입력 초록: {query[:100]}{'...' if len(query) > 100 else ''}\n\n" + 
                "\n".join(formatted_results))
    def _format_recommendation_results(self, recommendations: List[Dict], query: str, total_count: int) -> str:
        """연관콘텐츠 추천 결과 포맷팅"""
        formatted_results = []
        
        for rec in recommendations:
            title = rec.get("title", rec.get("contentTitle", "제목 없음"))
            content_type = rec.get("contentType", rec.get("type", "콘텐츠유형 없음"))
            author = rec.get("author", rec.get("researcher", ""))
            inst_name = rec.get("instName", rec.get("orgName", ""))
            relevance_score = rec.get("relevanceScore", rec.get("score", ""))
            content_url = rec.get("contentUrl", rec.get("url", ""))
            
            result_text = f"**{title}**\n  - 콘텐츠유형: {content_type}"
            
            if author and author.strip():
                result_text += f"\n  - 저자/연구자: {author}"
            
            if inst_name and inst_name.strip():
                result_text += f"\n  - 기관: {inst_name}"
            
            if relevance_score and relevance_score.strip():
                result_text += f"\n  - 연관도: {relevance_score}"
            
            if content_url and content_url.strip():
                result_text += f"\n  - 링크: {content_url}"
            
            formatted_results.append(result_text + "\n")
        
        return (f"**'{query}' 연관콘텐츠 추천 결과** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" + 
                "\n".join(formatted_results))
    def _format_related_content_results(self, contents: List[Dict], query: str, total_count: int, collection_type: str) -> str:
        """연관콘텐츠 검색 결과 포맷팅 (collection별)"""
        if not contents:
            return f"관련 콘텐츠가 없습니다."
            
        formatted_results = []
        
        # collection 타입별 기본 정보
        type_info = {
            "project": {"name": "관련 과제", "title_field": "KOR_PJT_NM", "id_field": "PJT_ID"},
            "paper": {"name": "관련 논문", "title_field": "PAPER_NM", "id_field": "RST_ID"},
            "patent": {"name": "관련 특허", "title_field": "IPR_INVENTION_NM", "id_field": "RST_ID"},
            "researchreport": {"name": "관련 연구보고서", "title_field": "KOR_RPT_TITLE_NM", "id_field": "RST_ID"}
        }
        
        info = type_info.get(collection_type, {"name": "관련 콘텐츠", "title_field": "title", "id_field": "id"})
        
        for content in contents:
            # 실제 API 응답에서 올바른 필드명 사용
            title = content.get(info["title_field"], content.get("title", "제목 없음"))
            content_id = content.get(info["id_field"], content.get("id", ""))
            
            result_text = f"* **{title}**"
            
            # ID 정보 추가
            if content_id:
                result_text += f"\n  - ID: {content_id}"
            
            # 순위 정보 추가
            rank = content.get("rank")
            if rank:
                result_text += f"\n  - 순위: {rank}"
            
            # 유사도 점수 추가
            similarity_score = content.get("similarity_score")
            if similarity_score:
                result_text += f"\n  - 유사도: {similarity_score:.3f}"
            
            # 생성일 추가
            creat_dt = content.get("creat_dt")
            if creat_dt:
                result_text += f"\n  - 생성일: {creat_dt}"
            
            formatted_results.append(result_text + "\n")
        
        return (f"## {info['name']} ({total_count:,}건)\n\n" + 
                "\n".join(formatted_results)) if formatted_results else "관련 콘텐츠가 없습니다."
    def _format_project_results(self, projects: List[Dict], query: str, total_count: int) -> str:
        """R&D 과제 검색 결과 포맷팅 - PDF 매뉴얼 기준 전체 필드 지원"""
        formatted_results = []
        
        for project in projects:
            # 기본 정보 (PDF 매뉴얼 page 8-9 기준)
            project_number = project.get("ProjectNumber", "")
            project_title = project.get("ProjectTitle", {})
            korean_title = project_title.get("Korean", "과제명 없음") if isinstance(project_title, dict) else str(project_title) if project_title else "과제명 없음"
            english_title = project_title.get("English", "") if isinstance(project_title, dict) else ""
            
            # 연구책임자 정보
            manager = project.get("Manager", {})
            manager_name = manager.get("Name", "연구책임자 없음") if isinstance(manager, dict) else str(manager) if manager else "연구책임자 없음"
            
            # 참여연구원 정보
            researchers = project.get("Researchers", {})
            if isinstance(researchers, dict):
                researcher_names = researchers.get("Name", "")
                man_count = researchers.get("ManCount", "")
                woman_count = researchers.get("WomanCount", "")
            else:
                researcher_names = ""
                man_count = ""
                woman_count = ""
            
            # 연구기관 정보
            research_agency = project.get("ResearchAgency", {})
            research_agency_name = research_agency.get("Name", "연구기관 없음") if isinstance(research_agency, dict) else str(research_agency) if research_agency else "연구기관 없음"
            
            order_agency = project.get("OrderAgency", {})
            order_agency_name = order_agency.get("Name", "") if isinstance(order_agency, dict) else ""
            
            # 예산 정보
            budget_project = project.get("BudgetProject", {})
            budget_project_name = budget_project.get("Name", "") if isinstance(budget_project, dict) else ""
            
            ministry = project.get("Ministry", {})
            ministry_name = ministry.get("Name", "") if isinstance(ministry, dict) else ""
            
            # 과제 기간 정보
            project_year = project.get("ProjectYear", "")
            project_period = project.get("ProjectPeriod", {})
            if isinstance(project_period, dict):
                start_date = project_period.get("Start", "")
                end_date = project_period.get("End", "")
                total_start = project_period.get("TotalStart", "")
                total_end = project_period.get("TotalEnd", "")
            else:
                start_date = end_date = total_start = total_end = ""
            
            # 예산 정보
            gov_funds = project.get("GovernmentFunds", "")
            total_funds = project.get("TotalFunds", "")
            
            # 연구 내용 (핵심!)
            goal = project.get("Goal", {})
            goal_full = goal.get("Full", "") if isinstance(goal, dict) else ""
            goal_teaser = goal.get("Teaser", "") if isinstance(goal, dict) else ""
            
            abstract = project.get("Abstract", {})
            abstract_full = abstract.get("Full", "") if isinstance(abstract, dict) else ""
            abstract_teaser = abstract.get("Teaser", "") if isinstance(abstract, dict) else ""
            
            effect = project.get("Effect", {})
            effect_full = effect.get("Full", "") if isinstance(effect, dict) else ""
            effect_teaser = effect.get("Teaser", "") if isinstance(effect, dict) else ""
            
            # 키워드
            keyword = project.get("Keyword", {})
            korean_keyword = keyword.get("Korean", "") if isinstance(keyword, dict) else ""
            english_keyword = keyword.get("English", "") if isinstance(keyword, dict) else ""
            
            # 결과 포맷팅
            result_text = f"**{korean_title}**"
            
            if english_title:
                result_text += f"\n  - 영문명: {english_title}"
            
            result_text += f"\n👤 연구책임자: {manager_name}"
            result_text += f"\n  - 연구기관: {research_agency_name}"
            
            if order_agency_name:
                result_text += f"\n  - 관리기관: {order_agency_name}"
            
            if project_year:
                result_text += f"\n  - 기준년도: {project_year}"
            
            if start_date and end_date:
                result_text += f"\n  - 연구기간: {start_date} ~ {end_date}"
            
            if total_start and total_end:
                result_text += f"\n  - 총 연구기간: {total_start.split()[0]} ~ {total_end.split()[0]}"
            
            if budget_project_name:
                result_text += f"\n  - 사업명: {budget_project_name}"
            
            if ministry_name:
                result_text += f"\n  - 부처: {ministry_name}"
            
            # 예산 정보 (원 단위를 억원 단위로 변환)
            if gov_funds and gov_funds.isdigit():
                gov_funds_in_100m = int(gov_funds) / 100000000
                result_text += f"\n  - 정부지원금: {gov_funds_in_100m:.1f}억원"
            
            if total_funds and total_funds.isdigit():
                total_funds_in_100m = int(total_funds) / 100000000
                result_text += f"\n  - 총 연구비: {total_funds_in_100m:.1f}억원"
            
            # 참여연구원 정보
            if man_count or woman_count:
                total_researchers = (int(man_count) if man_count.isdigit() else 0) + (int(woman_count) if woman_count.isdigit() else 0)
                if total_researchers > 0:
                    result_text += f"\n👥 참여연구원: {total_researchers}명"
                    if man_count.isdigit() and woman_count.isdigit():
                        result_text += f" (남:{man_count}, 여:{woman_count})"
            
            # 연구목표 (가장 중요!)
            if goal_teaser and goal_teaser.strip():
                clean_goal = goal_teaser.replace('<span class="search_word">', '').replace('</span>', '').replace('&lt;', '<').replace('&gt;', '>')
                if len(clean_goal) > 200:
                    clean_goal = clean_goal[:200] + "..."
                result_text += f"\n  - **연구목표**: {clean_goal}"
            elif goal_full and goal_full.strip():
                clean_goal = goal_full.replace('<span class="search_word">', '').replace('</span>', '').replace('&lt;', '<').replace('&gt;', '>')
                if len(clean_goal) > 200:
                    clean_goal = clean_goal[:200] + "..."
                result_text += f"\n  - **연구목표**: {clean_goal}"
            
            # 연구내용
            if abstract_teaser and abstract_teaser.strip():
                clean_abstract = abstract_teaser.replace('<span class="search_word">', '').replace('</span>', '').replace('&lt;', '<').replace('&gt;', '>')
                if len(clean_abstract) > 200:
                    clean_abstract = clean_abstract[:200] + "..."
                result_text += f"\n📝 **연구내용**: {clean_abstract}"
            elif abstract_full and abstract_full.strip():
                clean_abstract = abstract_full.replace('<span class="search_word">', '').replace('</span>', '').replace('&lt;', '<').replace('&gt;', '>')
                if len(clean_abstract) > 200:
                    clean_abstract = clean_abstract[:200] + "..."
                result_text += f"\n📝 **연구내용**: {clean_abstract}"
            
            # 기대효과
            if effect_teaser and effect_teaser.strip():
                clean_effect = effect_teaser.replace('<span class="search_word">', '').replace('</span>', '').replace('&lt;', '<').replace('&gt;', '>')
                if len(clean_effect) > 200:
                    clean_effect = clean_effect[:200] + "..."
                result_text += f"\n  - **기대효과**: {clean_effect}"
            elif effect_full and effect_full.strip():
                clean_effect = effect_full.replace('<span class="search_word">', '').replace('</span>', '').replace('&lt;', '<').replace('&gt;', '>')
                if len(clean_effect) > 200:
                    clean_effect = clean_effect[:200] + "..."
                result_text += f"\n  - **기대효과**: {clean_effect}"
            
            # 키워드
            if korean_keyword:
                clean_keyword = korean_keyword.replace('<span class="search_word">', '').replace('</span>', '')
                result_text += f"\n  - **한글키워드**: {clean_keyword}"
                
            if english_keyword:
                clean_eng_keyword = english_keyword.replace('<span class="search_word">', '').replace('</span>', '')
                result_text += f"\n  - **영문키워드**: {clean_eng_keyword}"
            
            if project_number:
                result_text += f"\n🔗 **과제번호**: {project_number}"
            
            formatted_results.append(result_text + "\n")
        
        return (f"**'{query}' 국가R&D 과제 검색 결과** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" + 
                "\n".join(formatted_results) +
                "\n과제 상세내용이 풍부하게 제공됩니다. 더 많은 정보는 과제번호로 NTIS 웹사이트에서 확인 가능합니다.")
    
    def _format_report_results(self, reports: List[Dict], query: str, total_count: int) -> str:
        """연구보고서 검색 결과 포맷팅"""
        formatted_results = []
        
        for report in reports:
            title = report.get("title", report.get("rptTitle", "보고서명 없음"))
            author = report.get("author", report.get("researcher", "연구자 없음"))
            inst_name = report.get("instName", report.get("orgName", "기관명 없음"))
            pub_year = report.get("pubYear", report.get("year", "연도 없음"))
            rpt_no = report.get("rptNo", report.get("reportNo", ""))
            
            result_text = f"**{title}**\n  - 연구자: {author}\n  - 연구기관: {inst_name}\n  - 발행연도: {pub_year}"
            
            if rpt_no and rpt_no.strip():
                result_text += f"\n🔗 보고서번호: {rpt_no}"
            
            formatted_results.append(result_text + "\n")
        
        return (f"**'{query}' NTIS 연구보고서 검색 결과** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" + 
                "\n".join(formatted_results))
    
    def _format_performance_results(self, performances: List[Dict], query: str, total_count: int) -> str:
        """연구성과 검색 결과 포맷팅"""
        formatted_results = []
        
        for perf in performances:
            title = perf.get("title", perf.get("perfTitle", "성과명 없음"))
            perf_type = perf.get("perfType", perf.get("type", "성과유형 없음"))
            inst_name = perf.get("instName", perf.get("orgName", "기관명 없음"))
            reg_date = perf.get("regDate", perf.get("date", "등록일 없음"))
            perf_no = perf.get("perfNo", perf.get("performanceNo", ""))
            
            # 성과 유형에 따른 이모지
            type_emoji = {
                "논문": "📄",
                "특허": "🏛️", 
                "기술이전": "🔄",
                "사업화": "💼"
            }.get(perf_type, "📋")
            
            result_text = f"{type_emoji} **{title}**\n📊 성과유형: {perf_type}\n  - 기관: {inst_name}\n📅 등록일: {reg_date}"
            
            if perf_no and perf_no.strip():
                result_text += f"\n🔗 성과번호: {perf_no}"
            
            formatted_results.append(result_text + "\n")
        
        return (f"**'{query}' NTIS 연구성과 검색 결과** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" + 
                "\n".join(formatted_results))
    
    def format_detail_result(self, result: Dict, identifier: str, result_type: str = "project") -> str:
        """NTIS 상세 결과 포맷팅"""
        if result_type == "project":
            return self._format_project_detail(result, identifier)
        elif result_type == "report":
            return self._format_report_detail(result, identifier)
        elif result_type == "performance":
            return self._format_performance_detail(result, identifier)
        else:
            return f"지원되지 않는 결과 타입: {result_type}"
    
    def _format_project_detail(self, project: Dict, pjt_no: str) -> str:
        """R&D 과제 상세 결과 포맷팅"""
        pjt_name = project.get("pjtName", "과제명 없음")
        inst_name = project.get("instName", "기관명 없음")
        research_manager = project.get("researchManager", project.get("manager", ""))
        pjt_period = project.get("pjtPeriod", "과제기간 없음")
        research_area = project.get("researchArea", "연구분야 없음")
        total_expense = project.get("totalExpense", "")
        govt_expense = project.get("govtExpense", "")
        abstract = project.get("abstract", project.get("summary", ""))
        keyword = project.get("keyword", "")
        
        result_text = f"**R&D 과제 상세정보 (과제번호: {pjt_no})**\n\n"
        result_text += f"**과제명**: {pjt_name}\n"
        result_text += f"🏢 **수행기관**: {inst_name}\n"
        result_text += f"📅 **과제기간**: {pjt_period}\n"
        result_text += f"**연구분야**: {research_area}\n"
        
        if research_manager and research_manager.strip():
            result_text += f"👤 **연구책임자**: {research_manager}\n"
        
        if total_expense and total_expense.strip():
            result_text += f"💰 **총 연구비**: {total_expense}\n"
        
        if govt_expense and govt_expense.strip():
            result_text += f"💵 **정부지원금**: {govt_expense}\n"
        
        if keyword and keyword.strip():
            result_text += f"  - **키워드**: {keyword}\n"
        
        if abstract and len(abstract.strip()) > 0:
            clean_abstract = abstract.strip()
            if len(clean_abstract) > 500:
                clean_abstract = clean_abstract[:500] + "..."
            result_text += f"\n📝 **과제요약**:\n{clean_abstract}\n"
        
        return result_text
    
    def _format_report_detail(self, report: Dict, rpt_no: str) -> str:
        """연구보고서 상세 결과 포맷팅"""
        title = report.get("title", "보고서명 없음")
        author = report.get("author", "연구자 없음")
        inst_name = report.get("instName", "기관명 없음")
        pub_year = report.get("pubYear", "연도 없음")
        abstract = report.get("abstract", "")
        keyword = report.get("keyword", "")
        
        result_text = f"**연구보고서 상세정보 (보고서번호: {rpt_no})**\n\n"
        result_text += f"**보고서명**: {title}\n"
        result_text += f"👤 **연구자**: {author}\n"
        result_text += f"🏢 **연구기관**: {inst_name}\n"
        result_text += f"📅 **발행연도**: {pub_year}\n"
        
        if keyword and keyword.strip():
            result_text += f"  - **키워드**: {keyword}\n"
        
        if abstract and len(abstract.strip()) > 0:
            clean_abstract = abstract.strip()
            if len(clean_abstract) > 500:
                clean_abstract = clean_abstract[:500] + "..."
            result_text += f"\n📝 **요약**:\n{clean_abstract}\n"
        
        return result_text
    
    def _format_performance_detail(self, performance: Dict, perf_no: str) -> str:
        """연구성과 상세 결과 포맷팅"""
        title = performance.get("title", "성과명 없음")
        perf_type = performance.get("perfType", "성과유형 없음")
        inst_name = performance.get("instName", "기관명 없음")
        reg_date = performance.get("regDate", "등록일 없음")
        abstract = performance.get("abstract", "")
        
        type_emoji = {
            "논문": "📄",
            "특허": "🏛️", 
            "기술이전": "🔄",
            "사업화": "💼"
        }.get(perf_type, "📋")
        
        result_text = f"**연구성과 상세정보 (성과번호: {perf_no})**\n\n"
        result_text += f"{type_emoji} **성과명**: {title}\n"
        result_text += f"**성과유형**: {perf_type}\n"
        result_text += f"🏢 **기관**: {inst_name}\n"
        result_text += f"📅 **등록일**: {reg_date}\n"
        
        if abstract and len(abstract.strip()) > 0:
            clean_abstract = abstract.strip()
            if len(clean_abstract) > 500:
                clean_abstract = clean_abstract[:500] + "..."
            result_text += f"\n📝 **상세정보**:\n{clean_abstract}\n"
        
        return result_text
class ScienceONFormatter(BaseResultFormatter):
    """ScienceON 결과 포맷터"""

    # 긴 텍스트(초록·본문·정의·내용) 포함 여부. format_* 진입 시 세팅된다.
    _include_body = True

    def _body(self, text: str) -> str:
        """긴 본문 텍스트 정리. _include_body=False 이면 빈 문자열(제외).

        전문 그대로(max_len=0) 반환하되, 제외 모드에서는 아무것도 내보내지 않는다.
        """
        if not self._include_body:
            return ""
        return clean_text(text, 0)

    def format_search_results(self, results: List[Dict], query: str, total_count: int, result_type: str, include_body: bool = True) -> str:
        """검색 결과 포맷팅

        include_body=False 이면 초록·본문·정의·내용 등 긴 텍스트를 제외하고
        서지정보·DOI·링크만 반환한다 (로컬 소형 모델/목록 훑기용).
        """
        self._include_body = include_body
        if result_type == "paper":
            return self._format_paper_results(results, query, total_count)
        elif result_type == "patent":
            return self._format_patent_results(results, query, total_count)
        elif result_type == "report":
            return self._format_report_results(results, query, total_count)
        elif result_type == "news_trend":
            return self._format_news_trend_results(results, query, total_count)
        elif result_type == "scent":
            return self._format_scent_results(results, query, total_count)
        elif result_type == "researcher":
            return self._format_researcher_results(results, query, total_count)
        elif result_type == "organization":
            return self._format_organization_results(results, query, total_count)
        elif result_type == "tech_trend":
            return self._format_tech_trend_results(results, query, total_count)
        elif result_type == "weekly_news":
            return self._format_weekly_news_results(results, query, total_count)
        else:
            return f"지원되지 않는 결과 타입: {result_type}"
    
    def _format_paper_results(self, papers: List[Dict], query: str, total_count: int) -> str:
        """논문 검색 결과 포맷팅"""
        formatted_results = []
        for paper in papers:
            title = paper.get("Title", paper.get("TI", "제목 없음"))
            author = paper.get("Author", paper.get("AU", "저자 없음"))
            year = paper.get("Pubyear", paper.get("PY", "연도 없음"))
            journal = paper.get("JournalName", paper.get("SO", "저널 없음"))
            abstract = paper.get("Abstract", paper.get("AB", ""))
            cn = paper.get("CN", "")
            doi = paper.get("DOI", "")
            keyword = paper.get("Keyword", "")
            affiliation = paper.get("Affiliation", "")
            publisher = paper.get("Publisher", "")
            page_info = paper.get("PageInfo", "")
            issn = paper.get("ISSN", "")
            db_code = paper.get("DBCode", "")
            degree = paper.get("Degree", "")
            fulltext_url = paper.get("FulltextURL", "")
            content_url = paper.get("ContentURL", "")

            result_text = f"**{title}**\n  - 저자: {author}\n  - 연도: {year}"

            if affiliation and affiliation.strip():
                result_text += f"\n🏢 소속: {affiliation}"
            if journal and journal.strip():
                result_text += f"\n📖 저널: {journal}"
            if publisher and publisher.strip():
                result_text += f"\n  - 발행기관: {publisher}"
            if page_info and page_info.strip():
                result_text += f"\n  - 페이지: {page_info}"
            if issn and issn.strip():
                result_text += f"\n  - ISSN: {issn}"
            if db_code and db_code.strip():
                result_text += f"\n  - DB구분: {db_code}"
            if degree and degree.strip():
                result_text += f"\n  - 학위구분: {degree}"
            if cn and cn.strip():
                result_text += f"\n🔗 논문번호(CN): {cn}"
            if doi and doi.strip():
                result_text += f"\n🔗 DOI: {doi}"
            if keyword and keyword.strip():
                result_text += f"\n  - 키워드: {self._clean(keyword, 0)}"

            # 초록 처리 (전문, include_body=False면 제외)
            clean_abstract = self._body(abstract)
            if clean_abstract:
                result_text += f"\n📝 초록: {clean_abstract}"

            # URL
            if fulltext_url and fulltext_url.strip():
                result_text += f"\n📄 원문 URL: {fulltext_url}"
            if content_url and content_url.strip():
                result_text += f"\n🔗 ScienceON 링크: {content_url}"

            formatted_results.append(result_text + "\n")
        
        return (f"**'{query}' 논문 검색 결과** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" + 
                "\n".join(formatted_results) +
                "\n💡 특정 논문의 상세정보를 원하면 CN번호를 이용해 논문상세보기를 사용하세요.")
    
    def _format_patent_results(self, patents: List[Dict], query: str, total_count: int) -> str:
        """특허 검색 결과 포맷팅"""
        formatted_results = []
        for patent in patents:
            title = patent.get("Title", "특허제목 없음")
            applicants = patent.get("Applicants", "출원인 없음")
            appl_date = patent.get("ApplDate", "출원일 없음")
            publ_date = patent.get("PublDate", "공개일 없음")
            abstract = patent.get("Abstract", "")
            patent_status = patent.get("PatentStatus", "")
            ipc = patent.get("IPC", "")
            cn = patent.get("CN", "")
            appl_num = patent.get("ApplNum", "")
            publ_num = patent.get("PublNum", "")
            grant_date = patent.get("GrantDate", "")
            grant_num = patent.get("GrantNum", "")
            notice_date = patent.get("NoticeDate", "")
            nation = patent.get("Nation", "")
            content_url = patent.get("ContentURL", "")

            result_text = f"**{title}**\n  - 출원인: {applicants}\n  - 출원일: {appl_date}"

            if appl_num and appl_num.strip():
                result_text += f"\n  - 출원번호: {appl_num}"
            if publ_date and publ_date.strip():
                result_text += f"\n📰 공개일: {publ_date}"
            if publ_num and publ_num.strip():
                result_text += f"\n  - 공개번호: {publ_num}"
            if grant_date and grant_date.strip():
                result_text += f"\n  - 등록일: {grant_date}"
            if grant_num and grant_num.strip():
                result_text += f"\n  - 등록번호: {grant_num}"
            if notice_date and notice_date.strip():
                result_text += f"\n  - 공고일: {notice_date}"
            if patent_status and patent_status.strip():
                result_text += f"\n  - 특허상태: {patent_status}"
            if ipc and ipc.strip():
                result_text += f"\n  - IPC분류: {ipc}"
            if nation and nation.strip():
                result_text += f"\n  - 국가: {nation}"
            if cn and cn.strip():
                result_text += f"\n🔗 특허번호(CN): {cn}"

            # 초록 처리 (전문, include_body=False면 제외)
            clean_abstract = self._body(abstract)
            if clean_abstract:
                result_text += f"\n📝 초록: {clean_abstract}"

            if content_url and content_url.strip():
                result_text += f"\n🔗 ScienceON 링크: {content_url}"

            formatted_results.append(result_text + "\n")
        
        return (f"**'{query}' 특허 검색 결과** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" +
                "\n".join(formatted_results) +
                "\n💡 특정 특허의 상세정보를 원하면 CN번호를 이용해 특허상세보기를 사용하세요.")
    
    def _format_report_results(self, reports: List[Dict], query: str, total_count: int) -> str:
        """보고서 검색 결과 포맷팅"""
        formatted_results = []
        for report in reports:
            title = report.get("Title", "보고서제목 없음")
            author = report.get("Author", "저자 없음")
            pubyear = report.get("Pubyear", "발행연도 없음")
            publisher = report.get("Publisher", "발행기관 없음")
            abstract = report.get("Abstract", "")
            cn = report.get("CN", "")
            keyword = report.get("Keyword", "")
            page_info = report.get("PageInfo", "")
            managing_agency = report.get("ManagingAgency", "")
            contributors = report.get("Contributors", "")
            co_research_org = report.get("CoResearchOrg", "")
            collaborating_org = report.get("CollaboratingOrg", "")
            research_mng_agency = report.get("ResearchMngAgency", "")
            stc_major_code = report.get("STCMajorCode", "")
            fulltext_url = report.get("FulltextURL", "")
            content_url = report.get("ContentURL", "")

            result_text = f"**{title}**\n  - 저자: {author}\n  - 발행연도: {pubyear}"

            if publisher and publisher.strip():
                result_text += f"\n🏢 발행기관: {publisher}"
            if managing_agency and managing_agency.strip():
                result_text += f"\n  - 주관기관: {managing_agency}"
            if research_mng_agency and research_mng_agency.strip():
                result_text += f"\n  - 연구관리기관: {research_mng_agency}"
            if co_research_org and co_research_org.strip():
                result_text += f"\n  - 공동연구기관: {co_research_org}"
            if collaborating_org and collaborating_org.strip():
                result_text += f"\n  - 협력기관: {collaborating_org}"
            if contributors and contributors.strip():
                result_text += f"\n  - 기여자: {contributors}"
            if page_info and page_info.strip():
                result_text += f"\n  - 페이지: {page_info}"
            if stc_major_code and stc_major_code.strip():
                result_text += f"\n  - 과학기술표준분류: {stc_major_code}"
            if cn and cn.strip():
                result_text += f"\n🔗 보고서번호(CN): {cn}"
            if keyword and keyword.strip():
                result_text += f"\n  - 키워드: {self._clean(keyword, 0)}"

            # 초록 처리 (전문, include_body=False면 제외)
            clean_abstract = self._body(abstract)
            if clean_abstract:
                result_text += f"\n📝 초록: {clean_abstract}"

            if fulltext_url and fulltext_url.strip():
                result_text += f"\n📄 원문 URL: {fulltext_url}"
            if content_url and content_url.strip():
                result_text += f"\n🔗 ScienceON 링크: {content_url}"

            formatted_results.append(result_text + "\n")
        
        return (f"**'{query}' 보고서 검색 결과** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" + 
                "\n".join(formatted_results) +
                "\n💡 특정 보고서의 상세정보를 원하면 CN번호를 이용해 보고서상세보기를 사용하세요.")
    
    def format_detail_result(self, item: Dict, identifier: str, result_type: str = "paper", include_body: bool = True) -> str:
        """상세 결과 포맷팅

        include_body=False 이면 초록·본문 등 긴 텍스트를 제외한다.
        """
        self._include_body = include_body
        if result_type == "paper":
            return self._format_paper_detail(item, identifier)
        elif result_type == "patent":
            return self._format_patent_detail(item, identifier)
        elif result_type == "report":
            return self._format_report_detail(item, identifier)
        elif result_type == "news_trend":
            return self._format_news_trend_detail(item, identifier)
        elif result_type == "scent":
            return self._format_scent_detail(item, identifier)
        elif result_type == "researcher":
            return self._format_researcher_detail(item, identifier)
        elif result_type == "organization":
            return self._format_organization_detail(item, identifier)
        else:
            return f"지원되지 않는 결과 타입: {result_type}"
    
    def _format_paper_detail(self, paper: Dict, cn: str) -> str:
        """논문 상세 결과 포맷팅"""
        # 기본 정보
        title = paper.get("Title", "제목 없음")
        author = paper.get("Author", "저자 없음")
        year = paper.get("Pubyear", "연도 없음")
        journal = paper.get("JournalName", "저널 없음")
        abstract = paper.get("Abstract", "")

        # 상세 정보
        doi = paper.get("DOI", "")
        keywords = paper.get("Keyword", "")
        page_info = paper.get("PageInfo", "")
        issn = paper.get("ISSN", "")
        db_code = paper.get("DBCode", "")
        degree = paper.get("Degree", "")
        publisher = paper.get("Publisher", "")
        affiliation = paper.get("Affiliation", "")
        fulltext_url = paper.get("FulltextURL", "")
        content_url = paper.get("ContentURL", "")

        result_text = f"**논문 상세정보 (CN: {cn})**\n\n"
        result_text += f"**제목**: {title}\n"
        result_text += f"👤 **저자**: {author}\n"
        if affiliation and affiliation.strip():
            result_text += f"🏢 **소속**: {affiliation}\n"
        result_text += f"📅 **연도**: {year}\n"
        result_text += f"📖 **저널**: {journal}\n"
        if publisher and publisher.strip():
            result_text += f"  - **발행기관**: {publisher}\n"
        if page_info and page_info.strip():
            result_text += f"  - **페이지**: {page_info}\n"
        if issn and issn.strip():
            result_text += f"  - **ISSN**: {issn}\n"
        if db_code and db_code.strip():
            result_text += f"  - **DB구분**: {db_code}\n"
        if degree and degree.strip():
            result_text += f"  - **학위구분**: {degree}\n"
        result_text += f"🔗 **ScienceON 링크**: https://scienceon.kisti.re.kr/srch/selectPORSrchArticle.do?cn={cn}\n"

        if doi and doi.strip():
            result_text += f"🔗 **DOI**: {doi}\n"

        if keywords and keywords.strip():
            result_text += f"  - **키워드**: {self._clean(keywords, 0)}\n"

        # 초록 (include_body=False면 제외)
        clean_abstract = self._body(abstract)
        if clean_abstract:
            result_text += f"\n📝 **초록**:\n{clean_abstract}\n"

        # URL 정보
        if fulltext_url and fulltext_url.strip():
            result_text += f"\n📄 **원문 URL**: {fulltext_url}\n"
        if content_url and content_url.strip():
            result_text += f"🔗 **콘텐츠 URL**: {content_url}\n"

        return result_text
    
    def _format_patent_detail(self, patent: Dict, cn: str) -> str:
        """특허 상세 결과 포맷팅"""
        # 기본 정보
        title = patent.get("Title", "특허제목 없음")
        applicants = patent.get("Applicants", "출원인 없음")
        appl_date = patent.get("ApplDate", "출원일 없음")
        publ_date = patent.get("PublDate", "공개일 없음")
        abstract = patent.get("Abstract", "")

        # 상세 정보
        patent_status = patent.get("PatentStatus", "")
        ipc = patent.get("IPC", "")
        nation = patent.get("Nation", "")
        content_url = patent.get("ContentURL", "")
        appl_num = patent.get("ApplNum", "")
        publ_num = patent.get("PublNum", "")
        grant_date = patent.get("GrantDate", "")
        grant_num = patent.get("GrantNum", "")
        notice_date = patent.get("NoticeDate", "")

        result_text = f"**특허 상세정보 (CN: {cn})**\n\n"
        result_text += f"**특허제목**: {title}\n"
        result_text += f"👥 **출원인**: {applicants}\n"
        result_text += f"📅 **출원일**: {appl_date}\n"
        if appl_num and appl_num.strip():
            result_text += f"  - **출원번호**: {appl_num}\n"
        result_text += f"📰 **공개일**: {publ_date}\n"
        if publ_num and publ_num.strip():
            result_text += f"  - **공개번호**: {publ_num}\n"
        if grant_date and grant_date.strip():
            result_text += f"  - **등록일**: {grant_date}\n"
        if grant_num and grant_num.strip():
            result_text += f"  - **등록번호**: {grant_num}\n"
        if notice_date and notice_date.strip():
            result_text += f"  - **공고일**: {notice_date}\n"
        result_text += f"🔗 **ScienceON 링크**: https://scienceon.kisti.re.kr/srch/selectPORSrchPatent.do?cn={cn}\n"

        if patent_status and patent_status.strip():
            result_text += f"**특허상태**: {patent_status}\n"
        if ipc and ipc.strip():
            result_text += f"🏷️ **IPC분류**: {ipc}\n"
        if nation and nation.strip():
            result_text += f"  - **국가**: {nation}\n"

        # 초록 (include_body=False면 제외)
        clean_abstract = self._body(abstract)
        if clean_abstract:
            result_text += f"\n📝 **초록**:\n{clean_abstract}\n"

        if content_url and content_url.strip():
            result_text += f"\n🔗 **콘텐츠 URL**: {content_url}\n"

        result_text += "\n💡 이 특허의 인용/피인용 특허는 특허인용정보조회(CN)로 확인할 수 있습니다.\n"

        return result_text
    
    def _format_report_detail(self, report: Dict, cn: str) -> str:
        """보고서 상세 결과 포맷팅"""
        # 기본 정보
        title = report.get("Title", "보고서제목 없음")
        author = report.get("Author", "저자 없음")
        pubyear = report.get("Pubyear", "발행연도 없음")
        publisher = report.get("Publisher", "발행기관 없음")
        abstract = report.get("Abstract", "")
        
        # 상세 정보
        keywords = report.get("Keyword", "")
        fulltext_url = report.get("FulltextURL", "")
        content_url = report.get("ContentURL", "")
        page_info = report.get("PageInfo", "")
        managing_agency = report.get("ManagingAgency", "")
        co_research_org = report.get("CoResearchOrg", "")
        collaborating_org = report.get("CollaboratingOrg", "")
        research_mng_agency = report.get("ResearchMngAgency", "")
        contributors = report.get("Contributors", "")
        stc_major_code = report.get("STCMajorCode", "")

        result_text = f"**보고서 상세정보 (CN: {cn})**\n\n"
        result_text += f"**제목**: {title}\n"
        result_text += f"👤 **저자**: {author}\n"
        result_text += f"📅 **발행연도**: {pubyear}\n"
        if publisher and publisher.strip() and publisher != "발행기관 없음":
            result_text += f"🏢 **발행기관**: {publisher}\n"
        if managing_agency and managing_agency.strip():
            result_text += f"  - **주관기관**: {managing_agency}\n"
        if research_mng_agency and research_mng_agency.strip():
            result_text += f"  - **연구관리기관**: {research_mng_agency}\n"
        if co_research_org and co_research_org.strip():
            result_text += f"  - **공동연구기관**: {co_research_org}\n"
        if collaborating_org and collaborating_org.strip():
            result_text += f"  - **협력기관**: {collaborating_org}\n"
        if contributors and contributors.strip():
            result_text += f"  - **기여자**: {contributors}\n"
        if page_info and page_info.strip():
            result_text += f"  - **페이지**: {page_info}\n"
        if stc_major_code and stc_major_code.strip():
            result_text += f"  - **과학기술표준분류**: {stc_major_code}\n"
        result_text += f"🔗 **ScienceON 링크**: https://scienceon.kisti.re.kr/srch/selectPORSrchReport.do?cn={cn}\n"

        if keywords and keywords.strip():
            result_text += f"  - **키워드**: {self._clean(keywords, 0)}\n"

        # 초록 (include_body=False면 제외)
        clean_abstract = self._body(abstract)
        if clean_abstract:
            result_text += f"\n📝 **초록**:\n{clean_abstract}\n"

        # URL 정보
        if fulltext_url and fulltext_url.strip():
            result_text += f"\n📄 **원문 URL**: {fulltext_url}\n"
        if content_url and content_url.strip():
            result_text += f"🔗 **콘텐츠 URL**: {content_url}\n"

        return result_text
    
    def format_citation_result(self, citations: List[Dict], cn: str) -> str:
        """인용/피인용 결과 포맷팅"""
        if not citations:
            return f"CN번호 '{cn}'에 대한 인용/피인용 정보가 없습니다."
        
        result_text = f"**특허 인용/피인용 정보 (CN: {cn})**\n\n"
        
        formatted_citations = []
        for i, citation in enumerate(citations[:10]):  # 최대 10개까지 표시
            title = citation.get("Title", "특허제목 없음")
            applicants = citation.get("Applicants", "출원인 없음")
            appl_date = citation.get("ApplDate", "출원일 없음")
            patent_status = citation.get("PatentStatus", "")
            citation_type = citation.get("Citation", "")   # 인용특허/피인용특허 구분
            ipc = citation.get("IPC", "")
            nation_code = citation.get("NationCode", "")
            inventor = citation.get("Inventor", "")
            c_cn = citation.get("CN", "")

            header = f"**{title}**"
            if citation_type and citation_type.strip():
                header += f"  [{citation_type}]"
            citation_text = f"{header}\n  - 출원인: {applicants}\n  - 출원일: {appl_date}"

            if inventor and inventor.strip():
                citation_text += f"\n  - 발명자: {inventor}"
            if patent_status and patent_status.strip():
                citation_text += f"\n  - 특허상태: {patent_status}"
            if ipc and ipc.strip():
                citation_text += f"\n  - IPC분류: {ipc}"
            if nation_code and nation_code.strip():
                citation_text += f"\n  - 국가: {nation_code}"
            if c_cn and c_cn.strip():
                citation_text += f"\n  - CN: {c_cn}"

            formatted_citations.append(citation_text + "\n")

        result_text += "\n".join(formatted_citations)

        if len(citations) > 10:
            result_text += f"\n총 {len(citations)}건 중 10건만 표시되었습니다."

        return result_text

    def _clean(self, text: str, max_len: int = 300) -> str:
        return clean_text(text, max_len)

    # ── 동향(ATT) ──────────────────────────────────────────
    def _format_news_trend_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """과학기술 동향 검색 결과 포맷팅"""
        formatted_results = []
        for r in items:
            title = r.get("Title", "제목 없음")
            year = r.get("Pubyear", "")
            cn = r.get("CN", "")
            author = r.get("Author", "")
            subject = r.get("Subject", "")
            keyword = r.get("Keyword", "")
            reg_date = r.get("RegDate", "")
            publisher = r.get("Publisher", "")
            db_code = r.get("DBCode", "")
            fulltext_url = r.get("FulltextURL", "")
            content_url = r.get("ContentURL", "")
            abstract = self._body(r.get("Abstract", ""))

            result_text = f"**{title}**"
            if author and author.strip():
                result_text += f"\n  - 저자: {author}"
            if publisher and publisher.strip():
                result_text += f"\n🏢 발행기관: {publisher}"
            if year and year.strip():
                result_text += f"\n  - 발행년: {year}"
            if reg_date and reg_date.strip():
                result_text += f"\n  - 등록일: {reg_date}"
            if subject and subject.strip():
                result_text += f"\n  - 주제: {subject}"
            if db_code and db_code.strip():
                result_text += f"\n  - DB구분: {db_code}"
            if keyword and keyword.strip():
                result_text += f"\n  - 키워드: {self._clean(keyword, 0)}"
            if cn and cn.strip():
                result_text += f"\n🔗 동향번호(CN): {cn}"
            if abstract:
                result_text += f"\n📝 내용: {abstract}"
            if fulltext_url and fulltext_url.strip():
                result_text += f"\n📄 원문 URL: {fulltext_url}"
            if content_url and content_url.strip():
                result_text += f"\n🔗 ScienceON 링크: {content_url}"
            formatted_results.append(result_text + "\n")

        return (f"**'{query}' 과학기술 동향 검색 결과** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" +
                "\n".join(formatted_results) +
                "\n💡 상세정보는 CN번호로 동향상세보기를 사용하세요.")

    def _format_news_trend_detail(self, r: Dict, cn: str) -> str:
        """과학기술 동향 상세 포맷팅"""
        result_text = f"**동향 기사 상세정보 (CN: {cn})**\n\n"
        result_text += f"**제목**: {r.get('Title', '')}\n"
        if r.get("Author"):
            result_text += f"👤 **저자**: {r['Author']}\n"
        if r.get("Pubyear"):
            result_text += f"📅 **발행년**: {r['Pubyear']}\n"
        if r.get("RegDate"):
            result_text += f"  - **등록일**: {r['RegDate']}\n"
        if r.get("Publisher"):
            result_text += f"🏢 **발행기관**: {r['Publisher']}\n"
        if r.get("Subject"):
            result_text += f"  - **주제**: {r['Subject']}\n"
        if r.get("DBCode"):
            result_text += f"  - **DB**: {r['DBCode']}\n"
        if r.get("Keyword"):
            result_text += f"  - **키워드**: {self._clean(r['Keyword'], 0)}\n"
        abstract = self._body(r.get("Abstract", ""))
        if abstract:
            result_text += f"\n📝 **내용**:\n{abstract}\n"
        if r.get("FulltextURL"):
            result_text += f"\n📄 **원문 URL**: {r['FulltextURL']}\n"
        if r.get("ContentURL"):
            result_text += f"🔗 **ScienceON 링크**: {r['ContentURL']}\n"
        return result_text

    # ── 과학향기(SCENT) ────────────────────────────────────
    def _format_scent_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """과학향기 칼럼 검색 결과 포맷팅"""
        formatted_results = []
        for r in items:
            title = r.get("ScentTitle", "제목 없음")
            volume = r.get("Volume", "")
            cn = r.get("CN", "")
            class_name = r.get("Class", "")
            subclass = r.get("Subclass", "")
            register_date = r.get("RegisterDate", "")
            content_url = r.get("ContentURL", "")
            content = self._body(r.get("Content", ""))

            result_text = f"**{title}**"
            if volume and volume.strip():
                result_text += f"\n  - 권호: {volume}"
            if class_name and class_name.strip():
                result_text += f"\n  - 분류: {class_name}"
            if subclass and subclass.strip():
                result_text += f"\n  - 세부분류: {subclass}"
            if register_date and register_date.strip():
                result_text += f"\n  - 등록일: {register_date}"
            if cn and cn.strip():
                result_text += f"\n🔗 과학향기번호(CN): {cn}"
            if content:
                result_text += f"\n📝 본문: {content}"
            if content_url and content_url.strip():
                result_text += f"\n🔗 ScienceON 링크: {content_url}"
            formatted_results.append(result_text + "\n")

        return (f"**'{query}'년 과학향기 칼럼 목록** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" +
                "\n".join(formatted_results) +
                "\n💡 본문은 CN번호로 과학향기상세보기를 사용하세요.")

    def _format_scent_detail(self, r: Dict, cn: str) -> str:
        """과학향기 칼럼 본문 포맷팅"""
        result_text = f"**과학향기 칼럼 (CN: {cn})**\n\n"
        result_text += f"**제목**: {r.get('ScentTitle', '')}\n"
        if r.get("Volume"):
            result_text += f"  - **권호**: {r['Volume']}\n"
        if r.get("Class"):
            result_text += f"  - **분류**: {r['Class']}\n"
        if r.get("Subclass"):
            result_text += f"  - **세부분류**: {r['Subclass']}\n"
        if r.get("RegisterDate"):
            result_text += f"  - **등록일**: {r['RegisterDate']}\n"
        content = self._body(r.get("Content", ""))
        if content:
            result_text += f"\n📝 **본문**:\n{content}\n"
        if r.get("ContentURL"):
            result_text += f"\n🔗 **ScienceON 링크**: {r['ContentURL']}\n"
        return result_text

    # ── 연구자(RESEARCHER) ─────────────────────────────────
    def _format_researcher_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """연구자 검색 결과 포맷팅"""
        formatted_results = []
        for r in items:
            name_kor = r.get("AuthorNameKor", "")
            name_eng = r.get("AuthorNameEng", "")
            inst_kor = r.get("AuthorInstKor", "")
            inst_eng = r.get("AuthorInstEng", "")
            email = r.get("Email", "")
            keyword = r.get("Keyword", "")
            art_cnt = r.get("ArticleCnt", "0")
            pat_cnt = r.get("PatentCnt", "0")
            rpt_cnt = r.get("ReportCnt", "0")
            cn = r.get("CN", "")

            name = name_kor or name_eng or "이름 없음"
            result_text = f"**{name}**"
            if name_eng and name_kor:
                result_text += f"\n  - 영문명: {name_eng}"
            if inst_kor and inst_kor.strip():
                result_text += f"\n🏢 소속: {inst_kor}"
            if inst_eng and inst_eng.strip():
                result_text += f"\n  - 소속(영문): {inst_eng}"
            if email and email.strip():
                result_text += f"\n  - 이메일: {email}"
            if keyword and keyword.strip():
                result_text += f"\n  - 키워드: {self._clean(keyword, 0)}"
            result_text += f"\n  - 실적: 논문 {art_cnt}건 / 특허 {pat_cnt}건 / 보고서 {rpt_cnt}건"
            if cn and cn.strip():
                result_text += f"\n🔗 연구자번호(CN): {cn}"
            formatted_results.append(result_text + "\n")

        return (f"**'{query}' 연구자 검색 결과** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" +
                "\n".join(formatted_results) +
                "\n💡 상세정보는 CN번호로 연구자상세보기를 사용하세요.")

    def _format_researcher_detail(self, r: Dict, cn: str) -> str:
        """연구자 상세 포맷팅"""
        result_text = f"**연구자 상세정보 (CN: {cn})**\n\n"
        if r.get("AuthorNameKor"):
            result_text += f"**이름(국문)**: {r['AuthorNameKor']}\n"
        if r.get("AuthorNameEng"):
            result_text += f"**이름(영문)**: {r['AuthorNameEng']}\n"
        if r.get("AuthorInstKor"):
            result_text += f"🏢 **소속(국문)**: {r['AuthorInstKor']}\n"
        if r.get("AuthorInstEng"):
            result_text += f"  - **소속(영문)**: {r['AuthorInstEng']}\n"
        if r.get("Email"):
            result_text += f"  - **이메일**: {r['Email']}\n"
        if r.get("Keyword"):
            result_text += f"  - **키워드**: {r['Keyword']}\n"
        result_text += (f"📊 **실적**: 논문 {r.get('ArticleCnt', '0')}건 / "
                        f"특허 {r.get('PatentCnt', '0')}건 / "
                        f"보고서 {r.get('ReportCnt', '0')}건\n")
        return result_text

    # ── 연구기관(ORGAN) ────────────────────────────────────
    def _format_organization_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """연구기관 검색 결과 포맷팅"""
        formatted_results = []
        for r in items:
            name_kor = r.get("OrganKor", "")
            name_eng = r.get("OrganEng", "")
            keyword = r.get("Keyword", "")
            art_cnt = r.get("ArticleCnt", "0")
            pat_cnt = r.get("PatentCnt", "0")
            rpt_cnt = r.get("ReportCnt", "0")
            cn = r.get("CN", "")

            name = name_kor or name_eng or "기관명 없음"
            result_text = f"**{name}**"
            if name_eng and name_kor:
                result_text += f"\n  - 영문명: {name_eng}"
            if keyword and keyword.strip():
                result_text += f"\n  - 키워드: {self._clean(keyword, 0)}"
            result_text += f"\n  - 실적: 논문 {art_cnt}건 / 특허 {pat_cnt}건 / 보고서 {rpt_cnt}건"
            if cn and cn.strip():
                result_text += f"\n🔗 기관번호(CN): {cn}"
            formatted_results.append(result_text + "\n")

        return (f"**'{query}' 연구기관 검색 결과** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" +
                "\n".join(formatted_results) +
                "\n💡 상세정보는 CN번호로 연구기관상세보기를 사용하세요.")

    def _format_organization_detail(self, r: Dict, cn: str) -> str:
        """연구기관 상세 포맷팅"""
        result_text = f"**연구기관 상세정보 (CN: {cn})**\n\n"
        if r.get("OrganKor"):
            result_text += f"**기관명(국문)**: {r['OrganKor']}\n"
        if r.get("OrganEng"):
            result_text += f"**기관명(영문)**: {r['OrganEng']}\n"
        if r.get("Keyword"):
            result_text += f"  - **키워드**: {self._clean(r['Keyword'], 0)}\n"
        result_text += (f"📊 **실적**: 논문 {r.get('ArticleCnt', '0')}건 / "
                        f"특허 {r.get('PatentCnt', '0')}건 / "
                        f"보고서 {r.get('ReportCnt', '0')}건\n")
        return result_text

    # ── 기술트렌드(TREND) ──────────────────────────────────
    def _format_tech_trend_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """기술트렌드 검색 결과 포맷팅"""
        formatted_results = []
        for r in items:
            title = r.get("Title", "제목 없음")
            keywords = r.get("RelatedKeywords", "")
            definition = self._body(r.get("Definition", ""))
            pub_date = r.get("PublDate", "")
            cn = r.get("CN", "")
            content_url = r.get("ContentURL", "")
            pdf_url = r.get("PdfURL", "")
            def_source_url = r.get("DefinitionSourceURL", "")
            thumbnail_url = r.get("ThumbnailURL", "")

            result_text = f"**{title}**"
            if pub_date and pub_date.strip():
                result_text += f"\n  - 생성일: {pub_date}"
            if keywords and keywords.strip():
                result_text += f"\n  - 연관키워드: {self._clean(keywords, 0)}"
            if definition:
                result_text += f"\n📝 정의: {definition}"
            if def_source_url and def_source_url.strip():
                result_text += f"\n  - 정의 출처: {def_source_url}"
            if cn and cn.strip():
                result_text += f"\n🔗 트렌드번호(CN): {cn}"
            if content_url and content_url.strip():
                result_text += f"\n🔗 상세보기: {content_url}"
            if pdf_url and pdf_url.strip():
                result_text += f"\n📄 PDF: {pdf_url}"
            if thumbnail_url and thumbnail_url.strip():
                result_text += f"\n🖼 썸네일: {thumbnail_url}"
            formatted_results.append(result_text + "\n")

        return (f"**'{query}' 기술트렌드 검색 결과** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" +
                "\n".join(formatted_results))

    # ── 금주의과학기술뉴스(SNEWS) ──────────────────────────
    def _format_weekly_news_results(self, items: List[Dict], query: str, total_count: int) -> str:
        """금주의 과학기술뉴스 결과 포맷팅 (소문자 키 사용)"""
        formatted_results = []
        for r in items:
            title = r.get("sj", "제목 없음")
            contents = self._body(r.get("contents", ""))
            category = r.get("cdNm", "")
            origin_url = r.get("originUrl", "")
            reg_date = r.get("registDt", "")

            result_text = f"**{title}**"
            if category and category.strip():
                result_text += f"\n  - 분류: {category}"
            if reg_date and reg_date.strip():
                result_text += f"\n  - 등록일: {reg_date}"
            if contents:
                result_text += f"\n📝 내용: {contents}"
            if origin_url and origin_url.strip():
                result_text += f"\n🔗 원문: {origin_url}"
            formatted_results.append(result_text + "\n")

        return (f"**금주의 과학기술뉴스 ({query})** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" +
                "\n".join(formatted_results))

class DataONFormatter(BaseResultFormatter):
    """DataON 결과 포매터"""

    def format_search_results(self, results: List[Dict], query: str, total_count: int, result_type: str) -> str:
        """DataON 연구데이터 검색 결과 포맷팅"""
        if not results:
            return f"'{query}'에 대한 연구데이터 검색 결과가 없습니다."

        formatted_results = []
        formatted_results.append(f"**DataON 연구데이터 검색 결과**")
        formatted_results.append(f"검색어: '{query}' | 총 {total_count}건 중 {len(results)}건 표시\n")

        for i, data in enumerate(results, 1):
            svc_id = data.get("svcId", "ID 없음")
            title = data.get("title", "제목 없음")
            creator = data.get("creator", "작성자 없음")
            publisher = data.get("publisher", "발행기관 없음")
            date = data.get("date", "날짜 없음")
            data_type = data.get("type", "")
            score = data.get("score", 0)
            description = data.get("description", "")
            subject = data.get("subject", [])

            # 제목과 기본 정보
            formatted_results.append(f"\n**[{i}] {title}**")
            formatted_results.append(f"  - **svcId**: {svc_id}")
            formatted_results.append(f"  - **작성자**: {creator}")
            if publisher and publisher.strip() and publisher != "발행기관 없음":
                formatted_results.append(f"  - **발행기관**: {publisher}")
            formatted_results.append(f"  - **날짜**: {date}")

            if data_type and data_type.strip():
                formatted_results.append(f"  - **타입**: {data_type}")

            if score:
                formatted_results.append(f"  - **관련도 점수**: {score:.2f}")

            # 주제어
            if subject:
                if isinstance(subject, list):
                    subject_str = ", ".join(subject[:5])  # 최대 5개까지 표시
                else:
                    subject_str = str(subject)
                formatted_results.append(f"  - **주제어**: {subject_str}")

            # 설명 (간략히)
            if description and description.strip():
                clean_desc = description.replace('\n', ' ').replace('\\r\\n', ' ').strip()
                if len(clean_desc) > 150:
                    clean_desc = clean_desc[:150] + "..."
                formatted_results.append(f"  - **설명**: {clean_desc}")

            # DOI와 랜딩 페이지 링크
            doi = data.get("doi", "")
            if doi and doi.strip():
                formatted_results.append(f"  - **DOI**: {doi}")

            landing_page = data.get("landing_page", "")
            if landing_page and landing_page.strip():
                formatted_results.append(f"  - **데이터 링크**: {landing_page}")

        return "\n".join(formatted_results)

    def format_detail_result(self, result: Dict, identifier: str) -> str:
        """DataON 연구데이터 상세 정보 포맷팅"""
        if not result:
            return f"svcId '{identifier}'에 대한 상세 정보를 찾을 수 없습니다."

        svc_id = result.get("svcId", identifier)
        title = result.get("title", "제목 없음")
        creator = result.get("creator", "작성자 없음")
        publisher = result.get("publisher", "발행기관 없음")
        date = result.get("date", "날짜 없음")
        data_type = result.get("type", "")
        data_format = result.get("format", "")
        language = result.get("language", "")
        rights = result.get("rights", "")
        coverage = result.get("coverage", "")
        description = result.get("description", "")
        subject = result.get("subject", [])
        relation = result.get("relation", "")
        identifier_field = result.get("identifier", "")
        contributor = result.get("contributor", "")

        formatted_result = []
        formatted_result.append(f"**DataON 연구데이터 상세정보**\n")
        formatted_result.append(f"**제목**: {title}")
        formatted_result.append(f"**svcId**: {svc_id}\n")

        # 메타데이터 정보
        formatted_result.append(f"📋 **메타데이터**")
        formatted_result.append(f"  - **작성자**: {creator}")

        if contributor and contributor.strip():
            formatted_result.append(f"  - **기여자**: {contributor}")

        formatted_result.append(f"  - **발행기관**: {publisher}")
        formatted_result.append(f"  - **날짜**: {date}")

        if data_type and (data_type.strip() if isinstance(data_type, str) else data_type):
            formatted_result.append(f"  - **타입**: {data_type}")

        # format은 리스트일 수 있음
        if data_format:
            if isinstance(data_format, list):
                format_str = ", ".join(data_format)
                if format_str and format_str.strip():
                    formatted_result.append(f"  - **포맷**: {format_str}")
            elif isinstance(data_format, str) and data_format.strip():
                formatted_result.append(f"  - **포맷**: {data_format}")

        if language and language.strip():
            formatted_result.append(f"  - **언어**: {language}")

        if coverage and coverage.strip():
            formatted_result.append(f"  - **범위**: {coverage}")

        if rights and rights.strip():
            formatted_result.append(f"  - **권리**: {rights}")

        # 주제어
        if subject:
            if isinstance(subject, list):
                subject_str = ", ".join(subject)
            else:
                subject_str = str(subject)
            formatted_result.append(f"\n🏷️ **주제어**: {subject_str}")

        # 설명
        if description and description.strip():
            clean_desc = description.replace('\n', ' ').strip()
            formatted_result.append(f"\n📝 **설명**:\n{clean_desc}")

        # 관련 정보 (리스트일 수 있음)
        if relation:
            if isinstance(relation, list):
                relation_str = ", ".join(relation)
                if relation_str and relation_str.strip():
                    formatted_result.append(f"\n🔗 **관련 정보**: {relation_str}")
            elif isinstance(relation, str) and relation.strip():
                formatted_result.append(f"\n🔗 **관련 정보**: {relation}")

        if identifier_field and identifier_field.strip():
            formatted_result.append(f"\n🆔 **식별자**: {identifier_field}")

        return "\n".join(formatted_result)

# 서비스 클래스 (비즈니스 로직)
class SearchService:
    """검색 서비스"""
    
    def __init__(self, client: BaseAPIClient, formatter: BaseResultFormatter):
        self.client = client
        self.formatter = formatter
    
    async def search_papers(self, query: str, max_results: int = 10, include_body: bool = True) -> str:
        """논문 검색"""
        try:
            # 토큰 발급
            if not await self.client.get_token():
                return "🚨 토큰 발급에 실패했습니다. 인증 정보를 확인해주세요."

            # 검색 수행
            result = await self.client.search(query, "ARTI", max_results)

            if result.get("error"):
                return f"🚨 API 오류: {result.get('error_message', '알 수 없는 오류')}"

            if result.get("success") and result.get("papers"):
                papers = result["papers"]
                total_count = result.get("total_count", 0)
                return self.formatter.format_search_results(papers[:max_results], query, total_count, "paper", include_body=include_body)
            else:
                return f"'{query}'에 대한 논문 검색 결과가 없습니다."
                
        except Exception as e:
            logger.error(f"논문 검색 중 오류: {str(e)}")
            return f"논문 검색 중 오류가 발생했습니다: {str(e)}"

    async def get_paper_details(self, cn: str, include_body: bool = True) -> str:
        """논문 상세 정보 조회"""
        try:
            # 토큰 발급
            if not await self.client.get_token():
                return "🚨 토큰 발급에 실패했습니다. 인증 정보를 확인해주세요."

            # 상세 정보 조회
            result = await self.client.get_details(cn, "ARTI")

            if result.get("error"):
                return f"🚨 API 오류: {result.get('error_message', '알 수 없는 오류')}"

            if result.get("success") and result.get("papers"):
                papers = result["papers"]
                if papers:
                    return self.formatter.format_detail_result(papers[0], cn, "paper", include_body=include_body)
                else:
                    return f"CN번호 '{cn}'에 해당하는 논문을 찾을 수 없습니다."
            else:
                return f"CN번호 '{cn}'에 대한 상세정보를 가져올 수 없습니다."

        except Exception as e:
            logger.error(f"논문 상세보기 중 오류: {str(e)}")
            return f"논문 상세보기 중 오류가 발생했습니다: {str(e)}"

    async def search_patents(self, query: str, max_results: int = 10, include_body: bool = True) -> str:
        """특허 검색"""
        try:
            # 토큰 발급
            if not await self.client.get_token():
                return "🚨 토큰 발급에 실패했습니다. 인증 정보를 확인해주세요."

            # 검색 수행
            result = await self.client.search(query, "PATENT", max_results)

            if result.get("error"):
                return f"🚨 API 오류: {result.get('error_message', '알 수 없는 오류')}"

            if result.get("success") and result.get("papers"):  # 특허도 papers 필드로 반환
                patents = result["papers"]
                total_count = result.get("total_count", 0)
                return self.formatter.format_search_results(patents[:max_results], query, total_count, "patent", include_body=include_body)
            else:
                return f"'{query}'에 대한 특허 검색 결과가 없습니다."
                
        except Exception as e:
            logger.error(f"특허 검색 중 오류: {str(e)}")
            return f"특허 검색 중 오류가 발생했습니다: {str(e)}"
    
    async def search_reports(self, query: str, max_results: int = 10, include_body: bool = True) -> str:
        """보고서 검색"""
        try:
            # 토큰 발급
            if not await self.client.get_token():
                return "🚨 토큰 발급에 실패했습니다. 인증 정보를 확인해주세요."

            # 검색 수행
            result = await self.client.search(query, "REPORT", max_results)

            if result.get("error"):
                return f"🚨 API 오류: {result.get('error_message', '알 수 없는 오류')}"

            if result.get("success") and result.get("papers"):  # 보고서도 papers 필드로 반환
                reports = result["papers"]
                total_count = result.get("total_count", 0)
                return self.formatter.format_search_results(reports[:max_results], query, total_count, "report", include_body=include_body)
            else:
                return f"'{query}'에 대한 보고서 검색 결과가 없습니다."
                
        except Exception as e:
            logger.error(f"보고서 검색 중 오류: {str(e)}")
            return f"보고서 검색 중 오류가 발생했습니다: {str(e)}"
    
    async def get_patent_details(self, cn: str, include_body: bool = True) -> str:
        """특허 상세 정보 조회"""
        try:
            # 토큰 발급
            if not await self.client.get_token():
                return "🚨 토큰 발급에 실패했습니다. 인증 정보를 확인해주세요."

            # 상세 정보 조회
            result = await self.client.get_details(cn, "PATENT")

            if result.get("error"):
                return f"🚨 API 오류: {result.get('error_message', '알 수 없는 오류')}"

            if result.get("success") and result.get("papers"):
                patents = result["papers"]
                if patents:
                    return self.formatter.format_detail_result(patents[0], cn, "patent", include_body=include_body)
                else:
                    return f"CN번호 '{cn}'에 해당하는 특허를 찾을 수 없습니다."
            else:
                return f"CN번호 '{cn}'에 대한 상세정보를 가져올 수 없습니다."
                
        except Exception as e:
            logger.error(f"특허 상세보기 중 오류: {str(e)}")
            return f"특허 상세보기 중 오류가 발생했습니다: {str(e)}"
    
    async def get_patent_citations(self, cn: str) -> str:
        """특허 인용/피인용 정보 조회"""
        try:
            # 토큰 발급
            if not await self.client.get_token():
                return "🚨 토큰 발급에 실패했습니다. 인증 정보를 확인해주세요."
            
            # 인용 정보 조회
            result = await self.client.get_citations(cn, "PATENT")
            
            if result.get("error"):
                return f"🚨 API 오류: {result.get('error_message', '알 수 없는 오류')}"
            
            if result.get("success") and result.get("papers"):
                citations = result["papers"]
                return self.formatter.format_citation_result(citations, cn)
            else:
                return f"CN번호 '{cn}'에 대한 인용/피인용 정보가 없습니다."
                
        except Exception as e:
            logger.error(f"특허 인용정보 조회 중 오류: {str(e)}")
            return f"특허 인용정보 조회 중 오류가 발생했습니다: {str(e)}"
    
    async def get_report_details(self, cn: str, include_body: bool = True) -> str:
        """보고서 상세 정보 조회"""
        try:
            # 토큰 발급
            if not await self.client.get_token():
                return "🚨 토큰 발급에 실패했습니다. 인증 정보를 확인해주세요."

            # 상세 정보 조회
            result = await self.client.get_details(cn, "REPORT")

            if result.get("error"):
                return f"🚨 API 오류: {result.get('error_message', '알 수 없는 오류')}"

            if result.get("success") and result.get("papers"):
                reports = result["papers"]
                if reports:
                    return self.formatter.format_detail_result(reports[0], cn, "report", include_body=include_body)
                else:
                    return f"CN번호 '{cn}'에 해당하는 보고서를 찾을 수 없습니다."
            else:
                return f"CN번호 '{cn}'에 대한 상세정보를 가져올 수 없습니다."
                
        except Exception as e:
            logger.error(f"보고서 상세보기 중 오류: {str(e)}")
            return f"보고서 상세보기 중 오류가 발생했습니다: {str(e)}"

    # ── 신규 ScienceON 도메인 (동향/과학향기/연구자/연구기관/기술트렌드/금주뉴스) ──
    async def _search_generic(self, query, target: str, result_type: str,
                              display_query: str, max_results: int,
                              query_field: str = "BI", empty_msg: str = None,
                              include_body: bool = True) -> str:
        """검색 공통 처리 (records alias 사용)"""
        try:
            if not await self.client.get_token():
                return "🚨 토큰 발급에 실패했습니다. 인증 정보를 확인해주세요."

            result = await self.client.search(query, target, max_results, query_field=query_field)

            if result.get("error"):
                return f"🚨 API 오류: {result.get('error_message', '알 수 없는 오류')}"

            if result.get("success") and result.get("records"):
                records = result["records"]
                total_count = result.get("total_count", 0)
                return self.formatter.format_search_results(
                    records[:max_results], display_query, total_count, result_type,
                    include_body=include_body)
            else:
                return empty_msg or f"'{display_query}'에 대한 검색 결과가 없습니다."
        except Exception as e:
            logger.error(f"{result_type} 검색 중 오류: {str(e)}")
            return f"{result_type} 검색 중 오류가 발생했습니다: {str(e)}"

    async def _detail_generic(self, cn: str, target: str, result_type: str,
                              include_body: bool = True) -> str:
        """상세 조회 공통 처리 (records alias 사용)"""
        try:
            if not await self.client.get_token():
                return "🚨 토큰 발급에 실패했습니다. 인증 정보를 확인해주세요."

            result = await self.client.get_details(cn, target)

            if result.get("error"):
                return f"🚨 API 오류: {result.get('error_message', '알 수 없는 오류')}"

            if result.get("success") and result.get("records"):
                records = result["records"]
                if records:
                    return self.formatter.format_detail_result(records[0], cn, result_type,
                                                               include_body=include_body)
                return f"CN번호 '{cn}'에 해당하는 정보를 찾을 수 없습니다."
            return f"CN번호 '{cn}'에 대한 상세정보를 가져올 수 없습니다."
        except Exception as e:
            logger.error(f"{result_type} 상세보기 중 오류: {str(e)}")
            return f"{result_type} 상세보기 중 오류가 발생했습니다: {str(e)}"

    async def search_news_trends(self, query: str, max_results: int = 10, include_body: bool = True) -> str:
        return await self._search_generic(query, "ATT", "news_trend", query, max_results, include_body=include_body)

    async def get_news_trend_details(self, cn: str, include_body: bool = True) -> str:
        return await self._detail_generic(cn, "ATT", "news_trend", include_body=include_body)

    async def search_scents(self, year: str, max_results: int = 10, include_body: bool = True) -> str:
        return await self._search_generic(
            year, "SCENT", "scent", year, max_results, query_field="PY",
            empty_msg=f"{year}년 과학향기 칼럼 검색 결과가 없습니다.", include_body=include_body)

    async def get_scent_details(self, cn: str, include_body: bool = True) -> str:
        return await self._detail_generic(cn, "SCENT", "scent", include_body=include_body)

    async def search_researchers(self, query: str, max_results: int = 10, include_body: bool = True) -> str:
        return await self._search_generic(query, "RESEARCHER", "researcher", query, max_results, include_body=include_body)

    async def get_researcher_details(self, cn: str, include_body: bool = True) -> str:
        return await self._detail_generic(cn, "RESEARCHER", "researcher", include_body=include_body)

    async def search_organizations(self, query: str, max_results: int = 10, include_body: bool = True) -> str:
        return await self._search_generic(query, "ORGAN", "organization", query, max_results, include_body=include_body)

    async def get_organization_details(self, cn: str, include_body: bool = True) -> str:
        return await self._detail_generic(cn, "ORGAN", "organization", include_body=include_body)

    async def search_tech_trends(self, query: str, max_results: int = 10, include_body: bool = True) -> str:
        return await self._search_generic(query, "TREND", "tech_trend", query, max_results, include_body=include_body)

    async def search_weekly_news(self, date: str, max_results: int = 20, include_body: bool = True) -> str:
        return await self._search_generic(
            date, "SNEWS", "weekly_news", date, max_results, query_field="RD",
            empty_msg=(f"{date} 날짜의 금주의과학기술뉴스가 없습니다.\n"
                       "날짜 형식: YYYYMMDD (예: 20250224)\n"
                       "뉴스는 매주 월요일 기준으로 등록됩니다."), include_body=include_body)

# 서비스 클래스에 NTIS 메서드 추가
class NTISSearchService:
    """NTIS 검색 서비스"""
    
    def __init__(self, client: NTISClient, formatter: NTISFormatter):
        self.client = client
        self.formatter = formatter
    
    async def search_projects(self, query: str, max_results: int = 10) -> str:
        """국가R&D 과제 검색 (전문기관용→전체용 자동 폴백)

        키 권한이 닿는 가장 풍부한 응답을 반환한다. LLM은 권한 구분을 몰라도 된다.
        """
        try:
            if not await self.client.get_token():
                return "🚨 NTIS API 연결에 실패했습니다."

            # 전문기관용(projectAllSearch) → 전체용(public_project) 순으로 시도
            result = None
            for tgt in ("PROJECT_SPECIAL", "PROJECT"):
                r = await self.client.search(query, tgt, max_results)
                if not r.get("error") and r.get("success") and r.get("results"):
                    result = r
                    break
                # 마지막 시도의 결과(에러/빈결과)는 보존
                result = r

            if result.get("error"):
                return f"🚨 NTIS API 오류: {result.get('error_message', '알 수 없는 오류')}"

            if result.get("success") and result.get("results"):
                projects = result["results"]
                total_count = result.get("total_count", 0)
                return self.formatter.format_search_results(projects[:max_results], query, total_count, "project")
            else:
                return f"'{query}'에 대한 국가R&D 과제 검색 결과가 없습니다."

        except Exception as e:
            logger.error(f"NTIS 과제 검색 중 오류: {str(e)}")
            return f"국가R&D 과제 검색 중 오류가 발생했습니다: {str(e)}"
    
    async def search_classifications(self, query: str, classification_type: str = "standard", max_results: int = 10) -> str:
        """분류 추천 (연구과제 초록 기반)"""
        try:
            # 최소 길이 검증 (128바이트)
            if len(query.encode('utf-8')) < 128:
                return "🚨 분류 추천을 위해서는 최소 128바이트 이상의 연구 초록이 필요합니다. 더 자세한 내용을 입력해주세요."
            
            if not await self.client.get_token():
                return "🚨 NTIS API 연결에 실패했습니다."
            
            # 쿼리와 분류 타입을 튜플로 전달
            result = await self.client.search((query, classification_type), "CLASSIFICATION", max_results)
            
            if result.get("error"):
                return f"🚨 NTIS API 오류: {result.get('error_message', '알 수 없는 오류')}"
            
            if result.get("success") and result.get("classifications"):
                classifications = result["classifications"] 
                total_count = result.get("total_count", 0)
                return self.formatter.format_search_results(classifications, query, total_count, f"classification_{classification_type}")
            else:
                classification_names = {
                    "standard": "과학기술표준분류",
                    "health": "보건의료기술분류", 
                    "industry": "산업기술분류"
                }
                classification_name = classification_names.get(classification_type, "분류")
                return f"'{query[:50]}{'...' if len(query) > 50 else ''}'에 대한 {classification_name} 추천 결과가 없습니다."
                
        except Exception as e:
            logger.error(f"NTIS 분류코드 검색 중 오류: {str(e)}")
            return f"과학기술표준분류코드 검색 중 오류가 발생했습니다: {str(e)}"
    async def search_classifications_detailed(
        self, 
        research_goal: str, 
        research_content: str, 
        expected_effect: str,
        korean_keywords: str, 
        english_keywords: str,
        classification_type: str = "standard", 
        max_results: int = 10
    ) -> str:
        """분류 추천 (항목별 세부 추천)"""
        try:
            # 전체 텍스트 길이 검증 (300바이트)
            total_text = f"{research_goal} {research_content} {expected_effect} {korean_keywords} {english_keywords}".strip()
            if len(total_text.encode('utf-8')) < 300:
                return "🚨 항목별 세부 추천을 위해서는 전체 내용이 최소 300바이트 이상이어야 합니다. 더 자세한 내용을 입력해주세요."
            
            if not await self.client.get_token():
                return "🚨 NTIS API 연결에 실패했습니다."
            
            # 항목별 파라미터를 튜플로 전달 (detailed mode)
            detailed_params = (research_goal, research_content, expected_effect, korean_keywords, english_keywords, classification_type)
            result = await self.client.search(detailed_params, "CLASSIFICATION_DETAILED", max_results)
            
            if result.get("error"):
                return f"🚨 NTIS API 오류: {result.get('error_message', '알 수 없는 오류')}"
            
            if result.get("success") and result.get("classifications"):
                classifications = result["classifications"] 
                total_count = result.get("total_count", 0)
                return self.formatter.format_search_results(classifications, f"항목별 세부 추천", total_count, f"classification_{classification_type}_detailed")
            else:
                classification_names = {
                    "standard": "과학기술표준분류",
                    "health": "보건의료기술분류", 
                    "industry": "산업기술분류"
                }
                classification_name = classification_names.get(classification_type, "분류")
                return f"제출된 항목별 정보에 대한 {classification_name} 추천 결과가 없습니다."
                
        except Exception as e:
            logger.error(f"NTIS 항목별 분류 추천 중 오류: {str(e)}")
            return f"항목별 분류 추천 중 오류가 발생했습니다: {str(e)}"
    
    async def search_recommendations(self, query: str, max_results: int = 10) -> str:
        """연관콘텐츠 추천 (과제명 기반)"""
        try:
            if not await self.client.get_token():
                return "NTIS API 연결에 실패했습니다."
            
            # 1단계: 과제명으로 R&D 과제 검색하여 pjtId 획득
            logger.info(f"1단계: 과제명 '{query}'로 R&D 과제 검색")
            project_result = await self.client.search(query, "PROJECT", 5)  # 최대 5개 검색
            
            if project_result.get("error"):
                return f"과제 검색 중 오류: {project_result.get('error_message', '알 수 없는 오류')}"
            
            if not project_result.get("success") or not project_result.get("results"):
                return f"'{query}'와 관련된 R&D 과제를 찾을 수 없습니다. 정확한 과제명을 입력해주세요."
            
            # 가장 관련성 높은 과제 선택 (첫 번째 결과)
            projects = project_result["results"]
            target_project = projects[0]
            pjt_id = target_project.get("pjtId")
            project_title = target_project.get("title", "")
            
            if not pjt_id:
                return f"선택된 과제의 고유번호(pjtId)를 찾을 수 없습니다."
            
            logger.info(f"2단계: 과제 ID '{pjt_id}'로 연관콘텐츠 검색")
            
            # 2단계: pjtId로 4개 collection 타입 모두 검색
            collections = [
                ("project", "관련 과제"),
                ("paper", "관련 논문"), 
                ("patent", "관련 특허"),
                ("researchreport", "관련 연구보고서")
            ]
            
            all_results = []
            header = f"**선택된 과제:** {project_title}\n**과제 ID:** {pjt_id}\n\n"
            
            for collection_type, section_title in collections:
                logger.info(f"검색 중: {collection_type} collection")
                
                # 각 collection별로 연관콘텐츠 검색
                related_result = await self.client.search((pjt_id, collection_type), "RELATED_CONTENT", max_results)
                
                if related_result.get("error"):
                    header += f"* {section_title} 검색 중 오류: {related_result.get('error_message')}\n"
                    continue
                
                if related_result.get("success") and related_result.get("results"):
                    related_contents = related_result["results"]
                    total_count = related_result.get("total_count", 0)
                    
                    # 각 섹션별 결과 포매팅
                    section_result = self.formatter.format_search_results(
                        related_contents[:max_results], 
                        f"{section_title}", 
                        total_count, 
                        f"related_{collection_type}"
                    )
                    all_results.append(f"\n## {section_title}\n{section_result}")
                else:
                    all_results.append(f"\n## {section_title}\n📭 관련 콘텐츠가 없습니다.")
            
            if not all_results:
                return f"과제 '{project_title}' (ID: {pjt_id})에 대한 연관콘텐츠가 없습니다."
            
            return header + "\n".join(all_results)
                
        except Exception as e:
            logger.error(f"NTIS 연관콘텐츠 추천 중 오류: {str(e)}")
            return f"연관콘텐츠 추천 중 오류가 발생했습니다: {str(e)}"
    
    async def search_recommendations_by_id(self, pjt_id: str, max_results: int = 15) -> str:
        """연관콘텐츠 추천 (과제번호 직접 입력)"""
        try:
            if not await self.client.get_token():
                return "NTIS API 연결에 실패했습니다."
            
            if not pjt_id:
                return "과제 고유번호(pjtId)가 필요합니다."
            
            logger.info(f"과제 ID '{pjt_id}'로 연관콘텐츠 검색")
            
            # 4개 collection 타입 모두 검색
            collections = [
                ("project", "관련 과제"),
                ("paper", "관련 논문"), 
                ("patent", "관련 특허"),
                ("researchreport", "관련 연구보고서")
            ]
            
            all_results = []
            header = f"**과제 ID:** {pjt_id}\n\n"
            
            for collection_type, section_title in collections:
                logger.info(f"검색 중: {collection_type} collection")
                
                # 각 collection별로 연관콘텐츠 검색
                related_result = await self.client.search((pjt_id, collection_type), "RELATED_CONTENT", max_results)
                
                if related_result.get("error"):
                    header += f"* {section_title} 검색 중 오류: {related_result.get('error_message')}\n"
                    continue
                
                if related_result.get("success") and related_result.get("results"):
                    related_contents = related_result["results"]
                    total_count = related_result.get("total_count", 0)
                    
                    # collection별 결과 포매팅
                    formatted_section = self.formatter.format_search_results(
                        related_contents, "", total_count, "related_content"
                    )
                    
                    all_results.append(f"## {section_title}")
                    all_results.append(formatted_section)
                else:
                    all_results.append(f"## {section_title}")
                    all_results.append("관련 콘텐츠가 없습니다.\n")
            
            if not any("**" in result for result in all_results):
                return f"과제 ID '{pjt_id}'에 대한 연관콘텐츠를 찾을 수 없습니다."
            
            return header + "\n".join(all_results)
            
        except Exception as e:
            logger.error(f"NTIS 연관콘텐츠 추천 중 오류: {str(e)}")
            return f"연관콘텐츠 추천 중 오류가 발생했습니다: {str(e)}"

    # ── 신규 전체용 NTIS 서비스 ──────────────────────────────
    async def _ntis_search(self, query, target: str, result_type: str,
                           display_query: str, max_results: int,
                           empty_msg: str = None) -> str:
        """NTIS 신규 서비스 공통 검색 처리"""
        try:
            if not await self.client.get_token():
                return "🚨 NTIS API 연결에 실패했습니다."
            result = await self.client.search(query, target, max_results)
            if result.get("error"):
                return f"🚨 NTIS API 오류: {result.get('error_message', '알 수 없는 오류')}"
            if result.get("success") and result.get("results"):
                records = result["results"]
                total_count = result.get("total_count", 0)
                return self.formatter.format_search_results(
                    records[:max_results], display_query, total_count, result_type)
            return empty_msg or f"'{display_query}'에 대한 검색 결과가 없습니다."
        except Exception as e:
            logger.error(f"NTIS {result_type} 검색 중 오류: {str(e)}")
            return f"NTIS {result_type} 검색 중 오류가 발생했습니다: {str(e)}"

    async def search_outcomes(self, query: str, outcome_type: str = "paper",
                              max_results: int = 10) -> str:
        """국가R&D 성과검색 (논문/특허/연구시설장비/보고서)

        전문기관용(natRnDAllSearch)→기관용(natRnDSearch)→전체용(public_result) 자동 폴백.
        """
        collection_map = {"paper": "rpaper", "patent": "rpatent",
                          "equip": "requip", "report": "rresearch"}
        collection = collection_map.get(outcome_type, "rpaper")
        try:
            if not await self.client.get_token():
                return "🚨 NTIS API 연결에 실패했습니다."

            result = None
            for level in ("all", "org", "public"):
                # rresearch(보고서)는 public_result에 없으므로 public 단계 건너뜀
                if collection == "rresearch" and level == "public":
                    continue
                r = await self.client.search(
                    (query, collection, level), "OUTCOME", max_results)
                if not r.get("error") and r.get("success") and r.get("results"):
                    result = r
                    break
                result = r

            if result.get("error"):
                return f"🚨 NTIS API 오류: {result.get('error_message', '알 수 없는 오류')}"
            if result.get("success") and result.get("results"):
                records = result["results"]
                total_count = result.get("total_count", 0)
                return self.formatter.format_search_results(
                    records[:max_results], query, total_count, "outcome")
            return f"'{query}'에 대한 국가R&D 성과검색 결과가 없습니다."
        except Exception as e:
            logger.error(f"NTIS 성과검색 중 오류: {str(e)}")
            return f"NTIS 성과검색 중 오류가 발생했습니다: {str(e)}"

    async def search_research_reports(self, query: str, max_results: int = 10) -> str:
        """국가R&D 연구보고서 검색"""
        return await self._ntis_search(
            query, "REPORT_SEARCH", "report_search", query, max_results)

    async def search_terminology(self, query: str, max_results: int = 10) -> str:
        """국가R&D 용어사전 조회"""
        return await self._ntis_search(
            query, "TERMINOLOGY", "terminology", query, max_results)

    async def search_rnd_issues(self, query: str = "", max_results: int = 10) -> str:
        """이슈로보는R&D"""
        return await self._ntis_search(
            query, "ISSUE", "issue", query, max_results,
            empty_msg="이슈 정보를 가져올 수 없습니다.")

    async def search_institution_status(self, org_name: str = "",
                                        org_bno: str = "") -> str:
        """수행기관 R&D현황조회 (기관명 또는 사업자등록번호)"""
        if org_bno:
            query = (org_bno, "bno")
            display = org_bno
        elif org_name:
            query = (org_name, "nm")
            display = org_name
        else:
            return "🚨 기관명(org_name) 또는 사업자등록번호(org_bno) 중 하나가 필요합니다."
        return await self._ntis_search(
            query, "ORG_STATUS", "org_status", display, 100,
            empty_msg=f"'{display}'에 대한 수행기관 R&D현황 정보가 없습니다.")

    async def search_classification_codes(self, code_type: str = "standard",
                                          search_code: str = "") -> str:
        """과학기술표준분류코드/국가중점기술코드 검색"""
        slct = "NTIS002" if code_type == "technology" else "NTIS001"
        display = "국가중점기술코드" if slct == "NTIS002" else "과학기술표준분류코드"
        return await self._ntis_search(
            (slct, search_code), "CLASS_CODE", "class_code", display, 100,
            empty_msg=f"{display} 검색 결과가 없습니다.")

    async def search_commission_projects(self, pjt_id: str) -> str:
        """위탁/공동연구 과제 정보 조회 (과제고유번호 기반)"""
        return await self._ntis_search(
            pjt_id, "COMMISSION", "commission", pjt_id, 100,
            empty_msg=f"과제번호 '{pjt_id}'에 대한 위탁/공동연구 정보가 없습니다.")

    async def search_participation(self, person_name: str, researcher_no: str) -> str:
        """과제참여정보 조회 (참여연구원 성명+국가연구자번호)"""
        if not person_name or not researcher_no:
            return "🚨 참여연구원 성명(person_name)과 국가연구자번호(researcher_no)가 모두 필요합니다."
        return await self._ntis_search(
            (person_name, researcher_no), "PARTICIPATION", "participation",
            person_name, 100,
            empty_msg=f"'{person_name}'에 대한 과제참여정보가 없습니다.")

    async def search_total(self, query: str, content_type: str = "project",
                           max_results: int = 10) -> str:
        """국가R&D 통합검색 (collection별)"""
        collection_map = {"project": "project", "paper": "rpaper",
                          "patent": "rpatent", "report": "rresearch",
                          "equip": "requip"}
        collection = collection_map.get(content_type, "project")
        return await self._ntis_search(
            (query, collection), "TOTAL_SEARCH", "total_search", query, max_results)

    async def search_researcher_info(self, name: str, researcher_no: str = "",
                                     birth_date: str = "") -> str:
        """출연(연) 연구자정보 검색 (연구자명 + 국가연구자번호 또는 생년월일)"""
        if not name:
            return "🚨 연구자명(name)이 필요합니다."
        if not researcher_no and not birth_date:
            return "🚨 국가연구자번호(researcher_no) 또는 생년월일(birth_date) 중 하나가 필요합니다."
        return await self._ntis_search(
            (name, researcher_no, birth_date), "RESEARCHER_INFO", "researcher_info",
            name, 100, empty_msg=f"'{name}'에 대한 연구자정보가 없습니다.")

class DataONSearchService:
    """DataON 검색 서비스"""

    def __init__(self, client: DataONClient, formatter: DataONFormatter):
        self.client = client
        self.formatter = formatter

    async def search_research_data(self, query: str, max_results: int = 10,
                                  from_pos: int = 0, sort_con: str = "", sort_arr: str = "desc") -> str:
        """
        연구데이터 검색

        Args:
            query: 검색 키워드
            max_results: 최대 결과 수 (기본 10)
            from_pos: 시작 위치 (기본 0)
            sort_con: 정렬 조건 (date, title 등)
            sort_arr: 정렬 방향 (asc, desc)
        """
        try:
            if not await self.client.get_token():
                return "🚨 DataON API 연결에 실패했습니다."

            result = await self.client.search(
                query=query,
                target="RESEARCH_DATA",
                max_results=max_results,
                from_pos=from_pos,
                sort_con=sort_con,
                sort_arr=sort_arr
            )

            if result.get("error"):
                return f"🚨 DataON API 오류: {result.get('message', '알 수 없는 오류')}"

            if result.get("success") and result.get("results"):
                research_data_list = result["results"]
                total_count = result.get("total_count", 0)
                return self.formatter.format_search_results(research_data_list, query, total_count, "research_data")
            else:
                return f"'{query}'에 대한 연구데이터 검색 결과가 없습니다."

        except Exception as e:
            logger.error(f"DataON 연구데이터 검색 중 오류: {str(e)}")
            return f"연구데이터 검색 중 오류가 발생했습니다: {str(e)}"

    async def get_research_data_details(self, svc_id: str) -> str:
        """
        연구데이터 상세 정보 조회

        Args:
            svc_id: 서비스 ID (데이터셋 고유 식별자)
        """
        try:
            if not await self.client.get_token():
                return "🚨 DataON API 연결에 실패했습니다."

            result = await self.client.get_details(svc_id)

            if result.get("error"):
                return f"🚨 DataON API 오류: {result.get('message', '알 수 없는 오류')}"

            if result.get("success") and result.get("result"):
                detail_info = result["result"]
                return self.formatter.format_detail_result(detail_info, svc_id)
            else:
                return f"svcId '{svc_id}'에 대한 상세 정보를 찾을 수 없습니다."

        except Exception as e:
            logger.error(f"DataON 연구데이터 상세조회 중 오류: {str(e)}")
            return f"연구데이터 상세조회 중 오류가 발생했습니다: {str(e)}"

# 전역 서비스 인스턴스
try:
    scienceon_client = ScienceONClient()
    scienceon_formatter = ScienceONFormatter()
    search_service = SearchService(scienceon_client, scienceon_formatter)
except ValueError as e:
    logger.error(f"ScienceON 서비스 초기화 실패: {str(e)}")
    search_service = None
# NTIS 서비스 초기화
try:
    ntis_client = NTISClient()
    ntis_formatter = NTISFormatter()
    ntis_search_service = NTISSearchService(ntis_client, ntis_formatter)
except Exception as e:
    logger.error(f"NTIS 서비스 초기화 실패: {str(e)}")
    ntis_search_service = None

# DataON 서비스 초기화
try:
    dataon_client = DataONClient()
    dataon_formatter = DataONFormatter()
    dataon_search_service = DataONSearchService(dataon_client, dataon_formatter)
except Exception as e:
    logger.error(f"DataON 서비스 초기화 실패: {str(e)}")
    dataon_search_service = None

# MCP 함수들
@mcp.tool()
async def search_scienceon_papers(
    query: str,
    max_results: int = 10,
    include_body: bool = True
) -> str:
    """
    KISTI ScienceON에서 논문 목록을 검색합니다. 키워드로 여러 논문을 검색하여 목록을 반환합니다.

    Args:
        query: 검색할 키워드
        max_results: 최대 결과 수 (기본값: 10)
        include_body: 초록 등 긴 본문 포함 여부 (기본값: True). False면 초록을 제외하고
            서지정보·DOI·링크만 반환합니다. 컨텍스트가 작은 로컬 모델이나 목록만 훑을 때 유용합니다.

    Returns:
        논문 목록 검색 결과 (제목, 저자, 소속, 저널, 페이지, DOI, 초록 등 포함)
    """
    if search_service is None:
        return ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
               "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")

    return await search_service.search_papers(query, max_results, include_body)
@mcp.tool()
async def search_scienceon_paper_details(
    cn: str,
    include_body: bool = True
) -> str:
    """
    KISTI ScienceON에서 특정 논문의 상세 정보를 조회합니다. 논문 검색에서 얻은 CN번호를 사용하여 해당 논문의 자세한 정보를 가져옵니다.

    Args:
        cn: 논문 고유 식별번호 (논문 검색 결과에서 얻은 CN 번호)
        include_body: 초록 등 긴 본문 포함 여부 (기본값: True). False면 초록을 제외하고
            서지정보·DOI·링크만 반환합니다.

    Returns:
        논문의 상세 정보 (제목, 저자, 소속, 발행기관, 페이지, ISSN, DOI, 초록, 링크 등)
    """
    if search_service is None:
        return ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
               "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")

    return await search_service.get_paper_details(cn, include_body)
@mcp.tool()
async def search_scienceon_patents(
    query: str,
    max_results: int = 10,
    include_body: bool = True
) -> str:
    """
    KISTI ScienceON에서 특허 목록을 검색합니다. 키워드로 여러 특허를 검색하여 목록을 반환합니다.

    Args:
        query: 검색할 키워드
        max_results: 최대 결과 수 (기본값: 10)
        include_body: 초록 등 긴 본문 포함 여부 (기본값: True). False면 초록을 제외하고
            서지정보·링크만 반환합니다.

    Returns:
        특허 목록 검색 결과 (특허제목, 출원인, 출원/공개/등록번호, 상태, IPC 등 포함)
    """
    if search_service is None:
        return ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
               "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")

    return await search_service.search_patents(query, max_results, include_body)
@mcp.tool()
async def search_scienceon_patent_details(
    cn: str,
    include_body: bool = True
) -> str:
    """
    KISTI ScienceON에서 특정 특허의 상세 정보를 조회합니다. 특허 검색에서 얻은 CN번호를 사용하여 해당 특허의 자세한 정보를 가져옵니다.
    인용/피인용 특허는 별도 도구(search_scienceon_patent_citations)로 조회합니다.

    Args:
        cn: 특허 고유 식별번호 (특허 검색 결과에서 얻은 CN 번호)
        include_body: 초록 등 긴 본문 포함 여부 (기본값: True). False면 초록을 제외합니다.

    Returns:
        특허의 상세 정보 (특허제목, 출원인, 출원/공개/등록번호, 공고일, 상태, IPC, 초록 등)
    """
    if search_service is None:
        return ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
               "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")

    return await search_service.get_patent_details(cn, include_body)
@mcp.tool()
async def search_scienceon_patent_citations(
    cn: str
) -> str:
    """
    KISTI ScienceON에서 특정 특허의 인용/피인용 정보를 조회합니다. 특허 검색에서 얻은 CN번호를 사용하여 해당 특허를 인용한 특허들과 해당 특허가 인용한 특허들을 가져옵니다.
    
    Args:
        cn: 특허 고유 식별번호 (특허 검색 결과에서 얻은 CN 번호)
    
    Returns:
        특허의 인용/피인용 관계 정보 (인용한 특허들과 인용된 특허들 목록)
    """
    if search_service is None:
        return ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
               "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")
    
    return await search_service.get_patent_citations(cn)
@mcp.tool()
async def search_scienceon_reports(
    query: str,
    max_results: int = 10,
    include_body: bool = True
) -> str:
    """
    KISTI ScienceON에서 R&D 보고서 목록을 검색합니다. 키워드로 여러 보고서를 검색하여 목록을 반환합니다.

    Args:
        query: 검색할 키워드
        max_results: 최대 결과 수 (기본값: 10)
        include_body: 초록 등 긴 본문 포함 여부 (기본값: True). False면 초록을 제외합니다.

    Returns:
        보고서 목록 검색 결과 (제목, 저자, 발행연도, 발행/주관기관, 초록 포함)
    """
    if search_service is None:
        return ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
               "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")

    return await search_service.search_reports(query, max_results, include_body)
@mcp.tool()
async def search_scienceon_report_details(
    cn: str,
    include_body: bool = True
) -> str:
    """
    KISTI ScienceON에서 특정 R&D 보고서의 상세 정보를 조회합니다. 보고서 검색에서 얻은 CN번호를 사용하여 해당 보고서의 자세한 정보를 가져옵니다.

    Args:
        cn: 보고서 고유 식별번호 (보고서 검색 결과에서 얻은 CN 번호)
        include_body: 초록 등 긴 본문 포함 여부 (기본값: True). False면 초록을 제외합니다.

    Returns:
        보고서의 상세 정보 (제목, 저자, 발행/주관/공동연구기관, 기여자, 표준분류, 초록 등)
    """
    if search_service is None:
        return ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
               "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")

    return await search_service.get_report_details(cn, include_body)

_SCIENCEON_CRED_MSG = ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
                       "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
                       "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")

@mcp.tool()
async def search_scienceon_news_trends(query: str, max_results: int = 10, include_body: bool = True) -> str:
    """
    KISTI ScienceON에서 과학기술 동향 기사를 검색합니다.
    국내외 과학기술 뉴스/기사 모음 (해외과학기술동향, 정보서비스 글로벌동향 등).

    Args:
        query: 검색할 키워드
        max_results: 최대 결과 수 (기본값: 10)
        include_body: 내용 등 긴 본문 포함 여부 (기본값: True). False면 본문을 제외합니다.

    Returns:
        동향 기사 목록 (제목, 저자, 발행년, 주제, 내용, CN번호)
    """
    if search_service is None:
        return _SCIENCEON_CRED_MSG
    return await search_service.search_news_trends(query, max_results, include_body)

@mcp.tool()
async def search_scienceon_news_trend_details(cn: str, include_body: bool = True) -> str:
    """
    KISTI ScienceON에서 특정 과학기술 동향 기사의 상세 정보를 조회합니다.

    Args:
        cn: 동향 기사 고유 식별번호 (동향 검색 결과의 CN 번호)
        include_body: 내용 등 긴 본문 포함 여부 (기본값: True). False면 본문을 제외합니다.

    Returns:
        동향 기사 상세정보 (내용, 발행기관, 원문 등 포함)
    """
    if search_service is None:
        return _SCIENCEON_CRED_MSG
    return await search_service.get_news_trend_details(cn, include_body)

@mcp.tool()
async def search_scienceon_scents(year: str, max_results: int = 10, include_body: bool = True) -> str:
    """
    KISTI ScienceON에서 과학향기 칼럼을 검색합니다.
    2003년부터 과학기술 전 분야를 다루는 대중과학 칼럼 서비스입니다.
    ※ 과학향기 API는 발행연도(year)로만 검색 가능합니다.

    Args:
        year: 발행연도 (예: "2024")
        max_results: 최대 결과 수 (기본값: 10)
        include_body: 본문 등 긴 텍스트 포함 여부 (기본값: True). False면 본문을 제외합니다.

    Returns:
        과학향기 칼럼 목록 (제목, 권호, 분류, 본문, CN번호)
    """
    if search_service is None:
        return _SCIENCEON_CRED_MSG
    return await search_service.search_scents(year, max_results, include_body)

@mcp.tool()
async def search_scienceon_scent_details(cn: str, include_body: bool = True) -> str:
    """
    KISTI ScienceON에서 특정 과학향기 칼럼의 상세정보 및 본문을 조회합니다.

    Args:
        cn: 과학향기 고유 식별번호 (과학향기 검색 결과의 CN 번호)
        include_body: 본문 포함 여부 (기본값: True). False면 본문을 제외하고 메타정보만 반환합니다.

    Returns:
        과학향기 칼럼 상세정보 및 본문
    """
    if search_service is None:
        return _SCIENCEON_CRED_MSG
    return await search_service.get_scent_details(cn, include_body)

@mcp.tool()
async def search_scienceon_researchers(query: str, max_results: int = 10) -> str:
    """
    KISTI ScienceON에서 연구자를 검색합니다. (국내 식별 연구자)

    Args:
        query: 연구자 이름 또는 키워드
        max_results: 최대 결과 수 (기본값: 10)

    Returns:
        연구자 목록 (이름, 소속기관, 논문/특허/보고서 건수, CN번호)
    """
    if search_service is None:
        return _SCIENCEON_CRED_MSG
    return await search_service.search_researchers(query, max_results)

@mcp.tool()
async def search_scienceon_researcher_details(cn: str) -> str:
    """
    KISTI ScienceON에서 특정 연구자의 상세 정보를 조회합니다.

    Args:
        cn: 연구자 고유 식별번호 (연구자 검색 결과의 CN 번호)

    Returns:
        연구자 상세정보 (소속, 이메일, 키워드, 실적 등)
    """
    if search_service is None:
        return _SCIENCEON_CRED_MSG
    return await search_service.get_researcher_details(cn)

@mcp.tool()
async def search_scienceon_organizations(query: str, max_results: int = 10) -> str:
    """
    KISTI ScienceON에서 연구기관을 검색합니다. (국내 식별 연구기관)
    ※ 한글 기관명으로 검색하세요. (예: "한국과학기술정보연구원")

    Args:
        query: 기관명 (한글 권장)
        max_results: 최대 결과 수 (기본값: 10)

    Returns:
        연구기관 목록 (기관명, 키워드, CN번호)
    """
    if search_service is None:
        return _SCIENCEON_CRED_MSG
    return await search_service.search_organizations(query, max_results)

@mcp.tool()
async def search_scienceon_organization_details(cn: str) -> str:
    """
    KISTI ScienceON에서 특정 연구기관의 상세 정보를 조회합니다.

    Args:
        cn: 연구기관 고유 식별번호 (연구기관 검색 결과의 CN 번호)

    Returns:
        연구기관 상세정보 (국/영문 기관명, 키워드 등)
    """
    if search_service is None:
        return _SCIENCEON_CRED_MSG
    return await search_service.get_organization_details(cn)

@mcp.tool()
async def search_scienceon_tech_trends(query: str, max_results: int = 10, include_body: bool = True) -> str:
    """
    KISTI ScienceON에서 기술트렌드 토픽을 검색합니다.
    특정 기술 키워드/토픽 중심의 트렌드 분석 서비스입니다.
    (예: "디지털 트윈", "메타버스", "양자컴퓨팅" 등 신기술 개념 정의·연관콘텐츠 제공)

    Args:
        query: 검색할 키워드
        max_results: 최대 결과 수 (기본값: 10)
        include_body: 정의 등 긴 텍스트 포함 여부 (기본값: True). False면 정의를 제외합니다.

    Returns:
        기술트렌드 토픽 목록 (트렌드명, 연관키워드, 정의, ContentURL, PdfURL)
    """
    if search_service is None:
        return _SCIENCEON_CRED_MSG
    return await search_service.search_tech_trends(query, max_results, include_body)

@mcp.tool()
async def search_scienceon_weekly_news(date: str, max_results: int = 20, include_body: bool = True) -> str:
    """
    KISTI ScienceON에서 금주의 과학기술뉴스를 조회합니다.
    주차별로 신뢰성 높은 국내외 과학기술뉴스를 제공합니다.

    Args:
        date: 조회 날짜 (형식: YYYYMMDD, 예: "20250224"). 해당 날짜가 포함된 주의 뉴스를 반환합니다.
        max_results: 최대 결과 수 (기본값: 20)
        include_body: 내용 등 긴 텍스트 포함 여부 (기본값: True). False면 내용을 제외합니다.

    Returns:
        해당 주의 과학기술뉴스 목록 (제목, 내용요약, 분류, 원문URL)
    """
    if search_service is None:
        return _SCIENCEON_CRED_MSG
    return await search_service.search_weekly_news(date, max_results, include_body)

# NTIS MCP 도구들
@mcp.tool()
async def search_ntis_rnd_projects(
    query: str,
    max_results: int = 10
) -> str:
    """
    NTIS에서 국가R&D 과제를 검색합니다. 키워드로 연구과제를 검색하여 목록을 반환합니다.
    
    Args:
        query: 검색할 키워드 (과제명, 연구분야, 기관명 등)
        max_results: 최대 결과 수 (기본값: 10)
    
    Returns:
        국가R&D 과제 목록 검색 결과 (과제명, 수행기관, 과제기간, 연구분야, 연구비 등 포함)
    """
    if ntis_search_service is None:
        return ("🚨 NTIS API 인증 정보가 설정되지 않았습니다.\n"
               "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
               "필요한 변수: NTIS_API_KEY")

    return await ntis_search_service.search_projects(query, max_results)
@mcp.tool()
async def search_ntis_science_tech_classifications(
    query: str = "",
    classification_type: str = "standard",
    max_results: int = 10,
    
    # 항목별 세부 추천용 파라미터 (선택적)
    research_goal: str = "",
    research_content: str = "",
    expected_effect: str = "",
    korean_keywords: str = "",
    english_keywords: str = ""
) -> str:
    """
    NTIS 분류 추천 서비스를 통해 연구과제 초록에 적합한 분류코드를 추천받습니다. 
    사업과제의 초록이나 연구내용을 입력하면 관련성이 높은 분류코드를 매칭점수와 함께 제공합니다.
    
    두 가지 추천 방식을 지원합니다:
    1. 일반 추천: query 파라미터만 사용 (기존 방식)
    2. 항목별 세부 추천: research_goal, research_content 등 세부 항목 사용 (더 정확한 추천)
    
    Args:
        query: 연구과제 초록 또는 연구내용 (일반 추천용, 최소 300바이트 필요)
        classification_type: 분류 타입 선택
            - "standard": 과학기술표준분류 (기본값)
            - "health": 보건의료기술분류
            - "industry": 산업기술분류
        max_results: 최대 결과 수 (기본값: 10)
        
        # 항목별 세부 추천용 파라미터 (하나 이상 입력시 항목별 추천 모드 활성화)
        research_goal: 연구 개발 목표
        research_content: 연구 개발 내용  
        expected_effect: 연구성과의 응용 분야 및 활용 범위 등
        korean_keywords: 국문 핵심어
        english_keywords: 영문 핵심어
    
    Returns:
        선택된 분류체계의 추천 결과 (분류코드, 분류명, 매칭점수, 분류레벨, 상위분류코드 등 포함)
    """
    if ntis_search_service is None:
        return ("🚨 NTIS API 인증 정보가 설정되지 않았습니다.\n"
               "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
               "필요한 변수: NTIS_API_KEY")
    
    # 유효한 분류 타입 검증
    valid_types = ["standard", "health", "industry"]
    if classification_type not in valid_types:
        return f"🚨 지원하지 않는 분류 타입입니다. 사용 가능한 타입: {', '.join(valid_types)}"
    
    # 항목별 세부 추천 모드 판단 (항목별 파라미터가 하나라도 있으면 세부 추천 모드)
    is_detailed_mode = any([research_goal, research_content, expected_effect, korean_keywords, english_keywords])
    
    if is_detailed_mode:
        # 항목별 세부 추천 모드
        return await ntis_search_service.search_classifications_detailed(
            research_goal, research_content, expected_effect, 
            korean_keywords, english_keywords, 
            classification_type, max_results
        )
    else:
        # 일반 추천 모드 (기존 방식)
        if not query:
            return "🚨 일반 추천 모드에서는 query 파라미터가 필요합니다."
        return await ntis_search_service.search_classifications(query, classification_type, max_results)
@mcp.tool()
async def search_ntis_related_content_recommendations(
    pjt_id: str,
    max_results: int = 15
) -> str:
    """
    NTIS에서 특정 R&D 과제와 연관된 콘텐츠를 추천합니다. 
    과제 고유번호(pjtId)를 입력하면 해당 과제와 연관된 논문, 특허, 보고서, 관련 과제 등을 추천합니다.
    
    사용법:
    1. 먼저 search_ntis_rnd_projects로 과제명을 검색하여 과제번호를 찾습니다
    2. 찾은 과제번호를 이 함수에 입력합니다
    
    Args:
        pjt_id: 과제 고유번호 (예: "1425118980")
        max_results: 각 collection당 최대 결과 수 (기본값: 15)
    
    Returns:
        4개 collection별 연관콘텐츠 목록 (관련 과제, 논문, 특허, 연구보고서)
    """
    if ntis_search_service is None:
        return ("🚨 NTIS API 인증 정보가 설정되지 않았습니다.\n"
               "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
               "필요한 변수: NTIS_API_KEY")

    return await ntis_search_service.search_recommendations_by_id(pjt_id, max_results)

_NTIS_CRED_MSG = ("🚨 NTIS API 인증 정보가 설정되지 않았습니다.\n"
                  "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
                  "필요한 변수: NTIS_API_KEY")

@mcp.tool()
async def search_ntis_rnd_outcomes(
    query: str,
    outcome_type: str = "paper",
    max_results: int = 10
) -> str:
    """
    NTIS에서 국가R&D 성과(논문/특허/연구시설장비)를 검색합니다.

    Args:
        query: 검색할 키워드
        outcome_type: 성과 유형 - "paper"(논문, 기본), "patent"(특허), "equip"(연구시설장비), "report"(연구보고서)
        max_results: 최대 결과 수 (기본값: 10)

    Returns:
        국가R&D 성과 목록 (논문명/발명명/장비명, 수행기관, 연도 등)
    """
    if ntis_search_service is None:
        return _NTIS_CRED_MSG
    valid = ["paper", "patent", "equip", "report"]
    if outcome_type not in valid:
        return f"🚨 지원하지 않는 성과 유형입니다. 사용 가능: {', '.join(valid)}"
    return await ntis_search_service.search_outcomes(query, outcome_type, max_results)

@mcp.tool()
async def search_ntis_research_reports(
    query: str,
    max_results: int = 10
) -> str:
    """
    NTIS에서 국가R&D 연구보고서를 검색합니다.

    Args:
        query: 검색할 키워드
        max_results: 최대 결과 수 (기본값: 10)

    Returns:
        연구보고서 목록 (보고서명, 발행기관, 발행년도, 초록, 원문URL 등)
    """
    if ntis_search_service is None:
        return _NTIS_CRED_MSG
    return await ntis_search_service.search_research_reports(query, max_results)

@mcp.tool()
async def search_ntis_terminology(
    query: str,
    max_results: int = 10
) -> str:
    """
    NTIS에서 국가R&D 용어사전을 조회합니다.

    Args:
        query: 검색할 용어 또는 키워드
        max_results: 최대 결과 수 (기본값: 10)

    Returns:
        용어 목록 (한글/영문 용어명, 주약어, 용어설명, 연관어)
    """
    if ntis_search_service is None:
        return _NTIS_CRED_MSG
    return await ntis_search_service.search_terminology(query, max_results)

@mcp.tool()
async def search_ntis_rnd_issues(
    query: str = "",
    max_results: int = 10
) -> str:
    """
    NTIS '이슈로보는R&D' 서비스에서 최신 과학기술 이슈를 조회합니다.

    Args:
        query: 검색 키워드 (선택. 미입력 시 최신 이슈 제공)
        max_results: 최대 결과 수 (기본값: 10)

    Returns:
        이슈 목록 (이슈명, 연관과제 건수, 관련키워드, 바로가기 링크)
    """
    if ntis_search_service is None:
        return _NTIS_CRED_MSG
    return await ntis_search_service.search_rnd_issues(query, max_results)

@mcp.tool()
async def search_ntis_institution_status(
    org_name: str = "",
    org_bno: str = ""
) -> str:
    """
    NTIS에서 국가R&D 수행기관의 R&D현황을 조회합니다.
    기관명 또는 사업자등록번호 중 하나로 조회합니다.

    Args:
        org_name: 기관명 (예: "한국과학기술정보연구원")
        org_bno: 사업자등록번호 (예: "205-82-04043")

    Returns:
        수행기관 R&D현황 (연도별 과제/논문/특허/보고서 건수, 연구키워드, 연구분야)
    """
    if ntis_search_service is None:
        return _NTIS_CRED_MSG
    return await ntis_search_service.search_institution_status(org_name, org_bno)

@mcp.tool()
async def search_ntis_classification_codes(
    code_type: str = "standard",
    search_code: str = ""
) -> str:
    """
    NTIS에서 과학기술표준분류코드 또는 국가중점기술코드를 검색합니다.

    Args:
        code_type: 코드 유형 - "standard"(과학기술표준분류, 기본), "technology"(국가중점기술)
        search_code: 특정 코드 (선택. 예: "060200". 미입력 시 전체 조회)

    Returns:
        코드 목록 (코드, 코드명, 영문명, 설명, 상위코드)
    """
    if ntis_search_service is None:
        return _NTIS_CRED_MSG
    valid = ["standard", "technology"]
    if code_type not in valid:
        return f"🚨 지원하지 않는 코드 유형입니다. 사용 가능: {', '.join(valid)}"
    return await ntis_search_service.search_classification_codes(code_type, search_code)

@mcp.tool()
async def search_ntis_commission_projects(pjt_id: str) -> str:
    """
    NTIS에서 특정 국가R&D 과제의 위탁/공동연구 과제 정보를 조회합니다.

    Args:
        pjt_id: 주관과제 고유번호 (search_ntis_rnd_projects로 먼저 과제번호를 찾으세요)

    Returns:
        위탁/공동연구 과제 정보 (위탁수행기관, 위탁 연구책임자, 위탁 연구비 등)
    """
    if ntis_search_service is None:
        return _NTIS_CRED_MSG
    return await ntis_search_service.search_commission_projects(pjt_id)

@mcp.tool()
async def search_ntis_participation(person_name: str, researcher_no: str) -> str:
    """
    NTIS에서 연구자의 국가R&D 과제 참여정보(참여기간·인건비계상률)를 조회합니다.

    Args:
        person_name: 참여연구원 성명
        researcher_no: 참여연구원 국가연구자번호(과학기술인등록번호)

    Returns:
        과제참여정보 (과제명, 참여구분, 수행기관, 참여기간, 인건비계상률)
    """
    if ntis_search_service is None:
        return _NTIS_CRED_MSG
    return await ntis_search_service.search_participation(person_name, researcher_no)

@mcp.tool()
async def search_ntis_total(
    query: str,
    content_type: str = "project",
    max_results: int = 10
) -> str:
    """
    NTIS 통합검색으로 과제/논문/특허/보고서/연구시설장비를 검색합니다.

    Args:
        query: 검색할 키워드
        content_type: 검색 대상 - "project"(과제, 기본), "paper"(논문), "patent"(특허), "report"(연구보고서), "equip"(연구시설장비)
        max_results: 최대 결과 수 (기본값: 10)

    Returns:
        통합검색 결과 목록
    """
    if ntis_search_service is None:
        return _NTIS_CRED_MSG
    valid = ["project", "paper", "patent", "report", "equip"]
    if content_type not in valid:
        return f"🚨 지원하지 않는 검색 대상입니다. 사용 가능: {', '.join(valid)}"
    return await ntis_search_service.search_total(query, content_type, max_results)

@mcp.tool()
async def search_ntis_researcher_info(
    name: str,
    researcher_no: str = "",
    birth_date: str = ""
) -> str:
    """
    NTIS에서 출연(연) 연구자정보를 검색합니다. (정보제공 동의 연구자에 한함)

    Args:
        name: 연구자명
        researcher_no: 국가연구자번호(과학기술인등록번호). researcher_no 또는 birth_date 중 하나 필수
        birth_date: 생년월일 8자리 (예: "19790301"). researcher_no와 택1

    Returns:
        연구자정보 (소속기관, 키워드, 과제/논문/특허 실적 등)
    """
    if ntis_search_service is None:
        return _NTIS_CRED_MSG
    return await ntis_search_service.search_researcher_info(name, researcher_no, birth_date)

@mcp.tool()
async def search_dataon_research_data(
    query: str,
    max_results: int = 10,
    from_pos: int = 0,
    sort_con: str = "",
    sort_arr: str = "desc"
) -> str:
    """
    KISTI DataON에서 연구데이터를 검색합니다. 키워드로 공개된 연구데이터를 검색하여 목록을 반환합니다.
    ⚠️ 참고: DataON OpenAPI는 2026년 3월부터 기관사용자만 신규 신청/이용기간 연장이 가능합니다. 기존 발급 키는 승인된 이용 기간 내에서 정상 동작합니다.

    Args:
        query: 검색할 키워드 (연구자명, 연구주제, 데이터명 등)
        max_results: 최대 결과 수 (기본값: 10, 최대 100)
        from_pos: 시작 위치 (페이징용, 기본값: 0)
        sort_con: 정렬 조건 (예: "date", "title" 등, 기본값: 공백 - 관련도순)
        sort_arr: 정렬 방향 ("asc" 또는 "desc", 기본값: "desc")

    Returns:
        연구데이터 목록 검색 결과 (제목, 작성자, 발행기관, 설명, svcId 등 포함)

    Examples:
        - search_dataon_research_data("이승우", 10)
        - search_dataon_research_data("기후변화", 20, 0, "date", "desc")
    """
    if dataon_search_service is None:
        return ("🚨 DataON API 인증 정보가 설정되지 않았습니다.\n"
               "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
               "필요한 변수: DataON_ResearchData_API_KEY, DataON_ResearchDataMetadata_API_KEY")

    return await dataon_search_service.search_research_data(query, max_results, from_pos, sort_con, sort_arr)

@mcp.tool()
async def search_dataon_research_data_details(
    svc_id: str
) -> str:
    """
    KISTI DataON에서 특정 연구데이터의 상세 정보를 조회합니다.
    연구데이터 검색에서 얻은 svcId를 사용하여 해당 데이터의 자세한 메타데이터를 가져옵니다.
    ⚠️ 참고: DataON OpenAPI는 2026년 3월부터 기관사용자만 신규 신청/이용기간 연장이 가능합니다. 기존 발급 키는 승인된 이용 기간 내에서 정상 동작합니다.

    사용법:
    1. 먼저 search_dataon_research_data로 연구데이터를 검색하여 svcId를 찾습니다
    2. 찾은 svcId를 이 함수에 입력합니다

    Args:
        svc_id: 연구데이터 고유 식별번호 (검색 결과에서 얻은 svcId)

    Returns:
        연구데이터의 상세 메타데이터 (작성자, 기여자, 발행기관, 주제어, 포맷, 권리, 관련정보 등)

    Examples:
        - search_dataon_research_data_details("KISTI-OAK-1234567890")
    """
    if dataon_search_service is None:
        return ("🚨 DataON API 인증 정보가 설정되지 않았습니다.\n"
               "MCP 클라이언트 설정(JSON)의 env 항목에 필요한 환경변수를 추가해주세요.\n"
               "필요한 변수: DataON_ResearchData_API_KEY, DataON_ResearchDataMetadata_API_KEY")

    return await dataon_search_service.get_research_data_details(svc_id)

def main():
    """메인 엔트리포인트"""
    active_services = []
    if search_service is not None:
        active_services.append("ScienceON")
    if ntis_search_service is not None:
        active_services.append("NTIS")
    if dataon_search_service is not None:
        active_services.append("DataON")

    if active_services:
        logger.info(f"활성 서비스: {', '.join(active_services)}")
        mcp.run()
    else:
        logger.error("활성화된 서비스가 없습니다. 환경변수를 확인해주세요.")

if __name__ == "__main__":
    main()