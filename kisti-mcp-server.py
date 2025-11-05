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
import base64
from Crypto.Cipher import AES
from urllib.parse import quote
import xml.etree.ElementTree as ET
from pathlib import Path
from abc import ABC, abstractmethod
# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# MCP 서버 초기화
mcp = FastMCP("KISTI-MCP Server")
# 환경변수 캐시 (중복 로딩 방지)
_env_cache = None
_env_loaded = False

def load_env_file(env_file_path: str = ".env") -> Dict[str, str]:
    """
    .env 파일에서 환경변수를 로드합니다. (캐시 사용)

    Args:
        env_file_path: .env 파일 경로

    Returns:
        환경변수 딕셔너리
    """
    global _env_cache, _env_loaded

    # 이미 로드된 경우 캐시 반환
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
            logger.info(f".env 파일에서 {len(env_vars)}개의 환경변수를 로드했습니다.")
        except Exception as e:
            logger.error(f".env 파일 로드 중 오류: {str(e)}")
    else:
        logger.warning(f".env 파일을 찾을 수 없습니다: {env_path}")

    _env_cache = env_vars
    _env_loaded = True

    return env_vars
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
        
        # .env 파일에서 환경변수 로드
        env_vars = load_env_file()

        # 환경변수에서 인증 정보 읽기 (통합 API 키)
        self.api_key = os.getenv("NTIS_API_KEY") or env_vars.get("NTIS_API_KEY", "")

        # 필수 정보 검증
        self._validate_credentials()

    def _validate_credentials(self):
        """인증 정보 검증"""
        if not self.api_key:
            logger.warning("NTIS API KEY가 설정되지 않았습니다: NTIS_API_KEY")
            logger.info("NTIS 서비스가 비활성화됩니다.")
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
        if target == "PROJECT":
            endpoint = "/rndopen/openApi/public_project"
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
        else:
            return {"error": True, "message": f"지원되지 않는 검색 타입: {target}"}
        
        url = f"{self.base_url}{endpoint}"
        
        logger.info(f"NTIS 요청 URL: {url}")
        logger.info(f"파라미터: {params}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
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
        
        # .env 파일에서 환경변수 로드
        env_vars = load_env_file()
        
        # 환경변수에서 인증 정보 읽기
        self.api_key = os.getenv("SCIENCEON_API_KEY") or env_vars.get("SCIENCEON_API_KEY", "")
        self.client_id = os.getenv("SCIENCEON_CLIENT_ID") or env_vars.get("SCIENCEON_CLIENT_ID", "")
        self.mac_address = os.getenv("SCIENCEON_MAC_ADDRESS") or env_vars.get("SCIENCEON_MAC_ADDRESS", "")
        
        # 필수 정보 검증
        self._validate_credentials()
        
        self.refresh_token = None
    
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
        """토큰 발급"""
        logger.info("토큰 발급 요청 중...")
        
        try:
            url = self._create_token_request_url()
            if not url:
                return False
            
            logger.info(f"요청 URL: {url[:100]}...")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                
                logger.info(f"응답 상태: {response.status_code}")
                logger.info(f"응답 내용: {response.text}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        self.access_token = data.get('access_token')
                        self.refresh_token = data.get('refresh_token')
                        
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
    
    async def search(self, query: str, target: str, max_results: int = 5) -> Dict[str, Any]:
        """검색 수행"""
        # JSON 형식으로 검색 쿼리 생성
        search_query = json.dumps({"BI": query}, ensure_ascii=False)
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
        
        async with httpx.AsyncClient(timeout=30.0) as client:
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
        
        async with httpx.AsyncClient(timeout=30.0) as client:
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
        
        async with httpx.AsyncClient(timeout=30.0) as client:
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
                "papers": papers
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

        # .env 파일에서 환경변수 로드
        env_vars = load_env_file()

        # 환경변수에서 인증 정보 읽기
        self.research_data_api_key = os.getenv("DataON_ResearchData_API_KEY") or env_vars.get("DataON_ResearchData_API_KEY", "")
        self.research_data_metadata_api_key = os.getenv("DataON_ResearchDataMetadata_API_KEY") or env_vars.get("DataON_ResearchDataMetadata_API_KEY", "")

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
            async with httpx.AsyncClient(timeout=30.0) as client:
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
            async with httpx.AsyncClient(timeout=30.0) as client:
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
        else:
            return f"지원되지 않는 결과 타입: {result_type}"
    
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
    
    def format_search_results(self, results: List[Dict], query: str, total_count: int, result_type: str) -> str:
        """검색 결과 포맷팅"""
        if result_type == "paper":
            return self._format_paper_results(results, query, total_count)
        elif result_type == "patent":
            return self._format_patent_results(results, query, total_count)
        elif result_type == "report":
            return self._format_report_results(results, query, total_count)
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
            
            result_text = f"**{title}**\n  - 저자: {author}\n  - 연도: {year}"
            
            if journal and journal.strip():
                result_text += f"\n📖 저널: {journal}"
            
            if cn and cn.strip():
                result_text += f"\n🔗 논문번호(CN): {cn}"
            
            # 초록 처리
            if abstract and len(abstract.strip()) > 0:
                clean_abstract = re.sub(r'<[^>]+>', '', abstract)
                clean_abstract = clean_abstract.replace('&amp;#xD;', '').replace('&amp;', '&').strip()
                
                if len(clean_abstract) > 300:
                    clean_abstract = clean_abstract[:300] + "..."
                result_text += f"\n📝 초록: {clean_abstract}"
            
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
            
            result_text = f"**{title}**\n  - 출원인: {applicants}\n  - 출원일: {appl_date}"
            
            if publ_date and publ_date.strip():
                result_text += f"\n📰 공개일: {publ_date}"
            
            if patent_status and patent_status.strip():
                result_text += f"\n  - 특허상태: {patent_status}"
            
            if ipc and ipc.strip():
                result_text += f"\n  - IPC분류: {ipc}"
            
            # 초록 처리
            if abstract and len(abstract.strip()) > 0:
                clean_abstract = re.sub(r'<[^>]+>', '', abstract)
                clean_abstract = clean_abstract.replace('&amp;#xD;', '').replace('&amp;', '&').strip()
                
                if len(clean_abstract) > 300:
                    clean_abstract = clean_abstract[:300] + "..."
                result_text += f"\n📝 초록: {clean_abstract}"
            
            formatted_results.append(result_text + "\n")
        
        return (f"**'{query}' 특허 검색 결과** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" + 
                "\n".join(formatted_results))
    
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
            
            result_text = f"**{title}**\n  - 저자: {author}\n  - 발행연도: {pubyear}"
            
            if publisher and publisher.strip():
                result_text += f"\n🏢 발행기관: {publisher}"
            
            if cn and cn.strip():
                result_text += f"\n🔗 보고서번호(CN): {cn}"
            
            # 초록 처리
            if abstract and len(abstract.strip()) > 0:
                clean_abstract = re.sub(r'<[^>]+>', '', abstract)
                clean_abstract = clean_abstract.replace('&amp;#xD;', '').replace('&amp;', '&').strip()
                
                if len(clean_abstract) > 300:
                    clean_abstract = clean_abstract[:300] + "..."
                result_text += f"\n📝 초록: {clean_abstract}"
            
            formatted_results.append(result_text + "\n")
        
        return (f"**'{query}' 보고서 검색 결과** "
                f"(총 {total_count:,}건 중 {len(formatted_results)}건 표시):\n\n" + 
                "\n".join(formatted_results) +
                "\n💡 특정 보고서의 상세정보를 원하면 CN번호를 이용해 보고서상세보기를 사용하세요.")
    
    def format_detail_result(self, item: Dict, identifier: str, result_type: str = "paper") -> str:
        """상세 결과 포맷팅"""
        if result_type == "paper":
            return self._format_paper_detail(item, identifier)
        elif result_type == "patent":
            return self._format_patent_detail(item, identifier)
        elif result_type == "report":
            return self._format_report_detail(item, identifier)
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
        fulltext_url = paper.get("FulltextURL", "")
        content_url = paper.get("ContentURL", "")
        
        # 관련 논문 정보
        similar_title = paper.get("SimilarTitle", "")
        citing_title = paper.get("CitingTitle", "")
        cited_title = paper.get("CitedTitle", "")
        
        result_text = f"**논문 상세정보 (CN: {cn})**\n\n"
        result_text += f"**제목**: {title}\n"
        result_text += f"👤 **저자**: {author}\n"
        result_text += f"📅 **연도**: {year}\n"
        result_text += f"📖 **저널**: {journal}\n"
        
        if doi and doi.strip():
            result_text += f"🔗 **DOI**: {doi}\n"
        
        if keywords and keywords.strip():
            result_text += f"  - **키워드**: {keywords}\n"
        
        # 초록
        if abstract and len(abstract.strip()) > 0:
            clean_abstract = re.sub(r'<[^>]+>', '', abstract)
            clean_abstract = clean_abstract.replace('&amp;#xD;', '').replace('&amp;', '&').strip()
            result_text += f"\n📝 **초록**:\n{clean_abstract}\n"
        
        # URL 정보
        if fulltext_url and fulltext_url.strip():
            result_text += f"\n  - **원문 URL**: {fulltext_url}\n"
        
        if content_url and content_url.strip():
            result_text += f"  - **ScienceON 링크**: {content_url}\n"
        
        # 관련 논문 정보
        if similar_title and similar_title.strip():
            result_text += f"\n  - **유사 논문**: {similar_title[:200]}...\n"
        
        if citing_title and citing_title.strip():
            result_text += f"\n  - **인용 논문**: {citing_title[:200]}...\n"
        
        if cited_title and cited_title.strip():
            result_text += f"\n  - **참고 논문**: {cited_title[:200]}...\n"
        
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
        
        # 관련 특허 정보
        similar_title = patent.get("SimilarTitle", "")
        citing_title = patent.get("CitingTitle", "")
        
        result_text = f"**특허 상세정보 (CN: {cn})**\n\n"
        result_text += f"**특허제목**: {title}\n"
        result_text += f"👥 **출원인**: {applicants}\n"
        result_text += f"📅 **출원일**: {appl_date}\n"
        result_text += f"📰 **공개일**: {publ_date}\n"
        
        if patent_status and patent_status.strip():
            result_text += f"**특허상태**: {patent_status}\n"
        
        if ipc and ipc.strip():
            result_text += f"🏷️ **IPC분류**: {ipc}\n"
        
        if nation and nation.strip():
            result_text += f"  - **국가**: {nation}\n"
        
        # 초록
        if abstract and len(abstract.strip()) > 0:
            clean_abstract = re.sub(r'<[^>]+>', '', abstract)
            clean_abstract = clean_abstract.replace('&amp;#xD;', '').replace('&amp;', '&').strip()
            result_text += f"\n📝 **초록**:\n{clean_abstract}\n"
        
        # URL 정보
        if content_url and content_url.strip():
            result_text += f"\n  - **ScienceON 링크**: {content_url}\n"
        
        # 관련 특허 정보
        if similar_title and similar_title.strip():
            result_text += f"\n  - **유사 특허**: {similar_title[:200]}...\n"
        
        if citing_title and citing_title.strip():
            result_text += f"\n  - **인용 특허**: {citing_title[:200]}...\n"
        
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
        
        # 인용 정보
        cited_paper_info = report.get("CitedPaperinfo", "")
        cited_patent_info = report.get("CitedPatentinfo", "")
        cited_report_info = report.get("CitedReportinfo", "")
        
        result_text = f"**보고서 상세정보 (CN: {cn})**\n\n"
        result_text += f"**제목**: {title}\n"
        result_text += f"👤 **저자**: {author}\n"
        result_text += f"📅 **발행연도**: {pubyear}\n"
        result_text += f"🏢 **발행기관**: {publisher}\n"
        
        if keywords and keywords.strip():
            result_text += f"  - **키워드**: {keywords}\n"
        
        # 초록
        if abstract and len(abstract.strip()) > 0:
            clean_abstract = re.sub(r'<[^>]+>', '', abstract)
            clean_abstract = clean_abstract.replace('&amp;#xD;', '').replace('&amp;', '&').strip()
            result_text += f"\n📝 **초록**:\n{clean_abstract}\n"
        
        # URL 정보
        if fulltext_url and fulltext_url.strip():
            result_text += f"\n  - **원문 URL**: {fulltext_url}\n"
        
        if content_url and content_url.strip():
            result_text += f"  - **ScienceON 링크**: {content_url}\n"
        
        # 인용 정보
        if cited_paper_info and cited_paper_info.strip():
            result_text += f"\n  - **인용 논문**: {cited_paper_info[:200]}...\n"
        
        if cited_patent_info and cited_patent_info.strip():
            result_text += f"\n  - **인용 특허**: {cited_patent_info[:200]}...\n"
        
        if cited_report_info and cited_report_info.strip():
            result_text += f"\n  - **인용 보고서**: {cited_report_info[:200]}...\n"
        
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
            
            citation_text = f"**{title}**\n  - 출원인: {applicants}\n  - 출원일: {appl_date}"
            
            if patent_status and patent_status.strip():
                citation_text += f"\n  - 특허상태: {patent_status}"
            
            formatted_citations.append(citation_text + "\n")
        
        result_text += "\n".join(formatted_citations)
        
        if len(citations) > 10:
            result_text += f"\n총 {len(citations)}건 중 10건만 표시되었습니다."
        
        return result_text

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
    
    async def search_papers(self, query: str, max_results: int = 10) -> str:
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
                return self.formatter.format_search_results(papers[:max_results], query, total_count, "paper")
            else:
                return f"'{query}'에 대한 논문 검색 결과가 없습니다."
                
        except Exception as e:
            logger.error(f"논문 검색 중 오류: {str(e)}")
            return f"논문 검색 중 오류가 발생했습니다: {str(e)}"
    
    async def search_patents(self, query: str, max_results: int = 10) -> str:
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
                return self.formatter.format_search_results(patents[:max_results], query, total_count, "patent")
            else:
                return f"'{query}'에 대한 특허 검색 결과가 없습니다."
                
        except Exception as e:
            logger.error(f"특허 검색 중 오류: {str(e)}")
            return f"특허 검색 중 오류가 발생했습니다: {str(e)}"
    
    async def search_reports(self, query: str, max_results: int = 10) -> str:
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
                return self.formatter.format_search_results(reports[:max_results], query, total_count, "report")
            else:
                return f"'{query}'에 대한 보고서 검색 결과가 없습니다."
                
        except Exception as e:
            logger.error(f"보고서 검색 중 오류: {str(e)}")
            return f"보고서 검색 중 오류가 발생했습니다: {str(e)}"
    
    async def get_patent_details(self, cn: str) -> str:
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
                    return self.formatter.format_detail_result(patents[0], cn, "patent")
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
    
    async def get_report_details(self, cn: str) -> str:
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
                    return self.formatter.format_detail_result(reports[0], cn, "report")
                else:
                    return f"CN번호 '{cn}'에 해당하는 보고서를 찾을 수 없습니다."
            else:
                return f"CN번호 '{cn}'에 대한 상세정보를 가져올 수 없습니다."
                
        except Exception as e:
            logger.error(f"보고서 상세보기 중 오류: {str(e)}")
            return f"보고서 상세보기 중 오류가 발생했습니다: {str(e)}"
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
                    return self.formatter.format_detail_result(papers[0], cn)
                else:
                    return f"CN번호 '{cn}'에 해당하는 논문을 찾을 수 없습니다."
            else:
                return f"CN번호 '{cn}'에 대한 상세정보를 가져올 수 없습니다."
                
        except Exception as e:
            logger.error(f"논문 상세보기 중 오류: {str(e)}")
            return f"논문 상세보기 중 오류가 발생했습니다: {str(e)}"
# 서비스 클래스에 NTIS 메서드 추가
class NTISSearchService:
    """NTIS 검색 서비스"""
    
    def __init__(self, client: NTISClient, formatter: NTISFormatter):
        self.client = client
        self.formatter = formatter
    
    async def search_projects(self, query: str, max_results: int = 10) -> str:
        """국가R&D 과제 검색"""
        try:
            if not await self.client.get_token():
                return "🚨 NTIS API 연결에 실패했습니다."
            
            result = await self.client.search(query, "PROJECT", max_results)
            
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
    max_results: int = 10
) -> str:
    """
    KISTI ScienceON에서 논문 목록을 검색합니다. 키워드로 여러 논문을 검색하여 목록을 반환합니다.
    
    Args:
        query: 검색할 키워드
        max_results: 최대 결과 수 (기본값: 10)
    
    Returns:
        논문 목록 검색 결과 (제목, 저자, 연도, 저널명, 초록 포함)
    """
    if search_service is None:
        return ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
               ".env 파일을 생성하거나 환경변수를 설정해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")
    
    return await search_service.search_papers(query, max_results)
@mcp.tool()
async def search_scienceon_paper_details(
    cn: str
) -> str:
    """
    KISTI ScienceON에서 특정 논문의 상세 정보를 조회합니다. 논문 검색에서 얻은 CN번호를 사용하여 해당 논문의 자세한 정보를 가져옵니다.
    
    Args:
        cn: 논문 고유 식별번호 (논문 검색 결과에서 얻은 CN 번호)
    
    Returns:
        논문의 상세 정보 (인용논문, 참고문헌, 관련논문, 유사논문 등 포함)
    """
    if search_service is None:
        return ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
               ".env 파일을 생성하거나 환경변수를 설정해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")
    
    return await search_service.get_paper_details(cn)
@mcp.tool()
async def search_scienceon_patents(
    query: str,
    max_results: int = 10
) -> str:
    """
    KISTI ScienceON에서 특허 목록을 검색합니다. 키워드로 여러 특허를 검색하여 목록을 반환합니다.
    
    Args:
        query: 검색할 키워드
        max_results: 최대 결과 수 (기본값: 10)
    
    Returns:
        특허 목록 검색 결과 (특허제목, 출원인, 출원일, 공개일 등 포함)
    """
    if search_service is None:
        return ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
               ".env 파일을 생성하거나 환경변수를 설정해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")
    
    return await search_service.search_patents(query, max_results)
@mcp.tool()
async def search_scienceon_patent_details(
    cn: str
) -> str:
    """
    KISTI ScienceON에서 특정 특허의 상세 정보를 조회합니다. 특허 검색에서 얻은 CN번호를 사용하여 해당 특허의 자세한 정보를 가져옵니다.
    
    Args:
        cn: 특허 고유 식별번호 (특허 검색 결과에서 얻은 CN 번호)
    
    Returns:
        특허의 상세 정보 (유사특허, 인용특허, 특허상태 등 포함)
    """
    if search_service is None:
        return ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
               ".env 파일을 생성하거나 환경변수를 설정해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")
    
    return await search_service.get_patent_details(cn)
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
               ".env 파일을 생성하거나 환경변수를 설정해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")
    
    return await search_service.get_patent_citations(cn)
@mcp.tool()
async def search_scienceon_reports(
    query: str,
    max_results: int = 10
) -> str:
    """
    KISTI ScienceON에서 R&D 보고서 목록을 검색합니다. 키워드로 여러 보고서를 검색하여 목록을 반환합니다.
    
    Args:
        query: 검색할 키워드
        max_results: 최대 결과 수 (기본값: 10)
    
    Returns:
        보고서 목록 검색 결과 (제목, 저자, 발행연도, 발행기관, 초록 포함)
    """
    if search_service is None:
        return ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
               ".env 파일을 생성하거나 환경변수를 설정해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")
    
    return await search_service.search_reports(query, max_results)
@mcp.tool()
async def search_scienceon_report_details(
    cn: str
) -> str:
    """
    KISTI ScienceON에서 특정 R&D 보고서의 상세 정보를 조회합니다. 보고서 검색에서 얻은 CN번호를 사용하여 해당 보고서의 자세한 정보를 가져옵니다.
    
    Args:
        cn: 보고서 고유 식별번호 (보고서 검색 결과에서 얻은 CN 번호)
    
    Returns:
        보고서의 상세 정보 (인용논문, 인용특허, 관련보고서 등 포함)
    """
    if search_service is None:
        return ("🚨 API 인증 정보가 설정되지 않았습니다.\n"
               ".env 파일을 생성하거나 환경변수를 설정해주세요.\n"
               "필요한 변수: SCIENCEON_API_KEY, SCIENCEON_CLIENT_ID, SCIENCEON_MAC_ADDRESS")
    
    return await search_service.get_report_details(cn)
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
               ".env 파일을 생성하거나 환경변수를 설정해주세요.\n"
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
               ".env 파일을 생성하거나 환경변수를 설정해주세요.\n"
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
               ".env 파일을 생성하거나 환경변수를 설정해주세요.\n"
               "필요한 변수: NTIS_API_KEY")

    return await ntis_search_service.search_recommendations_by_id(pjt_id, max_results)

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
               ".env 파일을 생성하거나 환경변수를 설정해주세요.\n"
               "필요한 변수: DataON_ResearchData_API_KEY, DataON_ResearchDataMetadata_API_KEY")

    return await dataon_search_service.search_research_data(query, max_results, from_pos, sort_con, sort_arr)

@mcp.tool()
async def search_dataon_research_data_details(
    svc_id: str
) -> str:
    """
    KISTI DataON에서 특정 연구데이터의 상세 정보를 조회합니다.
    연구데이터 검색에서 얻은 svcId를 사용하여 해당 데이터의 자세한 메타데이터를 가져옵니다.

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
               ".env 파일을 생성하거나 환경변수를 설정해주세요.\n"
               "필요한 변수: DataON_ResearchData_API_KEY, DataON_ResearchDataMetadata_API_KEY")

    return await dataon_search_service.get_research_data_details(svc_id)

def main():
    """메인 엔트리포인트"""
    if search_service is not None:
        mcp.run()
    else:
        logger.error("환경변수 설정 후 다시 실행해주세요.")
if __name__ == "__main__":
    main()