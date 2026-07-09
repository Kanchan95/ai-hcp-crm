import { useDispatch, useSelector } from 'react-redux'
import FormPanel from './components/FormPanel/FormPanel'
import ChatPanel from './components/ChatPanel/ChatPanel'
import { addUserMessage, sendMessage, resetChat } from './store/slices/chatSlice'
import { updateInteraction, resetInteraction } from './store/slices/interactionSlice'
import './App.css'

export default function App() {
  const dispatch = useDispatch()
  const interaction = useSelector(state => state.interaction)
  const chat = useSelector(state => state.chat)

  const handleSendMessage = async (text) => {
    dispatch(addUserMessage(text))
    const history = chat.messages.slice(-8)
    const result = await dispatch(sendMessage({
      message: text,
      interactionId: interaction.id,
      history,
    }))
    if (result.payload?.form_data) {
      dispatch(updateInteraction(result.payload.form_data))
    }
  }

  const handleReset = () => {
    dispatch(resetInteraction())
    dispatch(resetChat())
  }

  return (
    <div className="app-container">
      <div className="page-title-row">
        <h1 className="page-title">Log HCP Interaction</h1>
        {interaction.id && (
          <button className="new-interaction-btn" onClick={handleReset}>
            + New Interaction
          </button>
        )}
      </div>
      <div className="panels-row">
        <FormPanel />
        <ChatPanel onSendMessage={handleSendMessage} />
      </div>
    </div>
  )
}
