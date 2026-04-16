import { useState, useEffect } from 'react';
import { Shield, FileText, FileSearch, Tag, ClipboardCheck } from 'lucide-react';
import ModuleCard from '../components/ModuleCard';
import { motion } from 'motion/react';

const modules = [
  {
    id: 'anonymisation',
    moduleNo: 1,
    title: 'AI Anonymisation Tool',
    description: 'Detect and redact sensitive PII (Aadhaar, PAN, Names, Addresses, Phone) from regulatory documents using hybrid NLP + regex.',
    icon: Shield,
    color: 'bg-blue-600',
    formats: { input: ['TXT', 'CSV', 'XLSX', 'DOCX', 'PDF', 'JPG', 'JSON', 'MP3', 'WAV'], output: ['TXT', 'CSV', 'XLSX', 'DOCX', 'PDF', 'JSON'] },
  },
  {
    id: 'summarisation',
    moduleNo: 2,
    title: 'Document Summarisation',
    description: 'Condense lengthy regulatory filings into concise, actionable summaries using advanced NLP.',
    icon: FileText,
    color: 'bg-indigo-600',
    formats: { input: ['TXT', 'CSV', 'XLSX', 'DOCX', 'PDF', 'JPG', 'JSON', 'MP3', 'WAV'], output: ['TXT', 'CSV', 'XLSX', 'DOCX', 'PDF', 'JSON'] },
  },
  {
    id: 'comparison',
    moduleNo: 3,
    title: 'Completeness & Comparison',
    description: 'Compare multiple document versions and check for mandatory regulatory compliance fields.',
    icon: FileSearch,
    color: 'bg-cyan-600',
    formats: { input: ['TXT', 'CSV', 'XLSX', 'DOCX', 'PDF', 'JPG', 'JSON', 'MP3', 'WAV'], output: ['TXT', 'CSV', 'XLSX', 'DOCX', 'PDF', 'JSON'] },
  },
  {
    id: 'classification',
    moduleNo: 4,
    title: 'Classification Tool',
    description: 'Automatically categorize medical device and drug applications into correct regulatory classes.',
    icon: Tag,
    color: 'bg-sky-600',
    formats: { input: ['TXT', 'CSV', 'XLSX', 'DOCX', 'PDF', 'JPG', 'JSON', 'MP3', 'WAV'], output: ['TXT', 'CSV', 'XLSX', 'DOCX', 'PDF', 'JSON'] },
  },
  {
    id: 'inspection',
    moduleNo: 5,
    title: 'Inspection Report Generator',
    description: 'Generate structured inspection reports from raw field notes and observation data.',
    icon: ClipboardCheck,
    color: 'bg-blue-500',
    formats: { input: ['TXT', 'CSV', 'XLSX', 'DOCX', 'PDF', 'JPG', 'JSON', 'MP3', 'WAV'], output: ['TXT', 'CSV', 'XLSX', 'DOCX', 'PDF', 'JSON'] },
  },
];

export default function Dashboard() {
  const [activeModules, setActiveModules] = useState<Set<string>>(() => {
    try {
      const saved = sessionStorage.getItem('RegLens_active_modules');
      return saved ? new Set(JSON.parse(saved)) : new Set<string>();
    } catch {
      return new Set<string>();
    }
  });

  // Track navigation - mark modules as active when user navigates back from them
  useEffect(() => {
    const handleClick = (moduleId: string) => {
      setActiveModules(prev => {
        const next = new Set(prev);
        next.add(moduleId);
        sessionStorage.setItem('RegLens_active_modules', JSON.stringify([...next]));
        return next;
      });
    };

    // Expose the handler globally so ModuleCard clicks can trigger it
    (window as any).__RegLens_markActive = handleClick;
    return () => { delete (window as any).__RegLens_markActive; };
  }, []);

  return (
    <div className="max-w-7xl mx-auto px-6 py-12">
      {/* Hero Section */}
      <header className="mb-16 text-center lg:text-left">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <div className="flex items-center justify-center lg:justify-start gap-2 mb-6">
            <div className="h-1 w-12 bg-blue-600 rounded-full" />
            <span className="text-sm font-bold text-blue-600 uppercase tracking-widest">CDSCO-India AI Hackathon</span>
          </div>
          <h1 className="text-4xl md:text-6xl font-black text-slate-900 mb-6 tracking-tight flex items-center justify-center lg:justify-start gap-3">
            <span className="text-blue-600 font-bold">RegLens</span>
            <span className="text-slate-900 font-bold">AI</span>
          </h1>
          <p className="text-lg text-slate-500 max-w-2xl mx-auto lg:mx-0 leading-relaxed">
            AI-Powered CDSCO Regulatory Intelligence Platform. Streamline your compliance workflow with intelligent document processing, anonymization, and analysis.
          </p>
        </motion.div>
      </header>

      {/* Module Cards */}
      <div className="mb-8">
        <h2 className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-6">Available Modules</h2>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {modules.map((module, index) => (
          <motion.div
            key={module.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: index * 0.1 }}
            onClick={() => {
              setActiveModules(prev => {
                const next = new Set(prev);
                next.add(module.id);
                sessionStorage.setItem('RegLens_active_modules', JSON.stringify([...next]));
                return next;
              });
            }}
          >
            <ModuleCard
              id={module.id}
              moduleNo={module.moduleNo}
              title={module.title}
              description={module.description}
              icon={module.icon}
              color={module.color}
              isActive={activeModules.has(module.id)}
              formats={module.formats}
            />
          </motion.div>
        ))}
      </div>

      {/* DPDP Act Compliance Notice */}
      <div className="mt-12 p-5 bg-blue-50 border border-blue-200 rounded-2xl">
        <div className="flex items-start gap-3">
          <Shield className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
          <div>
            <h3 className="text-sm font-bold text-blue-900 mb-1">DPDP Act 2023 Compliant</h3>
            <p className="text-xs text-blue-700 leading-relaxed">
              <strong>RegLens AI</strong> is designed in alignment with the Digital Personal Data Protection (DPDP) Act, 2023.
              All anonymisation and de-identification processes follow Section 2(b) guidelines for data protection.
              The platform ensures NDHM Health Data Management Policy and ICMR Ethical Guidelines (2017) compliance
              for handling sensitive health and regulatory data.
            </p>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-12 pt-8 border-t border-slate-100 text-center">
        <p className="text-sm text-slate-400">
          &copy; 2026 <strong>RegLens AI</strong> &bull; CDSCO Regulatory Intelligence Platform
        </p>
      </footer>
    </div>
  );
}
