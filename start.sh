#!/bin/bash

echo "🚀 WebSearch RAG Bot 시스템을 시작합니다..."

# Docker Compose로 전체 시스템 시작
echo "📦 Docker 컨테이너들을 시작합니다..."
docker-compose up -d

# 서비스들이 준비될 때까지 대기
echo "⏳ 서비스들이 준비될 때까지 대기 중..."
sleep 30

# 서비스 상태 확인
echo "🔍 서비스 상태를 확인합니다..."

# PostgreSQL 확인
echo "📊 PostgreSQL 상태 확인..."
docker-compose exec -T postgres pg_isready -U postgres

# Qdrant 확인
echo "🧠 Qdrant 상태 확인..."
curl -f http://localhost:6333/collections || echo "Qdrant가 아직 준비되지 않았습니다."

# Kafka 확인
echo "📨 Kafka 상태 확인..."
docker-compose exec -T kafka kafka-topics --list --bootstrap-server localhost:9092 || echo "Kafka가 아직 준비되지 않았습니다."

# Elasticsearch 확인
echo "🔍 Elasticsearch 상태 확인..."
curl -f http://localhost:9200/_cluster/health || echo "Elasticsearch가 아직 준비되지 않았습니다."

# Kibana 확인
echo "📊 Kibana 상태 확인..."
curl -f http://localhost:5601/api/status || echo "Kibana가 아직 준비되지 않았습니다."

# Prometheus 확인
echo "📈 Prometheus 상태 확인..."
curl -f http://localhost:9090/api/v1/status/config || echo "Prometheus가 아직 준비되지 않았습니다."

# Grafana 확인
echo "📊 Grafana 상태 확인..."
curl -f http://localhost:3001/api/health || echo "Grafana가 아직 준비되지 않았습니다."

# RAG 서비스 확인
echo "🤖 RAG 서비스 상태 확인..."
curl -f http://localhost:8000/health || echo "RAG 서비스가 아직 준비되지 않았습니다."

# Backend 확인
echo "🔧 Backend 상태 확인..."
curl -f http://localhost:4000/graphql || echo "Backend가 아직 준비되지 않았습니다."

# Frontend 확인
echo "🎨 Frontend 상태 확인..."
curl -f http://localhost:3000 || echo "Frontend가 아직 준비되지 않았습니다."

echo ""
echo "✅ 시스템이 시작되었습니다!"
echo ""
echo "📱 접속 정보:"
echo "   Frontend: http://localhost:3000"
echo "   Backend GraphQL: http://localhost:4000/graphql"
echo "   RAG Service: http://localhost:8000"
echo "   Qdrant: http://localhost:6333"
echo "   PostgreSQL: localhost:5432"
echo ""
echo "📊 모니터링 및 로깅:"
echo "   Grafana: http://localhost:3001 (admin/admin)"
echo "   Prometheus: http://localhost:9090"
echo "   Kibana: http://localhost:5601"
echo "   Elasticsearch: http://localhost:9200"
echo "   Kafka: localhost:9092"
echo ""
echo "🛑 시스템을 중지하려면: docker-compose down"
echo "📋 로그를 확인하려면: docker-compose logs -f"
echo "📊 특정 서비스 로그: docker-compose logs -f [service-name]"
