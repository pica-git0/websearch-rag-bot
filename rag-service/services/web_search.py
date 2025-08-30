import requests
from bs4 import BeautifulSoup
import httpx
from typing import List, Dict, Any
import os
import re
from urllib.parse import urljoin, urlparse
import asyncio

class WebSearchService:
    def __init__(self):
        self.session = httpx.AsyncClient(timeout=30.0)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """웹 검색 수행"""
        try:
            # 간단한 웹 검색 시뮬레이션 (실제로는 Google Custom Search API 등을 사용)
            # 여기서는 예시 URL들을 반환
            search_results = await self._simulate_search(query, max_results)
            return search_results
        except Exception as e:
            print(f"Error in web search: {e}")
            return []
    
    async def _simulate_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """검색 시뮬레이션 (실제 구현에서는 검색 API 사용)"""
        # 예시 검색 결과
        sample_results = [
            {
                'title': f'검색 결과: {query}',
                'url': 'https://example.com/result1',
                'snippet': f'{query}에 대한 정보를 찾을 수 있습니다.'
            },
            {
                'title': f'{query} 관련 정보',
                'url': 'https://example.com/result2',
                'snippet': f'{query}와 관련된 다양한 자료들이 있습니다.'
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
                for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                    tag.decompose()
                
                # 텍스트 추출
                title = soup.find('title')
                title_text = title.get_text().strip() if title else ''
                
                # 본문 텍스트 추출
                main_content = soup.find('main') or soup.find('article') or soup.find('body')
                if main_content:
                    text = main_content.get_text(separator=' ', strip=True)
                else:
                    text = soup.get_text(separator=' ', strip=True)
                
                # 텍스트 정리
                text = re.sub(r'\s+', ' ', text).strip()
                
                return {
                    'url': url,
                    'title': title_text,
                    'content': text,
                    'metadata': {
                        'charset': response.encoding,
                        'content_type': response.headers.get('content-type', ''),
                        'status_code': response.status_code
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
            # 간단한 연결 테스트
            return True
        except Exception:
            return False
    
    async def close(self):
        """세션 정리"""
        await self.session.aclose()
