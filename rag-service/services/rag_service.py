from langchain_openai import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Qdrant
from langchain_community.document_loaders import WebBaseLoader
from langchain.schema import Document
import os
import uuid
from typing import List, Dict, Any, Tuple
import asyncio
import re

from dotenv import load_dotenv


load_dotenv()  
class RAGService:
    def __init__(self, vector_store, web_search):
        self.vector_store = vector_store
        self.web_search = web_search
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # LLM 초기화
        if self.openai_api_key:
            self.llm = ChatOpenAI(
                temperature=0.7,
                model="gpt-4o-mini"
            )
        else:
            # OpenAI API 키가 없을 경우 대체 LLM 사용
            self.llm = self._create_fallback_llm()
        
        # 대화 메모리
        self.conversation_memories = {}
        
        # 텍스트 분할기
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        
        # 대화별 벡터 스토어 캐시
        self.conversation_vector_stores = {}
    
    def _create_fallback_llm(self):
        """대체 LLM 생성 (OpenAI API 키가 없을 경우)"""
        class FallbackLLM:
            def __call__(self, prompt: str) -> str:
                # 간단한 응답 생성
                return f"죄송합니다. 현재 OpenAI API 키가 설정되지 않아 완전한 응답을 제공할 수 없습니다. 질문: {prompt}"
        
        return FallbackLLM()
    
    def _get_conversation_collection_name(self, conversation_id: str) -> str:
        """대화별 단기기억 콜렉션 이름 생성"""
        return f"conversation_{conversation_id.replace('-', '_')}"
    
    def _get_long_term_memory_collection_name(self, conversation_id: str) -> str:
        """장기기억 콜렉션 이름 생성 (대화별 분리)
        
        각 대화마다 별도의 장기기억 콜렉션을 생성하여:
        - 대화별로 독립적인 메모리 관리
        - 다른 대화와의 정보 혼재 방지
        - 대화별 컨텍스트 유지
        """
        return f"long_term_memory_{conversation_id.replace('-', '_')}"
    
    async def _ensure_conversation_collection(self, conversation_id: str) -> Qdrant:
        """대화별 단기기억 콜렉션이 존재하는지 확인하고 없으면 생성"""
        collection_name = self._get_conversation_collection_name(conversation_id)
        
        if collection_name not in self.conversation_vector_stores:
            try:
                # 기존 콜렉션이 있는지 확인
                collections = self.vector_store.client.get_collections()
                collection_exists = any(col.name == collection_name for col in collections.collections)
                
                if collection_exists:
                    print(f"기존 단기기억 콜렉션 사용: {collection_name}")
                else:
                    # 콜렉션이 없으면 생성
                    print(f"새 단기기억 콜렉션 생성: {collection_name}")
                    
                    # OpenAI embeddings 사용 시 1536차원, 그렇지 않으면 384차원
                    vector_size = 1536 if self.openai_api_key else 384
                    
                    self.vector_store.client.create_collection(
                        collection_name,
                        vectors_config={
                            "size": vector_size,
                            "distance": "Cosine"
                        }
                    )
            except Exception as e:
                print(f"단기기억 콜렉션 확인/생성 오류: {e}")
                # 오류 발생 시 기본 콜렉션 사용
                return self.vector_store
            
            # 대화별 벡터 스토어 생성
            self.conversation_vector_stores[collection_name] = Qdrant(
                client=self.vector_store.client,
                collection_name=collection_name,
                embeddings=OpenAIEmbeddings() if self.openai_api_key else None
            )
        
        return self.conversation_vector_stores[collection_name]
    
    async def _ensure_long_term_memory_collection(self, conversation_id: str) -> Qdrant:
        """장기기억 콜렉션이 존재하는지 확인하고 없으면 생성 (대화별 분리)"""
        collection_name = self._get_long_term_memory_collection_name(conversation_id)
        
        if collection_name not in self.conversation_vector_stores:
            try:
                # 기존 콜렉션이 있는지 확인
                collections = self.vector_store.client.get_collections()
                collection_exists = any(col.name == collection_name for col in collections.collections)
                
                if collection_exists:
                    print(f"기존 장기기억 콜렉션 사용: {collection_name}")
                else:
                    # 콜렉션이 없으면 생성
                    print(f"새 장기기억 콜렉션 생성: {collection_name}")
                    
                    # OpenAI embeddings 사용 시 1536차원, 그렇지 않으면 384차원
                    vector_size = 1536 if self.openai_api_key else 384
                    
                    self.vector_store.client.create_collection(
                        collection_name,
                        vectors_config={
                            "size": vector_size,
                            "distance": "Cosine"
                        }
                    )
            except Exception as e:
                print(f"장기기억 콜렉션 확인/생성 오류: {e}")
                # 오류 발생 시 기본 콜렉션 사용
                return self.vector_store
            
            # 장기기억 벡터 스토어 생성
            self.conversation_vector_stores[collection_name] = Qdrant(
                client=self.vector_store.client,
                collection_name=collection_name,
                embeddings=OpenAIEmbeddings() if self.openai_api_key else None
            )
        
        return self.conversation_vector_stores[collection_name]
    
    def _should_use_web_search(self, message: str) -> bool:
        """메시지 내용을 분석하여 웹 검색이 필요한지 판단"""
        message_lower = message.lower()
        
        # 웹 검색이 필요한 키워드들
        web_search_keywords = [
            '최신', '최근', '현재', '오늘', '어제', '이번 주', '이번 달', '올해',
            '검색', '찾아', '찾기', '검색해', '검색해줘', '검색해주세요',
            '뉴스', '소식', '정보', '업데이트', '변경사항', '새로운',
            '가격', '시세', '환율', '주식', '날씨', '교통', '지도',
            '위치', '주소', '전화번호', '영업시간', '리뷰', '평점',
            '비교', '추천', '랭킹', '순위', '인기', '트렌드',
            '사실', '진실', '확인', '검증', '정확한', '정확히',
            '언제', '어디서', '누가', '무엇을', '어떻게', '왜',
            '도구', 'tool', 'search', 'find', 'latest', 'current', 'recent',
            'news', 'information', 'update', 'price', 'weather', 'location'
        ]
        
        # 한국어와 영어 키워드 모두 확인
        for keyword in web_search_keywords:
            if keyword in message_lower:
                return True
        
        # 특정 질문 패턴 확인
        question_patterns = [
            '무엇', '뭐', '어떤', '어떻게', '왜', '언제', '어디서', '누가',
            'what', 'how', 'why', 'when', 'where', 'who', 'which'
        ]
        
        for pattern in question_patterns:
            if pattern in message_lower:
                return True
        
        # 명령형 표현 확인
        command_patterns = [
            '검색해', '찾아', '알려', '보여', '가져와', '가져와줘',
            'search', 'find', 'show', 'tell', 'get', 'bring'
        ]
        
        for pattern in command_patterns:
            if pattern in message_lower:
                return True
        
        return False

    async def chat(self, message: str, conversation_id: str = None, use_web_search: bool = True) -> Tuple[str, List[str], str, Dict[str, int]]:
        """챗봇 대화 처리 - 대화별 콜렉션에 저장"""
        try:
            # 빈 메시지 체크
            if not message or not message.strip():
                empty_context_info = {
                    'shortTermMemory': 0,
                    'longTermMemory': 0,
                    'webSearch': 0
                }
                return "검색어가 없습니다. 구체적인 질문이나 검색하고 싶은 내용을 입력해주세요.", [], conversation_id or str(uuid.uuid4()), empty_context_info
            
            # 대화 ID 생성
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # 대화 메모리 초기화
            if conversation_id not in self.conversation_memories:
                self.conversation_memories[conversation_id] = ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=True
                )
            
            memory = self.conversation_memories[conversation_id]
            
            # 대화별 콜렉션 확인/생성
            conversation_vector_store = await self._ensure_conversation_collection(conversation_id)
            
            # 웹 검색 필요성 판단
            should_search = use_web_search and self._should_use_web_search(message)
            
            # 1단계: 웹 검색 수행 (필요한 경우에만)
            sources = []
            if should_search:
                print(f"웹 검색 수행 중: {message}")
                search_results = await self.web_search.search(message, max_results=5)
                
                # 2단계: 검색 결과를 대화별 콜렉션에 저장
                for result in search_results:
                    if result.get('url'):
                        try:
                            # URL에서 콘텐츠 추출
                            content = await self.web_search.fetch_url_content(result['url'])
                            if content.get('content'):
                                # 텍스트 분할
                                documents = self.text_splitter.split_text(content['content'])
                                
                                # 벡터 스토어에 추가 (대화별 콜렉션)
                                doc_objects = []
                                for i, doc_text in enumerate(documents):
                                    doc_objects.append(Document(
                                        page_content=doc_text,
                                        metadata={
                                            'url': result['url'],
                                            'title': content.get('title', ''),
                                            'chunk_index': i,
                                            'total_chunks': len(documents),
                                            'source_url': result['url'],
                                            'search_query': message,
                                            'conversation_id': conversation_id,
                                            'timestamp': asyncio.get_event_loop().time()
                                        }
                                    ))
                                
                                # 대화별 콜렉션에 저장
                                conversation_vector_store.add_documents(doc_objects)
                                sources.append(result['url'])
                                print(f"URL 인덱싱 완료: {result['url']} -> {self._get_conversation_collection_name(conversation_id)}")
                        except Exception as e:
                            print(f"URL 인덱싱 실패 {result['url']}: {e}")
                            continue
            else:
                print(f"웹 검색 건너뛰기: {message} (로컬 메모리만 사용)")
            
            # 3단계: 단기기억 → 장기기억 → 웹검색 순으로 컨텍스트 수집
            print(f"컨텍스트 수집 중: {message}")
            
            # 3-1: 단기기억 (현재 대화)에서 검색
            short_term_context = []
            try:
                print(f"단기기억 검색 시작: {self._get_conversation_collection_name(conversation_id)}")
                short_term_results = conversation_vector_store.similarity_search(message, k=3)
                short_term_context = [result for result in short_term_results if hasattr(result, 'page_content') and result.page_content]
                print(f"단기기억에서 {len(short_term_context)}개 문서 검색 완료")
            except Exception as e:
                print(f"단기기억 검색 실패: {e}")
                print(f"단기기억 벡터 스토어 상태: {type(conversation_vector_store)}")
                short_term_context = []
            
            # 3-2: 장기기억 (대화별 히스토리)에서 검색
            long_term_context = []
            try:
                print(f"장기기억 검색 시작: {self._get_long_term_memory_collection_name(conversation_id)}")
                long_term_vector_store = await self._ensure_long_term_memory_collection(conversation_id)
                long_term_results = long_term_vector_store.similarity_search(message, k=3)
                long_term_context = [result for result in long_term_results if hasattr(result, 'page_content') and result.page_content]
                print(f"장기기억에서 {len(long_term_context)}개 문서 검색 완료")
            except Exception as e:
                print(f"장기기억 검색 실패: {e}")
                print(f"장기기억 벡터 스토어 상태: {type(long_term_vector_store) if 'long_term_vector_store' in locals() else 'Not created'}")
                long_term_context = []
            
            # 3-3: 웹검색 결과를 현재 대화에 저장 (이미 수행됨)
            web_search_context = []
            if sources:
                web_search_context = [f"웹검색 결과: {len(sources)}개 URL에서 정보 수집됨"]
                print(f"웹검색에서 {len(sources)}개 소스 수집")
            
            # 4단계: 통합 컨텍스트 생성 (우선순위: 단기기억 > 장기기억 > 웹검색)
            all_context_docs = []
            
            # 단기기억 우선 (가장 관련성 높음)
            for result in short_term_context:
                all_context_docs.append(result)
                if hasattr(result, 'metadata') and result.metadata.get('url') and result.metadata.get('url') not in sources:
                    sources.append(result.metadata.get('url'))
            
            # 장기기억 추가 (중간 관련성)
            for result in long_term_context:
                all_context_docs.append(result)
                if hasattr(result, 'metadata') and result.metadata.get('url') and result.metadata.get('url') not in sources:
                    sources.append(result.metadata.get('url'))
            
            # 컨텍스트 생성
            context = self._create_context(all_context_docs)
            print(f"통합 컨텍스트: 단기기억 {len(short_term_context)}개, 장기기억 {len(long_term_context)}개, 웹검색 {len(web_search_context)}개")
            
            # 검색 결과가 없을 때 기본 정보 제공
            if not all_context_docs and not sources:
                print("검색 결과가 없어 기본 AI 정보를 제공합니다.")
                context = self._get_default_ai_context(message)
            
            # 5단계: 프롬프트 생성 및 LLM 응답
            prompt = self._create_prompt(
                message, 
                context, 
                short_term_count=len(short_term_context),
                long_term_count=len(long_term_context),
                web_search_count=len(sources),
                chat_history=memory.chat_memory.messages # 대화 히스토리 전달
            )
            
            print("LLM 응답 생성 중...")
            if hasattr(self.llm, 'invoke'):
                # 최신 LangChain API
                response = self.llm.invoke(prompt)
                if hasattr(response, 'content'):
                    response = response.content
            else:
                # 구버전 호환성
                response = self.llm(prompt)
            
            # 대화 메모리에 저장
            memory.chat_memory.add_user_message(message)
            memory.chat_memory.add_ai_message(response)
            
            # 6단계: 현재 대화를 장기기억에 저장
            await self._save_to_long_term_memory(conversation_id, message, response, sources)
            
            # 컨텍스트 정보 생성
            context_info = {
                'shortTermMemory': len(short_term_context),
                'longTermMemory': len(long_term_context),
                'webSearch': len(sources)
            }
            
            return response, sources, conversation_id, context_info
            
        except Exception as e:
            print(f"챗봇 처리 오류: {e}")
            error_context_info = {
                'shortTermMemory': 0,
                'longTermMemory': 0,
                'webSearch': 0
            }
            return f"죄송합니다. 처리 중 오류가 발생했습니다: {str(e)}", [], conversation_id or str(uuid.uuid4()), error_context_info
    
    def _create_context(self, documents: List[Document]) -> str:
        """문서들로부터 컨텍스트 생성"""
        if not documents:
            return ""
        
        context_parts = []
        for doc in documents:
            content = doc.page_content
            title = doc.metadata.get('title', '')
            url = doc.metadata.get('url', '')
            
            if content:
                context_part = f"제목: {title}\nURL: {url}\n내용: {content[:800]}...\n"
                context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _create_prompt(self, message: str, context: str, short_term_count: int = 0, long_term_count: int = 0, web_search_count: int = 0, chat_history: List = None) -> str:
        """프롬프트 생성 - 대화 히스토리와 컨텍스트를 포함하여 맥락 의존적 질문 처리"""
        
        # 대화 히스토리 처리
        chat_history_text = ""
        if chat_history and len(chat_history) > 0:
            chat_history_text = "\n=== 이전 대화 내용 ===\n"
            for i, msg in enumerate(chat_history[-6:], 1):  # 최근 6개 메시지만 포함
                if hasattr(msg, 'content'):
                    role = "사용자" if hasattr(msg, 'type') and msg.type == 'human' else "AI"
                    chat_history_text += f"{i}. {role}: {msg.content}\n"
            chat_history_text += "==================\n"
        
        if context:
            context_summary = f"""
=== 컨텍스트 정보 ===
- 단기기억 (현재 대화): {short_term_count}개 문서
- 장기기억 (이전 대화 내용): {long_term_count}개 문서  
- 웹검색 결과: {web_search_count}개 소스
==================

{context}"""
            
            prompt = f"""당신은 사용자와 자연스럽게 대화하는 AI 어시스턴트입니다. 
이전 대화 내용과 현재 컨텍스트를 바탕으로 사용자의 질문에 답변해주세요.

{chat_history_text}

{context_summary}

사용자 질문: {message}

답변 지침:
1. **대화 맥락 파악**: 이전 대화 내용을 먼저 확인하여 사용자가 무엇을 언급했는지 파악하세요
2. **맥락 의존적 질문 처리**: "그거", "이것", "저것" 등의 대명사가 나오면 이전 대화에서 언급된 내용을 참고하세요
3. **정보 우선순위**: 단기기억(현재 대화) > 장기기억(이전 대화) > 웹검색 결과 순으로 정보를 활용하세요
4. **자연스러운 대화**: 이전 대화와 연결되는 자연스러운 답변을 제공하세요
5. **정보 보완**: 정보가 부족하다면 웹검색을 통해 최신 정보를 보완하세요
6. **한국어 답변**: 한국어로 친근하고 이해하기 쉽게 답변해주세요
7. **출처 명시**: 참고한 정보의 출처를 간단히 언급해주세요

답변:"""
        else:
            prompt = f"""당신은 사용자와 자연스럽게 대화하는 AI 어시스턴트입니다.

{chat_history_text}

사용자 질문: {message}

이전 대화 내용을 참고하여 사용자의 질문에 답변해주세요. 
대화 맥락을 유지하고 자연스럽게 대화를 이어가세요. 한국어로 답변해주세요."""
        
        return prompt
    
    def _get_default_ai_context(self, message: str) -> str:
        """검색 결과가 없을 때 기본 AI 정보 제공"""
        return "검색어가 없습니다. 구체적인 질문이나 검색하고 싶은 내용을 입력해주세요."
    
    def _create_structured_prompt(self, message: str, context: str, chat_history: List = None) -> str:
        """구조화된 분석 답변을 위한 프롬프트 생성"""
        
        # 대화 히스토리 처리
        chat_history_text = ""
        if chat_history and len(chat_history) > 0:
            chat_history_text = "\n=== 이전 대화 내용 ===\n"
            for i, msg in enumerate(chat_history[-6:], 1):  # 최근 6개 메시지만 포함
                if hasattr(msg, 'content'):
                    role = "사용자" if hasattr(msg, 'type') and msg.type == 'human' else "AI"
                    chat_history_text += f"{i}. {role}: {msg.content}\n"
            chat_history_text += "==================\n"
        
        structured_prompt = f"""당신은 정보를 체계적으로 분석하고 구조화된 답변을 제공하는 전문가입니다.

{chat_history_text}

사용자 질문: {message}

{context}

다음 형식으로 구조화된 분석 답변을 생성하세요:

## 📋 핵심 요약
[2-3문장으로 핵심 내용 요약]

## 🔍 세부 분석
### [첫 번째 주제/요인]
[구체적인 설명과 예시, 데이터 포함]

### [두 번째 주제/요인]
[구체적인 설명과 예시, 데이터 포함]

### [세 번째 주제/요인] (필요한 경우)
[구체적인 설명과 예시, 데이터 포함]

## 💡 결론 및 인사이트
[핵심 포인트와 향후 전망, 트렌드 분석]

답변 시 다음 사항을 준수하세요:
- 불릿 포인트(•) 활용하여 가독성 향상
- 구체적인 데이터, 통계, 예시 포함
- 사용자 친화적이고 이해하기 쉬운 언어 사용
- 논리적 구조와 흐름 유지
- 한국어로 답변
- 참고한 정보의 출처를 간단히 언급

답변:"""
        
        return structured_prompt
    
    async def generate_structured_response(self, message: str, conversation_id: str = None, use_web_search: bool = True) -> Tuple[str, List[str], str, Dict[str, int]]:
        """구조화된 분석 답변 생성 - 체계적이고 분석적인 답변 제공"""
        try:
            # 빈 메시지 체크
            if not message or not message.strip():
                empty_context_info = {
                    'shortTermMemory': 0,
                    'longTermMemory': 0,
                    'webSearch': 0
                }
                return "검색어가 없습니다. 구체적인 질문이나 검색하고 싶은 내용을 입력해주세요.", [], conversation_id or str(uuid.uuid4()), empty_context_info
            
            # 대화 ID 생성
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # 대화 메모리 초기화
            if conversation_id not in self.conversation_memories:
                self.conversation_memories[conversation_id] = ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=True
                )
            
            memory = self.conversation_memories[conversation_id]
            
            # 대화별 콜렉션 확인/생성
            conversation_vector_store = await self._ensure_conversation_collection(conversation_id)
            
            # 웹 검색 필요성 판단
            should_search = use_web_search and self._should_use_web_search(message)
            
            # 1단계: 웹 검색 수행 (필요한 경우에만)
            sources = []
            if should_search:
                print(f"구조화된 답변을 위한 웹 검색 수행 중: {message}")
                search_results = await self.web_search.search(message, max_results=8)  # 더 많은 정보 수집
                
                # 2단계: 검색 결과를 대화별 콜렉션에 저장
                for result in search_results:
                    if result.get('url'):
                        try:
                            # URL에서 콘텐츠 추출
                            content = await self.web_search.fetch_url_content(result['url'])
                            if content.get('content'):
                                # 텍스트 분할
                                documents = self.text_splitter.split_text(content['content'])
                                
                                # 벡터 스토어에 추가 (대화별 콜렉션)
                                doc_objects = []
                                for i, doc_text in enumerate(documents):
                                    doc_objects.append(Document(
                                        page_content=doc_text,
                                        metadata={
                                            'url': result['url'],
                                            'title': content.get('title', ''),
                                            'chunk_index': i,
                                            'total_chunks': len(documents),
                                            'source_url': result['url'],
                                            'search_query': message,
                                            'conversation_id': conversation_id,
                                            'timestamp': asyncio.get_event_loop().time()
                                        }
                                    ))
                                
                                # 대화별 콜렉션에 저장
                                conversation_vector_store.add_documents(doc_objects)
                                sources.append(result['url'])
                                print(f"구조화된 답변용 URL 인덱싱 완료: {result['url']}")
                        except Exception as e:
                            print(f"구조화된 답변용 URL 인덱싱 실패 {result['url']}: {e}")
                            continue
            else:
                print(f"구조화된 답변을 위한 웹 검색 건너뛰기: {message} (로컬 메모리만 사용)")
            
            # 3단계: 단기기억 → 장기기억 → 웹검색 순으로 컨텍스트 수집
            print(f"구조화된 답변을 위한 컨텍스트 수집 중: {message}")
            
            # 3-1: 단기기억 (현재 대화)에서 검색
            short_term_context = []
            try:
                print(f"단기기억 검색 시작: {self._get_conversation_collection_name(conversation_id)}")
                short_term_results = conversation_vector_store.similarity_search(message, k=5)  # 더 많은 문서 검색
                short_term_context = [result for result in short_term_results if hasattr(result, 'page_content') and result.page_content]
                print(f"단기기억에서 {len(short_term_context)}개 문서 검색 완료")
            except Exception as e:
                print(f"단기기억 검색 실패: {e}")
                print(f"단기기억 벡터 스토어 상태: {type(conversation_vector_store)}")
                short_term_context = []
            
            # 3-2: 장기기억 (대화별 히스토리)에서 검색
            long_term_context = []
            try:
                print(f"장기기억 검색 시작: {self._get_long_term_memory_collection_name(conversation_id)}")
                long_term_vector_store = await self._ensure_long_term_memory_collection(conversation_id)
                long_term_results = long_term_vector_store.similarity_search(message, k=5)  # 더 많은 문서 검색
                long_term_context = [result for result in long_term_results if hasattr(result, 'page_content') and result.page_content]
                print(f"장기기억에서 {len(long_term_context)}개 문서 검색 완료")
            except Exception as e:
                print(f"장기기억 검색 실패: {e}")
                print(f"장기기억 벡터 스토어 상태: {type(long_term_vector_store) if 'long_term_vector_store' in locals() else 'Not created'}")
                long_term_context = []
            
            # 4단계: 통합 컨텍스트 생성
            all_context_docs = []
            
            # 단기기억 우선 (가장 관련성 높음)
            for result in short_term_context:
                all_context_docs.append(result)
                if hasattr(result, 'metadata') and result.metadata.get('url') and result.metadata.get('url') not in sources:
                    sources.append(result.metadata.get('url'))
            
            # 장기기억 추가 (중간 관련성)
            for result in long_term_context:
                all_context_docs.append(result)
                if hasattr(result, 'metadata') and result.metadata.get('url') and result.metadata.get('url') not in sources:
                    sources.append(result.metadata.get('url'))
            
            # 컨텍스트 생성
            context = self._create_context(all_context_docs)
            print(f"구조화된 답변용 통합 컨텍스트: 단기기억 {len(short_term_context)}개, 장기기억 {len(long_term_context)}개, 웹검색 {len(sources)}개")
            
            # 검색 결과가 없을 때 기본 정보 제공
            if not all_context_docs and not sources:
                print("구조화된 답변을 위한 검색 결과가 없어 기본 AI 정보를 제공합니다.")
                context = self._get_default_ai_context(message)
            
            # 5단계: 구조화된 프롬프트 생성 및 LLM 응답
            structured_prompt = self._create_structured_prompt(
                message, 
                context, 
                chat_history=memory.chat_memory.messages
            )
            
            print("구조화된 분석 답변 생성 중...")
            if hasattr(self.llm, 'invoke'):
                # 최신 LangChain API
                response = self.llm.invoke(structured_prompt)
                if hasattr(response, 'content'):
                    response = response.content
                else:
                    response = str(response)
            else:
                # 구버전 호환성
                response = self.llm(structured_prompt)
            
            # 대화 메모리에 저장
            memory.chat_memory.add_user_message(message)
            memory.chat_memory.add_ai_message(response)
            
            # 6단계: 현재 대화를 장기기억에 저장
            await self._save_to_long_term_memory(conversation_id, message, response, sources)
            
            # 컨텍스트 정보 생성
            context_info = {
                'shortTermMemory': len(short_term_context),
                'longTermMemory': len(long_term_context),
                'webSearch': len(sources)
            }
            
            return response, sources, conversation_id, context_info
            
        except Exception as e:
            print(f"구조화된 답변 생성 오류: {e}")
            error_context_info = {
                'shortTermMemory': 0,
                'longTermMemory': 0,
                'webSearch': 0
            }
            return f"죄송합니다. 구조화된 답변 생성 중 오류가 발생했습니다: {str(e)}", [], conversation_id or str(uuid.uuid4()), error_context_info
    
    async def generate_topic_based_response(self, message: str, conversation_id: str = None, use_web_search: bool = True) -> Tuple[str, List[str], str, Dict[str, int]]:
        """질문 분석 → 초기 웹 검색 → 주제 추출 → 벡터 DB 검색 → 구조화된 답변 생성"""
        try:
            # 빈 메시지 체크
            if not message or not message.strip():
                empty_context_info = {
                    'shortTermMemory': 0,
                    'longTermMemory': 0,
                    'webSearch': 0
                }
                return "검색어가 없습니다. 구체적인 질문이나 검색하고 싶은 내용을 입력해주세요.", [], conversation_id or str(uuid.uuid4()), empty_context_info
            
            # 대화 ID 생성
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # 대화 메모리 초기화
            if conversation_id not in self.conversation_memories:
                self.conversation_memories[conversation_id] = ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=True
                )
            
            memory = self.conversation_memories[conversation_id]
            
            print(f"=== 주제 기반 답변 생성 시작 ===: {message}")
            
            # 1단계: 질문에 대한 초기 웹 검색 수행 (10개 정도)
            initial_search_results = []
            if use_web_search:
                print(f"1단계: 질문에 대한 초기 웹 검색 수행: {message}")
                initial_search_results = await self.web_search.search(message, max_results=10)
                print(f"초기 검색 결과: {len(initial_search_results)}개")
                
                # 초기 검색 결과를 벡터 데이터베이스에 저장
                await self._store_initial_search_results(initial_search_results, message, conversation_id)
            
            # 2단계: 검색 결과에서 특정 대상 식별 및 주제 추출
            topics = await self._extract_topics_from_question_with_context(message, initial_search_results)
            print(f"추출된 주제들: {topics}")
            
            # 3단계: 주제별 벡터 데이터베이스 검색 및 정보 수집
            topic_research_results = {}
            all_sources = []
            
            if topics:
                for i, topic in enumerate(topics):
                    print(f"주제 {i+1} 벡터 검색 중: {topic}")
                    
                    # 주제별 벡터 데이터베이스 검색 수행
                    topic_content = await self._search_topic_in_vector_db(topic, message, conversation_id)
                    
                    if topic_content:
                        # 관련성 점수로 정렬
                        topic_content.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
                        
                        # 상위 2개 결과만 사용
                        top_content = topic_content[:2]
                        topic_sources = [item['url'] for item in top_content if item.get('url')]
                        
                        topic_research_results[topic] = {
                            'content': top_content,
                            'sources': topic_sources
                        }
                        
                        # 전체 소스 목록에도 추가
                        all_sources.extend(topic_sources)
                        
                        print(f"주제 '{topic}' 벡터 검색 완료: {len(topic_content)}개 결과, {len(topic_sources)}개 소스")
                    else:
                        print(f"주제 '{topic}'에 대한 벡터 검색 결과 없음")
            
            # 4단계: 구조화된 답변 생성
            structured_response = await self._generate_topic_based_answer(message, topics, topic_research_results)
            
            # 대화 메모리에 저장
            memory.chat_memory.add_user_message(message)
            memory.chat_memory.add_ai_message(structured_response)
            
            # 현재 대화를 장기기억에 저장
            await self._save_to_long_term_memory(conversation_id, message, structured_response, all_sources)
            
            # 컨텍스트 정보 생성
            context_info = {
                'shortTermMemory': 0,  # 주제 기반 답변은 새로운 검색 결과에 의존
                'longTermMemory': 0,
                'webSearch': len(all_sources)
            }
            
            return structured_response, all_sources, conversation_id, context_info
            
        except Exception as e:
            print(f"주제 기반 답변 생성 오류: {e}")
            error_context_info = {
                'shortTermMemory': 0,
                'longTermMemory': 0,
                'webSearch': 0
            }
            return f"죄송합니다. 주제 기반 답변 생성 중 오류가 발생했습니다: {str(e)}", [], conversation_id or str(uuid.uuid4()), error_context_info

    async def _store_initial_search_results(self, search_results: List[Dict[str, Any]], query: str, conversation_id: str):
        """초기 검색 결과를 벡터 데이터베이스에 저장"""
        try:
            print(f"초기 검색 결과를 벡터 데이터베이스에 저장 중: {len(search_results)}개 결과")
            
            # 대화별 콜렉션 확인/생성
            conversation_vector_store = await self._ensure_conversation_collection(conversation_id)
            
            # 검색 결과에서 콘텐츠 추출 및 저장
            for result in search_results:
                if result.get('url'):
                    try:
                        # URL에서 콘텐츠 추출
                        content = await self.web_search.fetch_url_content(result['url'])
                        if content.get('content'):
                            # 텍스트 분할
                            documents = self.text_splitter.split_text(content['content'])
                            
                            # 벡터 스토어에 추가 (대화별 콜렉션)
                            doc_objects = []
                            for i, doc_text in enumerate(documents):
                                doc_objects.append(Document(
                                    page_content=doc_text,
                                    metadata={
                                        'url': result['url'],
                                        'title': content.get('title', ''),
                                        'chunk_index': i,
                                        'total_chunks': len(documents),
                                        'source_url': result['url'],
                                        'search_query': query,
                                        'conversation_id': conversation_id,
                                        'timestamp': asyncio.get_event_loop().time()
                                    }
                                ))
                            
                            # 대화별 콜렉션에 저장
                            conversation_vector_store.add_documents(doc_objects)
                            print(f"초기 검색 결과 저장 완료: {result['url']} -> {self._get_conversation_collection_name(conversation_id)}")
                    except Exception as e:
                        print(f"초기 검색 결과 저장 실패 {result['url']}: {e}")
                        continue
            
            print(f"초기 검색 결과 벡터 데이터베이스 저장 완료")
            
        except Exception as e:
            print(f"초기 검색 결과 저장 중 오류: {e}")

    async def _search_topic_in_vector_db(self, topic: str, original_query: str, conversation_id: str) -> List[Dict[str, Any]]:
        """주제에 대해 벡터 데이터베이스에서 검색"""
        try:
            print(f"주제 '{topic}'에 대해 벡터 데이터베이스 검색 수행")
            
            # 대화별 콜렉션에서 검색
            conversation_vector_store = await self._ensure_conversation_collection(conversation_id)
            
            # 주제와 원본 쿼리를 결합하여 검색
            search_query = f"{topic} {original_query}"
            search_results = conversation_vector_store.similarity_search(search_query, k=5)
            
            topic_content = []
            for result in search_results:
                if hasattr(result, 'page_content') and result.page_content:
                    # 관련성 점수 계산
                    relevance_score = self._calculate_relevance_score(result.page_content, topic)
                    
                    # 메타데이터에서 정보 추출
                    metadata = getattr(result, 'metadata', {})
                    url = metadata.get('url', '')
                    title = metadata.get('title', '')
                    
                    topic_content.append({
                        'content': result.page_content,
                        'url': url,
                        'title': title,
                        'relevance_score': relevance_score
                    })
            
            print(f"주제 '{topic}' 벡터 검색 완료: {len(topic_content)}개 결과")
            return topic_content
            
        except Exception as e:
            print(f"주제 '{topic}' 벡터 검색 중 오류: {e}")
            return []
    
    async def _extract_topics_from_question(self, question: str) -> List[str]:
        """질문에서 핵심 주제들을 추출"""
        try:
            # 주제 추출을 위한 프롬프트 생성
            topic_extraction_prompt = f"""
당신은 사용자의 질문을 분석하여 핵심 주제들을 추출하는 전문가입니다.

사용자 질문: {question}

다음 지침에 따라 3-4개의 핵심 주제를 추출해주세요:

1. **질문의 핵심 의도 파악**: 사용자가 무엇을 알고 싶어하는지 파악
2. **주제 분류**: 관련된 개념들을 논리적으로 그룹화
3. **검색 가능한 주제**: 각 주제가 독립적으로 웹 검색 가능해야 함
4. **사람들이 궁금해할 만한 주제**: 일반적으로 관심을 가질 만한 주제

출력 형식:
- 주제1: [구체적인 주제명]
    
- 주제2: [구체적인 주제명]

- 주제3: [구체적인 주제명]

- 주제4: [구체적인 주제명] (필요한 경우)

예시:
질문: "라부부 말차는 왜 이렇게 떴어?"
주제들:
- 라부부 아트토이의 인기 요인

- 말차 음료/디저트의 트렌드

- MZ세대의 소비 패턴 변화

- SNS와 셀럽의 영향

답변:"""

            # LLM을 사용하여 주제 추출
            if hasattr(self.llm, 'invoke'):
                response = self.llm.invoke(topic_extraction_prompt)
                if hasattr(response, 'content'):
                    response_text = response.content
                else:
                    response_text = str(response)
            else:
                response_text = self.llm(topic_extraction_prompt)
            
            # 응답에서 주제들 추출
            topics = self._parse_topics_from_response(response_text)
            print(f"LLM 응답: {response_text}")
            print(f"파싱된 주제들: {topics}")
            
            return topics[:4]  # 최대 4개 주제
            
        except Exception as e:
            print(f"주제 추출 실패: {e}")
            # 기본 주제 생성
            return [question]
    
    async def _extract_topics_from_question_with_context(self, question: str, search_results: List[Dict[str, Any]]) -> List[str]:
        """초기 웹 검색 결과와 분류 결과를 바탕으로 질문에서 핵심 주제들을 추출"""
        try:
            # 1단계: 웹 검색 결과를 바탕으로 검색어 분류
            print(f"🔍 1단계: 웹 검색 결과 기반으로 검색어 분류 수행")
            classification_result = await self.web_search.classify_search_query(question, search_results)
            print(f"🔍 분류 결과: {classification_result}")
            
            # 2단계: 검색 결과에서 특정 대상 식별
            identified_entities = self._identify_entities_from_search_results(search_results)
            
            # 3단계: 분류 결과를 바탕으로 주제 추출을 위한 프롬프트 생성
            category = classification_result.get('category', '')
            subcategory = classification_result.get('subcategory', '')
            keywords = classification_result.get('keywords', [])
            context_insights = classification_result.get('context_insights', '')
            
            topic_extraction_prompt = f"""
당신은 사용자의 질문과 웹 검색 결과, 그리고 검색어 분류 결과를 분석하여 핵심 주제들을 추출하는 전문가입니다.

사용자 질문: {question}

검색어 분류 결과:
- 카테고리: {category}
- 세부분류: {subcategory}
- 핵심 키워드: {', '.join(keywords) if keywords else '없음'}
- 컨텍스트 인사이트: {context_insights if context_insights else '없음'}

웹 검색 결과에서 식별된 특정 대상들:
{self._format_entities_for_prompt(identified_entities)}

다음 지침에 따라 3-4개의 핵심 주제를 추출해주세요:

1. **분류 결과 활용**: 검색어 분류 결과의 카테고리와 키워드를 중심으로 주제 구성
2. **식별된 특정 대상 활용**: 검색 결과에서 발견된 구체적인 대상, 인물, 회사, 제품 등을 중심으로 주제 구성
3. **질문의 핵심 의도 파악**: 사용자가 무엇을 알고 싶어하는지 파악
4. **주제 분류**: 관련된 개념들을 논리적으로 그룹화
5. **검색 가능한 주제**: 각 주제가 독립적으로 웹 검색 가능해야 함
6. **사람들이 궁금해할 만한 주제**: 일반적으로 관심을 가질 만한 주제

출력 형식:
- 주제1: [구체적인 주제명]
    
- 주제2: [구체적인 주제명]

- 주제3: [구체적인 주제명]

- 주제4: [구체적인 주제명] (필요한 경우)

예시:
질문: "라부부 말차는 왜 이렇게 떴어?"
분류 결과: 카테고리: object, 세부분류: 제품, 키워드: [인기, 트렌드, 소비]
식별된 대상: 라부부 아트토이, 말차 음료
주제들:
- 라부부 아트토이의 인기 요인과 트렌드

- 말차 음료/디저트의 소비 패턴 변화

- MZ세대의 소비 행동과 트렌드

- SNS와 셀럽의 제품 인기 영향

답변:"""

            # LLM을 사용하여 주제 추출
            if hasattr(self.llm, 'invoke'):
                response = self.llm.invoke(topic_extraction_prompt)
                if hasattr(response, 'content'):
                    response_text = response.content
                else:
                    response_text = str(response)
            else:
                response_text = self.llm(topic_extraction_prompt)
            
            # 응답에서 주제들 추출
            topics = self._parse_topics_from_response(response_text)
            print(f"🔍 2단계: 분류 기반 주제 추출 완료")
            print(f"LLM 응답: {response_text}")
            print(f"파싱된 주제들: {topics}")
            
            return topics[:4]  # 최대 4개 주제
            
        except Exception as e:
            print(f"컨텍스트 기반 주제 추출 실패: {e}")
            # 기본 주제 추출으로 폴백
            return await self._extract_topics_from_question(question)
    
    def _identify_entities_from_search_results(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """검색 결과에서 특정 대상(엔티티)들을 식별"""
        entities = []
        
        for result in search_results:
            title = result.get('title', '')
            snippet = result.get('snippet', '')
            
            # 제목과 스니펫에서 엔티티 추출
            extracted_entities = self._extract_entities_from_text(f"{title} {snippet}")
            
            for entity in extracted_entities:
                # 중복 제거
                if not any(existing['name'] == entity['name'] for existing in entities):
                    entities.append(entity)
        
        return entities[:5]  # 최대 5개 엔티티
    
    def _extract_entities_from_text(self, text: str) -> List[Dict[str, Any]]:
        """텍스트에서 엔티티(특정 대상) 추출"""
        entities = []
        
        # 간단한 패턴 매칭으로 엔티티 추출
        # 회사명, 브랜드명, 제품명, 인물명 등을 찾기 위한 패턴들
        
        # 한국어 회사/브랜드 패턴 (예: 삼성전자, 현대자동차, 라부부)
        korean_brands = re.findall(r'[가-힣]{2,}(?:전자|자동차|그룹|기업|주식회사|㈜|㈐)', text)
        for brand in korean_brands:
            entities.append({
                'name': brand,
                'type': 'company',
                'confidence': 0.8
            })
        
        # 영어 회사/브랜드 패턴 (예: Apple, Google, Microsoft)
        english_brands = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        for brand in english_brands:
            if len(brand) > 2 and brand.lower() not in ['the', 'and', 'for', 'with', 'from']:
                entities.append({
                    'name': brand,
                    'type': 'company',
                    'confidence': 0.7
                })
        
        # 제품명 패턴 (예: "iPhone 15", "갤럭시 S24")
        product_patterns = [
            r'[가-힣]+(?:\s+[가-힣]+)*\s*\d+',  # 한국어 제품명 + 숫자
            r'[A-Za-z]+\s*\d+',  # 영어 제품명 + 숫자
        ]
        
        for pattern in product_patterns:
            products = re.findall(pattern, text)
            for product in products:
                if len(product) > 3:
                    entities.append({
                        'name': product,
                        'type': 'product',
                        'confidence': 0.6
                    })
        
        # 인물명 패턴 (예: "김철수", "John Doe")
        person_patterns = [
            r'[가-힣]{2,3}',  # 한국어 이름 (2-3글자)
            r'[A-Z][a-z]+\s+[A-Z][a-z]+',  # 영어 이름 (First Last)
        ]
        
        for pattern in person_patterns:
            persons = re.findall(pattern, text)
            for person in persons:
                if len(person) > 2:
                    entities.append({
                        'name': person,
                        'type': 'person',
                        'confidence': 0.5
                    })
        
        return entities
    
    def _format_entities_for_prompt(self, entities: List[Dict[str, Any]]) -> str:
        """프롬프트용으로 엔티티 정보를 포맷팅"""
        if not entities:
            return "특정 대상이 식별되지 않았습니다."
        
        formatted = []
        for entity in entities:
            formatted.append(f"- {entity['name']} ({entity['type']}, 신뢰도: {entity['confidence']})")
        
        return '\n'.join(formatted)
    
    def _parse_topics_from_response(self, response: str) -> List[str]:
        """LLM 응답에서 주제들을 파싱"""
        topics = []
        lines = response.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                # 불릿 포인트 제거
                topic = line[1:].strip()
                if topic and len(topic) > 3:
                    topics.append(topic)
            elif ':' in line and not line.startswith('질문'):
                # 콜론이 있는 줄에서 주제 추출
                parts = line.split(':', 1)
                if len(parts) == 2:
                    topic = parts[1].strip()
                    if topic and len(topic) > 3:
                        topics.append(topic)
        
        # 주제가 없으면 기본값 반환
        if not topics:
            topics = ["일반적인 정보", "구체적인 사례", "전망 및 분석"]
        
        return topics
    
    def _generate_search_keywords(self, topic: str, original_question: str) -> str:
        """주제별 검색 키워드 생성 - 질문의 핵심 속성을 추출하여 주제와 결합"""
        # 질문에서 핵심 속성(의문사, 핵심 키워드) 추출
        core_attributes = self._extract_core_attributes_from_question(original_question)
        
        # 주제와 핵심 속성을 결합하여 검색 키워드 생성
        keywords = f"{topic} {core_attributes}"
        
        print(f"주제 '{topic}' 검색 키워드 생성: '{keywords}' (핵심 속성: {core_attributes})")
        return keywords
    
    def _extract_core_attributes_from_question(self, question: str) -> str:
        """질문에서 핵심 속성(의문사, 핵심 키워드)을 추출"""
        core_attributes = []
        
        # 의문사 패턴 매칭
        question_words = {
            '왜': '이유 원인 배경',
            '어떻게': '방법 과정 방법론',
            '언제': '시기 타이밍 일정',
            '어디서': '장소 지역 위치',
            '누가': '주체 인물 회사',
            '무엇을': '대상 제품 서비스',
            '얼마나': '규모 수치 통계',
            '어떤': '종류 유형 특징'
        }
        
        # 질문에서 의문사 찾기
        for question_word, attributes in question_words.items():
            if question_word in question:
                core_attributes.extend(attributes.split())
                break  # 첫 번째 의문사만 사용
        
        # 질문에서 핵심 명사/키워드 추출 (의문사가 없는 경우)
        if not core_attributes:
            # 한국어 명사 패턴 (2글자 이상)
            korean_nouns = re.findall(r'[가-힣]{2,}', question)
            # 영어 명사 패턴 (대문자로 시작하는 단어)
            english_nouns = re.findall(r'\b[A-Z][a-z]+\b', question)
            
            # 불용어 제거
            stop_words = {'이', '가', '을', '를', '은', '는', '에', '의', '로', '와', '과', '도', '만', '부터', '까지'}
            filtered_nouns = [noun for noun in korean_nouns + english_nouns if noun not in stop_words]
            
            if filtered_nouns:
                core_attributes.extend(filtered_nouns[:3])  # 최대 3개만 사용
        
        # 핵심 속성이 없으면 기본값 사용
        if not core_attributes:
            core_attributes = ['정보', '현황', '트렌드']
        
        return ' '.join(core_attributes)
    
    def _extract_relevant_content(self, content: str, topic: str, keywords: str) -> str:
        """주제와 관련된 내용만 추출"""
        # 간단한 키워드 매칭으로 관련성 높은 내용 추출
        relevant_sentences = []
        sentences = content.split('.')
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20:  # 너무 짧은 문장 제외
                # 주제나 키워드가 포함된 문장 찾기
                if any(keyword.lower() in sentence.lower() for keyword in keywords.split()):
                    relevant_sentences.append(sentence)
        
        if relevant_sentences:
            return '. '.join(relevant_sentences[:3])  # 상위 3개 문장만 반환
        else:
            # 관련 문장이 없으면 처음 200자 반환
            return content[:200] + "..." if len(content) > 200 else content
    
    def _calculate_relevance_score(self, content: str, topic: str) -> float:
        """콘텐츠와 주제의 관련성 점수 계산"""
        score = 0.0
        
        # 주제 키워드가 포함된 정도
        topic_words = topic.lower().split()
        content_lower = content.lower()
        
        for word in topic_words:
            if len(word) > 2:  # 2글자 이하 단어 제외
                score += content_lower.count(word) * 0.1
        
        # 콘텐츠 길이에 따른 보정
        if len(content) > 100:
            score += 0.5
        
        return score
    
    async def _generate_topic_based_answer(self, question: str, topics: List[str], research_results: Dict) -> str:
        """주제별 연구 결과를 바탕으로 구조화된 답변 생성"""
        try:
            # 답변 생성을 위한 프롬프트 생성
            answer_prompt = f"""
당신은 사용자의 질문에 대해 주제별로 체계적인 답변을 제공하는 전문가입니다.

사용자 질문: {question}

추출된 주제들:
{chr(10).join([f"- {topic}" for topic in topics])}

주제별 연구 결과:
{self._format_research_results(research_results)}

다음 형식으로 구조화된 답변을 생성해주세요:

## 📋 핵심 요약
[질문의 핵심을 2-3문장으로 요약]

## 🔍 주제별 상세 분석

### [주제1]
- [해당 주제에 대한 상세한 설명과 분석]

참고: [URL1], [URL2]

### [주제2]
- [해당 주제에 대한 상세한 설명과 분석]

참고: [URL1], [URL2]

### [주제3]
- [해당 주제에 대한 상세한 설명과 분석]

참고: [URL1], [URL2]

## 💡 결론 및 인사이트
[전체적인 결론과 향후 전망, 주목할 점]

답변 시 다음 사항을 준수하세요:
- 각 주제별로 구체적이고 유용한 정보 제공
- 참조 URL을 명확하게 표시
- 사용자 친화적이고 이해하기 쉬운 언어 사용
- 논리적 구조와 흐름 유지
- 불릿 포인트(•) 활용하여 가독성 향상
- 마크다운 문법에 따른 구조 정리
- 한국어로 답변

답변:"""

            # LLM을 사용하여 답변 생성
            if hasattr(self.llm, 'invoke'):
                response = self.llm.invoke(answer_prompt)
                if hasattr(response, 'content'):
                    return response.content
                else:
                    return str(response)
            else:
                return self.llm(answer_prompt)
                
        except Exception as e:
            print(f"주제별 답변 생성 실패: {e}")
            return f"죄송합니다. 주제별 답변 생성 중 오류가 발생했습니다: {str(e)}"
    
    def _format_research_results(self, research_results: Dict) -> str:
        """연구 결과를 프롬프트용으로 포맷팅"""
        formatted = ""
        
        for topic, data in research_results.items():
            formatted += f"\n### {topic}\n"
            
            if data['content']:
                for i, content_item in enumerate(data['content']):
                    formatted += f"내용 {i+1}: {content_item['content'][:1000]}...\n"
                    formatted += f"URL {i+1}: {content_item['url']}\n"
            else:
                formatted += "관련 정보를 찾을 수 없습니다.\n"
            
            formatted += f"소스: {', '.join(data['sources'])}\n"
        
        return formatted
    
    async def _save_to_long_term_memory(self, conversation_id: str, user_message: str, ai_response: str, sources: List[str]) -> None:
        """현재 대화를 장기기억에 저장 (대화별 분리)"""
        try:
            long_term_vector_store = await self._ensure_long_term_memory_collection(conversation_id)
            
            # 대화 내용을 문서로 변환
            conversation_text = f"사용자: {user_message}\n\nAI: {ai_response}"
            if sources:
                conversation_text += f"\n\n참고 소스: {', '.join(sources)}"
            
            # 텍스트 분할
            documents = self.text_splitter.split_text(conversation_text)
            
            # 장기기억에 저장
            doc_objects = []
            for i, doc_text in enumerate(documents):
                doc_objects.append(Document(
                    page_content=doc_text,
                    metadata={
                        'conversation_id': conversation_id,
                        'user_message': user_message,
                        'ai_response': ai_response,
                        'sources': sources,
                        'chunk_index': i,
                        'total_chunks': len(documents),
                        'timestamp': asyncio.get_event_loop().time(),
                        'memory_type': 'long_term'
                    }
                ))
            
            if doc_objects:
                long_term_vector_store.add_documents(doc_objects)
                print(f"장기기억에 저장 완료: 대화 {conversation_id} -> {len(doc_objects)}개 청크")
            
        except Exception as e:
            print(f"장기기억 저장 실패: {e}")
    
    async def index_urls(self, urls: List[str], conversation_id: str = None) -> int:
        """URL들을 대화별 콜렉션에 인덱싱"""
        try:
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # 대화별 콜렉션 확인/생성
            conversation_vector_store = await self._ensure_conversation_collection(conversation_id)
            
            indexed_count = 0
            
            for url in urls:
                # URL에서 콘텐츠 추출
                content = await self.web_search.fetch_url_content(url)
                
                if content.get('content'):
                    # 텍스트 분할
                    documents = self.text_splitter.split_text(content['content'])
                    
                    # 벡터 스토어에 추가
                    doc_objects = []
                    for i, doc_text in enumerate(documents):
                        doc_objects.append(Document(
                            page_content=doc_text,
                            metadata={
                                'url': url,
                                'title': content.get('title', ''),
                                'chunk_index': i,
                                'total_chunks': len(documents),
                                'source_url': url,
                                'conversation_id': conversation_id,
                                'timestamp': asyncio.get_event_loop().time()
                            }
                        ))
                    
                    # 대화별 콜렉션에 저장
                    conversation_vector_store.add_documents(doc_objects)
                    indexed_count += 1
            
            return indexed_count
            
        except Exception as e:
            print(f"Error indexing URLs: {e}")
            return 0
    
    async def get_conversation_collections(self) -> List[str]:
        """모든 대화 콜렉션 목록 조회"""
        try:
            collections = await self.vector_store.client.get_collections()
            conversation_collections = []
            
            for collection in collections.collections:
                if collection.name.startswith('conversation_'):
                    conversation_collections.append(collection.name)
            
            return conversation_collections
        except Exception as e:
            print(f"Error getting conversation collections: {e}")
            return []
    
    async def delete_conversation_collection(self, conversation_id: str) -> bool:
        """대화별 콜렉션 삭제"""
        try:
            collection_name = self._get_conversation_collection_name(conversation_id)
            
            # 콜렉션 삭제
            await self.vector_store.client.delete_collection(collection_name)
            
            # 캐시에서 제거
            if collection_name in self.conversation_vector_stores:
                del self.conversation_vector_stores[collection_name]
            
            # 대화 메모리 제거
            if conversation_id in self.conversation_memories:
                del self.conversation_memories[conversation_id]
            
            print(f"대화 콜렉션 삭제 완료: {collection_name}")
            return True
            
        except Exception as e:
            print(f"Error deleting conversation collection: {e}")
            return False
    
    def get_conversation_history(self, conversation_id: str) -> List[Dict[str, str]]:
        """대화 히스토리 조회"""
        if conversation_id in self.conversation_memories:
            memory = self.conversation_memories[conversation_id]
            messages = memory.chat_memory.messages
            
            history = []
            for i in range(0, len(messages), 2):
                if i + 1 < len(messages):
                    history.append({
                        'user': messages[i].content,
                        'assistant': messages[i + 1].content
                    })
            
            return history
        
        return []
    
    def clear_conversation(self, conversation_id: str):
        """대화 히스토리 삭제 (메모리만)"""
        if conversation_id in self.conversation_memories:
            del self.conversation_memories[conversation_id]
    
    async def chat_with_memory(self, message: str, conversation_id: str = None, use_web_search: bool = True) -> Tuple[str, List[str], str, Dict[str, int]]:
        """메모리 기반 자연스러운 대화형 챗봇 - 단기기억과 장기기억을 활용한 맥락 의존적 대화"""
        try:
            # 빈 메시지 체크
            if not message or not message.strip():
                empty_context_info = {
                    'shortTermMemory': 0,
                    'longTermMemory': 0,
                    'webSearch': 0
                }
                return "안녕하세요! 무엇을 도와드릴까요? 구체적인 질문이나 이야기하고 싶은 내용을 말씀해주세요.", [], conversation_id or str(uuid.uuid4()), empty_context_info
            
            # 대화 ID 생성
            if not conversation_id:
                conversation_id = str(uuid.uuid4())
            
            # 대화 메모리 초기화
            if conversation_id not in self.conversation_memories:
                self.conversation_memories[conversation_id] = ConversationBufferMemory(
                    memory_key="chat_history",
                    return_messages=True
                )
            
            memory = self.conversation_memories[conversation_id]
            
            # 1단계: 대화 맥락 분석
            conversation_context = await self._analyze_conversation_context(message, conversation_id)
            
            # 2단계: 감정 및 의도 분석
            emotional_context = await self._analyze_emotional_context(message, conversation_context)
            
            # 3단계: 메모리 기반 컨텍스트 수집
            memory_context = await self._gather_memory_context(message, conversation_id)
            
            # 4단계: 웹 검색 필요성 판단 (맥락 기반)
            should_search = use_web_search and self._should_use_web_search_with_context(message, conversation_context)
            
            # 5단계: 웹 검색 수행 (필요한 경우)
            sources = []
            if should_search:
                print(f"맥락 기반 웹 검색 수행: {message}")
                search_results = await self.web_search.search(message, max_results=5)
                
                # 검색 결과를 대화별 콜렉션에 저장
                conversation_vector_store = await self._ensure_conversation_collection(conversation_id)
                for result in search_results:
                    if result.get('url'):
                        try:
                            content = await self.web_search.fetch_url_content(result['url'])
                            if content.get('content'):
                                documents = self.text_splitter.split_text(content['content'])
                                
                                doc_objects = []
                                for i, doc_text in enumerate(documents):
                                    doc_objects.append(Document(
                                        page_content=doc_text,
                                        metadata={
                                            'url': result['url'],
                                            'title': content.get('title', ''),
                                            'chunk_index': i,
                                            'total_chunks': len(documents),
                                            'source_url': result['url'],
                                            'search_query': message,
                                            'conversation_id': conversation_id,
                                            'timestamp': asyncio.get_event_loop().time(),
                                            'context_type': 'web_search'
                                        }
                                    ))
                                
                                conversation_vector_store.add_documents(doc_objects)
                                sources.append(result['url'])
                        except Exception as e:
                            print(f"웹 검색 결과 저장 실패 {result['url']}: {e}")
                            continue
            
            # 6단계: 통합 컨텍스트 생성
            integrated_context = self._create_integrated_context(
                memory_context, 
                conversation_context, 
                emotional_context, 
                sources
            )
            
            # 7단계: 자연스러운 대화형 프롬프트 생성
            conversational_prompt = self._create_conversational_prompt(
                message, 
                integrated_context, 
                memory.chat_memory.messages,
                conversation_context,
                emotional_context
            )
            
            # 8단계: LLM 응답 생성
            print("자연스러운 대화형 응답 생성 중...")
            if hasattr(self.llm, 'invoke'):
                response = self.llm.invoke(conversational_prompt)
                if hasattr(response, 'content'):
                    response = response.content
            else:
                response = self.llm(conversational_prompt)
            
            # 9단계: 대화 메모리에 저장
            memory.chat_memory.add_user_message(message)
            memory.chat_memory.add_ai_message(response)
            
            # 10단계: 현재 대화를 장기기억에 저장
            await self._save_to_long_term_memory(conversation_id, message, response, sources)
            
            # 컨텍스트 정보 생성
            context_info = {
                'shortTermMemory': memory_context.get('short_term_count', 0),
                'longTermMemory': memory_context.get('long_term_count', 0),
                'webSearch': len(sources)
            }
            
            return response, sources, conversation_id, context_info
            
        except Exception as e:
            print(f"대화형 챗봇 처리 오류: {e}")
            error_context_info = {
                'shortTermMemory': 0,
                'longTermMemory': 0,
                'webSearch': 0
            }
            return f"죄송합니다. 대화 중 오류가 발생했습니다. 다시 시도해주세요.", [], conversation_id or str(uuid.uuid4()), error_context_info

    async def _analyze_conversation_context(self, message: str, conversation_id: str) -> Dict[str, Any]:
        """대화 맥락 분석"""
        try:
            # 대화 히스토리 가져오기
            history = self.get_conversation_history(conversation_id)
            
            # 맥락 분석을 위한 프롬프트
            context_analysis_prompt = f"""
다음 대화를 분석하여 현재 상황과 맥락을 파악해주세요.

현재 메시지: {message}

이전 대화 내용:
{self._format_conversation_history(history)}

다음 정보를 JSON 형식으로 분석해주세요:
{{
    "conversation_stage": "대화 단계 (시작/진행/마무리)",
    "topic_continuity": "이전 주제와의 연관성 (높음/중간/낮음)",
    "user_intent": "사용자 의도 (질문/대화/요청/감정표현)",
    "context_clues": "맥락 단서들",
    "referenced_entities": "언급된 대상들",
    "conversation_tone": "대화 톤 (친근함/공식적/감정적/중립적)"
}}

중요: 반드시 유효한 JSON 형식으로만 응답하세요.
"""
            
            if hasattr(self.llm, 'invoke'):
                response = self.llm.invoke(context_analysis_prompt)
                if hasattr(response, 'content'):
                    response_text = response.content
                else:
                    response_text = str(response)
            else:
                response_text = self.llm(context_analysis_prompt)
            
            # JSON 파싱
            import json
            try:
                context = json.loads(response_text)
                print(f"대화 맥락 분석 완료: {context.get('conversation_stage', 'unknown')}")
                return context
            except json.JSONDecodeError:
                print("대화 맥락 분석 JSON 파싱 실패, 기본값 사용")
                return {
                    "conversation_stage": "진행",
                    "topic_continuity": "중간",
                    "user_intent": "질문",
                    "context_clues": [],
                    "referenced_entities": [],
                    "conversation_tone": "친근함"
                }
                
        except Exception as e:
            print(f"대화 맥락 분석 실패: {e}")
            return {
                "conversation_stage": "진행",
                "topic_continuity": "중간", 
                "user_intent": "질문",
                "context_clues": [],
                "referenced_entities": [],
                "conversation_tone": "친근함"
            }

    async def _analyze_emotional_context(self, message: str, conversation_context: Dict[str, Any]) -> Dict[str, Any]:
        """감정 및 의도 분석"""
        try:
            emotional_analysis_prompt = f"""
다음 메시지의 감정과 의도를 분석해주세요.

메시지: {message}
대화 맥락: {conversation_context.get('conversation_tone', '중립적')}

다음 정보를 JSON 형식으로 분석해주세요:
{{
    "emotion": "감정 (기쁨/슬픔/분노/놀람/두려움/중립)",
    "intensity": "감정 강도 (1-5)",
    "intent": "의도 (질문/대화/도움요청/감정표현/정보요청)",
    "urgency": "긴급도 (낮음/보통/높음)",
    "personal_touch": "개인적 터치 필요성 (있음/없음)",
    "response_style": "응답 스타일 (친근함/공식적/감정적/중립적)"
}}

중요: 반드시 유효한 JSON 형식으로만 응답하세요.
"""
            
            if hasattr(self.llm, 'invoke'):
                response = self.llm.invoke(emotional_analysis_prompt)
                if hasattr(response, 'content'):
                    response_text = response.content
                else:
                    response_text = str(response)
            else:
                response_text = self.llm(emotional_analysis_prompt)
            
            # JSON 파싱
            import json
            try:
                emotional_context = json.loads(response_text)
                print(f"감정 분석 완료: {emotional_context.get('emotion', '중립')} (강도: {emotional_context.get('intensity', 3)})")
                return emotional_context
            except json.JSONDecodeError:
                print("감정 분석 JSON 파싱 실패, 기본값 사용")
                return {
                    "emotion": "중립",
                    "intensity": 3,
                    "intent": "질문",
                    "urgency": "보통",
                    "personal_touch": "없음",
                    "response_style": "친근함"
                }
                
        except Exception as e:
            print(f"감정 분석 실패: {e}")
            return {
                "emotion": "중립",
                "intensity": 3,
                "intent": "질문", 
                "urgency": "보통",
                "personal_touch": "없음",
                "response_style": "친근함"
            }

    async def _gather_memory_context(self, message: str, conversation_id: str) -> Dict[str, Any]:
        """메모리 기반 컨텍스트 수집"""
        try:
            # 단기기억 검색
            conversation_vector_store = await self._ensure_conversation_collection(conversation_id)
            short_term_results = conversation_vector_store.similarity_search(message, k=3)
            short_term_context = [result for result in short_term_results if hasattr(result, 'page_content') and result.page_content]
            
            # 장기기억 검색
            long_term_vector_store = await self._ensure_long_term_memory_collection(conversation_id)
            long_term_results = long_term_vector_store.similarity_search(message, k=3)
            long_term_context = [result for result in long_term_results if hasattr(result, 'page_content') and result.page_content]
            
            return {
                'short_term_context': short_term_context,
                'long_term_context': long_term_context,
                'short_term_count': len(short_term_context),
                'long_term_count': len(long_term_context)
            }
            
        except Exception as e:
            print(f"메모리 컨텍스트 수집 실패: {e}")
            return {
                'short_term_context': [],
                'long_term_context': [],
                'short_term_count': 0,
                'long_term_count': 0
            }

    def _should_use_web_search_with_context(self, message: str, conversation_context: Dict[str, Any]) -> bool:
        """맥락을 고려한 웹 검색 필요성 판단"""
        # 기본 웹 검색 필요성 체크
        basic_search_needed = self._should_use_web_search(message)
        
        # 맥락 기반 추가 판단
        user_intent = conversation_context.get('user_intent', '질문')
        topic_continuity = conversation_context.get('topic_continuity', '중간')
        
        # 질문이나 정보 요청인 경우 웹 검색 필요
        if user_intent in ['질문', '정보요청']:
            return True
        
        # 이전 주제와 연관성이 낮은 새로운 주제인 경우 웹 검색 필요
        if topic_continuity == '낮음' and basic_search_needed:
            return True
        
        return basic_search_needed

    def _create_integrated_context(self, memory_context: Dict, conversation_context: Dict, emotional_context: Dict, sources: List[str]) -> str:
        """통합 컨텍스트 생성"""
        context_parts = []
        
        # 대화 맥락
        context_parts.append(f"=== 대화 맥락 ===")
        context_parts.append(f"대화 단계: {conversation_context.get('conversation_stage', '진행')}")
        context_parts.append(f"주제 연속성: {conversation_context.get('topic_continuity', '중간')}")
        context_parts.append(f"사용자 의도: {conversation_context.get('user_intent', '질문')}")
        context_parts.append(f"대화 톤: {conversation_context.get('conversation_tone', '친근함')}")
        
        # 감정 맥락
        context_parts.append(f"\n=== 감정 맥락 ===")
        context_parts.append(f"감정: {emotional_context.get('emotion', '중립')} (강도: {emotional_context.get('intensity', 3)})")
        context_parts.append(f"의도: {emotional_context.get('intent', '질문')}")
        context_parts.append(f"긴급도: {emotional_context.get('urgency', '보통')}")
        context_parts.append(f"응답 스타일: {emotional_context.get('response_style', '친근함')}")
        
        # 메모리 정보
        context_parts.append(f"\n=== 메모리 정보 ===")
        context_parts.append(f"단기기억: {memory_context.get('short_term_count', 0)}개 문서")
        context_parts.append(f"장기기억: {memory_context.get('long_term_count', 0)}개 문서")
        context_parts.append(f"웹검색: {len(sources)}개 소스")
        
        # 단기기억 내용
        if memory_context.get('short_term_context'):
            context_parts.append(f"\n=== 단기기억 내용 ===")
            for i, doc in enumerate(memory_context['short_term_context'][:2]):
                content = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
                context_parts.append(f"{i+1}. {content}")
        
        # 장기기억 내용
        if memory_context.get('long_term_context'):
            context_parts.append(f"\n=== 장기기억 내용 ===")
            for i, doc in enumerate(memory_context['long_term_context'][:2]):
                content = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
                context_parts.append(f"{i+1}. {content}")
        
        return "\n".join(context_parts)

    def _create_conversational_prompt(self, message: str, integrated_context: str, chat_history: List, conversation_context: Dict, emotional_context: Dict) -> str:
        """자연스러운 대화형 프롬프트 생성"""
        
        # 대화 히스토리 처리
        chat_history_text = ""
        if chat_history and len(chat_history) > 0:
            chat_history_text = "\n=== 이전 대화 내용 ===\n"
            for i, msg in enumerate(chat_history[-4:], 1):  # 최근 4개 메시지만 포함
                if hasattr(msg, 'content'):
                    role = "사용자" if hasattr(msg, 'type') and msg.type == 'human' else "AI"
                    chat_history_text += f"{i}. {role}: {msg.content}\n"
            chat_history_text += "==================\n"
        
        # 감정 기반 응답 스타일 결정
        response_style = emotional_context.get('response_style', '친근함')
        emotion = emotional_context.get('emotion', '중립')
        intensity = emotional_context.get('intensity', 3)
        
        # 감정에 따른 응답 가이드라인
        emotion_guidelines = {
            '기쁨': '사용자의 기쁜 마음을 공유하고 긍정적인 에너지를 전달하세요.',
            '슬픔': '공감하고 위로의 말을 건네며 도움이 될 수 있는 정보를 제공하세요.',
            '분노': '차분하고 이해심 있게 응답하며 문제 해결에 도움이 되도록 하세요.',
            '놀람': '사용자의 놀라움에 공감하며 관련 정보를 흥미롭게 전달하세요.',
            '두려움': '안심시키고 도움이 될 수 있는 구체적인 정보를 제공하세요.',
            '중립': '친근하고 도움이 되는 정보를 제공하세요.'
        }
        
        emotion_guide = emotion_guidelines.get(emotion, emotion_guidelines['중립'])
        
        conversational_prompt = f"""당신은 사용자와 자연스럽게 대화하는 AI 어시스턴트입니다. 
이전 대화 내용과 현재 맥락을 바탕으로 사용자와 진정한 대화를 나누세요.

{chat_history_text}

{integrated_context}

현재 사용자 메시지: {message}

대화 지침:
1. **맥락 의존적 대화**: 이전 대화 내용을 참고하여 자연스럽게 대화를 이어가세요
2. **감정 인식**: 사용자의 감정({emotion}, 강도: {intensity})을 인식하고 적절히 반응하세요
3. **개인화된 응답**: {emotion_guide}
4. **자연스러운 언어**: "그거", "이것", "저것" 등의 대명사를 자연스럽게 사용하세요
5. **대화 연속성**: 이전에 언급된 내용을 기억하고 연결하여 대화하세요
6. **친근한 톤**: {response_style}한 톤으로 대화하세요
7. **정보 제공**: 필요한 정보는 정확하고 유용하게 제공하세요
8. **감정적 지지**: 사용자의 감정에 공감하고 지지하는 응답을 하세요

응답 시 다음을 고려하세요:
- 이전 대화에서 언급된 내용을 기억하고 참조하세요
- 사용자의 감정 상태에 맞는 톤으로 응답하세요
- "아, 그거 말씀이시군요!" 같은 자연스러운 반응을 포함하세요
- 필요한 경우 이전 대화 내용을 요약하거나 연결하세요
- 한국어로 친근하고 자연스럽게 답변하세요

답변:"""
        
        return conversational_prompt

    def _format_conversation_history(self, history: List[Dict[str, str]]) -> str:
        """대화 히스토리를 프롬프트용으로 포맷팅"""
        if not history:
            return "이전 대화 내용이 없습니다."
        
        formatted = []
        for i, turn in enumerate(history[-3:], 1):  # 최근 3턴만 포함
            formatted.append(f"{i}. 사용자: {turn.get('user', '')}")
            formatted.append(f"   AI: {turn.get('assistant', '')}")
        
        return "\n".join(formatted)

    def is_healthy(self) -> bool:
        """서비스 상태 확인"""
        try:
            return (
                self.vector_store.is_healthy() and
                self.web_search.is_healthy()
            )
        except Exception:
            return False
