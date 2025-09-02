'use client'

import { format } from 'date-fns'
import { ko } from 'date-fns/locale'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { LinkIcon } from '@heroicons/react/24/outline'

interface Message {
  id: string
  content: string
  role: 'user' | 'assistant'
  sources?: string[]
  createdAt: string
  contextInfo?: {
    shortTermMemory: number
    longTermMemory: number
    webSearch: number
  }
}

interface MessageListProps {
  messages: Message[]
}

export function MessageList({ messages }: MessageListProps) {
  if (messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="mx-auto h-12 w-12 text-gray-400">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h3 className="mt-2 text-sm font-medium text-gray-900">대화를 시작하세요</h3>
          <p className="mt-1 text-sm text-gray-500">
            메시지를 입력하여 AI와 대화를 시작하세요.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-3xl px-4 py-3 rounded-lg ${
              message.role === 'user'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-900'
            }`}
          >
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // 링크 스타일링
                  a: ({ href, children }) => (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`underline ${
                        message.role === 'user' ? 'text-blue-200' : 'text-blue-600'
                      }`}
                    >
                      {children}
                    </a>
                  ),
                  // 코드 블록 스타일링
                  code: ({ children, className }) => {
                    const isInline = !className
                    return isInline ? (
                      <code className="bg-gray-200 px-1 py-0.5 rounded text-sm">
                        {children}
                      </code>
                    ) : (
                      <code className="block bg-gray-800 text-gray-100 p-3 rounded-lg overflow-x-auto">
                        {children}
                      </code>
                    )
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>

            {/* 컨텍스트 정보 (AI 응답에만 표시) */}
            {message.role === 'assistant' && message.contextInfo && (
              <div className="mt-3 pt-3 border-t border-gray-300">
                <div className="flex items-center text-xs text-gray-500 mb-2">
                  <svg className="h-3 w-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span>메모리 사용:</span>
                </div>
                <div className="flex space-x-4 text-xs">
                  <div className="flex items-center">
                    <div className="w-2 h-2 bg-blue-500 rounded-full mr-1"></div>
                    <span>단기기억: {message.contextInfo.shortTermMemory}개</span>
                  </div>
                  <div className="flex items-center">
                    <div className="w-2 h-2 bg-green-500 rounded-full mr-1"></div>
                    <span>이전 대화: {message.contextInfo.longTermMemory}개</span>
                  </div>
                  <div className="flex items-center">
                    <div className="w-2 h-2 bg-purple-500 rounded-full mr-1"></div>
                    <span>웹검색: {message.contextInfo.webSearch}개</span>
                  </div>
                </div>
              </div>
            )}

            {/* 소스 링크들 */}
            {message.sources && message.sources.length > 0 && (
              <div className="mt-3 pt-3 border-t border-gray-300">
                <div className="flex items-center text-xs text-gray-500 mb-2">
                  <LinkIcon className="h-3 w-3 mr-1" />
                  <span>참고 자료:</span>
                </div>
                <div className="space-y-1">
                  {message.sources.map((source, index) => (
                    <a
                      key={index}
                      href={source}
                      target="_blank"
                      rel="noopener noreferrer"
                      className={`block text-xs truncate hover:underline ${
                        message.role === 'user' ? 'text-blue-200' : 'text-blue-600'
                      }`}
                    >
                      {source}
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* 시간 표시 */}
            <div className="mt-2 text-xs opacity-70">
              {format(new Date(message.createdAt), 'HH:mm', { locale: ko })}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
