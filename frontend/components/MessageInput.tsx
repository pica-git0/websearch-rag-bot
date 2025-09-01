'use client'

import { PaperAirplaneIcon } from '@heroicons/react/24/outline'

interface MessageInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  disabled?: boolean
}

export function MessageInput({
  value,
  onChange,
  onSend,
  disabled = false,
}: MessageInputProps) {
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div className="flex items-end space-x-4 p-4 border-t border-gray-200">
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
        disabled={!value.trim() || disabled}
        className={`p-3 rounded-lg transition-colors ${
          !value.trim() || disabled
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : 'bg-primary-600 text-white hover:bg-primary-700'
        }`}
      >
        <PaperAirplaneIcon className="h-5 w-5" />
      </button>
    </div>
  )
}
