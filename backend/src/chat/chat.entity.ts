import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, UpdateDateColumn } from 'typeorm';
import { ObjectType, Field, ID, Int } from '@nestjs/graphql';

@ObjectType()
export class ContextInfo {
  @Field(() => Int)
  shortTermMemory: number;

  @Field(() => Int)
  longTermMemory: number;

  @Field(() => Int)
  webSearch: number;
}

@ObjectType()
@Entity('conversations')
export class Conversation {
  @Field(() => ID)
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Field()
  @Column({ type: 'text' })
  title: string;

  @Field()
  @CreateDateColumn()
  createdAt: Date;

  @Field()
  @UpdateDateColumn()
  updatedAt: Date;
}

@ObjectType()
@Entity('messages')
export class Message {
  @Field(() => ID)
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Field()
  @Column({ type: 'uuid' })
  conversationId: string;

  @Field()
  @Column({ type: 'text' })
  content: string;

  @Field()
  @Column({ type: 'varchar', length: 10 })
  role: 'user' | 'assistant';

  @Field(() => [String], { nullable: true })
  @Column({ type: 'json', nullable: true, default: [] })
  sources: string[];

  @Field(() => ContextInfo, { nullable: true })
  contextInfo: ContextInfo;

  @Field()
  @CreateDateColumn()
  createdAt: Date;
}


