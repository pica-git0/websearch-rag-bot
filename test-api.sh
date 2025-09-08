#!/bin/bash

# 🧪 WebSearch RAG Bot API 테스트 스크립트
# API_TEST_GUIDE.md를 기반으로 생성된 자동화 테스트 스크립트

set -e

echo "🧪 WebSearch RAG Bot API 테스트 시작..."
echo "=================================="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 헬퍼 함수
print_step() {
    echo -e "\n${BLUE}$1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# 서비스 상태 확인 함수
check_service() {
    local url=$1
    local service_name=$2
    
    if curl -s -f "$url" > /dev/null; then
        print_success "$service_name 서비스 실행 중"
        return 0
    else
        print_error "$service_name 서비스가 응답하지 않습니다"
        return 1
    fi
}

# 1. 서비스 상태 확인
print_step "1. 서비스 상태 확인 중..."

# Backend GraphQL 서비스 확인 (POST 요청으로 체크)
echo "Backend (GraphQL) 서비스 확인 중..."
GRAPHQL_CHECK=$(curl -s -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ __typename }"}' || echo "error")

if echo "$GRAPHQL_CHECK" | grep -q "__typename"; then
    print_success "Backend (GraphQL) 서비스 실행 중"
else
    print_error "Backend 서비스를 시작하세요: docker-compose up -d backend"
    exit 1
fi

# RAG Service 확인
if ! check_service "http://localhost:8000/health" "RAG Service"; then
    print_error "RAG 서비스를 시작하세요: docker-compose up -d rag-service"
    exit 1
fi

# 2. GraphQL Schema 확인
print_step "2. GraphQL Schema 확인 중..."
SCHEMA_RESPONSE=$(curl -s -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ __schema { mutationType { fields { name } } } }"}')

if echo "$SCHEMA_RESPONSE" | grep -q "createConversation"; then
    print_success "GraphQL Schema 정상 - Mutations 확인됨"
else
    print_error "GraphQL Schema 문제 발생"
    echo "응답: $SCHEMA_RESPONSE"
fi

# 3. 대화 생성 테스트
print_step "3. 대화 생성 테스트 중..."
CONVERSATION_RESPONSE=$(curl -s -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { createConversation(title: \"API 테스트 대화\") { id title createdAt } }"}')

if echo "$CONVERSATION_RESPONSE" | grep -q '"id"'; then
    CONVERSATION_ID=$(echo $CONVERSATION_RESPONSE | jq -r '.data.createConversation.id')
    print_success "대화 생성 성공 - ID: $CONVERSATION_ID"
else
    print_error "대화 생성 실패"
    echo "응답: $CONVERSATION_RESPONSE"
    exit 1
fi

# 4. 대화 목록 조회 테스트
print_step "4. 대화 목록 조회 테스트 중..."
CONVERSATIONS_RESPONSE=$(curl -s -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query": "query { conversations { id title updatedAt } }"}')

if echo "$CONVERSATIONS_RESPONSE" | grep -q "$CONVERSATION_ID"; then
    print_success "대화 목록 조회 성공"
else
    print_error "대화 목록 조회 실패"
fi

# 5. 구조화된 답변 테스트
print_step "5. 구조화된 답변 테스트 중..."
STRUCTURED_RESPONSE=$(curl -s -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"mutation { sendMessage(conversationId: \\\"$CONVERSATION_ID\\\", content: \\\"인공지능에 대해 간단히 알려주세요\\\", useWebSearch: false, useStructuredResponse: true) { id content role } }\"}")

if echo "$STRUCTURED_RESPONSE" | grep -q '"content"'; then
    print_success "구조화된 답변 테스트 성공"
    echo "응답 내용 미리보기:"
    echo "$STRUCTURED_RESPONSE" | jq -r '.data.sendMessage.content' | head -3
else
    print_error "구조화된 답변 테스트 실패"
    echo "응답: $STRUCTURED_RESPONSE"
fi

# 6. 자연스러운 대화 테스트
print_step "6. 자연스러운 대화 테스트 중..."
CONVERSATIONAL_RESPONSE=$(curl -s -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"mutation { sendMessage(conversationId: \\\"$CONVERSATION_ID\\\", content: \\\"안녕하세요! 좋은 하루입니다.\\\", useWebSearch: false, useStructuredResponse: false) { id content role } }\"}")

if echo "$CONVERSATIONAL_RESPONSE" | grep -q '"content"'; then
    print_success "자연스러운 대화 테스트 성공"
    echo "응답 내용 미리보기:"
    echo "$CONVERSATIONAL_RESPONSE" | jq -r '.data.sendMessage.content' | head -2
else
    print_error "자연스러운 대화 테스트 실패"
fi

# 7. 메시지 히스토리 조회 테스트
print_step "7. 메시지 히스토리 조회 테스트 중..."
MESSAGES_RESPONSE=$(curl -s -X POST "http://localhost:4000/graphql" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"query { messages(conversationId: \\\"$CONVERSATION_ID\\\") { id content role createdAt } }\"}")

MESSAGE_COUNT=$(echo "$MESSAGES_RESPONSE" | jq '.data.messages | length')
if [ "$MESSAGE_COUNT" -gt 0 ]; then
    print_success "메시지 히스토리 조회 성공 - 총 $MESSAGE_COUNT개 메시지"
else
    print_error "메시지 히스토리 조회 실패"
fi

# 8. RAG Service REST API 테스트
print_step "8. RAG Service REST API 테스트 중..."

# Health Check
RAG_HEALTH=$(curl -s -X GET "http://localhost:8000/health")
if echo "$RAG_HEALTH" | grep -q "healthy"; then
    print_success "RAG Service 헬스 체크 통과"
else
    print_warning "RAG Service 헬스 체크 실패 또는 다른 형식"
fi

# 구조화된 답변 API 직접 테스트
RAG_STRUCTURED=$(curl -s -X POST "http://localhost:8000/chat/structured" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "AI에 대해 간단히 설명해주세요",
    "conversation_id": "test-conversation",
    "use_web_search": false
  }')

if echo "$RAG_STRUCTURED" | grep -q "AI"; then
    print_success "RAG Service 구조화된 답변 API 테스트 성공"
else
    print_warning "RAG Service 구조화된 답변 API 테스트 실패 또는 다른 응답"
fi

# 9. 성능 테스트 (간단한 동시 요청)
print_step "9. 간단한 성능 테스트 중..."
echo "5개 동시 요청으로 대화 목록 조회..."

for i in {1..5}; do
  {
    PERF_RESPONSE=$(curl -s -X POST "http://localhost:4000/graphql" \
      -H "Content-Type: application/json" \
      -d '{"query": "query { conversations { id title } }"}')
    if echo "$PERF_RESPONSE" | grep -q '"conversations"'; then
      echo "요청 $i: 성공"
    else
      echo "요청 $i: 실패"
    fi
  } &
done
wait
print_success "동시 요청 테스트 완료"

# 10. 메트릭 및 모니터링 확인
print_step "10. 메트릭 및 모니터링 확인 중..."

# Prometheus 메트릭 확인
if curl -s -f "http://localhost:9090/api/v1/query?query=up" > /dev/null; then
    print_success "Prometheus 메트릭 서버 실행 중"
else
    print_warning "Prometheus 메트릭 서버 미실행 (선택사항)"
fi

# Grafana 확인
if curl -s -f "http://localhost:3001/api/health" > /dev/null; then
    print_success "Grafana 대시보드 서버 실행 중"
else
    print_warning "Grafana 대시보드 서버 미실행 (선택사항)"
fi

# 테스트 완료
echo ""
echo "=================================="
print_success "🎉 API 테스트 완료!"
echo ""
echo "📊 테스트 결과 요약:"
echo "- 대화 ID: $CONVERSATION_ID"
echo "- 메시지 수: $MESSAGE_COUNT"
echo ""
echo "🔧 추가 테스트를 위한 유용한 명령어:"
echo "- Grafana 대시보드: http://localhost:3001 (admin/admin)"
echo "- GraphQL Playground: http://localhost:4000/graphql"
echo "- RAG Service API 문서: http://localhost:8000/docs"
echo "- Prometheus 메트릭: http://localhost:9090"
echo ""
echo "📝 자세한 API 사용법은 API_TEST_GUIDE.md를 참조하세요."