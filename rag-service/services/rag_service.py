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
        """대화별 콜렉션 이름 생성"""
        return f"conversation_{conversation_id.replace('-', '_')}"
    
    async def _ensure_conversation_collection(self, conversation_id: str) -> Qdrant:
        """대화별 콜렉션이 존재하는지 확인하고 없으면 생성"""
        collection_name = self._get_conversation_collection_name(conversation_id)
        
        if collection_name not in self.conversation_vector_stores:
            try:
                # 기존 콜렉션이 있는지 확인
                collections = self.vector_store.client.get_collections()
                collection_exists = any(col.name == collection_name for col in collections.collections)
                
                if collection_exists:
                    print(f"기존 콜렉션 사용: {collection_name}")
                else:
                    # 콜렉션이 없으면 생성
                    print(f"새 콜렉션 생성: {collection_name}")
                    
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
                print(f"콜렉션 확인/생성 오류: {e}")
                # 오류 발생 시 기본 콜렉션 사용
                return self.vector_store
            
            # 대화별 벡터 스토어 생성
            self.conversation_vector_stores[collection_name] = Qdrant(
                client=self.vector_store.client,
                collection_name=collection_name,
                embeddings=OpenAIEmbeddings() if self.openai_api_key else None
            )
        
        return self.conversation_vector_stores[collection_name]
    
    async def chat(self, message: str, conversation_id: str = None, use_web_search: bool = True) -> Tuple[str, List[str], str]:
        """챗봇 대화 처리 - 대화별 콜렉션에 저장"""
        try:
            # 빈 메시지 체크
            if not message or not message.strip():
                return "검색어가 없습니다. 구체적인 질문이나 검색하고 싶은 내용을 입력해주세요.", [], conversation_id or str(uuid.uuid4())
            
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
            
            # 1단계: 웹 검색 수행 (필요한 경우)
            sources = []
            if use_web_search:
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
            
            # 3단계: 대화별 콜렉션에서 유사한 문서 검색 (Retrieval)
            print(f"벡터 검색 수행 중: {message}")
            try:
                vector_results = conversation_vector_store.similarity_search(message, k=5)
            except Exception as e:
                print(f"벡터 검색 실패: {e}")
                vector_results = []
            
            # 4단계: 컨텍스트 생성
            context_docs = []
            for result in vector_results:
                if hasattr(result, 'page_content') and result.page_content:
                    context_docs.append(result)
                    if hasattr(result, 'metadata') and result.metadata.get('url') and result.metadata.get('url') not in sources:
                        sources.append(result.metadata.get('url'))
            
            context = self._create_context(context_docs)
            print(f"검색된 문서 수: {len(context_docs)}")
            
            # 검색 결과가 없을 때 기본 정보 제공
            if not context_docs and not sources:
                print("검색 결과가 없어 기본 AI 정보를 제공합니다.")
                context = self._get_default_ai_context(message)
            
            # 5단계: 프롬프트 생성 및 LLM 응답
            prompt = self._create_prompt(message, context)
            
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
            
            print(f"응답 생성 완료. 소스 수: {len(sources)}")
            return response, sources, conversation_id
            
        except Exception as e:
            print(f"Error in chat: {e}")
            return f"죄송합니다. 오류가 발생했습니다: {str(e)}", [], conversation_id or str(uuid.uuid4())
    
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
    
    def _create_prompt(self, message: str, context: str) -> str:
        """프롬프트 생성"""
        if context:
            prompt = f"""다음은 사용자의 질문과 관련된 정보입니다:

{context}

사용자 질문: {message}

위의 정보를 바탕으로 사용자의 질문에 답변해주세요. 
- 제공된 정보를 활용하여 정확하고 도움이 되는 답변을 제공하세요
- 정보가 충분하지 않다면 그 점을 명시하고, 가능한 한 도움이 되는 답변을 제공해주세요
- 한국어로 답변해주세요
- 답변 후에는 참고한 정보의 출처를 간단히 언급해주세요"""
        else:
            prompt = f"""사용자 질문: {message}

이 질문에 대해 도움이 되는 답변을 제공해주세요. 한국어로 답변해주세요."""
        
        return prompt
    
    def _get_default_ai_context(self, message: str) -> str:
        """검색 결과가 없을 때 기본 AI 정보 제공"""
        return "검색어가 없습니다. 구체적인 질문이나 검색하고 싶은 내용을 입력해주세요."
    
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
