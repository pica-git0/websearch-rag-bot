import { Entity, PrimaryGeneratedColumn, Column, CreateDateColumn, UpdateDateColumn } from 'typeorm';
import { ObjectType, Field, ID } from '@nestjs/graphql';

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
  @Column({ type: 'json', nullable: true })
  sources: string[];

  @Field()
  @CreateDateColumn()
  createdAt: Date;
}


