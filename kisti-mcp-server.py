#!/usr/bin/env python3
"""
KOSMA
(KISTI-Oriented Science&Mission-driven Agent)
KISTI가 서비스하는 다양한 플랫폼의 OpenAPI를 활용할 수 있습니다.

KISTI-MCP Server 
v0.1.7 - ScienceON 논문, 특허, 보고서 검색 등 관련 도구 7종 제공 
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

def load_env_file(env_file_path: str = ".env") -> Dict[str, str]:
    """
    .env 파일에서 환경변수를 로드합니다.
    
    Args:
        env_file_path: .env 파일 경로
        
    Returns:
        환경변수 딕셔너리
    """
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
            
            result_text = f"📄 **{title}**\n👤 저자: {author}\n📅 연도: {year}"
            
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
        
        return (f"🔍 **'{query}' 논문 검색 결과** "
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
            
            result_text = f"🏛️ **{title}**\n👥 출원인: {applicants}\n📅 출원일: {appl_date}"
            
            if publ_date and publ_date.strip():
                result_text += f"\n📰 공개일: {publ_date}"
            
            if patent_status and patent_status.strip():
                result_text += f"\n📊 특허상태: {patent_status}"
            
            if ipc and ipc.strip():
                result_text += f"\n🏷️ IPC분류: {ipc}"
            
            # 초록 처리
            if abstract and len(abstract.strip()) > 0:
                clean_abstract = re.sub(r'<[^>]+>', '', abstract)
                clean_abstract = clean_abstract.replace('&amp;#xD;', '').replace('&amp;', '&').strip()
                
                if len(clean_abstract) > 300:
                    clean_abstract = clean_abstract[:300] + "..."
                result_text += f"\n📝 초록: {clean_abstract}"
            
            formatted_results.append(result_text + "\n")
        
        return (f"🔍 **'{query}' 특허 검색 결과** "
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
            
            result_text = f"📊 **{title}**\n👤 저자: {author}\n📅 발행연도: {pubyear}"
            
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
        
        return (f"🔍 **'{query}' 보고서 검색 결과** "
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
        
        result_text = f"📋 **논문 상세정보 (CN: {cn})**\n\n"
        result_text += f"📄 **제목**: {title}\n"
        result_text += f"👤 **저자**: {author}\n"
        result_text += f"📅 **연도**: {year}\n"
        result_text += f"📖 **저널**: {journal}\n"
        
        if doi and doi.strip():
            result_text += f"🔗 **DOI**: {doi}\n"
        
        if keywords and keywords.strip():
            result_text += f"🏷️ **키워드**: {keywords}\n"
        
        # 초록
        if abstract and len(abstract.strip()) > 0:
            clean_abstract = re.sub(r'<[^>]+>', '', abstract)
            clean_abstract = clean_abstract.replace('&amp;#xD;', '').replace('&amp;', '&').strip()
            result_text += f"\n📝 **초록**:\n{clean_abstract}\n"
        
        # URL 정보
        if fulltext_url and fulltext_url.strip():
            result_text += f"\n🔗 **원문 URL**: {fulltext_url}\n"
        
        if content_url and content_url.strip():
            result_text += f"🔗 **ScienceON 링크**: {content_url}\n"
        
        # 관련 논문 정보
        if similar_title and similar_title.strip():
            result_text += f"\n📚 **유사 논문**: {similar_title[:200]}...\n"
        
        if citing_title and citing_title.strip():
            result_text += f"📈 **인용 논문**: {citing_title[:200]}...\n"
        
        if cited_title and cited_title.strip():
            result_text += f"📊 **참고 논문**: {cited_title[:200]}...\n"
        
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
        
        result_text = f"📋 **특허 상세정보 (CN: {cn})**\n\n"
        result_text += f"🏛️ **특허제목**: {title}\n"
        result_text += f"👥 **출원인**: {applicants}\n"
        result_text += f"📅 **출원일**: {appl_date}\n"
        result_text += f"📰 **공개일**: {publ_date}\n"
        
        if patent_status and patent_status.strip():
            result_text += f"📊 **특허상태**: {patent_status}\n"
        
        if ipc and ipc.strip():
            result_text += f"🏷️ **IPC분류**: {ipc}\n"
        
        if nation and nation.strip():
            result_text += f"🌍 **국가**: {nation}\n"
        
        # 초록
        if abstract and len(abstract.strip()) > 0:
            clean_abstract = re.sub(r'<[^>]+>', '', abstract)
            clean_abstract = clean_abstract.replace('&amp;#xD;', '').replace('&amp;', '&').strip()
            result_text += f"\n📝 **초록**:\n{clean_abstract}\n"
        
        # URL 정보
        if content_url and content_url.strip():
            result_text += f"\n🔗 **ScienceON 링크**: {content_url}\n"
        
        # 관련 특허 정보
        if similar_title and similar_title.strip():
            result_text += f"\n📚 **유사 특허**: {similar_title[:200]}...\n"
        
        if citing_title and citing_title.strip():
            result_text += f"📈 **인용 특허**: {citing_title[:200]}...\n"
        
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
        
        result_text = f"📋 **보고서 상세정보 (CN: {cn})**\n\n"
        result_text += f"📊 **제목**: {title}\n"
        result_text += f"👤 **저자**: {author}\n"
        result_text += f"📅 **발행연도**: {pubyear}\n"
        result_text += f"🏢 **발행기관**: {publisher}\n"
        
        if keywords and keywords.strip():
            result_text += f"🏷️ **키워드**: {keywords}\n"
        
        # 초록
        if abstract and len(abstract.strip()) > 0:
            clean_abstract = re.sub(r'<[^>]+>', '', abstract)
            clean_abstract = clean_abstract.replace('&amp;#xD;', '').replace('&amp;', '&').strip()
            result_text += f"\n📝 **초록**:\n{clean_abstract}\n"
        
        # URL 정보
        if fulltext_url and fulltext_url.strip():
            result_text += f"\n🔗 **원문 URL**: {fulltext_url}\n"
        
        if content_url and content_url.strip():
            result_text += f"🔗 **ScienceON 링크**: {content_url}\n"
        
        # 인용 정보
        if cited_paper_info and cited_paper_info.strip():
            result_text += f"\n📚 **인용 논문**: {cited_paper_info[:200]}...\n"
        
        if cited_patent_info and cited_patent_info.strip():
            result_text += f"🏛️ **인용 특허**: {cited_patent_info[:200]}...\n"
        
        if cited_report_info and cited_report_info.strip():
            result_text += f"📊 **인용 보고서**: {cited_report_info[:200]}...\n"
        
        return result_text
    
    def format_citation_result(self, citations: List[Dict], cn: str) -> str:
        """인용/피인용 결과 포맷팅"""
        if not citations:
            return f"CN번호 '{cn}'에 대한 인용/피인용 정보가 없습니다."
        
        result_text = f"📋 **특허 인용/피인용 정보 (CN: {cn})**\n\n"
        
        formatted_citations = []
        for i, citation in enumerate(citations[:10]):  # 최대 10개까지 표시
            title = citation.get("Title", "특허제목 없음")
            applicants = citation.get("Applicants", "출원인 없음")
            appl_date = citation.get("ApplDate", "출원일 없음")
            patent_status = citation.get("PatentStatus", "")
            
            citation_text = f"🏛️ **{title}**\n👥 출원인: {applicants}\n📅 출원일: {appl_date}"
            
            if patent_status and patent_status.strip():
                citation_text += f"\n📊 특허상태: {patent_status}"
            
            formatted_citations.append(citation_text + "\n")
        
        result_text += "\n".join(formatted_citations)
        
        if len(citations) > 10:
            result_text += f"\n💡 총 {len(citations)}건 중 10건만 표시되었습니다."
        
        return result_text

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

# 전역 서비스 인스턴스
try:
    scienceon_client = ScienceONClient()
    scienceon_formatter = ScienceONFormatter()
    search_service = SearchService(scienceon_client, scienceon_formatter)
except ValueError as e:
    logger.error(f"서비스 초기화 실패: {str(e)}")
    search_service = None

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

def main():
    """메인 엔트리포인트"""
    if search_service is not None:
        mcp.run()
    else:
        logger.error("환경변수 설정 후 다시 실행해주세요.")

if __name__ == "__main__":
    main()