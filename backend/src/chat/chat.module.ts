import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { HttpModule } from '@nestjs/axios';
import { ChatService } from './chat.service';
import { ChatResolver } from './chat.resolver';
import { Conversation, Message } from './chat.entity';

@Module({
  imports: [
    TypeOrmModule.forFeature([Conversation, Message]),
    HttpModule,
  ],
  providers: [ChatService, ChatResolver],
  exports: [ChatService],
})
export class ChatModule {}
