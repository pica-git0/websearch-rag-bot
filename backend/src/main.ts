// Initialize tracing BEFORE importing any other modules
import { initializeTracing } from './tracing';
initializeTracing();

import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { ValidationPipe } from '@nestjs/common';
import { LoggingService } from './logging/logging.service';
import { Request, Response, NextFunction } from 'express';
import { trace, context, SpanStatusCode } from '@opentelemetry/api';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  
  // 로깅 서비스 가져오기
  const loggingService = app.get(LoggingService);
  
  // CORS 설정
  app.enableCors({
    origin: ['http://localhost:3000', 'http://frontend:3000'],
    credentials: true,
  });
  
  // 전역 파이프 설정
  app.useGlobalPipes(new ValidationPipe({
    whitelist: true,
    forbidNonWhitelisted: true,
    transform: true,
  }));
  
  // 요청 로깅 미들웨어
  app.use((req: Request, res: Response, next: NextFunction) => {
    const startTime = Date.now();
    
    res.on('finish', () => {
      const duration = (Date.now() - startTime) / 1000;
      loggingService.logRequest(
        req.method,
        req.url,
        res.statusCode,
        duration,
        {
          userAgent: req.get('User-Agent'),
          ip: req.ip,
        }
      );
    });
    
    next();
  });
  
  // 메트릭 엔드포인트
  app.use('/metrics', async (req: Request, res: Response, next: NextFunction) => {
    if (req.method === 'GET') {
      try {
        const metrics = await loggingService.getMetrics();
        res.set('Content-Type', 'text/plain');
        res.send(metrics);
      } catch (error) {
        res.status(500).send('Error generating metrics');
      }
    } else {
      next();
    }
  });
  
  // 포트 설정
  const port = process.env.PORT || 4000;
  await app.listen(port);
  
  // 시작 로그
  await loggingService.logApplicationEvent('startup', 'Backend service started', { port });
  
  console.log(`🚀 Application is running on: http://localhost:${port}`);
  console.log(`📊 GraphQL Playground: http://localhost:${port}/graphql`);
  console.log(`📈 Metrics endpoint: http://localhost:${port}/metrics`);
}

bootstrap();
