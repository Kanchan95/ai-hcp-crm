/**
 * interactionSlice.js
 *
 * Manages the left-panel form state.  The form is NEVER edited by the user
 * directly — only the AI (via the chat panel) can write to it.
 * updateInteraction is called after every successful /api/chat response
 * that includes form_data.
 */

import { createSlice } from '@reduxjs/toolkit'

const emptyState = {
  id: null,
  hcp_name: '',
  interaction_type: '',
  date: '',
  time: '',
  attendees: [],
  topics_discussed: [],
  materials_shared: [],
  samples_distributed: [],
  sentiment: '',
  outcomes: '',
  follow_up_actions: [],
  ai_suggested_follow_ups: [],
  compliance_notes: '',
  recommended_materials: [],
}

const interactionSlice = createSlice({
  name: 'interaction',
  initialState: emptyState,

  reducers: {
    /** Merge API form_data into state (partial update OK). */
    updateInteraction(state, action) {
      return { ...state, ...action.payload }
    },

    /** Reset to blank — triggered by "New Interaction" button. */
    resetInteraction() {
      return emptyState
    },
  },
})

export const { updateInteraction, resetInteraction } = interactionSlice.actions
export default interactionSlice.reducer
