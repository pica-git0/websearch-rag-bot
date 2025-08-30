import './globals.css'
import { Inter } from 'next/font/google'
import { ApolloProvider } from '@/components/ApolloProvider'

const inter = Inter({ subsets: ['latin'] })

export const metadata = {
  title: 'WebSearch RAG Bot',
  description: '검색 기반 대화형 챗봇 시스템',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ko">
      <body className={inter.className}>
        <ApolloProvider>
          {children}
        </ApolloProvider>
      </body>
    </html>
  )
}
