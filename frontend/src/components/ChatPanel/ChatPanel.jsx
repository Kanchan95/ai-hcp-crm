import { useEffect, useRef, useState } from 'react'
import { useSelector } from 'react-redux'
import './ChatPanel.css'

const INSTRUCTION_TEXT =
  'Log interaction details here (e.g., "Met Dr. Smith, discussed Product X efficacy, ' +
  'positive sentiment, shared brochure") or ask for help.'

function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  return (
    <div className={`msg-row ${isUser ? 'msg-user' : 'msg-ai'}`}>
      {!isUser && <div className="msg-avatar">🤖</div>}
      <div className={`msg-bubble ${isUser ? 'bubble-user' : 'bubble-ai'}`}>
        {message.content}
      </div>
    </div>
  )
}

function TypingDots() {
  return (
    <div className="msg-row msg-ai">
      <div className="msg-avatar">🤖</div>
      <div className="msg-bubble bubble-ai typing-dots">
        <span /><span /><span />
      </div>
    </div>
  )
}

export default function ChatPanel({ onSendMessage }) {
  const { messages, isLoading } = useSelector(state => state.chat)
  const [input, setInput] = useState('')
  const messagesRef = useRef(null)  // ref on the scroll container, not the bottom sentinel

  // Scroll the chat-messages DIV itself to the bottom — never touches the page scroll
  useEffect(() => {
    const el = messagesRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, isLoading])

  const handleSubmit = (e) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || isLoading) return
    setInput('')
    onSendMessage(text)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <div className="chat-panel">
      {/* Header */}
      <div className="chat-header">
        <span className="chat-header-icon">🤖</span>
        <div>
          <div className="chat-header-title">AI Assistant</div>
          <div className="chat-header-sub">Log interaction via chat</div>
        </div>
      </div>

      {/* Message area — ref here so scroll is contained within this div */}
      <div className="chat-messages" ref={messagesRef}>
        {/* Static instruction bubble shown at top always */}
        <div className="instruction-bubble">{INSTRUCTION_TEXT}</div>

        {messages.map(msg => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isLoading && <TypingDots />}
      </div>

      {/* Input bar */}
      <form className="chat-input-bar" onSubmit={handleSubmit}>
        <input
          className="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe interaction..."
          disabled={isLoading}
        />
        <button
          type="submit"
          className="log-btn"
          disabled={isLoading || !input.trim()}
        >
          {isLoading ? '…' : '▲ Log'}
        </button>
      </form>
    </div>
  )
}
