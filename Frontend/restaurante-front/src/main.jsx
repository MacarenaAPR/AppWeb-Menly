
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { registrarServiceWorkerMenly } from './pushNotifications'

registrarServiceWorkerMenly().catch(() => {
  // La aplicacion sigue funcionando aunque el navegador no pueda registrar la PWA.
})


createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
