# WebSearch RAG Bot

검색 기반 대화형 챗봇 시스템

## 프로젝트 구조

```
websearch-rag-bot/
├── frontend/          # Next.js + React + GraphQL
├── backend/           # Nest.js + GraphQL
├── rag-service/       # Python + LangChain + Qdrant
├── docker-compose.yml # 전체 시스템 오케스트레이션
└── README.md
```

## 기술 스택

### Frontend
- Next.js 14
- React 18
- Apollo Client (GraphQL)
- Tailwind CSS
- TypeScript

### Backend
- Nest.js
- GraphQL (Apollo Server)
- TypeScript
- PostgreSQL

### RAG Service
- Python 3.11+
- LangChain
- Qdrant Vector Database
- FastAPI

## 시작하기

1. **환경 설정**
```bash
# 전체 시스템 시작
docker-compose up -d

# 또는 개별 서비스 시작
cd frontend && npm install && npm run dev
cd backend && npm install && npm run start:dev
cd rag-service && pip install -r requirements.txt && python main.py
```

2. **접속**
- Frontend: http://localhost:3000
- Backend GraphQL: http://localhost:4000/graphql
- RAG Service: http://localhost:8000

## 기능

- 🔍 웹 검색 기반 RAG (Retrieval-Augmented Generation)
- 💬 실시간 대화형 챗봇
- 🧠 벡터 데이터베이스를 통한 지식 검색
- 📊 대화 히스토리 관리
- 🎨 모던한 UI/UX