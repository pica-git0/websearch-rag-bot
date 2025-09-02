'use client'

import { useState, useEffect, useRef } from 'react'
import { PaperAirplaneIcon } from '@heroicons/react/24/outline'
import { useMutation, useLazyQuery } from '@apollo/client'
import { MessageList } from './MessageList'
import { MessageInput } from './MessageInput'
import { SEARCH_WEB, SEND_MESSAGE } from '../lib/graphql'

interface Message {
  id: string
  content: string
  role: 'user' | 'assistant'
  createdAt: string
  sources?: string[]
  contextInfo?: {
    shortTermMemory: number
    longTermMemory: number
    webSearch: number
  }
}

interface ChatInterfaceProps {
  selectedConversationId?: string | null
  onConversationSelect?: (id: string) => void
}

export function ChatInterface({ selectedConversationId, onConversationSelect }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [useWebSearch, setUseWebSearch] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // GraphQL 뮤테이션과 쿼리
  const [searchWeb] = useLazyQuery(SEARCH_WEB)
  const [sendMessage] = useMutation(SEND_MESSAGE)

  // 선택된 대화가 변경될 때 메시지 로드
  useEffect(() => {
    if (selectedConversationId) {
      const savedMessages = localStorage.getItem(`messages_${selectedConversationId}`)
      if (savedMessages) {
        setMessages(JSON.parse(savedMessages))
      } else {
        setMessages([])
      }
    }
  }, [selectedConversationId])

  // 메시지를 로컬 스토리지에 저장
  const saveMessages = (conversationId: string, messages: Message[]) => {
    localStorage.setItem(`messages_${conversationId}`, JSON.stringify(messages))
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = async () => {
    if (!inputValue.trim() || !selectedConversationId) {
      if (!inputValue.trim()) {
        // 검색어가 없을 때 사용자에게 알림
        alert('검색어를 입력해주세요.')
      }
      return
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue.trim(),
      role: 'user',
      createdAt: new Date().toISOString(),
    }

    // 사용자 메시지를 즉시 표시
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setInputValue('')
    setIsLoading(true)

    try {
      // 백엔드의 sendMessage 뮤테이션을 사용하여 RAG 서비스와 통신
      // useWebSearch 상태를 메시지에 포함하여 전달
      const { data } = await sendMessage({
        variables: {
          conversationId: selectedConversationId,
          content: inputValue.trim(),
          useWebSearch: useWebSearch
        }
      })

      if (data?.sendMessage) {
        const aiMessage: Message = {
          id: data.sendMessage.id,
          content: data.sendMessage.content,
          role: 'assistant',
          createdAt: data.sendMessage.createdAt || new Date().toISOString(),
          sources: data.sendMessage.sources || [],
          contextInfo: {
            shortTermMemory: 0,
            longTermMemory: 0,
            webSearch: data.sendMessage.sources?.length || 0
          }
        }

        const finalMessages = [...updatedMessages, aiMessage]
        setMessages(finalMessages)
      }
    } catch (error) {
      console.error('Error sending message:', error)
      
      // 에러 메시지 표시
      const errorMessage: Message = {
        id: Date.now().toString(),
        content: '죄송합니다. 메시지 전송 중 오류가 발생했습니다.',
        role: 'assistant',
        createdAt: new Date().toISOString(),
      }

      const finalMessages = [...updatedMessages, errorMessage]
      setMessages(finalMessages)
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const handleNewConversation = () => {
    if (onConversationSelect) {
      onConversationSelect('')
    }
  }

  const handleConversationSelect = (id: string) => {
    if (onConversationSelect) {
      onConversationSelect(id)
    }
  }

  const handleWebSearchToggle = (enabled: boolean) => {
    setUseWebSearch(enabled)
  }

  if (!selectedConversationId) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <div className="mx-auto h-12 w-12 text-gray-400">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h3 className="mt-2 text-sm font-medium text-gray-900">새 대화 시작</h3>
          <p className="mt-1 text-sm text-gray-500">
            왼쪽 사이드바에서 새 대화를 시작하거나 기존 대화를 선택하세요.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col">
      {/* 메시지 목록 */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          </div>
        ) : (
          <MessageList messages={messages} />
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 메시지 입력 */}
      <MessageInput
        value={inputValue}
        onChange={setInputValue}
        onSend={handleSendMessage}
        disabled={!selectedConversationId}
        useWebSearch={useWebSearch}
        onWebSearchToggle={handleWebSearchToggle}
      />
    </div>
  )
}
