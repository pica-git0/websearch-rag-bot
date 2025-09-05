# WebSearch RAG Bot

검색 기반 대화형 챗봇 시스템

## 프로젝트 구조

```
websearch-rag-bot/
├── frontend/          # Next.js + React + GraphQL
├── backend/           # Nest.js + GraphQL
├── rag-service/       # Python + LangChain + Qdrant
├── logging/           # 로깅 및 모니터링 설정
│   ├── prometheus/    # Prometheus 설정
│   ├── grafana/       # Grafana 대시보드
│   └── logstash/      # Logstash 파이프라인
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

### 로깅 및 모니터링
- **Kafka**: 로그 스트리밍 및 메시지 브로커
- **Elasticsearch**: 로그 저장 및 검색
- **Kibana**: 로그 시각화 및 분석
- **Prometheus**: 메트릭 수집
- **Grafana**: 메트릭 시각화 및 대시보드
- **Logstash**: 로그 처리 및 파이프라인

## 시작하기

1. **환경 설정**
```bash
# 전체 시스템 시작 (로깅 시스템 포함)
./start.sh

# 또는 수동으로 시작
docker-compose up -d
```

2. **접속**
- Frontend: http://localhost:3000
- Backend GraphQL: http://localhost:4000/graphql
- RAG Service: http://localhost:8000

3. **모니터링 및 로깅**
- Grafana: http://localhost:3001 (admin/admin)
- Prometheus: http://localhost:9090
- Kibana: http://localhost:5601
- Elasticsearch: http://localhost:9200

## 기능

- 🔍 웹 검색 기반 RAG (Retrieval-Augmented Generation)
- 💬 실시간 대화형 챗봇
- 🧠 벡터 데이터베이스를 통한 지식 검색
- 📊 대화 히스토리 관리
- 🎨 모던한 UI/UX
- 📈 실시간 시스템 모니터링
- 📝 구조화된 로깅 및 분석
- 🚨 에러 추적 및 알림

## 로깅 및 모니터링

### 로그 수집
- **Kafka**: 모든 서비스의 로그를 중앙에서 수집
- **Logstash**: 로그 처리 및 Elasticsearch로 전송
- **Elasticsearch**: 로그 저장 및 인덱싱

### 메트릭 수집
- **Prometheus**: 시스템 메트릭 수집
- **Grafana**: 메트릭 시각화 및 대시보드

### 대시보드
1. **시스템 개요**: 전체 시스템 성능 및 상태
2. **로그 분석**: 실시간 로그 분석 및 검색

### 로그 타입
- **Application**: 애플리케이션 이벤트
- **Error**: 에러 및 예외
- **Performance**: 성능 메트릭
- **Request**: HTTP 요청/응답
- **GraphQL**: GraphQL 작업

