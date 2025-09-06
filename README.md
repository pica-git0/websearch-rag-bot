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

1. **환경 변수 설정**

프로젝트 루트에 `.env` 파일을 생성하고 API 키들을 설정하세요:
```bash
# 프로젝트 루트에 .env 파일 생성
touch .env
```

`.env` 파일에 다음 내용을 추가하세요:
```env
# OpenAI API 설정
OPENAI_API_KEY=your_openai_api_key_here

# Google Custom Search API 설정
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_CSE_ID=your_google_custom_search_engine_id_here

```

**중요**: 실제 API 키 값으로 교체해야 합니다!

2. **시스템 시작**
```bash
# 전체 시스템 시작 (로깅 시스템 포함)
./start.sh

# 또는 수동으로 시작
docker-compose up -d
```

3. **접속**
- Frontend: http://localhost:3000
- Backend GraphQL: http://localhost:4000/graphql
- RAG Service: http://localhost:8000

4. **모니터링 및 로깅**
- Grafana: http://localhost:3001 (admin/admin)
- Prometheus: http://localhost:9090
- Kibana: http://localhost:5601
- Elasticsearch: http://localhost:9200

## 사용법

### 🎛️ 대화 모드 선택

#### 구조화된 답변 모드 (ON)
- **용도**: 정보 검색, 분석, 연구
- **특징**: 마크다운 형식의 체계적 분석
- **예시**: "인공지능에 대해 알려주세요" → 주제별 상세 분석

#### 자연스러운 대화 모드 (OFF)
- **용도**: 일상 대화, 감정적 소통, 개인적 상담
- **특징**: 친근하고 자연스러운 대화
- **예시**: "오늘 날씨가 좋네요" → 공감과 대화 이어가기

### 💬 대화 시작하기

1. **새 대화 생성**: 사이드바에서 "새 대화" 클릭
2. **모드 선택**: 하단 토글에서 원하는 모드 선택
3. **메시지 입력**: 텍스트 입력 후 Enter 또는 전송 버튼 클릭
4. **대화 이어가기**: 이전 대화 내용을 기억하며 맥락 유지

### 🔧 고급 설정

#### 웹 검색 토글
- **ON**: 최신 정보 검색 포함
- **OFF**: 로컬 메모리만 사용

#### 구조화된 답변 토글
- **ON**: 체계적 분석 답변
- **OFF**: 자연스러운 대화형 답변

## 기능

### 🤖 AI 챗봇 기능
- 🔍 **웹 검색 기반 RAG**: Google Custom Search API를 통한 실시간 정보 검색
- 💬 **이중 모드 대화**: 구조화된 분석 vs 자연스러운 대화
- 🧠 **메모리 시스템**: 단기/장기 기억을 통한 맥락 유지
- 📊 **벡터 검색**: Qdrant를 활용한 의미 기반 정보 검색
- 🎯 **감정 인식**: 사용자 감정 분석 및 적절한 응답 생성

### 🎨 사용자 인터페이스
- 📱 **반응형 디자인**: 모바일/데스크톱 최적화
- 🎛️ **토글 모드**: 구조화된 답변 ↔ 자연스러운 대화 전환
- 💾 **대화 히스토리**: 로컬 스토리지 기반 대화 저장
- 🔄 **실시간 업데이트**: GraphQL 구독을 통한 실시간 메시지

### 🏗️ 시스템 기능
- 📈 **실시간 모니터링**: Grafana + Prometheus 기반 시스템 모니터링
- 📝 **구조화된 로깅**: ELK 스택 기반 로그 분석
- 🚨 **에러 추적**: 실시간 에러 모니터링 및 알림
- 🔧 **마이크로서비스**: Docker 기반 서비스 분리

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

## 📚 문서

- **[개발 가이드](DEVELOPMENT_GUIDE.md)**: 상세한 개발 및 배포 가이드
- **[API 테스트 가이드](API_TEST_GUIDE.md)**: API 테스트 및 성능 측정 가이드
- **[API 문서](DEVELOPMENT_GUIDE.md#api-문서)**: GraphQL 및 REST API 문서
- **[문제 해결](DEVELOPMENT_GUIDE.md#문제-해결)**: 일반적인 문제 해결 방법

