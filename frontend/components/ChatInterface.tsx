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
  sources?: string[]
  createdAt: string
}

interface ChatInterfaceProps {
  selectedConversationId?: string | null
  onConversationSelect?: (id: string) => void
}

export function ChatInterface({ selectedConversationId, onConversationSelect }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
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
    setMessages(messages)
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = async () => {
    if (!inputValue.trim() || !selectedConversationId || isLoading) return

    setIsLoading(true)
    
    // 사용자 메시지 추가
    const userMessage: Message = {
      id: `msg_${Date.now()}_user`,
      content: inputValue.trim(),
      role: 'user',
      createdAt: new Date().toISOString(),
    }
    
    const updatedMessages = [...messages, userMessage]
    saveMessages(selectedConversationId, updatedMessages)
    
    try {
      // 백엔드의 searchWeb 리졸버를 사용하여 웹 검색 수행
      const { data: searchData } = await searchWeb({
        variables: {
          query: inputValue.trim(),
          maxResults: 5
        }
      })
      
      // 검색 결과를 RAG 서비스에 전송
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputValue.trim(),
          conversation_id: selectedConversationId,
          use_web_search: true,
          search_results: searchData?.searchWeb || []
        }),
      })
      
      if (response.ok) {
        const data = await response.json()
        
        // AI 응답 추가
        const aiMessage: Message = {
          id: `msg_${Date.now()}_ai`,
          content: data.response,
          role: 'assistant',
          sources: data.sources,
          createdAt: new Date().toISOString(),
        }
        
        const finalMessages = [...updatedMessages, aiMessage]
        saveMessages(selectedConversationId, finalMessages)
        
        // 백엔드에 메시지 저장
        try {
          await sendMessage({
            variables: {
              conversationId: selectedConversationId,
              content: inputValue.trim()
            }
          })
        } catch (error) {
          console.error('Error saving message to backend:', error)
        }
      } else {
        throw new Error('Failed to get response from RAG service')
      }
    } catch (error) {
      console.error('Error sending message:', error)
      
      // 에러 메시지 추가
      const errorMessage: Message = {
        id: `msg_${Date.now()}_error`,
        content: '죄송합니다. 서비스에 일시적인 문제가 발생했습니다.',
        role: 'assistant',
        createdAt: new Date().toISOString(),
      }
      
      const finalMessages = [...updatedMessages, errorMessage]
      saveMessages(selectedConversationId, finalMessages)
    }
    
    setIsLoading(false)
    setInputValue('')
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
      <div className="border-t border-gray-200 p-4">
        <MessageInput
          value={inputValue}
          onChange={setInputValue}
          onSend={handleSendMessage}
          onKeyPress={handleKeyPress}
          isLoading={isLoading}
          disabled={!selectedConversationId}
        />
      </div>
    </div>
  )
}
