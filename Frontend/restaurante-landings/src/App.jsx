import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/menu/:slug" element={<Home />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;