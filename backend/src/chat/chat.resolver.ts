import { Resolver, Query, Mutation, Args, Subscription } from '@nestjs/graphql';
import { ChatService } from './chat.service';
import { Conversation, Message } from './chat.entity';
import { PubSub } from 'graphql-subscriptions';

const pubSub = new PubSub();

@Resolver()
export class ChatResolver {
  constructor(private readonly chatService: ChatService) {}

  @Query(() => [Conversation])
  async conversations(): Promise<Conversation[]> {
    return await this.chatService.getConversations();
  }

  @Query(() => Conversation)
  async conversation(@Args('id') id: string): Promise<Conversation> {
    return await this.chatService.getConversation(id);
  }

  @Query(() => [Message])
  async messages(@Args('conversationId') conversationId: string): Promise<Message[]> {
    return await this.chatService.getMessages(conversationId);
  }

  @Query(() => [String])
  async searchWeb(
    @Args('query') query: string,
    @Args('maxResults', { defaultValue: 5 }) maxResults: number,
  ): Promise<string[]> {
    const results = await this.chatService.searchWeb(query, maxResults);
    return results.map(result => result.url);
  }

  @Mutation(() => Conversation)
  async createConversation(@Args('title') title: string): Promise<Conversation> {
    return await this.chatService.createConversation(title);
  }

  @Mutation(() => Message)
  async sendMessage(
    @Args('conversationId') conversationId: string,
    @Args('content') content: string,
    @Args('useWebSearch', { defaultValue: true }) useWebSearch: boolean,
  ): Promise<Message> {
    const result = await this.chatService.sendMessage(conversationId, content, useWebSearch);
    
    // 실시간 업데이트를 위한 이벤트 발행
    pubSub.publish('messageAdded', {
      messageAdded: result.message,
      conversationId,
    });

    return result.message;
  }

  @Mutation(() => Boolean)
  async deleteConversation(@Args('id') id: string): Promise<boolean> {
    await this.chatService.deleteConversation(id);
    return true;
  }

  @Mutation(() => Boolean)
  async indexUrls(@Args('urls', { type: () => [String] }) urls: string[]): Promise<boolean> {
    const result = await this.chatService.indexUrls(urls);
    return result.success;
  }

  @Subscription(() => Message, {
    filter: (payload, variables) => {
      return payload.messageAdded.conversationId === variables.conversationId;
    },
  })
  messageAdded(@Args('conversationId') conversationId: string) {
    return pubSub.asyncIterator('messageAdded');
  }
}
