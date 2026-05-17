import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";

import Login from "./components/login/login";
import Homepage from "./components/homepage/Homepage";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />

        <Route
          path="/newproject"
          element={<Homepage defaultView="newProject" />}
        />

        <Route
          path="/profile"
          element={<Homepage defaultView="profile" />}
        />
      </Routes>
    </Router>
  );
}

export default App;