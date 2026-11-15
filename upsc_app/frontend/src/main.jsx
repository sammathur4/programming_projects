import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import CurrentAffairsReader from './reader/CurrentAffairsReader.jsx'

const isAtlas = /^\/atlas\/?$/.test(window.location.pathname)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {isAtlas ? <CurrentAffairsReader /> : <App />}
  </StrictMode>,
)
