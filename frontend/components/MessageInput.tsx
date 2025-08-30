'use client'

import { PaperAirplaneIcon } from '@heroicons/react/24/outline'

interface MessageInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  onKeyPress: (e: React.KeyboardEvent) => void
  isLoading: boolean
  disabled: boolean
}

export function MessageInput({
  value,
  onChange,
  onSend,
  onKeyPress,
  isLoading,
  disabled,
}: MessageInputProps) {
  return (
    <div className="flex items-end space-x-4">
      <div className="flex-1">
        <textarea
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyPress={onKeyPress}
          disabled={disabled || isLoading}
          placeholder={
            disabled
              ? '대화를 선택해주세요'
              : isLoading
              ? '응답을 생성하는 중...'
              : '메시지를 입력하세요 (Enter로 전송, Shift+Enter로 줄바꿈)'
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
        disabled={!value.trim() || disabled || isLoading}
        className={`p-3 rounded-lg transition-colors ${
          !value.trim() || disabled || isLoading
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : 'bg-primary-600 text-white hover:bg-primary-700'
        }`}
      >
        {isLoading ? (
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
        ) : (
          <PaperAirplaneIcon className="h-5 w-5" />
        )}
      </button>
    </div>
  )
}
