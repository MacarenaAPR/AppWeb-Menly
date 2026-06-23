import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import 'bootstrap-icons/font/bootstrap-icons.css'
import './index.css'
import './themes/themes.css'
import './styles/theme-layout.css'
import './themes/theme-1.css'
import './themes/theme_8.css'
import './themes/theme_9.css'
import App from './App.jsx'

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
