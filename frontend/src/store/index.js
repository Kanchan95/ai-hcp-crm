/**
 * store/index.js — Redux store configuration.
 *
 * Two slices:
 *   interaction — the form panel state (populated exclusively by the AI)
 *   chat        — the chat panel state (messages, loading flag)
 */

import { configureStore } from '@reduxjs/toolkit'
import interactionReducer from './slices/interactionSlice'
import chatReducer from './slices/chatSlice'

const store = configureStore({
  reducer: {
    interaction: interactionReducer,
    chat: chatReducer,
  },
})

export default store
