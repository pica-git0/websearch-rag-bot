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
    
    def _create_fallback_llm(self):
        """대체 LLM 생성 (OpenAI API 키가 없을 경우)"""
        class FallbackLLM:
            def __call__(self, prompt: str) -> str:
                # 간단한 응답 생성
                return f"죄송합니다. 현재 OpenAI API 키가 설정되지 않아 완전한 응답을 제공할 수 없습니다. 질문: {prompt}"
        
        return FallbackLLM()
    
    async def chat(self, message: str, conversation_id: str = None, use_web_search: bool = True, search_results: List[str] = None) -> Tuple[str, List[str], str]:
        """챗봇 대화 처리"""
        try:
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
            
            # 웹 검색 수행 (필요한 경우)
            context_docs = []
            sources = []
            
            if use_web_search:
                if search_results:
                    # 백엔드로부터 받은 검색 결과 사용
                    for url in search_results:
                        if url:
                            # URL에서 콘텐츠 추출
                            content = await self.web_search.fetch_url_content(url)
                            if content.get('content'):
                                context_docs.append(content)
                                sources.append(url)
                else:
                    # 백엔드 검색 결과가 없으면 직접 웹 검색 수행
                    search_results = await self.web_search.search(message, max_results=3)
                    
                    for result in search_results:
                        if result.get('url'):
                            # URL에서 콘텐츠 추출
                            content = await self.web_search.fetch_url_content(result['url'])
                            if content.get('content'):
                                context_docs.append(content)
                                sources.append(result['url'])
            
            # 벡터 스토어에서 유사한 문서 검색
            vector_results = self.vector_store.search(message, top_k=3)
            for result in vector_results:
                if result.get('content'):
                    context_docs.append(result)
                    if result.get('url'):
                        sources.append(result['url'])
            
            # 컨텍스트 생성
            context = self._create_context(context_docs)
            
            # 프롬프트 생성
            prompt = self._create_prompt(message, context)
            
            # LLM 응답 생성
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
            
            return response, sources, conversation_id
            
        except Exception as e:
            print(f"Error in chat: {e}")
            return f"죄송합니다. 오류가 발생했습니다: {str(e)}", [], conversation_id or str(uuid.uuid4())
    
    def _create_context(self, documents: List[Dict[str, Any]]) -> str:
        """문서들로부터 컨텍스트 생성"""
        if not documents:
            return ""
        
        context_parts = []
        for doc in documents:
            content = doc.get('content', '')
            title = doc.get('title', '')
            url = doc.get('url', '')
            
            if content:
                context_part = f"제목: {title}\nURL: {url}\n내용: {content[:500]}...\n"
                context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _create_prompt(self, message: str, context: str) -> str:
        """프롬프트 생성"""
        if context:
            prompt = f"""다음은 사용자의 질문과 관련된 정보입니다:

{context}

사용자 질문: {message}

위의 정보를 바탕으로 사용자의 질문에 답변해주세요. 정보가 충분하지 않다면 그 점을 명시하고, 가능한 한 도움이 되는 답변을 제공해주세요. 한국어로 답변해주세요."""
        else:
            prompt = f"""사용자 질문: {message}

이 질문에 대해 도움이 되는 답변을 제공해주세요. 한국어로 답변해주세요."""
        
        return prompt
    
    async def index_urls(self, urls: List[str]) -> int:
        """URL들을 인덱싱"""
        try:
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
                        doc_objects.append({
                            'content': doc_text,
                            'url': url,
                            'title': content.get('title', ''),
                            'metadata': {
                                'chunk_index': i,
                                'total_chunks': len(documents),
                                'source_url': url
                            }
                        })
                    
                    # 벡터 스토어에 저장
                    self.vector_store.add_documents(doc_objects)
                    indexed_count += 1
            
            return indexed_count
            
        except Exception as e:
            print(f"Error indexing URLs: {e}")
            return 0
    
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
        """대화 히스토리 삭제"""
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
