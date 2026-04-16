import { Shield } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 h-16 bg-white/80 backdrop-blur-md border-b border-slate-200/60 z-50 flex items-center px-6">
      <Link to="/" className="flex items-center gap-3 group">
        
          <img src="/images/cdesco.png" alt="CDSCO Logo" className="w-10 h-10" />
        
        <div className="flex items-baseline gap-1.5">
          <span className="text-lg font-bold text-blue-500 tracking-tight">RegLens AI</span>
        </div>
      </Link>
    </nav>
  );
}
