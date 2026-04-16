import { useState, useEffect } from 'react';
import { ModuleResult } from '../types';
import { FileText, Cpu, Clock, Database, Download, RefreshCcw, ArrowLeft, ChevronDown, Scan, PenTool, AlertTriangle, CheckCircle2, Tag, BarChart3, Eye, FileDown } from 'lucide-react';
import { fetchM5Reports, getM5ReportDownloadUrl, getM5ReportPreviewUrl } from '../services/api';
import { motion } from 'motion/react';

interface ResultPanelProps {
  result: ModuleResult;
  moduleId: string;
  onReset: () => void;
  onBack: () => void;
  onDownload: (format: 'txt' | 'json' | 'csv' | 'pdf' | 'docx') => void;
  onMoveTo?: (moduleId: string) => void;
}

// Color-code anonymized tokens for readability
function HighlightedText({ text }: { text: string }) {
  const parts = text.split(/(\[[\w_]+\]|<[\w_]+>|\*{3,}|\bINDIA\b|\b\d{4}-XX-XX\b)/g);
  return (
    <div className="whitespace-pre-wrap leading-relaxed">
      {parts.map((part, i) => {
        if (/^\[[\w_]+\]$/.test(part)) {
          return (
            <span key={i} className="inline-block bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-semibold text-xs mx-0.5 border border-amber-200">
              {part}
            </span>
          );
        }
        if (/^<[\w_]+>$/.test(part)) {
          return (
            <span key={i} className="inline-block bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded font-mono text-xs mx-0.5 border border-purple-200">
              {part}
            </span>
          );
        }
        if (/^\*{3,}$/.test(part)) {
          return (
            <span key={i} className="inline-block bg-red-100 text-red-600 px-1.5 py-0.5 rounded font-mono text-xs mx-0.5 border border-red-200">
              {part}
            </span>
          );
        }
        if (part === 'INDIA' || /^\d{4}-XX-XX$/.test(part)) {
          return (
            <span key={i} className="inline-block bg-green-100 text-green-700 px-1 py-0.5 rounded text-xs font-semibold mx-0.5 border border-green-200">
              {part}
            </span>
          );
        }
        return part;
      })}
    </div>
  );
}

const ENTITY_COLORS: Record<string, string> = {
  PERSON: 'bg-purple-100 text-purple-700',
  LOCATION: 'bg-green-100 text-green-700',
  ADDRESS: 'bg-green-100 text-green-700',
  IN_PHONE: 'bg-orange-100 text-orange-700',
  EMAIL_ADDRESS: 'bg-blue-100 text-blue-700',
  AADHAAR: 'bg-red-100 text-red-700',
  PAN: 'bg-red-100 text-red-700',
  DATE_TIME: 'bg-cyan-100 text-cyan-700',
  ORGANIZATION: 'bg-indigo-100 text-indigo-700',
  IN_PIN_CODE: 'bg-yellow-100 text-yellow-700',
  NRP: 'bg-teal-100 text-teal-700',
  DRUG_ID: 'bg-pink-100 text-pink-700',
};

const MODULES_FOR_MOVETO = [
  { id: 'anonymisation', label: 'Anonymisation' },
  { id: 'summarisation', label: 'Summarisation' },
  { id: 'comparison', label: 'Comparison' },
  { id: 'classification', label: 'Classification' },
  { id: 'inspection', label: 'Inspection Report' },
];

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-700 border-red-200',
  major: 'bg-orange-100 text-orange-700 border-orange-200',
  minor: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  observation: 'bg-blue-100 text-blue-700 border-blue-200',
};

export default function ResultPanel({ result, moduleId, onReset, onBack, onDownload, onMoveTo }: ResultPanelProps) {
  const [showFormatMenu, setShowFormatMenu] = useState(false);
  const [showMoveMenu, setShowMoveMenu] = useState(false);

  const availableModules = MODULES_FOR_MOVETO.filter(m => m.id !== moduleId);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      {/* Module-specific result content */}
      {result.type === 'anonymisation' && <AnonymisationPanel data={result.data} />}
      {result.type === 'summarisation' && <SummarisationPanel data={result.data} />}
      {result.type === 'comparison' && <ComparisonPanel data={result.data} />}
      {result.type === 'classification' && <ClassificationPanel data={result.data} />}
      {result.type === 'inspection' && <InspectionPanel data={result.data} />}

      {/* Actions */}
      <div className="flex flex-wrap items-center justify-center gap-3 pt-4 border-t border-slate-100">
        <button
          onClick={onReset}
          className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 rounded-xl text-slate-700 font-semibold hover:bg-slate-100 hover:border-slate-300 active:bg-slate-200 active:scale-95 transition-all shadow-sm text-sm"
        >
          <RefreshCcw className="w-4 h-4" />
          Process Another
        </button>

        <div className="relative">
          <button
            onClick={() => setShowFormatMenu(!showFormatMenu)}
            className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 hover:shadow-lg hover:shadow-blue-300 active:bg-blue-800 active:scale-95 transition-all shadow-md shadow-blue-200 text-sm"
          >
            <Download className="w-4 h-4" />
            Download
            <ChevronDown className={`w-3 h-3 transition-transform ${showFormatMenu ? 'rotate-180' : ''}`} />
          </button>
          {showFormatMenu && (
            <div className="absolute top-full mt-2 right-0 bg-white border border-slate-200 rounded-xl shadow-lg py-1 z-10 min-w-[180px]">
              <button
                onClick={() => { onDownload('pdf'); setShowFormatMenu(false); }}
                className="w-full text-left px-4 py-2 hover:bg-blue-50 hover:text-blue-700 active:bg-blue-200 text-sm font-medium text-slate-700 transition-colors"
              >
                PDF Document (.pdf)
              </button>
              <button
                onClick={() => { onDownload('docx'); setShowFormatMenu(false); }}
                className="w-full text-left px-4 py-2 hover:bg-blue-50 hover:text-blue-700 active:bg-blue-200 text-sm font-medium text-slate-700 transition-colors"
              >
                Word Document (.docx)
              </button>
              <button
                onClick={() => { onDownload('txt'); setShowFormatMenu(false); }}
                className="w-full text-left px-4 py-2 hover:bg-blue-50 hover:text-blue-700 active:bg-blue-200 text-sm font-medium text-slate-700 transition-colors"
              >
                Plain Text (.txt)
              </button>
              <button
                onClick={() => { onDownload('csv'); setShowFormatMenu(false); }}
                className="w-full text-left px-4 py-2 hover:bg-blue-50 hover:text-blue-700 active:bg-blue-200 text-sm font-medium text-slate-700 transition-colors"
              >
                CSV Spreadsheet (.csv)
              </button>
              <button
                onClick={() => { onDownload('json'); setShowFormatMenu(false); }}
                className="w-full text-left px-4 py-2 hover:bg-blue-50 hover:text-blue-700 active:bg-blue-200 text-sm font-medium text-slate-700 transition-colors"
              >
                JSON Report (.json)
              </button>
            </div>
          )}
        </div>

        {/* Move To dropdown */}
        {onMoveTo && (
          <div className="relative">
            <button
              onClick={() => setShowMoveMenu(!showMoveMenu)}
              className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 hover:shadow-lg hover:shadow-indigo-300 active:bg-indigo-800 active:scale-95 transition-all shadow-md shadow-indigo-200 text-sm"
            >
              Move Output To
              <ChevronDown className={`w-3 h-3 transition-transform ${showMoveMenu ? 'rotate-180' : ''}`} />
            </button>
            {showMoveMenu && (
              <div className="absolute top-full mt-2 right-0 bg-white border border-slate-200 rounded-xl shadow-lg py-1 z-10 min-w-[180px]">
                {availableModules.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => { onMoveTo(m.id); setShowMoveMenu(false); }}
                    className="w-full text-left px-4 py-2 hover:bg-slate-50 text-sm font-medium text-slate-700"
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <button
          onClick={onBack}
          className="flex items-center gap-2 px-5 py-2.5 text-slate-500 font-semibold hover:text-blue-600 transition-all text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Dashboard
        </button>
      </div>
    </motion.div>
  );
}


// =========================================================================== //
// Module 1: Anonymisation Panel
// =========================================================================== //
function AnonymisationPanel({ data }: { data: any }) {
  const [activeTab, setActiveTab] = useState<'processed' | 'original'>('processed');

  const modeLabel = data.mode === 'generalise' || data.mode === 'de-identification'
    ? 'De-identification (Identifiers)'
    : data.mode === 'mask' || data.mode === 'irreversible-anonymisation'
      ? 'Irreversible Anonymisation (Masking)'
      : data.mode === 'pseudonymise'
        ? 'Reversible Anonymisation'
        : data.mode || 'N/A';

  return (
    <>
      {/* Status Badges */}
      <div className="flex flex-wrap gap-2">
        <div className="px-3 py-1.5 bg-green-50 border border-green-200 rounded-full flex items-center gap-2">
          <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
          <span className="text-xs font-semibold text-green-700">Analysis Completed</span>
        </div>
        <div className="px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-full">
          <span className="text-xs font-semibold text-blue-700">{modeLabel}</span>
        </div>
        <div className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-full flex items-center gap-1.5">
          <Clock className="w-3 h-3 text-slate-500" />
          <span className="text-xs font-semibold text-slate-600">Time: {data.time}</span>
        </div>
        {data.isScanned && (
          <div className="px-3 py-1.5 bg-amber-50 border border-amber-200 rounded-full flex items-center gap-1.5">
            <Scan className="w-3 h-3 text-amber-600" />
            <span className="text-xs font-semibold text-amber-700">Scanned (OCR)</span>
          </div>
        )}
        {(data.handwrittenRegions ?? 0) > 0 && (
          <div className="px-3 py-1.5 bg-orange-50 border border-orange-200 rounded-full flex items-center gap-1.5">
            <PenTool className="w-3 h-3 text-orange-600" />
            <span className="text-xs font-semibold text-orange-700">
              {data.handwrittenRegions} handwritten region(s) redacted
            </span>
          </div>
        )}
        {(data.totalPages ?? 0) > 0 && (
          <div className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-full flex items-center gap-1.5">
            <FileText className="w-3 h-3 text-slate-500" />
            <span className="text-xs font-semibold text-slate-600">
              {data.pagesScanned}/{data.totalPages} pages scanned
              {(data.pagesSkipped ?? 0) > 0 && ` (${data.pagesSkipped} skipped)`}
            </span>
          </div>
        )}
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1 w-fit">
            <button
              onClick={() => setActiveTab('processed')}
              className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${
                activeTab === 'processed' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <Cpu className="w-4 h-4 inline mr-1.5 -mt-0.5" />
              Anonymized Output
            </button>
            <button
              onClick={() => setActiveTab('original')}
              className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${
                activeTab === 'original' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <FileText className="w-4 h-4 inline mr-1.5 -mt-0.5" />
              Original Extracted
            </button>
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-5 h-[500px] overflow-y-auto shadow-sm">
            {activeTab === 'processed' ? (
              <HighlightedText text={data.processedText || ''} />
            ) : (
              <div className="whitespace-pre-wrap text-sm text-slate-600 font-mono leading-relaxed">
                {data.extractedText || <span className="text-slate-400 italic">No text extracted</span>}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <Database className="w-4 h-4 text-blue-600" />
            Analysis Summary
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-4 h-[500px] overflow-y-auto">
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">Entities Found</span>
                <span className="text-sm font-bold text-blue-700 bg-blue-50 px-3 py-1 rounded-full">{data.entities}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">Processing Time</span>
                <div className="flex items-center gap-1.5 text-sm font-bold text-slate-700">
                  <Clock className="w-3.5 h-3.5 text-slate-400" />
                  {data.time}
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">File Type</span>
                <span className="text-sm font-bold text-slate-700 uppercase">{data.fileType}</span>
              </div>
            </div>

            {data.entitiesByType && Object.keys(data.entitiesByType).length > 0 && (
              <div className="space-y-2 pt-3 border-t border-slate-100">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Breakdown of Masked Entity</span>
                <div className="space-y-1.5">
                  {Object.entries(data.entitiesByType)
                    .sort(([, a]: any, [, b]: any) => b - a)
                    .map(([type, count]: any) => {
                      const colorClass = ENTITY_COLORS[type] || 'bg-slate-100 text-slate-600';
                      const maxCount = Math.max(...Object.values(data.entitiesByType) as number[]);
                      const barWidth = Math.max(8, (count / maxCount) * 100);
                      return (
                        <div key={type} className="flex items-center gap-2">
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${colorClass} shrink-0 min-w-[70px] text-center`}>{type}</span>
                          <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                            <div className="h-full bg-blue-400 rounded-full" style={{ width: `${barWidth}%` }} />
                          </div>
                          <span className="text-xs font-bold text-slate-600 w-5 text-right">{count}</span>
                        </div>
                      );
                    })}
                </div>
              </div>
            )}

            <div className="pt-3 border-t border-slate-100 space-y-1.5">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Color Coding Legend</span>
              <div className="grid grid-cols-1 gap-1 text-[10px]">
                <div className="flex items-center gap-1.5">
                  <span className="bg-red-100 text-red-600 px-1 rounded border border-red-200 font-mono">****</span>
                  <span className="text-slate-500">Masked (Irreversible Anonymisation)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="bg-purple-100 text-purple-700 px-1 rounded border border-purple-200 font-mono">&lt;TOKEN&gt;</span>
                  <span className="text-slate-500">Identifier (De-identification)</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}


// =========================================================================== //
// Module 2: Summarisation Panel
// =========================================================================== //
function SummarisationPanel({ data }: { data: any }) {
  const hasSections = data.sections && Object.keys(data.sections).length > 0;

  return (
    <>
      {/* Status badges */}
      <div className="flex flex-wrap gap-2">
        <div className="px-3 py-1.5 bg-green-50 border border-green-200 rounded-full flex items-center gap-2">
          <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
          <span className="text-xs font-semibold text-green-700">Analysis Completed</span>
        </div>
        <div className="px-3 py-1.5 bg-indigo-50 border border-indigo-200 rounded-full">
          <span className="text-xs font-semibold text-indigo-700">{data.wordCount} words / {data.sentenceCount} sentences</span>
        </div>
        <div className="px-3 py-1.5 bg-purple-50 border border-purple-200 rounded-full">
          <span className="text-xs font-semibold text-purple-700">Algorithm: {(data.algorithm || 'LSA').toUpperCase()}</span>
        </div>
        <div className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-full flex items-center gap-1.5">
          <Clock className="w-3 h-3 text-slate-500" />
          <span className="text-xs font-semibold text-slate-600">{data.processingTime}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left: Summary */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <FileText className="w-4 h-4 text-indigo-600" />
            Summary
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-5 h-[500px] overflow-y-auto shadow-sm space-y-4">
            <div className="whitespace-pre-wrap text-sm text-slate-700 leading-relaxed">
              {data.summary || <span className="text-slate-400 italic">No summary generated</span>}
            </div>

            {/* Section summaries */}
            {hasSections && (
              <div className="pt-4 border-t border-slate-100 space-y-3">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Section Summaries</span>
                {Object.entries(data.sections).map(([secName, secSummary]: any) => (
                  <div key={secName} className="p-3 bg-indigo-50 border border-indigo-100 rounded-xl">
                    <h5 className="text-xs font-bold text-indigo-700 uppercase mb-1">{secName}</h5>
                    <p className="text-xs text-slate-700 leading-relaxed">{secSummary}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: Key points + info */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <CheckCircle2 className="w-4 h-4 text-indigo-600" />
            Key Points ({data.keyPoints?.length || 0})
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm h-[500px] overflow-y-auto space-y-3">
            {data.keyPoints && data.keyPoints.length > 0 ? (
              data.keyPoints.map((point: string, i: number) => (
                <div key={i} className="flex gap-3 items-start">
                  <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">{i + 1}</span>
                  <p className="text-sm text-slate-700 leading-relaxed">{point}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-400 italic">No key points extracted</p>
            )}

            {/* Algorithm info */}
            <div className="pt-3 border-t border-slate-100 space-y-2">
              <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Processing Info</span>
              {[
                { label: 'Algorithm', value: (data.algorithm || 'lsa').toUpperCase() },
                { label: 'Document Type', value: data.docType || 'N/A' },
                { label: 'Sentences', value: data.sentenceCount },
                { label: 'Words', value: data.wordCount },
                { label: 'Time', value: data.processingTime },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">{item.label}</span>
                  <span className="text-xs font-semibold text-slate-800">{String(item.value)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}


// =========================================================================== //
// Module 3: Dispatcher (Completeness or Comparison)
// =========================================================================== //
function ComparisonPanel({ data }: { data: any }) {
  if (data.mode === 'completeness') {
    return <CompletenessResultPanel data={data.data} />;
  }
  return <ComparisonResultPanel data={data.data} />;
}

// --- Completeness Result ---
function CompletenessResultPanel({ data }: { data: any }) {
  const score = Math.round(data.completeness_score || 0);
  const scoreColor = score >= 80 ? 'text-green-700' : score >= 50 ? 'text-amber-700' : 'text-red-700';
  const barColor = score >= 80 ? 'bg-green-500' : score >= 50 ? 'bg-amber-500' : 'bg-red-500';

  const FLAG_SEVERITY_COLORS: Record<string, string> = {
    critical: 'bg-red-50 border-red-200 text-red-800',
    major: 'bg-orange-50 border-orange-200 text-orange-800',
    minor: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800',
  };

  const FLAG_STATUS_BADGE: Record<string, string> = {
    missing: 'bg-red-100 text-red-700',
    invalid: 'bg-orange-100 text-orange-700',
    inconsistent: 'bg-amber-100 text-amber-700',
    warning: 'bg-yellow-100 text-yellow-700',
    ok: 'bg-green-100 text-green-700',
  };

  return (
    <>
      <div className="flex flex-wrap gap-2">
        <div className="px-3 py-1.5 bg-green-50 border border-green-200 rounded-full flex items-center gap-2">
          <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
          <span className="text-xs font-semibold text-green-700">Analysis Completed</span>
        </div>
        <div className="px-3 py-1.5 bg-cyan-50 border border-cyan-200 rounded-full">
          <span className="text-xs font-semibold text-cyan-700">{data.document_type}</span>
        </div>
        <div className={`px-3 py-1.5 rounded-full border ${score >= 80 ? 'bg-green-50 border-green-200' : score >= 50 ? 'bg-amber-50 border-amber-200' : 'bg-red-50 border-red-200'}`}>
          <span className={`text-xs font-semibold ${scoreColor}`}>Score: {score}%</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left: Flags table */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <AlertTriangle className="w-4 h-4 text-cyan-600" />
            Field Flags ({data.flags?.length || 0})
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl shadow-sm h-[500px] overflow-y-auto">
            {data.flags && data.flags.length > 0 ? (
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="text-left px-4 py-2.5 text-xs font-bold text-slate-500 uppercase">Field</th>
                    <th className="text-left px-4 py-2.5 text-xs font-bold text-slate-500 uppercase">Message</th>
                  </tr>
                </thead>
                <tbody>
                  {data.flags.map((flag: any, i: number) => (
                    <tr key={i} className={`border-b border-slate-100 ${FLAG_SEVERITY_COLORS[flag.severity] || ''}`}>
                      <td className="px-4 py-2.5 font-semibold">{flag.field_label}</td>
                      <td className="px-4 py-2.5 text-xs text-slate-600">{flag.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="p-8 text-center text-sm text-green-600 italic">
                <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-green-500" />
                All fields are complete and valid
              </div>
            )}
          </div>
        </div>

        {/* Right: Score summary */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <BarChart3 className="w-4 h-4 text-cyan-600" />
            Assessment Summary
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm h-[500px] overflow-y-auto space-y-4">
            {/* Score gauge */}
            <div className="text-center pb-4 border-b border-slate-100">
              <span className={`text-4xl font-black ${scoreColor}`}>{score}%</span>
              <p className="text-xs text-slate-500 mt-1">Completeness Score</p>
              <div className="h-3 bg-slate-100 rounded-full overflow-hidden mt-3">
                <div className={`h-full rounded-full ${barColor}`} style={{ width: `${score}%` }} />
              </div>
            </div>

            {/* Stats */}
            <div className="space-y-2.5">
              {[
                { label: 'Total Fields', value: data.total_fields, color: 'text-slate-700' },
                { label: 'Complete', value: data.complete_fields, color: 'text-green-700' },
                { label: 'Missing', value: data.missing_fields, color: 'text-red-700' },
                { label: 'Invalid', value: data.invalid_fields, color: 'text-orange-700' },
                { label: 'Inconsistent', value: data.inconsistent_fields, color: 'text-amber-700' },
              ].map((stat) => (
                <div key={stat.label} className="flex items-center justify-between">
                  <span className="text-sm text-slate-500">{stat.label}</span>
                  <span className={`text-sm font-bold ${stat.color}`}>{stat.value}</span>
                </div>
              ))}
            </div>

            {data.summary && (
              <div className="pt-3 border-t border-slate-100">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Summary</span>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed">{data.summary}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

// --- Comparison Result with Summary Table ---
function ComparisonResultPanel({ data }: { data: any }) {
  const SIGNIFICANCE_COLORS: Record<string, string> = {
    critical: 'bg-red-50 border-red-200',
    substantive: 'bg-orange-50 border-orange-200',
    editorial: 'bg-blue-50 border-blue-200',
    no_change: 'bg-slate-50 border-slate-200',
  };

  const SIGNIFICANCE_BADGE: Record<string, string> = {
    critical: 'bg-red-200 text-red-800',
    substantive: 'bg-orange-200 text-orange-800',
    editorial: 'bg-blue-200 text-blue-800',
    no_change: 'bg-slate-200 text-slate-600',
  };

  const CHANGE_TYPE_BADGE: Record<string, string> = {
    modified: 'bg-yellow-100 text-yellow-800',
    added: 'bg-green-100 text-green-800',
    deleted: 'bg-red-100 text-red-800',
    reordered: 'bg-purple-100 text-purple-800',
    unchanged: 'bg-slate-100 text-slate-600',
  };

  return (
    <>
      {/* Comparison table — full width, no stats sidebar */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
          <BarChart3 className="w-4 h-4 text-cyan-600" />
          Document Comparison
        </div>
        <div className="bg-white border border-slate-200 rounded-2xl shadow-sm max-h-[600px] overflow-y-auto">
          {data.field_changes && data.field_changes.length > 0 ? (
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="text-left px-4 py-2.5 text-xs font-bold text-slate-500 uppercase">Field</th>
                  <th className="text-left px-4 py-2.5 text-xs font-bold text-slate-500 uppercase">{data.version_a || 'V1'}</th>
                  <th className="text-left px-4 py-2.5 text-xs font-bold text-slate-500 uppercase">{data.version_b || 'V2'}</th>
                </tr>
              </thead>
              <tbody>
                {data.field_changes.map((change: any, i: number) => (
                  <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-2.5 font-semibold text-slate-800">{change.field_name}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-700 font-mono max-w-[300px]" title={String(change.old_value)}>
                      {change.old_value != null ? String(change.old_value) : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-700 font-mono max-w-[300px]" title={String(change.new_value)}>
                      {change.new_value != null ? String(change.new_value) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="p-8 text-center text-sm text-green-600 italic">
              <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-green-500" />
              No field changes detected between versions
            </div>
          )}
        </div>
      </div>
    </>
  );
}


// =========================================================================== //
// Module 4: Classification Panel
// =========================================================================== //
function ClassificationPanel({ data }: { data: any }) {
  const confidencePercent = Math.round((data.confidence || 0) * 100);

  return (
    <>
      <div className="flex flex-wrap gap-2">
        <div className="px-3 py-1.5 bg-green-50 border border-green-200 rounded-full flex items-center gap-2">
          <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
          <span className="text-xs font-semibold text-green-700">Analysis Completed</span>
        </div>
        <div className="px-3 py-1.5 bg-sky-50 border border-sky-200 rounded-full flex items-center gap-1.5">
          <Tag className="w-3 h-3 text-sky-600" />
          <span className="text-xs font-semibold text-sky-700">{data.category}</span>
        </div>
        <div className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-full flex items-center gap-1.5">
          <Clock className="w-3 h-3 text-slate-500" />
          <span className="text-xs font-semibold text-slate-600">{data.processingTime}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <Tag className="w-4 h-4 text-sky-600" />
            Classification Result
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-8 h-[500px] overflow-y-auto shadow-sm flex flex-col items-center justify-center">
            <div className="text-center space-y-6">
              <div className="w-24 h-24 rounded-full bg-sky-100 flex items-center justify-center mx-auto">
                <Tag className="w-12 h-12 text-sky-600" />
              </div>
              <div>
                <h2 className="text-3xl font-black text-slate-900">{data.category || 'Unknown'}</h2>
                <p className="text-sm text-slate-500 mt-2">Primary Classification</p>
              </div>
              <div className="w-64 mx-auto">
                <div className="flex justify-between text-xs text-slate-500 mb-1">
                  <span>Confidence</span>
                  <span className="font-bold text-sky-700">{confidencePercent}%</span>
                </div>
                <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${confidencePercent >= 80 ? 'bg-green-500' : confidencePercent >= 50 ? 'bg-yellow-500' : 'bg-red-500'}`}
                    style={{ width: `${confidencePercent}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <BarChart3 className="w-4 h-4 text-sky-600" />
            Sub-Categories
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm h-[500px] overflow-y-auto space-y-3">
            {data.subCategories && data.subCategories.length > 0 ? (
              data.subCategories.map((sub: any, i: number) => (
                <div key={i} className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-bold text-slate-700">{sub.name}</span>
                    <span className="text-xs font-bold text-sky-700">{Math.round(sub.confidence * 100)}%</span>
                  </div>
                  <div className="h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div className="h-full bg-sky-400 rounded-full" style={{ width: `${sub.confidence * 100}%` }} />
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-400 italic">No sub-categories</p>
            )}
          </div>
        </div>
      </div>
    </>
  );
}


// =========================================================================== //
// Module 5: Inspection Report Panel (real backend)
// =========================================================================== //
function InspectionPanel({ data }: { data: any }) {
  const [activeTab, setActiveTab] = useState<'observations' | 'extracted'>('observations');
  const [m5Reports, setM5Reports] = useState<any[]>([]);
  const obs = data.observations || {};
  const parsed = data.parsed_data || {};
  const reports = data.reports || {};

  // Load generated reports list
  useEffect(() => {
    fetchM5Reports().then(setM5Reports);
  }, []);
  const criticalCount = obs.critical?.length || 0;
  const majorCount = obs.major?.length || 0;
  const minorCount = obs.minor?.length || 0;
  const totalObs = criticalCount + majorCount + minorCount;

  const ratingColor = parsed.overall_rating?.includes('Critical')
    ? 'bg-red-50 border-red-200 text-red-700'
    : parsed.overall_rating?.includes('Major')
      ? 'bg-orange-50 border-orange-200 text-orange-700'
      : parsed.overall_rating?.includes('Minor')
        ? 'bg-yellow-50 border-yellow-200 text-yellow-700'
        : 'bg-green-50 border-green-200 text-green-700';

  return (
    <>
      {/* Status badges */}
      <div className="flex flex-wrap gap-2">
        <div className="px-3 py-1.5 bg-green-50 border border-green-200 rounded-full flex items-center gap-2">
          <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
          <span className="text-xs font-semibold text-green-700">Analysis Completed</span>
        </div>
        <div className="px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-full">
          <span className="text-xs font-semibold text-blue-700">
            {data.doc_type === 'gcp_checklist' ? 'GCP Checklist' : 'Drug Manufacturing'}
          </span>
        </div>
        <div className={`px-3 py-1.5 rounded-full border ${ratingColor}`}>
          <span className="text-xs font-semibold">{parsed.overall_rating || 'N/A'}</span>
        </div>
        {criticalCount > 0 && (
          <div className="px-3 py-1.5 bg-red-50 border border-red-200 rounded-full">
            <span className="text-xs font-semibold text-red-700">{criticalCount} critical</span>
          </div>
        )}
        {majorCount > 0 && (
          <div className="px-3 py-1.5 bg-orange-50 border border-orange-200 rounded-full">
            <span className="text-xs font-semibold text-orange-700">{majorCount} major</span>
          </div>
        )}
        {minorCount > 0 && (
          <div className="px-3 py-1.5 bg-yellow-50 border border-yellow-200 rounded-full">
            <span className="text-xs font-semibold text-yellow-700">{minorCount} minor</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left: Observations + Extracted Text */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1 w-fit">
            <button
              onClick={() => setActiveTab('observations')}
              className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${
                activeTab === 'observations' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <AlertTriangle className="w-4 h-4 inline mr-1.5 -mt-0.5" />
              Observations ({totalObs})
            </button>
            <button
              onClick={() => setActiveTab('extracted')}
              className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-all ${
                activeTab === 'extracted' ? 'bg-white text-blue-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              <FileText className="w-4 h-4 inline mr-1.5 -mt-0.5" />
              Extracted Text
            </button>
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-5 h-[500px] overflow-y-auto shadow-sm">
            {activeTab === 'observations' ? (
              <div className="space-y-4">
                {/* Critical */}
                {criticalCount > 0 && (
                  <div>
                    <h4 className="text-xs font-bold text-red-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <div className="w-2 h-2 rounded-full bg-red-500" />
                      Critical Observations ({criticalCount})
                    </h4>
                    <div className="space-y-1.5">
                      {obs.critical.map((o: string, i: number) => (
                        <div key={i} className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-800 leading-relaxed">{o}</div>
                      ))}
                    </div>
                  </div>
                )}
                {/* Major */}
                {majorCount > 0 && (
                  <div>
                    <h4 className="text-xs font-bold text-orange-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <div className="w-2 h-2 rounded-full bg-orange-500" />
                      Major Observations ({majorCount})
                    </h4>
                    <div className="space-y-1.5">
                      {obs.major.map((o: string, i: number) => (
                        <div key={i} className="p-3 bg-orange-50 border border-orange-200 rounded-xl text-xs text-orange-800 leading-relaxed">{o}</div>
                      ))}
                    </div>
                  </div>
                )}
                {/* Minor */}
                {minorCount > 0 && (
                  <div>
                    <h4 className="text-xs font-bold text-yellow-700 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <div className="w-2 h-2 rounded-full bg-yellow-500" />
                      Minor Observations ({minorCount})
                    </h4>
                    <div className="space-y-1.5">
                      {obs.minor.map((o: string, i: number) => (
                        <div key={i} className="p-3 bg-yellow-50 border border-yellow-200 rounded-xl text-xs text-yellow-800 leading-relaxed">{o}</div>
                      ))}
                    </div>
                  </div>
                )}
                {totalObs === 0 && (
                  <div className="text-center py-8">
                    <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-green-500" />
                    <p className="text-sm text-green-600">No observations found — Satisfactory</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="whitespace-pre-wrap text-sm text-slate-600 font-mono leading-relaxed">
                {data.raw_text || <span className="text-slate-400 italic">No text extracted</span>}
              </div>
            )}
          </div>
        </div>

        {/* Right: Parsed data summary */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
            <Database className="w-4 h-4 text-blue-500" />
            Report Details
          </div>
          <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm h-[500px] overflow-y-auto space-y-3">
            {/* Key fields */}
            {[
              { label: 'Document Type', value: data.doc_type === 'gcp_checklist' ? 'GCP Checklist (QMS-INS-008)' : 'Drug Manufacturing (Form 31)' },
              { label: 'Firm / Site', value: parsed.firm_name },
              { label: 'License No.', value: parsed.license_number },
              { label: 'Inspection Date', value: parsed.inspection_date },
              { label: 'State', value: parsed.state },
              { label: 'Product Category', value: parsed.product_category },
              { label: 'GMP Status', value: parsed.gmp_status },
              { label: 'Schedule M', value: parsed.schedule_m_status },
              { label: 'Total Observations', value: parsed.total_observations },
              { label: 'Overall Rating', value: parsed.overall_rating },
              { label: 'Report Generated', value: parsed.report_generated_on },
            ].filter(f => f.value && f.value !== 'Not Specified').map((field, i) => (
              <div key={i} className="flex items-start justify-between gap-2">
                <span className="text-xs text-slate-500 shrink-0">{field.label}</span>
                <span className="text-xs font-semibold text-slate-800 text-right">{String(field.value)}</span>
              </div>
            ))}

            {/* Inspectors */}
            {parsed.inspectors && parsed.inspectors.length > 0 && (
              <div className="pt-2 border-t border-slate-100">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Inspectors</span>
                <div className="mt-1 space-y-1">
                  {parsed.inspectors.map((name: string, i: number) => (
                    <div key={i} className="text-xs text-slate-700">{name}</div>
                  ))}
                </div>
              </div>
            )}

            {/* CAPA */}
            {parsed.capa_requirements && (
              <div className="pt-2 border-t border-slate-100">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">CAPA Requirements</span>
                <p className="text-xs text-slate-700 mt-1 leading-relaxed">{parsed.capa_requirements}</p>
              </div>
            )}

            {/* Sections (for GCP checklist) */}
            {data.sections && data.sections.length > 0 && (
              <div className="pt-2 border-t border-slate-100">
                <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Sections Assessed</span>
                <div className="mt-1 flex flex-wrap gap-1">
                  {data.sections.map((sec: string, i: number) => (
                    <span key={i} className="text-[10px] font-medium bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{sec}</span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Report Download Buttons */}
      {(reports.pdf || reports.docx) && (() => {
        // reports.pdf / reports.docx can be either a string path or an object {success, path, name}
        const pdfName = reports.pdf
          ? (typeof reports.pdf === 'object' ? (reports.pdf.name || String(reports.pdf.path || '').split(/[/\\]/).pop()) : String(reports.pdf).split(/[/\\]/).pop()) || ''
          : '';
        const docxName = reports.docx
          ? (typeof reports.docx === 'object' ? (reports.docx.name || String(reports.docx.path || '').split(/[/\\]/).pop()) : String(reports.docx).split(/[/\\]/).pop()) || ''
          : '';
        return (
        <div className="flex flex-wrap gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl">
          <span className="text-sm font-bold text-blue-900 flex items-center gap-2 mr-2">
            <FileDown className="w-4 h-4" /> Generated Reports:
          </span>
          {pdfName && (
            <a href={getM5ReportDownloadUrl(pdfName)}
               target="_blank" rel="noopener"
               className="flex items-center gap-1.5 px-4 py-2 bg-red-600 text-white rounded-lg text-xs font-bold hover:bg-red-700 transition-all">
              <Download className="w-3.5 h-3.5" /> Download PDF
            </a>
          )}
          {pdfName && (
            <a href={getM5ReportPreviewUrl(pdfName)}
               target="_blank" rel="noopener"
               className="flex items-center gap-1.5 px-4 py-2 bg-white border border-slate-300 text-slate-700 rounded-lg text-xs font-bold hover:bg-slate-50 transition-all">
              <Eye className="w-3.5 h-3.5" /> Preview PDF
            </a>
          )}
          {docxName && (
            <a href={getM5ReportDownloadUrl(docxName)}
               target="_blank" rel="noopener"
               className="flex items-center gap-1.5 px-4 py-2 bg-blue-700 text-white rounded-lg text-xs font-bold hover:bg-blue-800 transition-all">
              <Download className="w-3.5 h-3.5" /> Download DOCX
            </a>
          )}
        </div>
        );
      })()}

      {/* Generated Reports List */}
      {m5Reports.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
            <Database className="w-4 h-4 text-blue-500" />
            Generated Reports ({m5Reports.length})
          </div>
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="text-left px-4 py-2 font-bold text-slate-500">Filename</th>
                  <th className="text-left px-4 py-2 font-bold text-slate-500">Type</th>
                  <th className="text-left px-4 py-2 font-bold text-slate-500">Size</th>
                  <th className="text-left px-4 py-2 font-bold text-slate-500">Date</th>
                  <th className="text-left px-4 py-2 font-bold text-slate-500">Actions</th>
                </tr>
              </thead>
              <tbody>
                {m5Reports.slice(0, 10).map((r: any, i: number) => (
                  <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                    <td className="px-4 py-2 font-medium text-slate-700 truncate max-w-[250px]">{r.name}</td>
                    <td className="px-4 py-2">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${r.type === 'PDF' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>{r.type}</span>
                    </td>
                    <td className="px-4 py-2 text-slate-500">{(r.size / 1024).toFixed(1)} KB</td>
                    <td className="px-4 py-2 text-slate-500">{r.modified}</td>
                    <td className="px-4 py-2 flex gap-1">
                      <a href={getM5ReportDownloadUrl(r.name)} target="_blank" rel="noopener"
                         className="px-2 py-1 bg-slate-100 text-slate-600 rounded text-[10px] font-bold hover:bg-slate-200">Download</a>
                      {r.type === 'PDF' && (
                        <a href={getM5ReportPreviewUrl(r.name)} target="_blank" rel="noopener"
                           className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-[10px] font-bold hover:bg-blue-200">Preview</a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
