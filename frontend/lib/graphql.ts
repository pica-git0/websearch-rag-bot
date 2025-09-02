import { gql } from '@apollo/client';

// 웹 검색 쿼리
export const SEARCH_WEB = gql`
  query SearchWeb($query: String!, $maxResults: Int) {
    searchWeb(query: $query, maxResults: $maxResults)
  }
`;

// 대화 생성 뮤테이션
export const CREATE_CONVERSATION = gql`
  mutation CreateConversation($title: String!) {
    createConversation(title: $title) {
      id
      title
      createdAt
    }
  }
`;

// 메시지 전송 뮤테이션
export const SEND_MESSAGE = gql`
  mutation SendMessage($conversationId: String!, $content: String!, $useWebSearch: Boolean, $useStructuredResponse: Boolean) {
    sendMessage(conversationId: $conversationId, content: $content, useWebSearch: $useWebSearch, useStructuredResponse: $useStructuredResponse) {
      id
      content
      role
      createdAt
      sources
      contextInfo {
        shortTermMemory
        longTermMemory
        webSearch
      }
    }
  }
`;

// 대화 목록 조회 쿼리
export const GET_CONVERSATIONS = gql`
  query GetConversations {
    conversations {
      id
      title
      createdAt
    }
  }
`;

// 대화별 메시지 조회 쿼리
export const GET_MESSAGES = gql`
  query GetMessages($conversationId: String!) {
    messages(conversationId: $conversationId) {
      id
      content
      role
      createdAt
    }
  }
`;

// URL 인덱싱 뮤테이션
export const INDEX_URLS = gql`
  mutation IndexUrls($urls: [String!]!) {
    indexUrls(urls: $urls)
  }
`;

// 대화 삭제 뮤테이션
export const DELETE_CONVERSATION = gql`
  mutation DeleteConversation($id: String!) {
    deleteConversation(id: $id)
  }
`;
