# 🧪 API 테스트 가이드

## 📋 목차
1. [GraphQL API 테스트](#graphql-api-테스트)
2. [REST API 테스트](#rest-api-테스트)
3. [자동화 테스트](#자동화-테스트)
4. [성능 테스트](#성능-테스트)

---

## 🔍 GraphQL API 테스트

### 1. 대화 생성 테스트

```bash
curl -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { createConversation(title: \"테스트 대화\") { id title createdAt } }"
  }'
```

**예상 응답:**
```json
{
  "data": {
    "createConversation": {
      "id": "420854bd-fd6a-4d31-bf1b-0f9c95a0b2e7",
      "title": "테스트 대화",
      "createdAt": "2025-01-09T02:00:00.000Z"
    }
  }
}
```

### 2. 구조화된 답변 모드 테스트

```bash
curl -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { sendMessage(conversationId: \"YOUR_CONVERSATION_ID\", content: \"인공지능에 대해 알려주세요\", useWebSearch: true, useStructuredResponse: true) { id content role sources contextInfo { shortTermMemory longTermMemory webSearch } } }"
  }'
```

### 3. 자연스러운 대화 모드 테스트

```bash
curl -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { sendMessage(conversationId: \"YOUR_CONVERSATION_ID\", content: \"안녕하세요! 오늘 날씨가 좋네요.\", useWebSearch: true, useStructuredResponse: false) { id content role sources contextInfo { shortTermMemory longTermMemory webSearch } } }"
  }'
```

### 4. 대화 목록 조회 테스트

```bash
curl -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { conversations { id title updatedAt } }"
  }'
```

### 5. 메시지 히스토리 조회 테스트

```bash
curl -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { messages(conversationId: \"YOUR_CONVERSATION_ID\") { id content role createdAt sources } }"
  }'
```

---

## 🌐 REST API 테스트

### 1. RAG Service 헬스 체크

```bash
curl -X GET "http://localhost:8000/health"
```

**예상 응답:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-09T02:00:00.000Z"
}
```

### 2. 구조화된 답변 API 테스트

```bash
curl -X POST "http://localhost:8000/chat/structured" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "인공지능에 대해 알려주세요",
    "conversation_id": "test-conversation",
    "use_web_search": true
  }'
```

### 3. 대화형 챗봇 API 테스트

```bash
curl -X POST "http://localhost:8000/chat/conversational" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "안녕하세요! 오늘 기분이 좋아요.",
    "conversation_id": "test-conversation"
  }'
```

### 4. 웹 검색 API 테스트

```bash
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "인공지능 최신 동향",
    "max_results": 5
  }'
```

### 5. URL 인덱싱 API 테스트

```bash
curl -X POST "http://localhost:8000/index" \
  -H "Content-Type: application/json" \
  -d '[
    "https://example.com/article1",
    "https://example.com/article2"
  ]'
```

---

## 🤖 자동화 테스트

### 1. 전체 플로우 테스트 스크립트

```bash
#!/bin/bash

echo "🧪 WebSearch RAG Bot API 테스트 시작..."

# 1. 대화 생성
echo "1. 대화 생성 중..."
CONVERSATION_RESPONSE=$(curl -s -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { createConversation(title: \"API 테스트 대화\") { id } }"}')

CONVERSATION_ID=$(echo $CONVERSATION_RESPONSE | jq -r '.data.createConversation.id')
echo "생성된 대화 ID: $CONVERSATION_ID"

# 2. 구조화된 답변 테스트
echo "2. 구조화된 답변 테스트 중..."
curl -s -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"mutation { sendMessage(conversationId: \\\"$CONVERSATION_ID\\\", content: \\\"인공지능에 대해 알려주세요\\\", useWebSearch: true, useStructuredResponse: true) { id content } }\"}" \
  | jq '.data.sendMessage.content' | head -3

# 3. 자연스러운 대화 테스트
echo "3. 자연스러운 대화 테스트 중..."
curl -s -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"mutation { sendMessage(conversationId: \\\"$CONVERSATION_ID\\\", content: \\\"안녕하세요! 오늘 날씨가 좋네요.\\\", useWebSearch: true, useStructuredResponse: false) { id content } }\"}" \
  | jq '.data.sendMessage.content'

echo "✅ API 테스트 완료!"
```

### 2. 성능 테스트 스크립트

```bash
#!/bin/bash

echo "⚡ 성능 테스트 시작..."

# 동시 요청 테스트
echo "동시 요청 테스트 (10개 요청)..."
for i in {1..10}; do
  curl -s -X POST "http://localhost:4000/graphql" \
    -H "Content-Type: application/json" \
    -d '{"query": "query { conversations { id title } }"}' &
done
wait

echo "✅ 성능 테스트 완료!"
```

---

## 📊 성능 테스트

### 1. 응답 시간 측정

```bash
# 단일 요청 응답 시간 측정
time curl -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query": "query { conversations { id title } }"}'
```

### 2. 동시 요청 테스트

```bash
# 10개 동시 요청
seq 1 10 | xargs -n1 -P10 -I{} curl -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query": "query { conversations { id title } }"}'
```

### 3. 메모리 사용량 모니터링

```bash
# Docker 컨테이너 메모리 사용량 확인
docker stats --no-stream
```

---

## 🔧 테스트 환경 설정

### 1. 테스트 데이터 준비

```bash
# 테스트용 대화 생성
curl -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "mutation { createConversation(title: \"테스트 대화 1\") { id } createConversation(title: \"테스트 대화 2\") { id } }"
  }'
```

### 2. 로그 모니터링

```bash
# 실시간 로그 모니터링
docker-compose logs -f backend rag-service

# 특정 패턴 필터링
docker-compose logs -f | grep -E "(ERROR|WARN|INFO)"
```

### 3. 메트릭 확인

```bash
# Prometheus 메트릭 확인
curl http://localhost:9090/api/v1/query?query=up

# Grafana 대시보드 확인
open http://localhost:3001
```

---

## 🐛 디버깅 팁

### 1. GraphQL 쿼리 디버깅

```bash
# GraphQL Playground 사용
open http://localhost:4000/graphql

# 쿼리 검증
curl -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ __schema { types { name } } }"}'
```

### 2. RAG Service 디버깅

```bash
# 상세 로그 확인
docker-compose logs -f rag-service

# API 엔드포인트 확인
curl http://localhost:8000/docs
```

### 3. 데이터베이스 상태 확인

```bash
# PostgreSQL 연결 확인
docker-compose exec postgres pg_isready -U postgres

# Qdrant 상태 확인
curl http://localhost:6333/collections
```

---

## 📝 테스트 체크리스트

### ✅ 기본 기능 테스트
- [ ] 대화 생성
- [ ] 메시지 전송 (구조화된 답변)
- [ ] 메시지 전송 (자연스러운 대화)
- [ ] 대화 목록 조회
- [ ] 메시지 히스토리 조회

### ✅ 고급 기능 테스트
- [ ] 웹 검색 기능
- [ ] 메모리 시스템
- [ ] 감정 인식
- [ ] 벡터 검색
- [ ] URL 인덱싱

### ✅ 성능 테스트
- [ ] 응답 시간 측정
- [ ] 동시 요청 처리
- [ ] 메모리 사용량
- [ ] 데이터베이스 성능

### ✅ 에러 처리 테스트
- [ ] 잘못된 입력 처리
- [ ] 네트워크 오류 처리
- [ ] API 키 오류 처리
- [ ] 데이터베이스 연결 오류

---

## 🚀 CI/CD 통합

### GitHub Actions 예시

```yaml
name: API Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Start services
      run: docker-compose up -d
      
    - name: Wait for services
      run: sleep 30
      
    - name: Run API tests
      run: ./test-api.sh
      
    - name: Cleanup
      run: docker-compose down
```

---

이 테스트 가이드를 통해 WebSearch RAG Bot의 모든 API를 체계적으로 테스트할 수 있습니다! 🎉
