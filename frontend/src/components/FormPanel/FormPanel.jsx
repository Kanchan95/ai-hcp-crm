import { useLayoutEffect, useRef } from 'react'
import { useSelector } from 'react-redux'
import './FormPanel.css'

const INTERACTION_TYPES = ['Meeting', 'Phone Call', 'Email', 'Conference', 'Webinar', 'Product Detail']

export default function FormPanel() {
  const f = useSelector(state => state.interaction)
  const panelRef = useRef(null)
  const scrollRef = useRef(0)

  // Save scroll position before React re-renders, restore it after
  useLayoutEffect(() => {
    const el = panelRef.current
    if (!el) return
    el.scrollTop = scrollRef.current
  })

  const handleScroll = () => {
    if (panelRef.current) scrollRef.current = panelRef.current.scrollTop
  }

  // Helpers to display array fields as readable text
  const join    = (arr, sep = ', ') => Array.isArray(arr) && arr.length ? arr.join(sep) : ''
  const joinNL  = (arr) => Array.isArray(arr) && arr.length ? arr.join('\n') : ''

  return (
    <div className="form-panel" ref={panelRef} onScroll={handleScroll}>
      <div className="form-card">
        <div className="form-card-header">Interaction Details</div>

        {/* ── Row 1: HCP Name + Interaction Type ── */}
        <div className="form-row two-col">
          <div className="field-group">
            <label className="field-label">HCP Name</label>
            <input
              className="field-input"
              readOnly
              value={f.hcp_name || ''}
              placeholder="Search or select HCP..."
            />
          </div>
          <div className="field-group">
            <label className="field-label">Interaction Type</label>
            <div className="select-wrapper">
              <select className="field-select" value={f.interaction_type || 'Meeting'} disabled>
                {INTERACTION_TYPES.map(t => <option key={t}>{t}</option>)}
              </select>
              <span className="select-chevron">▾</span>
            </div>
          </div>
        </div>

        {/* ── Row 2: Date + Time ── */}
        <div className="form-row two-col">
          <div className="field-group">
            <label className="field-label">Date</label>
            <input
              className="field-input"
              type="text"
              readOnly
              value={f.date || ''}
              placeholder="DD-MM-YYYY"
            />
          </div>
          <div className="field-group">
            <label className="field-label">Time</label>
            <input
              className="field-input"
              type="text"
              readOnly
              value={f.time || ''}
              placeholder="HH:MM"
            />
          </div>
        </div>

        {/* ── Attendees ── */}
        <div className="form-row">
          <div className="field-group">
            <label className="field-label">Attendees</label>
            <input
              className="field-input"
              readOnly
              value={join(f.attendees)}
              placeholder="Enter names or search..."
            />
          </div>
        </div>

        {/* ── Topics Discussed ── */}
        <div className="form-row">
          <div className="field-group">
            <label className="field-label">Topics Discussed</label>
            <div className="textarea-wrapper">
              <textarea
                className="field-textarea"
                readOnly
                value={joinNL(f.topics_discussed)}
                placeholder="Enter key discussion points..."
                rows={4}
              />
              <span className="mic-icon">🎤</span>
            </div>
            <button className="voice-note-btn" type="button" disabled>
              <span className="voice-icon">✦</span>
              Summarize from Voice Note (Requires Consent)
            </button>
          </div>
        </div>

        {/* ── Materials Shared / Samples Distributed ── */}
        <div className="form-row">
          <label className="field-label">Materials Shared / Samples Distributed</label>
          <div className="materials-card">
            <div className="materials-row">
              <div className="materials-left">
                <span className="materials-title">Materials Shared</span>
                <div className="materials-list">
                  {f.materials_shared && f.materials_shared.length > 0
                    ? f.materials_shared.map((m, i) => <span key={i} className="material-item">{m}</span>)
                    : <span className="materials-empty">No materials added.</span>
                  }
                </div>
              </div>
              <button className="materials-btn" type="button" disabled>
                <span>🔍</span> Search/Add
              </button>
            </div>
            <div className="materials-divider" />
            <div className="materials-row">
              <div className="materials-left">
                <span className="materials-title">Samples Distributed</span>
                <div className="materials-list">
                  {f.samples_distributed && f.samples_distributed.length > 0
                    ? f.samples_distributed.map((s, i) => <span key={i} className="material-item">{s}</span>)
                    : <span className="materials-empty">No samples added.</span>
                  }
                </div>
              </div>
              <button className="materials-btn" type="button" disabled>
                <span>⊕</span> Add Sample
              </button>
            </div>
          </div>
        </div>

        {/* ── Sentiment ── */}
        <div className="form-row">
          <label className="field-label">Observed/Inferred HCP Sentiment</label>
          <div className="sentiment-row">
            {[
              { value: 'Positive', emoji: '😊' },
              { value: 'Neutral',  emoji: '😐' },
              { value: 'Negative', emoji: '😟' },
            ].map(({ value, emoji }) => (
              <label key={value} className={`sentiment-option ${f.sentiment === value ? 'selected' : ''}`}>
                <input
                  type="radio"
                  name="sentiment"
                  value={value}
                  checked={f.sentiment === value}
                  readOnly
                  onChange={() => {}}
                />
                <span className="sentiment-emoji">{emoji}</span>
                <span className="sentiment-label">{value}</span>
              </label>
            ))}
          </div>
        </div>

        {/* ── Outcomes ── */}
        <div className="form-row">
          <div className="field-group">
            <label className="field-label">Outcomes</label>
            <textarea
              className="field-textarea"
              readOnly
              value={f.outcomes || ''}
              placeholder="Key outcomes or agreements..."
              rows={3}
            />
          </div>
        </div>

        {/* ── Follow-up Actions ── */}
        <div className="form-row">
          <div className="field-group">
            <label className="field-label">Follow-up Actions</label>
            <textarea
              className="field-textarea"
              readOnly
              value={joinNL(f.follow_up_actions)}
              placeholder="Enter next steps or tasks..."
              rows={3}
            />
          </div>
        </div>

        {/* ── AI Suggested Follow-ups ── */}
        {f.ai_suggested_follow_ups && f.ai_suggested_follow_ups.length > 0 && (
          <div className="form-row">
            <div className="ai-followups">
              <span className="ai-followups-label">AI Suggested Follow-ups:</span>
              <ul className="ai-followups-list">
                {f.ai_suggested_follow_ups.map((item, i) => (
                  <li key={i} className="ai-followup-item">
                    <span className="ai-followup-plus">+</span> {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
