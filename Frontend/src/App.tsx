import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import ModulePage from './pages/ModulePage';
import SAEPage from './pages/SAEPage';

export default function App() {
  return (
    <Router>
      <div className="min-h-screen bg-slate-50 font-sans text-slate-900 selection:bg-blue-100 selection:text-blue-900">
        <Navbar />
        <main className="pt-16 min-h-[calc(100vh-64px)]">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/module/anonymisation" element={<SAEPage />} />
            <Route path="/module/:id" element={<ModulePage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
