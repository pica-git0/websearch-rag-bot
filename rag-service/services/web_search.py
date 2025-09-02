import requests
from bs4 import BeautifulSoup
import httpx
from typing import List, Dict, Any
import os
import re
from urllib.parse import urljoin, urlparse
import asyncio
import json
import openai

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
        

        
        # OpenAI API 설정
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if self.openai_api_key:
            openai.api_key = self.openai_api_key
        
        # 검색어 전처리 및 대체 검색어 매핑
        self.query_mappings = {
            'llm': ['LLM', 'large language model', 'AI 모델'],
            '응답': ['response', 'answer', '답변'],
            '완성': ['complete', 'finish', '완성'],
            '시장': ['market', 'trading', '주식'],
            '주식': ['stock', 'investment', '투자']
        }
    
    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """웹 검색 수행 - Google Custom Search API 우선, 대체로 검색 시뮬레이션 사용"""
        try:
            # Google Custom Search API 사용 시도
            if self.google_api_key and self.google_cse_id:
                print(f"Google Custom Search API 사용: {query}")
                search_results = await self._google_search(query, max_results)
                if search_results:
                    return search_results
            
            # Google API가 없거나 실패한 경우 검색 시뮬레이션 사용
            print(f"검색 시뮬레이션 사용: {query}")
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
        
        # 검색어가 너무 길면 핵심 키워드만 추출
        if len(cleaned_query) > 50:
            # 한국어 단어들을 추출하고 상위 3-4개만 사용
            korean_words = re.findall(r'[가-힣]{2,}', cleaned_query)
            if len(korean_words) > 3:
                cleaned_query = ' '.join(korean_words[:3])
                print(f"검색어 길이 제한: '{query}' -> '{cleaned_query}'")
        
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
    
    async def _create_fallback_query(self, query: str) -> str:
        """대체 검색어 생성: GPT API를 사용하여 더 일반적인 키워드로 변경"""
        try:
            # OpenAI API가 설정되어 있으면 GPT를 사용
            if self.openai_api_key:
                print(f"GPT API를 사용하여 대체 검색어 생성: {query}")
                
                # GPT에게 검색어를 일반적인 키워드로 변환하도록 요청
                prompt = f"""
                다음 검색어를 웹 검색에 적합한 일반적인 키워드로 변환해주세요.
                검색어: "{query}"
                
                요구사항:
                1. 원래 의미를 유지하면서 더 일반적이고 검색하기 쉬운 키워드로 변환
                2. 한국어와 영어 키워드를 모두 포함 (한국어 우선)
                3. 3-5개의 핵심 키워드만 제공
                4. 검색 엔진에서 잘 찾을 수 있는 일반적인 용어 사용
                5. 전문 용어는 쉬운 동의어로 변환
                6. 잘 모르겠으면 기존 검색어 그대로 사용
                
                예시:
                - "고급 AI 모델" → "AI 모델 인공지능 머신러닝"
                - "복잡한 알고리즘" → "알고리즘 프로그래밍 코딩"
                
                변환된 키워드만 출력하세요 (설명 없이):
                """
                
                # 최신 OpenAI API 사용
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_api_key)
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "당신은 검색어 최적화 전문가입니다. 검색어를 웹 검색에 적합한 일반적인 키워드로 변환합니다."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=100,
                    temperature=0.3
                )
                
                if response.choices and response.choices[0].message:
                    fallback_query = response.choices[0].message.content.strip()
                    print(f"GPT 대체 검색어 생성: '{query}' -> '{fallback_query}'")
                    return fallback_query
                else:
                    print("GPT API 응답이 비어있습니다. 기본 방식으로 대체 검색어 생성")
            
        except Exception as e:
            print(f"GPT API 오류: {e}. 기본 방식으로 대체 검색어 생성")
        
        # GPT API가 없거나 실패한 경우 기본 방식 사용
        print("기본 방식으로 대체 검색어 생성")
        fallback_parts = []
        for korean_word, english_list in self.query_mappings.items():
            if korean_word in query:
                fallback_parts.append(english_list[0])  # 첫 번째 영어 키워드 사용
        
        if fallback_parts:
            fallback_query = ' '.join(fallback_parts)
            print(f"기본 대체 검색어 생성: '{query}' -> '{fallback_query}'")
            return fallback_query
        
        # 한국어 키워드가 없으면 일반적인 검색어로
        # 원본 검색어에서 핵심 단어 추출 시도
        core_words = re.findall(r'[가-힣]{2,}', query)
        if core_words:
            # 상위 2개 단어만 사용
            fallback_query = ' '.join(core_words[:2])
            print(f"핵심 단어 추출: '{query}' -> '{fallback_query}'")
            return fallback_query
        
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
                    fallback_query = await self._create_fallback_query(query)
                    if fallback_query != query:
                        print(f"대체 검색어로 재시도: {fallback_query}")
                        return await self._google_search(fallback_query, max_results)
                    return []
                
                results = []
                print(f"🔍 Google 검색 결과 URL들:")
                for i, item in enumerate(data['items']):
                    result = {
                        'title': item.get('title', ''),
                        'url': item.get('link', ''),
                        'snippet': item.get('snippet', ''),
                        'source': 'google'
                    }
                    results.append(result)
                    
                    # URL을 콘솔에 출력 (개발 환경 모니터링용)
                    print(f"  [{i+1}] {result['url']}")
                    print(f"      제목: {result['title'][:80]}...")
                
                print(f"✅ Google 검색 완료: 총 {len(results)}개 결과")
                return results[:max_results]
                
        except Exception as e:
            print(f"Google 검색 오류: {e}")
            return []
    

    
    async def _simulate_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """검색 시뮬레이션 (모든 API가 실패한 경우)"""
        print(f"🔍 검색 시뮬레이션 실행: {query}")
        
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
        
        # URL을 콘솔에 출력 (개발 환경 모니터링용)
        print(f"🔍 시뮬레이션 검색 결과 URL들:")
        for i, result in enumerate(sample_results[:max_results]):
            print(f"  [{i+1}] {result['url']}")
            print(f"      제목: {result['title'][:80]}...")
        
        print(f"✅ 시뮬레이션 검색 완료: 총 {len(sample_results[:max_results])}개 결과")
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
            # Google API가 없으면 시뮬레이션 사용
            return False
        except Exception:
            return False
    
    async def close(self):
        """세션 정리"""
        await self.session.aclose()

    async def classify_search_query(self, query: str) -> Dict[str, Any]:
        """검색어를 분류하여 적절한 검색 전략 결정"""
        try:
            classification_prompt = f"""
다음 검색어를 분석하여 분류해주세요:

검색어: "{query}"

분류 카테고리:
1. 사람 (person): 인물, 유명인, 전문가, 일반인
2. 동물 (animal): 동물, 생물, 반려동물
3. 추상적 개념 (concept): 아이디어, 이론, 철학, 감정, 상태
4. 기업/조직 (organization): 회사, 단체, 정부기관, NGO
5. 사물/제품 (object): 물건, 제품, 도구, 장비
6. 장소 (location): 지역, 국가, 도시, 건물
7. 이벤트 (event): 행사, 축제, 경기, 회의
8. 기타 (other): 위 카테고리에 속하지 않는 것

분류 결과를 JSON 형식으로 출력하세요:
{{
    "category": "카테고리명",
    "confidence": 0.95,
    "subcategory": "세부분류",
    "search_strategy": "검색 전략",
    "keywords": ["추가 키워드1", "추가 키워드2"]
}}
"""

            # OpenAI API를 사용하여 분류
            if self.openai_api_key:
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=self.openai_api_key)
                    
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "당신은 검색어 분류 전문가입니다. 정확하고 일관된 분류를 제공합니다."},
                            {"role": "user", "content": classification_prompt}
                        ],
                        max_tokens=200,
                        temperature=0.1
                    )
                    
                    if response.choices and response.choices[0].message:
                        result_text = response.choices[0].message.content.strip()
                        # JSON 파싱 시도
                        try:
                            import json
                            classification = json.loads(result_text)
                            print(f"🔍 검색어 분류 결과: {query} -> {classification['category']} (신뢰도: {classification['confidence']})")
                            return classification
                        except json.JSONDecodeError:
                            print(f"JSON 파싱 실패, 기본 분류 사용: {result_text}")
                
                except Exception as e:
                    print(f"GPT 분류 실패: {e}, 기본 분류 사용")
            
        except Exception as e:
            print(f"검색어 분류 중 오류: {e}")
        
        # 기본 분류 (GPT API 실패 시)
        return self._basic_query_classification(query)
    
    def _basic_query_classification(self, query: str) -> Dict[str, Any]:
        """기본 규칙 기반 검색어 분류"""
        query_lower = query.lower()
        
        # 사람 분류
        person_patterns = [
            r'[가-힣]{2,3}',  # 한국어 이름 (2-3글자)
            r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',  # 영어 이름
            r'씨$|님$|군$|양$',  # 호칭
            r'가수|배우|연예인|정치인|기업인|학자|의사|변호사'
        ]
        
        # 동물 분류
        animal_patterns = [
            r'강아지|고양이|개|새|물고기|토끼|햄스터|거북이|고래|사자|호랑이|코끼리',
            r'dog|cat|bird|fish|rabbit|hamster|turtle|whale|lion|tiger|elephant',
            r'동물|생물|반려동물|야생동물|애완동물'
        ]
        
        # 기업/조직 분류
        organization_patterns = [
            r'회사|기업|그룹|주식회사|㈜|㈐|corporation|company|inc|corp|ltd',
            r'정부|청|부|처|기관|협회|재단|재단법인|사단법인',
            r'학교|대학교|초등학교|중학교|고등학교|university|college|school'
        ]
        
        # 장소 분류
        location_patterns = [
            r'서울|부산|대구|인천|광주|대전|울산|제주|경기|강원|충북|충남|전북|전남|경북|경남',
            r'한국|일본|중국|미국|영국|프랑스|독일|korea|japan|china|usa|uk|france|germany',
            r'시|군|구|동|읍|면|도|국|city|country|state|province'
        ]
        
        # 이벤트 분류
        event_patterns = [
            r'축제|행사|경기|대회|회의|컨퍼런스|세미나|워크샵|festival|event|game|conference|seminar'
        ]
        
        # 사물/제품 분류
        object_patterns = [
            r'폰|휴대폰|스마트폰|컴퓨터|노트북|태블릿|phone|smartphone|computer|laptop|tablet',
            r'자동차|차|버스|기차|비행기|car|bus|train|airplane',
            r'책|영화|음악|게임|book|movie|music|game'
        ]
        
        # 추상적 개념 분류
        concept_patterns = [
            r'사랑|행복|슬픔|기쁨|분노|사랑|우정|가족|love|happiness|sadness|joy|anger|friendship|family',
            r'민주주의|자유|평등|정의|democracy|freedom|equality|justice',
            r'예술|철학|과학|기술|art|philosophy|science|technology'
        ]
        
        # 패턴 매칭으로 분류
        if any(re.search(pattern, query_lower) for pattern in person_patterns):
            return {
                "category": "person",
                "confidence": 0.8,
                "subcategory": "인물",
                "search_strategy": "인물 정보 검색",
                "keywords": ["프로필", "경력", "수상", "활동"]
            }
        elif any(re.search(pattern, query_lower) for pattern in animal_patterns):
            return {
                "category": "animal",
                "confidence": 0.8,
                "subcategory": "동물",
                "search_strategy": "동물 정보 검색",
                "keywords": ["특징", "습성", "사육법", "정보"]
            }
        elif any(re.search(pattern, query_lower) for pattern in organization_patterns):
            return {
                "category": "organization",
                "confidence": 0.8,
                "subcategory": "기업/조직",
                "search_strategy": "기업 정보 검색",
                "keywords": ["회사 정보", "사업", "연혁", "뉴스"]
            }
        elif any(re.search(pattern, query_lower) for pattern in location_patterns):
            return {
                "category": "location",
                "confidence": 0.8,
                "subcategory": "장소",
                "search_strategy": "지역 정보 검색",
                "keywords": ["관광", "역사", "문화", "정보"]
            }
        elif any(re.search(pattern, query_lower) for pattern in event_patterns):
            return {
                "category": "event",
                "confidence": 0.8,
                "subcategory": "이벤트",
                "search_strategy": "이벤트 정보 검색",
                "keywords": ["일정", "장소", "참가", "정보"]
            }
        elif any(re.search(pattern, query_lower) for pattern in object_patterns):
            return {
                "category": "object",
                "confidence": 0.8,
                "subcategory": "사물/제품",
                "search_strategy": "제품 정보 검색",
                "keywords": ["스펙", "가격", "리뷰", "구매"]
            }
        elif any(re.search(pattern, query_lower) for pattern in concept_patterns):
            return {
                "category": "concept",
                "confidence": 0.8,
                "subcategory": "추상적 개념",
                "search_strategy": "개념 정보 검색",
                "keywords": ["정의", "예시", "관련", "정보"]
            }
        else:
            return {
                "category": "other",
                "confidence": 0.5,
                "subcategory": "기타",
                "search_strategy": "일반 정보 검색",
                "keywords": ["정보", "뉴스", "최신", "트렌드"]
            }
