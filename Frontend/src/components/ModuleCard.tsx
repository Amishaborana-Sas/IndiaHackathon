import { motion } from 'motion/react';
import { Link } from 'react-router-dom';
import { ArrowRight, CheckCircle2 } from 'lucide-react';

interface ModuleCardProps {
  id: string;
  moduleNo: number;
  title: string;
  description: string;
  icon: any;
  color: string;
  isActive?: boolean;
  formats?: { input: string[]; output: string[] };
}

export default function ModuleCard({ id, moduleNo, title, description, icon: Icon, color, isActive, formats }: ModuleCardProps) {
  return (
    <Link
      to={`/module/${id}`}
      className="block h-full group"
    >
      <motion.div
        whileHover={{ y: -4 }}
        whileTap={{ scale: 0.98 }}
        className={`h-full p-6 bg-white rounded-2xl border-2 transition-all ${
          isActive
            ? 'border-blue-400 shadow-lg shadow-blue-100 ring-2 ring-blue-200 bg-blue-50/30'
            : 'border-slate-200/80 hover:border-blue-200 hover:shadow-lg hover:shadow-blue-50'
        }`}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-11 h-11 rounded-xl ${color} flex items-center justify-center group-hover:scale-110 transition-transform shadow-sm`}>
              <Icon className="w-5 h-5 text-white" />
            </div>
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider bg-slate-100 px-2 py-1 rounded-md">Module {moduleNo}</span>
          </div>
          {isActive && (
            <div className="flex items-center gap-1 px-2 py-1 bg-blue-100 rounded-full">
              <CheckCircle2 className="w-3 h-3 text-blue-600" />
              <span className="text-[10px] font-bold text-blue-700">ACTIVE</span>
            </div>
          )}
        </div>
        <h3 className={`text-base font-bold mb-2 mt-4 transition-colors ${
          isActive ? 'text-blue-700' : 'text-slate-900 group-hover:text-blue-700'
        }`}>
          {title}
        </h3>
        <p className="text-sm text-slate-500 leading-relaxed mb-3">
          {description}
        </p>
        {formats && (
          <div className="mb-4 space-y-1.5">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[9px] font-bold text-slate-400 uppercase w-10 shrink-0">In:</span>
              {formats.input.map((f) => (
                <span key={f} className="text-[9px] font-semibold text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">{f}</span>
              ))}
            </div>
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="text-[9px] font-bold text-slate-400 uppercase w-10 shrink-0">Out:</span>
              {formats.output.map((f) => (
                <span key={f} className="text-[9px] font-semibold text-green-600 bg-green-50 px-1.5 py-0.5 rounded">{f}</span>
              ))}
            </div>
          </div>
        )}
        <div className={`flex items-center text-sm font-semibold transition-opacity ${
          isActive ? 'text-blue-600 opacity-100' : 'text-blue-600 opacity-0 group-hover:opacity-100'
        }`}>
          {isActive ? 'Continue' : 'Launch Module'}
          <ArrowRight className="w-4 h-4 ml-1.5 group-hover:translate-x-1 transition-transform" />
        </div>
      </motion.div>
    </Link>
  );
}
