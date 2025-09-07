import { Controller, Get, HttpException, HttpStatus, Query } from '@nestjs/common';
import { LoggingService } from '../logging/logging.service';

@Controller('test')
export class TestController {
  constructor(private readonly loggingService: LoggingService) {}

  @Get('error')
  async triggerError(@Query('type') errorType: string = 'generic') {
    const traceId = Math.random().toString(36).substring(7);
    
    // Log the error for testing
    await this.loggingService.logError(
      new Error(`Test error: ${errorType}`),
      { traceId, errorType, endpoint: '/test/error' }
    );

    switch (errorType) {
      case '404':
        throw new HttpException('Test resource not found', HttpStatus.NOT_FOUND);
      case '500':
        throw new HttpException('Test internal server error', HttpStatus.INTERNAL_SERVER_ERROR);
      case 'timeout':
        throw new HttpException('Test request timeout', HttpStatus.REQUEST_TIMEOUT);
      default:
        throw new HttpException('Test generic error', HttpStatus.BAD_REQUEST);
    }
  }

  @Get('success')
  async testSuccess() {
    await this.loggingService.logApplicationEvent(
      'test_success',
      'Test success endpoint called',
      { endpoint: '/test/success' }
    );
    return { message: 'Test success', timestamp: new Date().toISOString() };
  }
}