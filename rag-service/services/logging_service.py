import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

import structlog
from kafka import KafkaProducer
from elasticsearch import Elasticsearch
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request
from fastapi.responses import Response

# Prometheus 메트릭 정의
REQUEST_COUNT = Counter('rag_requests_total', 'Total number of RAG requests', ['endpoint', 'status'])
REQUEST_DURATION = Histogram('rag_request_duration_seconds', 'RAG request duration in seconds', ['endpoint'])
VECTOR_SEARCH_DURATION = Histogram('vector_search_duration_seconds', 'Vector search duration in seconds')
DOCUMENT_PROCESSING_DURATION = Histogram('document_processing_duration_seconds', 'Document processing duration in seconds')
ACTIVE_CONNECTIONS = Gauge('rag_active_connections', 'Number of active connections')

class LoggingService:
    def __init__(self):
        self.kafka_producer = None
        self.elasticsearch_client = None
        self.struct_logger = None
        
        self._setup_logging()
        self._setup_kafka()
        self._setup_elasticsearch()
    
    def _setup_logging(self):
        """구조화된 로깅 설정"""
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        self.struct_logger = structlog.get_logger()
    
    def _setup_kafka(self):
        """Kafka 프로듀서 설정"""
        try:
            kafka_brokers = os.getenv('KAFKA_BROKERS', 'kafka:29092')
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=kafka_brokers.split(','),
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None
            )
            self.struct_logger.info("Kafka producer initialized", brokers=kafka_brokers)
        except Exception as e:
            self.struct_logger.error("Failed to initialize Kafka producer", error=str(e))
    
    def _setup_elasticsearch(self):
        """Elasticsearch 클라이언트 설정"""
        try:
            es_url = os.getenv('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
            self.elasticsearch_client = Elasticsearch([es_url])
            self.struct_logger.info("Elasticsearch client initialized", url=es_url)
        except Exception as e:
            self.struct_logger.error("Failed to initialize Elasticsearch client", error=str(e))
    
    def log_application_event(self, event_type: str, message: str, **kwargs):
        """애플리케이션 이벤트 로깅"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'type': 'application',
            'event_type': event_type,
            'message': message,
            'service': 'rag-service',
            **kwargs
        }
        
        self._send_to_kafka('application-logs', log_data)
        self.struct_logger.info(message, **log_data)
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """에러 로깅"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'type': 'error',
            'error_type': type(error).__name__,
            'error_message': str(error),
            'service': 'rag-service',
            'context': context or {}
        }
        
        self._send_to_kafka('error-logs', log_data)
        self.struct_logger.error("Error occurred", **log_data)
    
    def log_performance(self, operation: str, duration: float, **kwargs):
        """성능 로깅"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'type': 'performance',
            'operation': operation,
            'duration': duration,
            'service': 'rag-service',
            **kwargs
        }
        
        self._send_to_kafka('performance-logs', log_data)
        self.struct_logger.info(f"Performance: {operation}", **log_data)
    
    def log_request(self, request: Request, response_status: int, duration: float):
        """HTTP 요청 로깅"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'type': 'request',
            'method': request.method,
            'url': str(request.url),
            'status_code': response_status,
            'duration': duration,
            'client_ip': request.client.host if request.client else None,
            'user_agent': request.headers.get('user-agent'),
            'service': 'rag-service'
        }
        
        self._send_to_kafka('application-logs', log_data)
        self.struct_logger.info("HTTP request", **log_data)
    
    def _send_to_kafka(self, topic: str, data: Dict[str, Any]):
        """Kafka로 로그 전송"""
        if self.kafka_producer:
            try:
                self.kafka_producer.send(topic, value=data)
                self.kafka_producer.flush()
            except Exception as e:
                self.struct_logger.error("Failed to send log to Kafka", error=str(e), topic=topic)
    
    def get_metrics(self) -> str:
        """Prometheus 메트릭 반환"""
        return generate_latest()
    
    def get_metrics_response(self) -> Response:
        """Prometheus 메트릭 HTTP 응답"""
        return Response(
            content=self.get_metrics(),
            media_type=CONTENT_TYPE_LATEST
        )

# 전역 로깅 서비스 인스턴스
logging_service = LoggingService()
