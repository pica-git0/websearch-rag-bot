import { NodeSDK } from '@opentelemetry/sdk-node';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';

// OpenTelemetry configuration with Tempo-compatible resource attributes
// Environment variables take precedence over code-defined attributes
const sdk = new NodeSDK({
  resource: new Resource({
    // Core service identification (will be overridden by OTEL_RESOURCE_ATTRIBUTES)
    [SemanticResourceAttributes.SERVICE_NAME]: process.env.OTEL_SERVICE_NAME || 'websearch-rag-bot',
    [SemanticResourceAttributes.SERVICE_VERSION]: '1.0.0',
    [SemanticResourceAttributes.SERVICE_NAMESPACE]: 'websearch',
    [SemanticResourceAttributes.SERVICE_INSTANCE_ID]: 'backend-1',
    
    // Deployment context
    [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: 'development',
    
    // Custom attributes for Tempo indexing
    'application': 'websearch-rag-bot',
    'component': 'backend',
    'tier': 'api',
    'framework': 'nestjs'
  }).merge(new Resource({})), // This allows env vars to take precedence
  traceExporter: new OTLPTraceExporter({
    url: 'http://otel-collector:4318/v1/traces',
  }),
  instrumentations: [getNodeAutoInstrumentations({
    '@opentelemetry/instrumentation-fs': { enabled: false },
  })],
});

export function initializeTracing() {
  sdk.start();
  console.log('🔍 OpenTelemetry tracing initialized successfully');
  
  process.on('SIGTERM', () => {
    sdk.shutdown()
      .then(() => console.log('Tracing terminated'))
      .catch((error) => console.log('Error terminating tracing', error))
      .finally(() => process.exit(0));
  });
}