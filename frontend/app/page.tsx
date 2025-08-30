'use client'

import { useState } from 'react'
import { ChatInterface } from '@/components/ChatInterface'
import { Sidebar } from '@/components/Sidebar'
import { Header } from '@/components/Header'

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="h-screen flex overflow-hidden bg-gray-50">
      {/* 사이드바 */}
      <Sidebar open={sidebarOpen} setOpen={setSidebarOpen} />
      
      {/* 메인 콘텐츠 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* 헤더 */}
        <Header onMenuClick={() => setSidebarOpen(true)} />
        
        {/* 채팅 인터페이스 */}
        <main className="flex-1 overflow-hidden">
          <ChatInterface />
        </main>
      </div>
    </div>
  )
}
