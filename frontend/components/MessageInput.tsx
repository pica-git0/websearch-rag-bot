'use client'

import { PaperAirplaneIcon, MagnifyingGlassIcon } from '@heroicons/react/24/outline'

interface MessageInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  disabled?: boolean
  useWebSearch?: boolean
  onWebSearchToggle?: (enabled: boolean) => void
}

export function MessageInput({
  value,
  onChange,
  onSend,
  disabled = false,
  useWebSearch = true,
  onWebSearchToggle,
}: MessageInputProps) {
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  const handleWebSearchToggle = () => {
    if (onWebSearchToggle) {
      onWebSearchToggle(!useWebSearch)
    }
  }

  return (
    <div className="flex flex-col space-y-3 p-4 border-t border-gray-200">
      {/* 웹 검색 토글 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <MagnifyingGlassIcon className="h-4 w-4 text-gray-500" />
          <span className="text-sm text-gray-600">웹 검색</span>
          <span className="text-xs text-gray-400">
            {useWebSearch ? '(최신 정보 검색)' : '(로컬 메모리만)'}
          </span>
        </div>
        <button
          onClick={handleWebSearchToggle}
          disabled={disabled}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
            useWebSearch ? 'bg-primary-600' : 'bg-gray-300'
          } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              useWebSearch ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
      </div>

      {/* 메시지 입력 */}
      <div className="flex items-end space-x-4">
        <div className="flex-1">
          <textarea
            rows={1}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={disabled}
            placeholder={
              disabled
                ? '대화를 선택해주세요'
                : useWebSearch
                ? '검색하고 싶은 내용을 입력하세요 (Enter로 전송, Shift+Enter로 줄바꿈)'
                : '질문이나 대화를 입력하세요 (로컬 메모리만 사용)'
            }
            className="input-field resize-none overflow-hidden"
            style={{
              minHeight: '44px',
              maxHeight: '200px',
            }}
          />
        </div>
        
        <button
          onClick={onSend}
          disabled={!value.trim() || disabled}
          className={`p-3 rounded-lg transition-colors ${
            !value.trim() || disabled
              ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
              : 'bg-primary-600 text-white hover:bg-primary-700'
          }`}
          title={!value.trim() ? '검색어를 입력해주세요' : '메시지 전송'}
        >
          <PaperAirplaneIcon className="h-5 w-5" />
        </button>
      </div>
    </div>
  )
}
