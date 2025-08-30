'use client'

import { useState, useEffect, useRef } from 'react'
import { useMutation, useQuery } from '@apollo/client'
import { gql } from '@apollo/client'
import { PaperAirplaneIcon } from '@heroicons/react/24/outline'
import { MessageList } from './MessageList'
import { MessageInput } from './MessageInput'

const GET_MESSAGES = gql`
  query GetMessages($conversationId: String!) {
    messages(conversationId: $conversationId) {
      id
      content
      role
      sources
      createdAt
    }
  }
`

const SEND_MESSAGE = gql`
  mutation SendMessage($conversationId: String!, $content: String!) {
    sendMessage(conversationId: $conversationId, content: $content) {
      id
      content
      role
      sources
      createdAt
    }
  }
`

export function ChatInterface() {
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null)
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { data: messagesData, loading: messagesLoading, refetch } = useQuery(GET_MESSAGES, {
    variables: { conversationId: selectedConversationId || '' },
    skip: !selectedConversationId,
  })

  const [sendMessage] = useMutation(SEND_MESSAGE, {
    onCompleted: () => {
      refetch()
      setIsLoading(false)
      setInputValue('')
    },
    onError: (error) => {
      console.error('Error sending message:', error)
      setIsLoading(false)
    },
  })

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messagesData])

  const handleSendMessage = async () => {
    if (!inputValue.trim() || !selectedConversationId || isLoading) return

    setIsLoading(true)
    try {
      await sendMessage({
        variables: {
          conversationId: selectedConversationId,
          content: inputValue.trim(),
        },
      })
    } catch (error) {
      console.error('Error sending message:', error)
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
    setSelectedConversationId(null)
  }

  const handleConversationSelect = (id: string) => {
    setSelectedConversationId(id)
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
        {messagesLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
          </div>
        ) : (
          <MessageList messages={messagesData?.messages || []} />
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
