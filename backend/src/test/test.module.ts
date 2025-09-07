import { Module } from '@nestjs/common';
import { TestController } from './test.controller';
import { LoggingModule } from '../logging/logging.module';

@Module({
  imports: [LoggingModule],
  controllers: [TestController],
})
export class TestModule {}