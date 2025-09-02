import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Conversation, Message } from './chat.entity';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom } from 'rxjs';

@Injectable()
export class ChatService {
  constructor(
    @InjectRepository(Conversation)
    private conversationRepository: Repository<Conversation>,
    @InjectRepository(Message)
    private messageRepository: Repository<Message>,
    private httpService: HttpService,
    private configService: ConfigService,
  ) {}

  async createConversation(title: string): Promise<Conversation> {
    const conversation = this.conversationRepository.create({ title });
    return await this.conversationRepository.save(conversation);
  }

  async getConversations(): Promise<Conversation[]> {
    return await this.conversationRepository.find({
      order: { updatedAt: 'DESC' },
    });
  }

  async getConversation(id: string): Promise<Conversation> {
    return await this.conversationRepository.findOne({ where: { id } });
  }

  async getMessages(conversationId: string): Promise<Message[]> {
    return await this.messageRepository.find({
      where: { conversationId },
      order: { createdAt: 'ASC' },
    });
  }

  async sendMessage(conversationId: string, content: string, useWebSearch: boolean = true, useStructuredResponse: boolean = false): Promise<{ message: Message; response: string; sources: string[]; contextInfo: any }> {
    // 빈 메시지 체크
    if (!content || !content.trim()) {
      const errorMessage = this.messageRepository.create({
        conversationId,
        content: '검색어가 없습니다. 구체적인 질문이나 검색하고 싶은 내용을 입력해주세요.',
        role: 'assistant',
      });
      await this.messageRepository.save(errorMessage);

      return {
        message: errorMessage,
        response: '검색어가 없습니다. 구체적인 질문이나 검색하고 싶은 내용을 입력해주세요.',
        sources: [],
        contextInfo: {
          shortTermMemory: 0,
          longTermMemory: 0,
          webSearch: 0
        }
      };
    }

    // 사용자 메시지 저장
    const userMessage = this.messageRepository.create({
      conversationId,
      content: content.trim(),
      role: 'user',
    });
    await this.messageRepository.save(userMessage);

      // RAG 서비스에 요청
      const ragServiceUrl = this.configService.get('RAG_SERVICE_URL', 'http://localhost:8000');
      console.log('=== RAG Service 호출 시작 ===');
      console.log('RAG Service URL:', ragServiceUrl);
      console.log('Request payload:', { message: content, conversation_id: conversationId, use_web_search: useWebSearch, use_structured_response: useStructuredResponse });
      
      try {
        console.log('RAG Service HTTP 요청 전송 중...');
        
        // 구조화된 답변 사용 여부에 따라 다른 엔드포인트 호출
        const endpoint = useStructuredResponse ? '/chat/structured' : '/chat';
        console.log(`사용할 엔드포인트: ${endpoint}`);
        
        const response = await firstValueFrom(
          this.httpService.post(`${ragServiceUrl}${endpoint}`, {
            message: content,
            conversation_id: conversationId,
            use_web_search: useWebSearch,
          })
        );

        console.log('=== RAG Service 응답 성공 ===');
        console.log('RAG Service Response Status:', response.status);
        console.log('RAG Service Response Headers:', response.headers);
        console.log('RAG Service Response Data:', JSON.stringify(response.data, null, 2));
        
        const { response: aiResponse, sources, context_info } = response.data;
        
        // 디버깅을 위한 로그
        console.log('=== 추출된 데이터 ===');
        console.log('AI Response:', aiResponse);
        console.log('Sources:', sources);
        console.log('Context Info:', context_info);
        console.log('Context Info type:', typeof context_info);
        console.log('Context Info value:', JSON.stringify(context_info, null, 2));

        // AI 응답 저장
        console.log('=== AI 응답 저장 시작 ===');
        console.log('저장할 sources:', sources);
        console.log('저장할 sources 타입:', typeof sources);
        console.log('저장할 sources 길이:', sources ? sources.length : 'null');
        
        const assistantMessage = this.messageRepository.create({
          conversationId,
          content: aiResponse,
          role: 'assistant',
          sources: sources || [],
        });
        
        console.log('생성된 메시지 객체:', assistantMessage);
        const savedMessage = await this.messageRepository.save(assistantMessage);
        console.log('저장된 메시지:', savedMessage);

        // 대화 제목 업데이트 (첫 번째 메시지인 경우)
        const messageCount = await this.messageRepository.count({
          where: { conversationId },
        });
        
        if (messageCount === 2) { // 사용자 메시지 + AI 응답
          const title = content.length > 50 ? content.substring(0, 50) + '...' : content;
          await this.conversationRepository.update(conversationId, { title });
        }

        return {
          message: savedMessage,
          response: aiResponse,
          sources: sources || [],
          contextInfo: context_info || {
            shortTermMemory: 0,
            longTermMemory: 0,
            webSearch: sources?.length || 0
          }
        };
    } catch (error) {
      console.error('=== RAG Service 에러 발생 ===');
      console.error('Error details:', error);
      console.error('Error message:', error.message);
      console.error('Error stack:', error.stack);
      
      // 에러 응답 저장
      const errorMessage = this.messageRepository.create({
        conversationId,
        content: '죄송합니다. 서비스에 일시적인 문제가 발생했습니다.',
        role: 'assistant',
      });
      await this.messageRepository.save(errorMessage);

      return {
        message: errorMessage,
        response: '죄송합니다. 서비스에 일시적인 문제가 발생했습니다.',
        sources: [],
        contextInfo: {
          shortTermMemory: 0,
          longTermMemory: 0,
          webSearch: 0
        }
      };
    }
  }

  async deleteConversation(id: string): Promise<void> {
    // 메시지들 먼저 삭제
    await this.messageRepository.delete({ conversationId: id });
    // 대화 삭제
    await this.conversationRepository.delete(id);
  }

  async searchWeb(query: string, maxResults: number = 5): Promise<any[]> {
    const ragServiceUrl = this.configService.get('RAG_SERVICE_URL', 'http://localhost:8000');
    
    try {
      const response = await firstValueFrom(
        this.httpService.post(`${ragServiceUrl}/search`, {
          query,
          max_results: maxResults,
        })
      );

      return response.data.results || [];
    } catch (error) {
      console.error('Web search error:', error);
      return [];
    }
  }

  async indexUrls(urls: string[]): Promise<{ success: boolean; indexedCount: number }> {
    const ragServiceUrl = this.configService.get('RAG_SERVICE_URL', 'http://localhost:8000');
    
    try {
      const response = await firstValueFrom(
        this.httpService.post(`${ragServiceUrl}/index`, urls)
      );

      return {
        success: true,
        indexedCount: response.data.indexed_count || 0,
      };
    } catch (error) {
      console.error('Index URLs error:', error);
      return {
        success: false,
        indexedCount: 0,
      };
    }
  }
}
