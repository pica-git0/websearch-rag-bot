import { NodeSDK } from '@opentelemetry/sdk-node';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { OTLPMetricExporter } from '@opentelemetry/exporter-metrics-otlp-http';
import { OTLPLogExporter } from '@opentelemetry/exporter-logs-otlp-http';
import { PeriodicExportingMetricReader } from '@opentelemetry/sdk-metrics';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';

// Configure the SDK with instrumentations, exporters, and resource
const sdk = new NodeSDK({
  resource: new Resource({
    [SemanticResourceAttributes.SERVICE_NAME]: 'websearch-rag-bot-backend',
    [SemanticResourceAttributes.SERVICE_VERSION]: '1.0.0',
    [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: 'development',
  }),
  
  traceExporter: new OTLPTraceExporter({
    url: 'http://otel-collector:4318/v1/traces',
    headers: {},
  }),

  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter({
      url: 'http://otel-collector:4318/v1/metrics',
      headers: {},
    }),
    exportIntervalMillis: 5000,
  }),

  logRecordProcessor: undefined, // We'll handle logs separately
  
  instrumentations: [
    getNodeAutoInstrumentations({
      // Disable instrumentations that are not needed or cause issues
      '@opentelemetry/instrumentation-fs': {
        enabled: false,
      },
      '@opentelemetry/instrumentation-http': {
        enabled: true,
        requestHook: (span, request) => {
          span.setAttributes({
            'http.request.method': request.method,
            'http.request.url': request.url,
            'http.request.headers.user-agent': request.headers['user-agent'],
          });
        },
        responseHook: (span, response) => {
          span.setAttributes({
            'http.response.status_code': response.statusCode,
            'http.response.headers.content-type': response.getHeader('content-type'),
          });
        },
      },
      '@opentelemetry/instrumentation-express': {
        enabled: true,
      },
      '@opentelemetry/instrumentation-graphql': {
        enabled: true,
      },
      '@opentelemetry/instrumentation-nestjs-core': {
        enabled: true,
      },
    }),
  ],
});

// Initialize the SDK
export function initializeTracing() {
  sdk.start();
  console.log('🔍 OpenTelemetry tracing initialized successfully');
  
  // Graceful shutdown
  process.on('SIGTERM', () => {
    sdk.shutdown()
      .then(() => console.log('Tracing terminated'))
      .catch((error) => console.log('Error terminating tracing', error))
      .finally(() => process.exit(0));
  });
}