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
                model="gpt-3.5-turbo"
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
                short_term_results = conversation_vector_store.similarity_search(message, k=3)
                short_term_context = [result for result in short_term_results if hasattr(result, 'page_content') and result.page_content]
                print(f"단기기억에서 {len(short_term_context)}개 문서 검색")
            except Exception as e:
                print(f"단기기억 검색 실패: {e}")
            
            # 3-2: 장기기억 (대화별 히스토리)에서 검색
            long_term_context = []
            try:
                long_term_vector_store = await self._ensure_long_term_memory_collection(conversation_id)
                long_term_results = long_term_vector_store.similarity_search(message, k=3)
                long_term_context = [result for result in long_term_results if hasattr(result, 'page_content') and result.page_content]
                print(f"장기기억에서 {len(long_term_context)}개 문서 검색")
            except Exception as e:
                print(f"장기기억 검색 실패: {e}")
            
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
    
    def is_healthy(self) -> bool:
        """서비스 상태 확인"""
        try:
            return (
                self.vector_store.is_healthy() and
                self.web_search.is_healthy()
            )
        except Exception:
            return False
