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

  async sendMessage(conversationId: string, content: string, useWebSearch: boolean = true): Promise<{ message: Message; response: string; sources: string[] }> {
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
        sources: []
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
      
      try {
        const response = await firstValueFrom(
          this.httpService.post(`${ragServiceUrl}/chat`, {
            message: content,
            conversation_id: conversationId,
            use_web_search: useWebSearch,
          })
        );

        const { response: aiResponse, sources } = response.data;

        // AI 응답 저장
        const assistantMessage = this.messageRepository.create({
          conversationId,
          content: aiResponse,
          role: 'assistant',
          sources,
        });
        await this.messageRepository.save(assistantMessage);

        // 대화 제목 업데이트 (첫 번째 메시지인 경우)
        const messageCount = await this.messageRepository.count({
          where: { conversationId },
        });
        
        if (messageCount === 2) { // 사용자 메시지 + AI 응답
          const title = content.length > 50 ? content.substring(0, 50) + '...' : content;
          await this.conversationRepository.update(conversationId, { title });
        }

        return {
          message: assistantMessage,
          response: aiResponse,
          sources: sources || []
        };
    } catch (error) {
      console.error('RAG service error:', error);
      
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
        sources: []
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
