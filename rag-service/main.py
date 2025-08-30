from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv

from services.rag_service import RAGService
from services.web_search import WebSearchService
from services.vector_store import VectorStoreService

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

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    use_web_search: bool = True

class ChatResponse(BaseModel):
    response: str
    sources: List[str]
    conversation_id: str

class SearchRequest(BaseModel):
    query: str
    max_results: int = 5

class SearchResponse(BaseModel):
    results: List[dict]
    total: int

@app.get("/")
async def root():
    return {"message": "WebSearch RAG Bot API", "status": "running"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        response, sources, conversation_id = await rag_service.chat(
            request.message, 
            request.conversation_id,
            request.use_web_search
        )
        return ChatResponse(
            response=response,
            sources=sources,
            conversation_id=conversation_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    try:
        results = await web_search.search(request.query, request.max_results)
        return SearchResponse(results=results, total=len(results))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/index")
async def index_urls(urls: List[str]):
    try:
        indexed_count = await rag_service.index_urls(urls)
        return {"message": f"Indexed {indexed_count} URLs successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "services": {
        "vector_store": vector_store.is_healthy(),
        "web_search": web_search.is_healthy(),
        "rag_service": rag_service.is_healthy()
    }}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
