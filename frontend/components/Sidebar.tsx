'use client'

import { Fragment, useState, useEffect } from 'react'
import { Dialog, Transition } from '@headlessui/react'
import { XMarkIcon, PlusIcon, TrashIcon } from '@heroicons/react/24/outline'
import { format } from 'date-fns'
import { ko } from 'date-fns/locale'
import { useMutation, useQuery } from '@apollo/client'
import { CREATE_CONVERSATION, GET_CONVERSATIONS, DELETE_CONVERSATION } from '../lib/graphql'

interface Conversation {
  id: string
  title: string
  createdAt: string
  updatedAt: string
}

interface SidebarProps {
  open: boolean
  setOpen: (open: boolean) => void
  onConversationSelect?: (id: string) => void
  selectedConversationId?: string
}

export function Sidebar({ open, setOpen, onConversationSelect, selectedConversationId }: SidebarProps) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [loading, setLoading] = useState(false)

  // GraphQL 뮤테이션과 쿼리
  const [createConversation] = useMutation(CREATE_CONVERSATION)
  const [deleteConversation] = useMutation(DELETE_CONVERSATION)
  const { data: conversationsData, loading: conversationsLoading, refetch } = useQuery(GET_CONVERSATIONS)

  // 대화 목록 업데이트
  useEffect(() => {
    if (conversationsData?.conversations) {
      setConversations(conversationsData.conversations)
    }
  }, [conversationsData])

  const handleNewChat = async () => {
    try {
      setLoading(true)
      const { data } = await createConversation({
        variables: {
          title: '새 대화'
        }
      })

      if (data?.createConversation) {
        const newConversation = data.createConversation
        setConversations(prev => [newConversation, ...prev])
        
        if (onConversationSelect) {
          onConversationSelect(newConversation.id)
        }
        setOpen(false)
        
        // 대화 목록 새로고침
        refetch()
      }
    } catch (error) {
      console.error('Error creating conversation:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteConversation = async (id: string) => {
    try {
      await deleteConversation({
        variables: { id }
      })
      
      setConversations(prev => prev.filter(conv => conv.id !== id))
      
      // 대화 목록 새로고침
      refetch()
    } catch (error) {
      console.error('Error deleting conversation:', error)
    }
  }

  const SidebarContent = () => (
    <div className="flex flex-col h-full bg-white border-r border-gray-200">
      <div className="flex flex-shrink-0 items-center px-4 py-3 border-b border-gray-200">
        <h2 className="text-lg font-medium text-gray-900">대화 목록</h2>
        <button
          type="button"
          className="lg:hidden ml-auto p-1 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100"
          onClick={() => setOpen(false)}
        >
          <XMarkIcon className="h-6 w-6" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="p-4">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-primary-600 hover:bg-primary-700"
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            새 대화
          </button>
        </div>

        <div className="px-4">
          {conversationsLoading ? (
            <div className="text-center py-4">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600 mx-auto"></div>
            </div>
          ) : (
                                <div className="space-y-2">
                      {conversations.map((conversation: Conversation) => (
                <div
                  key={conversation.id}
                  className={`group flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${
                    selectedConversationId === conversation.id
                      ? 'bg-primary-50 border border-primary-200'
                      : 'hover:bg-gray-50'
                  }`}
                  onClick={() => {
                    if (onConversationSelect) {
                      onConversationSelect(conversation.id)
                    }
                    setOpen(false)
                  }}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {conversation.title}
                    </p>
                    <p className="text-xs text-gray-500">
                      {(() => {
                        try {
                          const date = conversation.updatedAt ? new Date(conversation.updatedAt) : new Date(conversation.createdAt);
                          if (isNaN(date.getTime())) {
                            return '날짜 없음';
                          }
                          return format(date, 'MMM d, yyyy', { locale: ko });
                        } catch (error) {
                          return '날짜 없음';
                        }
                      })()}
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      handleDeleteConversation(conversation.id)
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-500 transition-opacity"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )

  return (
    <Fragment>
      {/* 데스크톱 사이드바 */}
      <div className="hidden lg:flex lg:flex-shrink-0">
        <div className="flex flex-col w-80">
          <SidebarContent />
        </div>
      </div>

      {/* 모바일 사이드바 */}
      <Transition.Root show={open} as={Fragment}>
        <Dialog as="div" className="relative z-50 lg:hidden" onClose={setOpen}>
        <Transition.Child
          as={Fragment}
          enter="transition-opacity ease-linear duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="transition-opacity ease-linear duration-300"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-gray-600 bg-opacity-75" />
        </Transition.Child>

        <div className="fixed inset-0 z-40 flex">
          <Transition.Child
            as={Fragment}
            enter="transition ease-in-out duration-300 transform"
            enterFrom="-translate-x-full"
            enterTo="translate-x-0"
            leave="transition ease-in-out duration-300 transform"
            leaveFrom="translate-x-0"
            leaveTo="-translate-x-full"
          >
            <Dialog.Panel className="relative flex w-full max-w-xs flex-1 flex-col bg-white">
              <SidebarContent />
            </Dialog.Panel>
          </Transition.Child>
        </div>
      </Dialog>
    </Transition.Root>
    </Fragment>
  )
}

