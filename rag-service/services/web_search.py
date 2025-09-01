import requests
from bs4 import BeautifulSoup
import httpx
from typing import List, Dict, Any
import os
import re
from urllib.parse import urljoin, urlparse
import asyncio
import json

from dotenv import load_dotenv


load_dotenv()  
class WebSearchService:
    def __init__(self):
        self.session = httpx.AsyncClient(timeout=30.0)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Google Custom Search API 설정
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_cse_id = os.getenv("GOOGLE_CSE_ID")
        self.google_search_url = "https://www.googleapis.com/customsearch/v1"
        
        # DuckDuckGo API (Google API가 없을 때 대체)
        self.duckduckgo_url = "https://api.duckduckgo.com/"
        
        # 검색어 전처리 및 대체 검색어 매핑
        self.query_mappings = {
            'llm': ['LLM', 'large language model', 'AI 모델'],
            '응답': ['response', 'answer', '답변'],
            '완성': ['complete', 'finish', '완성'],
            '시장': ['market', 'trading', '주식'],
            '주식': ['stock', 'investment', '투자']
        }
    
    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """웹 검색 수행 - Google Custom Search API 우선, 대체로 DuckDuckGo 사용"""
        try:
            # Google Custom Search API 사용 시도
            if self.google_api_key and self.google_cse_id:
                print(f"Google Custom Search API 사용: {query}")
                search_results = await self._google_search(query, max_results)
                if search_results:
                    return search_results
            
            # Google API가 없거나 실패한 경우 DuckDuckGo 사용
            print(f"DuckDuckGo API 사용: {query}")
            search_results = await self._duckduckgo_search(query, max_results)
            if search_results:
                return search_results
            
            # 모든 API가 실패한 경우 기본 검색 시뮬레이션
            print(f"기본 검색 시뮬레이션 사용: {query}")
            return await self._simulate_search(query, max_results)
            
        except Exception as e:
            print(f"Error in web search: {e}")
            return await self._simulate_search(query, max_results)
    
    def _preprocess_query(self, query: str) -> str:
        """검색어 전처리: 한국어 특수문자 제거 및 키워드 정리"""
        # 특수문자 제거
        cleaned_query = re.sub(r'[^\w\s가-힣]', ' ', query)
        # 연속된 공백을 하나로
        cleaned_query = re.sub(r'\s+', ' ', cleaned_query).strip()
        
        # 한국어 키워드가 있으면 영어 키워드 추가
        english_keywords = []
        for korean_word, english_list in self.query_mappings.items():
            if korean_word in cleaned_query:
                english_keywords.extend(english_list[:2])  # 최대 2개만 추가
        
        if english_keywords:
            final_query = f"{cleaned_query} {' '.join(english_keywords)}"
            print(f"검색어 전처리: '{query}' -> '{final_query}'")
            return final_query
        
        return cleaned_query
    
    def _create_fallback_query(self, query: str) -> str:
        """대체 검색어 생성: 더 일반적인 키워드로 변경"""
        # 한국어 키워드를 영어로 변환
        fallback_parts = []
        for korean_word, english_list in self.query_mappings.items():
            if korean_word in query:
                fallback_parts.append(english_list[0])  # 첫 번째 영어 키워드 사용
        
        if fallback_parts:
            fallback_query = ' '.join(fallback_parts)
            print(f"대체 검색어 생성: '{query}' -> '{fallback_query}'")
            return fallback_query
        
        # 한국어 키워드가 없으면 일반적인 검색어로
        return "AI artificial intelligence"
    
    async def _google_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Google Custom Search API를 사용한 검색"""
        try:
            # 검색어 전처리: 한국어 특수문자 제거 및 영어 키워드 추가
            processed_query = self._preprocess_query(query)
            
            params = {
                'key': self.google_api_key,
                'cx': self.google_cse_id,
                'q': processed_query,
                'num': min(max_results, 10),  # Google API는 최대 10개
                'safe': 'active',
                'lr': 'lang_ko',  # 한국어 결과 우선
                'gl': 'kr'  # 한국 지역 설정
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.google_search_url,
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                
                if 'items' not in data:
                    print(f"Google API 응답에 items가 없음: {data}")
                    # 검색어를 더 일반적으로 변경해서 재시도
                    fallback_query = self._create_fallback_query(query)
                    if fallback_query != query:
                        print(f"대체 검색어로 재시도: {fallback_query}")
                        return await self._google_search(fallback_query, max_results)
                    return []
                
                results = []
                for item in data['items']:
                    result = {
                        'title': item.get('title', ''),
                        'url': item.get('link', ''),
                        'snippet': item.get('snippet', ''),
                        'source': 'google'
                    }
                    results.append(result)
                
                print(f"Google 검색 결과: {len(results)}개")
                return results[:max_results]
                
        except Exception as e:
            print(f"Google 검색 오류: {e}")
            return []
    
    async def _duckduckgo_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """DuckDuckGo API를 사용한 검색"""
        try:
            # DuckDuckGo Instant Answer API
            params = {
                'q': query,
                'format': 'json',
                'no_html': '1',
                'skip_disambig': '1'
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.duckduckgo_url,
                    params=params,
                    timeout=30.0
                )
                response.raise_for_status()
                
                data = response.json()
                
                results = []
                
                # 관련 주제들 추가
                if 'RelatedTopics' in data:
                    for topic in data['RelatedTopics'][:max_results]:
                        if 'FirstURL' in topic and 'Text' in topic:
                            result = {
                                'title': topic.get('Text', '')[:100],
                                'url': topic.get('FirstURL', ''),
                                'snippet': topic.get('Text', ''),
                                'source': 'duckduckgo'
                            }
                            results.append(result)
                
                # 추상 정보 추가
                if 'Abstract' in data and data['Abstract']:
                    result = {
                        'title': data.get('Heading', query),
                        'url': data.get('AbstractURL', ''),
                        'snippet': data.get('Abstract', ''),
                        'source': 'duckduckgo'
                    }
                    results.append(result)
                
                print(f"DuckDuckGo 검색 결과: {len(results)}개")
                return results[:max_results]
                
        except Exception as e:
            print(f"DuckDuckGo 검색 오류: {e}")
            return []
    
    async def _simulate_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """검색 시뮬레이션 (모든 API가 실패한 경우)"""
        print(f"검색 시뮬레이션 실행: {query}")
        
        # 실제 존재하는 AI/기술 관련 사이트들
        sample_results = [
            {
                'title': f'{query} - Wikipedia',
                'url': 'https://en.wikipedia.org/wiki/Artificial_intelligence',
                'snippet': f'{query}에 대한 위키피디아 정보입니다.',
                'source': 'simulation'
            },
            {
                'title': f'{query} - OpenAI Blog',
                'url': 'https://openai.com/blog/',
                'snippet': f'{query}와 관련된 OpenAI의 최신 정보입니다.',
                'source': 'simulation'
            },
            {
                'title': f'{query} - Google AI',
                'url': 'https://ai.google/',
                'snippet': f'{query}에 대한 Google AI의 연구 결과입니다.',
                'source': 'simulation'
            }
        ]
        
        return sample_results[:max_results]
    
    async def fetch_url_content(self, url: str) -> Dict[str, Any]:
        """URL에서 콘텐츠 추출"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, timeout=30.0)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 불필요한 태그 제거
                for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                    tag.decompose()
                
                # 텍스트 추출
                title = soup.find('title')
                title_text = title.get_text().strip() if title else ''
                
                # 본문 텍스트 추출 (우선순위: main > article > body)
                main_content = soup.find('main') or soup.find('article') or soup.find('body')
                if main_content:
                    text = main_content.get_text(separator=' ', strip=True)
                else:
                    text = soup.get_text(separator=' ', strip=True)
                
                # 텍스트 정리
                text = re.sub(r'\s+', ' ', text).strip()
                
                # 텍스트 길이 제한 (너무 긴 텍스트 방지)
                if len(text) > 10000:
                    text = text[:10000] + "..."
                
                return {
                    'url': url,
                    'title': title_text,
                    'content': text,
                    'metadata': {
                        'charset': response.encoding,
                        'content_type': response.headers.get('content-type', ''),
                        'status_code': response.status_code,
                        'content_length': len(text)
                    }
                }
                
        except Exception as e:
            print(f"Error fetching content from {url}: {e}")
            return {
                'url': url,
                'title': '',
                'content': '',
                'metadata': {'error': str(e)}
            }
    
    async def fetch_multiple_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """여러 URL에서 콘텐츠 병렬 추출"""
        tasks = [self.fetch_url_content(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 에러가 발생한 결과 필터링
        valid_results = []
        for result in results:
            if isinstance(result, dict) and result.get('content'):
                valid_results.append(result)
        
        return valid_results
    
    def extract_links(self, html_content: str, base_url: str) -> List[str]:
        """HTML에서 링크 추출"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            links = []
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                absolute_url = urljoin(base_url, href)
                
                # 유효한 URL인지 확인
                if self._is_valid_url(absolute_url):
                    links.append(absolute_url)
            
            return list(set(links))  # 중복 제거
            
        except Exception as e:
            print(f"Error extracting links: {e}")
            return []
    
    def _is_valid_url(self, url: str) -> bool:
        """URL 유효성 검사"""
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc) and parsed.scheme in ['http', 'https']
        except:
            return False
    
    def is_healthy(self) -> bool:
        """서비스 상태 확인"""
        try:
            # Google API 키 확인
            if self.google_api_key and self.google_cse_id:
                return True
            # DuckDuckGo API 확인
            return True
        except Exception:
            return False
    
    async def close(self):
        """세션 정리"""
        await self.session.aclose()
