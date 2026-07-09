/**
 * chatSlice.js
 *
 * Manages the right-panel chat state: message history, loading flag, and errors.
 *
 * sendMessage is the main async thunk.  It:
 *   1. Adds the user message to the local state immediately (optimistic)
 *   2. POSTs to /api/chat with the full conversation history for context
 *   3. On success, appends the AI response and returns payload so App.jsx
 *      can also dispatch updateInteraction with the form_data
 */

import { createSlice, createAsyncThunk } from '@reduxjs/toolkit'

// ── Async thunk ──────────────────────────────────────────────────────────────

export const sendMessage = createAsyncThunk(
  'chat/sendMessage',
  async ({ message, interactionId, history }, { rejectWithValue }) => {
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          interaction_id: interactionId,
          history: history.map(m => ({ role: m.role, content: m.content })),
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
        return rejectWithValue(err.detail || 'API error')
      }
      return await res.json()  // { message, interaction_id, form_data }
    } catch (err) {
      return rejectWithValue(err.message || 'Network error')
    }
  }
)

// ── Slice ─────────────────────────────────────────────────────────────────────

const initialState = {
  messages: [],   // [{ id, role: 'user'|'assistant', content }]
  isLoading: false,
  error: null,
}

const chatSlice = createSlice({
  name: 'chat',
  initialState,

  reducers: {
    /** Immediately add user bubble before API returns. */
    addUserMessage(state, action) {
      state.messages.push({
        id: Date.now(),
        role: 'user',
        content: action.payload,
      })
    },

    /** Clear everything for a new interaction session. */
    resetChat() {
      return initialState
    },
  },

  extraReducers: builder => {
    builder
      .addCase(sendMessage.pending, state => {
        state.isLoading = true
        state.error = null
      })
      .addCase(sendMessage.fulfilled, (state, action) => {
        state.isLoading = false
        state.messages.push({
          id: Date.now(),
          role: 'assistant',
          content: action.payload.message,
        })
      })
      .addCase(sendMessage.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.payload || 'Something went wrong'
        state.messages.push({
          id: Date.now(),
          role: 'assistant',
          content: `⚠️ Error: ${action.payload || 'Something went wrong. Please try again.'}`,
        })
      })
  },
})

export const { addUserMessage, resetChat } = chatSlice.actions
export default chatSlice.reducer
