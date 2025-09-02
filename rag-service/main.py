import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
from dotenv import load_dotenv

from services.rag_service import RAGService
from services.web_search import WebSearchService
from services.vector_store import VectorStoreService
from services.logging_service import logging_service, REQUEST_COUNT, REQUEST_DURATION

# 환경 변수 로드
load_dotenv()

app = FastAPI(title="WebSearch RAG Bot API", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 서비스 초기화
vector_store = VectorStoreService()
web_search = WebSearchService()
rag_service = RAGService(vector_store, web_search)

# 로깅 서비스 초기화
logging_service.log_application_event("startup", "RAG Service started")

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    use_web_search: bool = True
    search_results: Optional[List[str]] = None

class ChatResponse(BaseModel):
    response: str
    sources: List[str]
    conversation_id: str
    context_info: Optional[Dict[str, int]] = None

class SearchRequest(BaseModel):
    query: str
    max_results: int = 5

class SearchResponse(BaseModel):
    results: List[dict]
    total: int

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """요청 로깅 미들웨어"""
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    status_code = response.status_code
    
    # Prometheus 메트릭 업데이트
    REQUEST_COUNT.labels(endpoint=request.url.path, status=status_code).inc()
    REQUEST_DURATION.labels(endpoint=request.url.path).observe(duration)
    
    # 로그 기록
    logging_service.log_request(request, status_code, duration)
    
    return response

@app.get("/")
async def root():
    logging_service.log_application_event("health_check", "Root endpoint accessed")
    return {"message": "WebSearch RAG Bot API", "status": "running"}

@app.get("/metrics")
async def metrics():
    """Prometheus 메트릭 엔드포인트"""
    return logging_service.get_metrics_response()

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start_time = time.time()
    
    try:
        logging_service.log_application_event(
            "chat_request", 
            "Chat request received", 
            message_length=len(request.message),
            use_web_search=request.use_web_search
        )
        
        response, sources, conversation_id, context_info = await rag_service.chat(
            request.message, 
            request.conversation_id,
            request.use_web_search
        )
        
        duration = time.time() - start_time
        logging_service.log_performance(
            "chat_processing", 
            duration,
            message_length=len(request.message),
            sources_count=len(sources)
        )
        
        return ChatResponse(
            response=response,
            sources=sources,
            conversation_id=conversation_id,
            context_info=context_info
        )
    except Exception as e:
        duration = time.time() - start_time
        logging_service.log_error(e, {
            "endpoint": "/chat",
            "message": request.message,
            "duration": duration
        })
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    start_time = time.time()
    
    try:
        logging_service.log_application_event(
            "search_request", 
            "Search request received", 
            query=request.query,
            max_results=request.max_results
        )
        
        results = await web_search.search(request.query, request.max_results)
        
        duration = time.time() - start_time
        logging_service.log_performance(
            "web_search", 
            duration,
            query=request.query,
            results_count=len(results)
        )
        
        return SearchResponse(results=results, total=len(results))
    except Exception as e:
        duration = time.time() - start_time
        logging_service.log_error(e, {
            "endpoint": "/search",
            "query": request.query,
            "duration": duration
        })
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/index")
async def index_urls(urls: List[str]):
    start_time = time.time()
    
    try:
        logging_service.log_application_event(
            "index_request", 
            "URL indexing request received", 
            urls_count=len(urls)
        )
        
        indexed_count = await rag_service.index_urls(urls)
        
        duration = time.time() - start_time
        logging_service.log_performance(
            "url_indexing", 
            duration,
            urls_count=len(urls),
            indexed_count=indexed_count
        )
        
        return {"message": f"Indexed {indexed_count} URLs successfully"}
    except Exception as e:
        duration = time.time() - start_time
        logging_service.log_error(e, {
            "endpoint": "/index",
            "urls_count": len(urls),
            "duration": duration
        })
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    try:
        health_status = {
            "vector_store": vector_store.is_healthy(),
            "web_search": web_search.is_healthy(),
            "rag_service": rag_service.is_healthy()
        }
        
        logging_service.log_application_event(
            "health_check", 
            "Health check performed", 
            health_status=health_status
        )
        
        return {"status": "healthy", "services": health_status}
    except Exception as e:
        logging_service.log_error(e, {"endpoint": "/health"})
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
