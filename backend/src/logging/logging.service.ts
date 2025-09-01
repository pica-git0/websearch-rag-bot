import { Injectable, Logger } from '@nestjs/common';
import { Kafka, Producer } from 'kafkajs';
import { Client } from '@elastic/elasticsearch';
import { register, Counter, Histogram, Gauge, collectDefaultMetrics } from 'prom-client';
import { ConfigService } from '@nestjs/config';

// Prometheus 메트릭 정의
const REQUEST_COUNT = new Counter({
  name: 'backend_requests_total',
  help: 'Total number of backend requests',
  labelNames: ['endpoint', 'status'],
});

const REQUEST_DURATION = new Histogram({
  name: 'backend_request_duration_seconds',
  help: 'Backend request duration in seconds',
  labelNames: ['endpoint'],
});

const GRAPHQL_OPERATIONS = new Counter({
  name: 'graphql_operations_total',
  help: 'Total number of GraphQL operations',
  labelNames: ['operation', 'type'],
});

const ACTIVE_CONNECTIONS = new Gauge({
  name: 'backend_active_connections',
  help: 'Number of active connections',
});

@Injectable()
export class LoggingService {
  private readonly logger = new Logger(LoggingService.name);
  private kafkaProducer: Producer;
  private elasticsearchClient: Client;

  constructor(private configService: ConfigService) {
    this.setupPrometheus();
    // Kafka와 Elasticsearch는 비동기로 설정
    this.setupKafkaAsync();
    this.setupElasticsearchAsync();
  }

  private async setupKafkaAsync() {
    try {
      const kafkaBrokers = this.configService.get<string>('KAFKA_BROKERS', 'kafka:29092');
      const kafka = new Kafka({
        clientId: 'backend-service',
        brokers: kafkaBrokers.split(','),
      });
      this.kafkaProducer = kafka.producer();
      await this.kafkaProducer.connect();
      this.logger.log(`Kafka producer initialized with brokers: ${kafkaBrokers}`);
    } catch (error) {
      this.logger.error('Failed to initialize Kafka producer', error);
    }
  }

  private async setupElasticsearchAsync() {
    try {
      const esUrl = this.configService.get<string>('ELASTICSEARCH_URL', 'http://elasticsearch:9200');
      this.elasticsearchClient = new Client({
        node: esUrl,
      });
      this.logger.log(`Elasticsearch client initialized with URL: ${esUrl}`);
    } catch (error) {
      this.logger.error('Failed to initialize Elasticsearch client', error);
    }
  }

  private setupPrometheus() {
    collectDefaultMetrics();
  }

  async logApplicationEvent(eventType: string, message: string, metadata?: any) {
    const logData = {
      timestamp: new Date().toISOString(),
      type: 'application',
      event_type: eventType,
      message,
      service: 'backend',
      ...metadata,
    };

    await this.sendToKafka('application-logs', logData);
    this.logger.log(message, logData);
  }

  async logError(error: Error, context?: any) {
    const logData = {
      timestamp: new Date().toISOString(),
      type: 'error',
      error_type: error.constructor.name,
      error_message: error.message,
      error_stack: error.stack,
      service: 'backend',
      context: context || {},
    };

    await this.sendToKafka('error-logs', logData);
    this.logger.error('Error occurred', logData);
  }

  async logPerformance(operation: string, duration: number, metadata?: any) {
    const logData = {
      timestamp: new Date().toISOString(),
      type: 'performance',
      operation,
      duration,
      service: 'backend',
      ...metadata,
    };

    await this.sendToKafka('performance-logs', logData);
    this.logger.log(`Performance: ${operation}`, logData);
  }

  async logRequest(method: string, url: string, statusCode: number, duration: number, metadata?: any) {
    const logData = {
      timestamp: new Date().toISOString(),
      type: 'request',
      method,
      url,
      status_code: statusCode,
      duration,
      service: 'backend',
      ...metadata,
    };

    // Prometheus 메트릭 업데이트
    REQUEST_COUNT.labels(url, statusCode.toString()).inc();
    REQUEST_DURATION.labels(url).observe(duration);

    await this.sendToKafka('application-logs', logData);
    this.logger.log('HTTP request', logData);
  }

  async logGraphQLOperation(operation: string, type: string, duration: number, metadata?: any) {
    const logData = {
      timestamp: new Date().toISOString(),
      type: 'graphql',
      operation,
      operation_type: type,
      duration,
      service: 'backend',
      ...metadata,
    };

    // Prometheus 메트릭 업데이트
    GRAPHQL_OPERATIONS.labels(operation, type).inc();

    await this.sendToKafka('application-logs', logData);
    this.logger.log(`GraphQL operation: ${operation}`, logData);
  }

  private async sendToKafka(topic: string, data: any) {
    if (this.kafkaProducer) {
      try {
        await this.kafkaProducer.send({
          topic,
          messages: [
            {
              value: JSON.stringify(data),
            },
          ],
        });
      } catch (error) {
        this.logger.error('Failed to send log to Kafka', error);
      }
    }
  }

  async getMetrics(): Promise<string> {
    return register.metrics();
  }

  incrementActiveConnections() {
    ACTIVE_CONNECTIONS.inc();
  }

  decrementActiveConnections() {
    ACTIVE_CONNECTIONS.dec();
  }
}
