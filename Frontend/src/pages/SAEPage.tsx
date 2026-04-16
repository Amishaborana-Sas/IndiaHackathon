import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Shield, Lock, Unlock, KeyRound, FileSearch, ArrowLeft,
  Loader2, AlertCircle, FileText, Copy, CheckCircle2, Download,
  Database, Eye, RefreshCcw, ChevronDown, Search,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import UploadBox from '../components/UploadBox';
import DocumentPreview from '../components/DocumentPreview';
import {
  saeAnonymizeText, saeAnonymizeFile,
  saeTraceback, saeCheckDuplicateFile, saeCheckDuplicateText,
  lookupToken,
} from '../services/api';
import type { SAEResult, SAETracebackResult, SAEDuplicateResult } from '../types';

// ---- Token highlighting for SAE output ----
function SAEHighlightedText({ text }: { text: string }) {
  const parts = text.split(/(\[ID-[A-Z]{3}-[a-f0-9]{6}\]|\*{3,})/g);
  return (
    <div className="whitespace-pre-wrap leading-relaxed font-mono text-sm">
      {parts.map((part, i) => {
        if (/^\[ID-[A-Z]{3}-[a-f0-9]{6}\]$/.test(part)) {
          return (
            <span key={i} className="inline-block bg-violet-100 text-violet-800 px-1.5 py-0.5 rounded font-semibold text-xs mx-0.5 border border-violet-200">
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
        return part;
      })}
    </div>
  );
}

// ---- Entity badge colors ----
const ENTITY_COLORS: Record<string, string> = {
  PERSON: 'bg-purple-100 text-purple-700',
  IN_PHONE: 'bg-orange-100 text-orange-700',
  PHONE_NUMBER: 'bg-orange-100 text-orange-700',
  AADHAAR: 'bg-red-100 text-red-700',
  EMAIL_ADDRESS: 'bg-blue-100 text-blue-700',
  ADDRESS: 'bg-green-100 text-green-700',
  ORGANIZATION: 'bg-indigo-100 text-indigo-700',
  LOCATION: 'bg-emerald-100 text-emerald-700',
  PAN: 'bg-red-100 text-red-700',
  DATE_TIME: 'bg-cyan-100 text-cyan-700',
  IN_PIN_CODE: 'bg-yellow-100 text-yellow-700',
};

// ---- Tab types for internal services ----
type ResultTab = 'output' | 'traceback' | 'duplicate';

export default function SAEPage() {
  const navigate = useNavigate();

  // Input state
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [textInput, setTextInput] = useState('');
  const [previewFile, setPreviewFile] = useState<File | null>(null);

  // Processing state
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeMode, setActiveMode] = useState<'irreversible' | 'reversible' | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Result state
  const [saeResult, setSaeResult] = useState<SAEResult | null>(null);
  const [tracebackResult, setTracebackResult] = useState<SAETracebackResult | null>(null);
  const [duplicateResult, setDuplicateResult] = useState<SAEDuplicateResult | null>(null);

  // Tab state for results section
  const [resultTab, setResultTab] = useState<ResultTab>('output');

  // Internal service loading
  const [isTracing, setIsTracing] = useState(false);
  const [isDupChecking, setIsDupChecking] = useState(false);

  // Copy feedback
  const [copied, setCopied] = useState(false);
  // Search & download menu
  const [tokenSearch, setTokenSearch] = useState('');
  const [lookupResults, setLookupResults] = useState<Record<string, string>>({});
  const [isLookingUp, setIsLookingUp] = useState(false);
  const [showFormatMenu, setShowFormatMenu] = useState(false);
  const [showMoveMenu, setShowMoveMenu] = useState(false);

  const hasInput = selectedFiles.length > 0 || textInput.trim().length > 0;

  // ---- Action handlers (ONLY 2 buttons) ----
  const handleAnonymize = async (mode: 'irreversible' | 'reversible') => {
    setError(null);
    setIsProcessing(true);
    setActiveMode(mode);
    setSaeResult(null);
    setTracebackResult(null);
    setDuplicateResult(null);
    setResultTab('output');

    try {
      let result: SAEResult;
      if (selectedFiles.length > 0) {
        result = await saeAnonymizeFile(selectedFiles[0], mode);
      } else {
        result = await saeAnonymizeText(textInput, mode);
      }
      setSaeResult(result);
    } catch (err: any) {
      setError(err.message || 'Anonymization failed');
    } finally {
      setIsProcessing(false);
    }
  };

  // ---- Internal services (inside de-identification mode) ----
  const handleTraceback = async () => {
    if (!saeResult || saeResult.mode !== 'reversible') return;
    setIsTracing(true);
    setError(null);
    try {
      const result = await saeTraceback(saeResult.file_id, saeResult.processed_text);
      setTracebackResult(result);
      setResultTab('traceback');
    } catch (err: any) {
      setError(err.message || 'Traceback failed');
    } finally {
      setIsTracing(false);
    }
  };

  const handleDuplicateCheck = async () => {
    setIsDupChecking(true);
    setError(null);
    try {
      let result: SAEDuplicateResult;
      if (selectedFiles.length > 0) {
        result = await saeCheckDuplicateFile(selectedFiles[0]);
      } else if (textInput.trim()) {
        result = await saeCheckDuplicateText(textInput);
      } else {
        throw new Error('No input for duplicate check');
      }
      setDuplicateResult(result);
      setResultTab('duplicate');
    } catch (err: any) {
      setError(err.message || 'Duplicate check failed');
    } finally {
      setIsDupChecking(false);
    }
  };

  const handleReset = () => {
    setSaeResult(null);
    setTracebackResult(null);
    setDuplicateResult(null);
    setSelectedFiles([]);
    setTextInput('');
    setError(null);
    setActiveMode(null);
    setResultTab('output');
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadJson = () => {
    if (!saeResult) return;
    const blob = new Blob([JSON.stringify(saeResult, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `anonymised_${saeResult.mode}_${saeResult.file_id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDownloadMapping = () => {
    if (!saeResult?.encrypted_mapping) return;
    const data = {
      file_id: saeResult.file_id,
      file_hash: saeResult.file_hash,
      mode: saeResult.mode,
      timestamp: saeResult.timestamp,
      note: 'Values are encrypted. Decryption requires the server-side key.',
      encrypted_entries: saeResult.encrypted_mapping,
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `mapping_${saeResult.file_id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const triggerDownload = (content: string, mime: string, filename: string) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDownload = (format: 'txt' | 'json' | 'csv' | 'pdf' | 'docx') => {
    if (!saeResult) return;
    const stem = `anonymised_${saeResult.file_id}`;
    if (format === 'json') {
      triggerDownload(JSON.stringify(saeResult, null, 2), 'application/json', `${stem}.json`);
    } else if (format === 'csv') {
      const rows = [['Entity Type', 'Count']];
      Object.entries(saeResult.entities_by_type).forEach(([t, c]) => rows.push([t, String(c)]));
      rows.push([], ['Mode', saeResult.mode], ['File ID', saeResult.file_id], ['SHA256', saeResult.file_hash]);
      triggerDownload(rows.map(r => r.map(c => `"${c}"`).join(',')).join('\n'), 'text/csv', `${stem}.csv`);
    } else {
      const lines = [
        '=' .repeat(70), '  RegLens AI - ANONYMISATION REPORT', '=' .repeat(70), '',
        `Mode: ${saeResult.mode}`, `File ID: ${saeResult.file_id}`, `SHA256: ${saeResult.file_hash}`,
        `Entities: ${saeResult.num_entities}`, '', '--- OUTPUT ---', '', saeResult.processed_text,
      ];
      triggerDownload(lines.join('\n'), 'text/plain', `${stem}.txt`);
    }
    setShowFormatMenu(false);
  };

  const handleMoveTo = (targetId: string) => {
    navigate(`/module/${targetId}`, { state: { inputText: saeResult?.processed_text || '' } });
    setShowMoveMenu(false);
  };

  // Search: find matching tokens from mapping
  const searchResult = tokenSearch.trim() && saeResult?.encrypted_mapping
    ? Object.keys(saeResult.encrypted_mapping).filter(k =>
        k.toLowerCase().includes(tokenSearch.toLowerCase())
      )
    : [];

  const handleLookupToken = async (token: string) => {
    if (!saeResult?.file_id || lookupResults[token]) return;
    setIsLookingUp(true);
    try {
      const res = await lookupToken(saeResult.file_id, token);
      if (res.found && res.original_value) {
        setLookupResults(prev => ({ ...prev, [token]: res.original_value! }));
      }
    } catch { /* ignore */ }
    setIsLookingUp(false);
  };

  const handleLookupAll = async () => {
    if (!searchResult.length || !saeResult?.file_id) return;
    setIsLookingUp(true);
    for (const token of searchResult) {
      if (lookupResults[token]) continue;
      try {
        const res = await lookupToken(saeResult.file_id, token);
        if (res.found && res.original_value) {
          setLookupResults(prev => ({ ...prev, [token]: res.original_value! }));
        }
      } catch { /* ignore */ }
    }
    setIsLookingUp(false);
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="flex items-center justify-between mb-10">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate('/')} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
            <ArrowLeft className="w-6 h-6 text-slate-600" />
          </button>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-50 text-blue-600">
              <Shield className="w-6 h-6" />
            </div>
            <h1 className="text-2xl font-black text-slate-900">Anonymisation Tool</h1>
          </div>
        </div>
        <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">
          Module 1
        </span>
      </div>

      {/* Error Banner */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3"
          >
            <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-bold text-red-800">Error</p>
              <p className="text-xs text-red-600 mt-1">{error}</p>
            </div>
            <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600 text-xs font-bold">
              Dismiss
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="space-y-8">
        {/* Step 1: Upload / Paste */}
        <section className="space-y-4">
          <div className="flex items-center gap-2 text-slate-900 font-bold">
            <span className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold">1</span>
            <h2>Upload Document or Paste Text</h2>
          </div>
          <UploadBox onFilesSelect={setSelectedFiles} selectedFiles={selectedFiles} onPreview={setPreviewFile} />

          {/* File preview */}
          {selectedFiles.length > 0 && (
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
              <div className="flex items-center gap-2 text-sm">
                <Eye className="w-4 h-4 text-slate-500" />
                <span className="font-semibold text-slate-700">Uploaded:</span>
                <span className="text-slate-600">{selectedFiles[0].name}</span>
                <span className="text-slate-400">({(selectedFiles[0].size / 1024).toFixed(1)} KB)</span>
                <button
                  onClick={() => setPreviewFile(selectedFiles[0])}
                  className="ml-auto text-xs font-bold text-violet-600 hover:text-violet-800"
                >
                  Preview
                </button>
              </div>
            </div>
          )}

          <div className="pt-2">
            <div className="flex items-center gap-2 mb-2 text-sm font-bold text-slate-700">
              <FileText className="w-4 h-4 text-violet-600" />
              <span>Manual Text Input (Optional)</span>
            </div>
            <textarea
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder={`Paste your regulatory text here...\n\nExample:\nName: Ramesh Kumar\nAadhaar Number: 1234-5678-9012\nHospital: XYZ Hospital, Pune\nDoctor: Dr. Amit Sharma\n\nEvent Description:\nPatient Ramesh developed severe liver toxicity...`}
              className="w-full p-4 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all font-mono text-sm min-h-[160px] resize-y"
            />
          </div>
        </section>

        {/* Step 2: ONLY 2 Buttons */}
        <section className="space-y-4">
          <div className="flex items-center gap-2 text-slate-900 font-bold">
            <span className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold">2</span>
            <h2>Select Mode</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Button 1: Irreversible Anonymization */}
            <button
              onClick={() => handleAnonymize('irreversible')}
              disabled={isProcessing || !hasInput}
              className={`p-5 rounded-xl border-2 text-left transition-all ${
                activeMode === 'irreversible' && saeResult
                  ? 'border-red-500 bg-red-50 shadow-md shadow-red-100 ring-2 ring-red-300'
                  : !hasInput
                    ? 'border-slate-100 bg-slate-50 opacity-50 cursor-not-allowed'
                    : 'border-slate-200 hover:border-red-300 bg-white cursor-pointer'
              }`}
            >
              <div className="flex items-center gap-3 mb-2">
                <div className={`p-2 rounded-lg ${activeMode === 'irreversible' && saeResult ? 'bg-red-100' : 'bg-slate-100'}`}>
                  {isProcessing && activeMode === 'irreversible' ? (
                    <Loader2 className="w-5 h-5 text-red-600 animate-spin" />
                  ) : (
                    <Lock className={`w-5 h-5 ${activeMode === 'irreversible' && saeResult ? 'text-red-600' : 'text-slate-400'}`} />
                  )}
                </div>
                <h4 className="font-bold text-slate-900">Irreversible Anonymization</h4>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                Masks all PII with <code className="bg-red-100 text-red-600 px-1 rounded text-[10px] font-mono">************</code>. No recovery possible. No traceability. Safe for public release.
              </p>
              <div className="mt-3 pt-2 border-t border-slate-100 text-[10px] text-slate-400">
                Name &rarr; ************ | Phone &rarr; ************ | Aadhaar &rarr; ************ | Address &rarr; [REDACTED ADDRESS]
              </div>
            </button>

            {/* Button 2: Reversible De-Identification */}
            <button
              onClick={() => handleAnonymize('reversible')}
              disabled={isProcessing || !hasInput}
              className={`p-5 rounded-xl border-2 text-left transition-all ${
                activeMode === 'reversible' && saeResult
                  ? 'border-violet-500 bg-violet-50 shadow-md shadow-violet-100 ring-2 ring-violet-300'
                  : !hasInput
                    ? 'border-slate-100 bg-slate-50 opacity-50 cursor-not-allowed'
                    : 'border-slate-200 hover:border-violet-300 bg-white cursor-pointer'
              }`}
            >
              <div className="flex items-center gap-3 mb-2">
                <div className={`p-2 rounded-lg ${activeMode === 'reversible' && saeResult ? 'bg-violet-100' : 'bg-slate-100'}`}>
                  {isProcessing && activeMode === 'reversible' ? (
                    <Loader2 className="w-5 h-5 text-violet-600 animate-spin" />
                  ) : (
                    <Unlock className={`w-5 h-5 ${activeMode === 'reversible' && saeResult ? 'text-violet-600' : 'text-slate-400'}`} />
                  )}
                </div>
                <h4 className="font-bold text-slate-900">De-Identification (Reversible)</h4>
              </div>
              <p className="text-xs text-slate-500 leading-relaxed">
                Replaces PII with tokens like <code className="bg-violet-100 text-violet-700 px-1 rounded text-[10px] font-mono">[ID-PER-8f3a9c]</code>. Encrypted mapping stored. Includes traceback & duplicate detection.
              </p>
              <div className="mt-3 pt-2 border-t border-slate-100 text-[10px] text-slate-400">
                Person &rarr; [ID-PER-xxxxxx] | Phone &rarr; [ID-PHN-xxxxxx] | Aadhaar &rarr; [ID-UID-xxxxxx]
              </div>
            </button>
          </div>
        </section>

        {/* Results */}
        <AnimatePresence mode="wait">
          {saeResult && (
            <motion.section
              key="results"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="space-y-6"
            >
              {/* Results header */}
              <div className="flex items-center gap-2 text-slate-900 font-bold">
                <span className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold">3</span>
                <h2>Results</h2>
              </div>

              {/* Action bar: Process Another / Download / Move Output To */}
              <div className="flex flex-wrap items-center justify-center gap-3 p-4 bg-white border border-slate-200 rounded-xl">
                <button onClick={handleReset}
                  className="flex items-center gap-2 px-5 py-2.5 bg-white border border-slate-200 rounded-xl text-slate-700 font-semibold hover:bg-slate-100 active:bg-slate-200 active:scale-95 transition-all shadow-sm text-sm">
                  <RefreshCcw className="w-4 h-4" /> Process Another
                </button>
                <div className="relative">
                  <button onClick={() => setShowFormatMenu(!showFormatMenu)}
                    className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-xl font-semibold hover:bg-blue-700 hover:shadow-lg active:bg-blue-800 active:scale-95 transition-all shadow-md shadow-blue-200 text-sm">
                    <Download className="w-4 h-4" /> Download
                    <ChevronDown className={`w-3 h-3 transition-transform ${showFormatMenu ? 'rotate-180' : ''}`} />
                  </button>
                  {showFormatMenu && (
                    <div className="absolute top-full mt-2 right-0 bg-white border border-slate-200 rounded-xl shadow-lg py-1 z-10 min-w-[180px]">
                      {(['txt', 'json', 'csv'] as const).map(fmt => (
                        <button key={fmt} onClick={() => handleDownload(fmt)}
                          className="w-full text-left px-4 py-2 hover:bg-blue-50 hover:text-blue-700 active:bg-blue-200 text-sm font-medium text-slate-700 transition-colors">
                          {fmt === 'txt' ? 'Plain Text (.txt)' : fmt === 'json' ? 'JSON Report (.json)' : 'CSV Spreadsheet (.csv)'}
                        </button>
                      ))}
                      {saeResult.mode === 'reversible' && saeResult.encrypted_mapping && Object.keys(saeResult.encrypted_mapping).length > 0 && (
                        <button onClick={() => { handleDownloadMapping(); setShowFormatMenu(false); }}
                          className="w-full text-left px-4 py-2 hover:bg-violet-50 hover:text-violet-700 active:bg-violet-200 text-sm font-medium text-slate-700 transition-colors border-t border-slate-100">
                          Encrypted Mapping (.json)
                        </button>
                      )}
                    </div>
                  )}
                </div>
                <div className="relative">
                  <button onClick={() => setShowMoveMenu(!showMoveMenu)}
                    className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-semibold hover:bg-indigo-700 hover:shadow-lg active:bg-indigo-800 active:scale-95 transition-all shadow-md shadow-indigo-200 text-sm">
                    Move Output To
                    <ChevronDown className={`w-3 h-3 transition-transform ${showMoveMenu ? 'rotate-180' : ''}`} />
                  </button>
                  {showMoveMenu && (
                    <div className="absolute top-full mt-2 right-0 bg-white border border-slate-200 rounded-xl shadow-lg py-1 z-10 min-w-[180px]">
                      {[{id:'summarisation',label:'Summarisation'},{id:'comparison',label:'Comparison'},{id:'classification',label:'Classification'},{id:'inspection',label:'Inspection Report'}].map(m => (
                        <button key={m.id} onClick={() => handleMoveTo(m.id)}
                          className="w-full text-left px-4 py-2 hover:bg-slate-50 text-sm font-medium text-slate-700">
                          {m.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Stats bar */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div className="bg-white rounded-xl p-3 border border-slate-200 text-center">
                  <div className="text-2xl font-black text-slate-800">{saeResult.num_entities}</div>
                  <div className="text-[10px] font-semibold text-slate-500 uppercase">Entities Found</div>
                </div>
                <div className="bg-white rounded-xl p-3 border border-slate-200 text-center">
                  <div className="text-2xl font-black text-violet-700">{saeResult.mode === 'reversible' ? 'REV' : 'IRR'}</div>
                  <div className="text-[10px] font-semibold text-slate-500 uppercase">Mode</div>
                </div>
                <div className="bg-white rounded-xl p-3 border border-slate-200 text-center">
                  <div className="text-lg font-black text-slate-800 font-mono truncate">{saeResult.file_id}</div>
                  <div className="text-[10px] font-semibold text-slate-500 uppercase">File ID</div>
                </div>
                <div className="bg-white rounded-xl p-3 border border-slate-200 text-center">
                  <div className="text-2xl font-black text-slate-800">{saeResult.mapping_size}</div>
                  <div className="text-[10px] font-semibold text-slate-500 uppercase">Mappings</div>
                </div>
                <div className="bg-white rounded-xl p-3 border border-slate-200 text-center">
                  <div className="text-lg font-black text-slate-600 font-mono truncate">{saeResult.file_hash.slice(0, 16)}...</div>
                  <div className="text-[10px] font-semibold text-slate-500 uppercase">SHA256</div>
                </div>
              </div>

              {/* Entity breakdown */}
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <h4 className="text-sm font-bold text-slate-700 mb-3">Detected Entities</h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(saeResult.entities_by_type).sort(([,a],[,b]) => b - a).map(([type, count]) => (
                    <span
                      key={type}
                      className={`px-2.5 py-1 rounded-full text-xs font-bold border ${
                        ENTITY_COLORS[type] || 'bg-slate-100 text-slate-700'
                      }`}
                    >
                      {type}: {count}
                    </span>
                  ))}
                </div>
              </div>

              {/* Tab bar — Output + Internal Services (for reversible mode) */}
              <div className="flex items-center gap-1 border-b border-slate-200">
                <button
                  onClick={() => setResultTab('output')}
                  className={`px-4 py-2.5 text-sm font-bold transition-colors border-b-2 ${
                    resultTab === 'output'
                      ? 'border-violet-600 text-violet-700'
                      : 'border-transparent text-slate-400 hover:text-slate-600'
                  }`}
                >
                  {saeResult.mode === 'irreversible' ? 'Anonymized Output' : 'De-Identified Output'}
                </button>
                {saeResult.mode === 'reversible' && (
                  <>
                    <button
                      onClick={() => { setResultTab('traceback'); if (!tracebackResult) handleTraceback(); }}
                      className={`px-4 py-2.5 text-sm font-bold transition-colors border-b-2 flex items-center gap-1.5 ${
                        resultTab === 'traceback'
                          ? 'border-amber-600 text-amber-700'
                          : 'border-transparent text-slate-400 hover:text-slate-600'
                      }`}
                    >
                      <KeyRound className="w-3.5 h-3.5" />
                      Traceback File
                      {isTracing && <Loader2 className="w-3 h-3 animate-spin" />}
                    </button>
                    <button
                      onClick={() => { setResultTab('duplicate'); if (!duplicateResult) handleDuplicateCheck(); }}
                      className={`px-4 py-2.5 text-sm font-bold transition-colors border-b-2 flex items-center gap-1.5 ${
                        resultTab === 'duplicate'
                          ? 'border-cyan-600 text-cyan-700'
                          : 'border-transparent text-slate-400 hover:text-slate-600'
                      }`}
                    >
                      <FileSearch className="w-3.5 h-3.5" />
                      Check Duplicate
                      {isDupChecking && <Loader2 className="w-3 h-3 animate-spin" />}
                    </button>
                  </>
                )}
                {saeResult.mode === 'irreversible' && (
                  <button
                    onClick={() => { setResultTab('duplicate'); if (!duplicateResult) handleDuplicateCheck(); }}
                    className={`px-4 py-2.5 text-sm font-bold transition-colors border-b-2 flex items-center gap-1.5 ${
                      resultTab === 'duplicate'
                        ? 'border-cyan-600 text-cyan-700'
                        : 'border-transparent text-slate-400 hover:text-slate-600'
                    }`}
                  >
                    <FileSearch className="w-3.5 h-3.5" />
                    Check Duplicate
                    {isDupChecking && <Loader2 className="w-3 h-3 animate-spin" />}
                  </button>
                )}
              </div>

              {/* Tab content */}
              <AnimatePresence mode="wait">
                {resultTab === 'output' && (
                  <motion.div key="output-tab" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-4">
                    {/* Processed text */}
                    <div className="bg-white rounded-xl border border-slate-200 p-4">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-bold text-slate-700">
                          {saeResult.mode === 'irreversible' ? 'Anonymized Output' : 'De-Identified Output'}
                        </h4>
                        <button
                          onClick={() => handleCopy(saeResult.processed_text)}
                          className="flex items-center gap-1 px-2 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-600 text-xs font-bold transition-colors"
                        >
                          {copied ? <CheckCircle2 className="w-3.5 h-3.5 text-green-600" /> : <Copy className="w-3.5 h-3.5" />}
                          {copied ? 'Copied' : 'Copy'}
                        </button>
                      </div>
                      <div className="max-h-[500px] overflow-y-auto bg-slate-50 rounded-lg p-4 border border-slate-100">
                        <SAEHighlightedText text={saeResult.processed_text} />
                      </div>
                    </div>

                    {/* Token search & reveal (de-identification mode) */}
                    {saeResult.mode === 'reversible' && (
                      <div className="bg-white rounded-xl border border-blue-200 p-4 space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <Search className="w-4 h-4 text-blue-600" />
                            <h4 className="text-sm font-bold text-blue-700">Search & Reveal Token</h4>
                          </div>
                          {searchResult.length > 0 && (
                            <button onClick={handleLookupAll} disabled={isLookingUp}
                              className="text-xs font-bold text-blue-600 hover:text-blue-800 disabled:text-slate-400">
                              {isLookingUp ? 'Decrypting...' : 'Reveal All Matches'}
                            </button>
                          )}
                        </div>
                        <input
                          type="text"
                          value={tokenSearch}
                          onChange={(e) => setTokenSearch(e.target.value)}
                          placeholder="Search by token ID (e.g. ID-PER, ID-PHN, ID-UID)..."
                          className="w-full p-3 rounded-lg border border-blue-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none text-sm font-mono"
                        />
                        {tokenSearch.trim() && (
                          <div className="space-y-2">
                            {searchResult.length > 0 ? searchResult.map(token => (
                              <div key={token} className="flex items-center justify-between p-3 bg-blue-50 rounded-lg border border-blue-100">
                                <div className="flex-1 min-w-0">
                                  <code className="text-xs font-mono font-bold text-blue-800">{token}</code>
                                  {lookupResults[token] ? (
                                    <div className="mt-1 flex items-center gap-2">
                                      <span className="text-[10px] text-slate-500">Original:</span>
                                      <span className="text-sm font-semibold text-green-700 bg-green-50 px-2 py-0.5 rounded border border-green-200">{lookupResults[token]}</span>
                                    </div>
                                  ) : (
                                    <div className="mt-1 text-[10px] text-slate-400">Click Reveal to decrypt</div>
                                  )}
                                </div>
                                {!lookupResults[token] && (
                                  <button onClick={() => handleLookupToken(token)} disabled={isLookingUp}
                                    className="px-3 py-1 rounded-lg bg-blue-600 text-white text-xs font-bold hover:bg-blue-700 active:scale-95 transition-all disabled:bg-slate-300">
                                    Reveal
                                  </button>
                                )}
                              </div>
                            )) : (
                              <p className="text-xs text-slate-400 italic">No matching tokens found</p>
                            )}
                          </div>
                        )}
                      </div>
                    )}

                    {/* File tracking info */}
                    <div className="bg-white rounded-xl border border-slate-200 p-4">
                      <h4 className="text-sm font-bold text-slate-700 mb-3">File Tracking</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-500 text-xs uppercase w-24">File ID:</span>
                          <code className="font-mono text-slate-800 bg-slate-100 px-2 py-0.5 rounded">{saeResult.file_id}</code>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-500 text-xs uppercase w-24">SHA256:</span>
                          <code className="font-mono text-slate-600 text-xs bg-slate-100 px-2 py-0.5 rounded truncate">{saeResult.file_hash}</code>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-500 text-xs uppercase w-24">Timestamp:</span>
                          <span className="text-slate-700">{saeResult.timestamp}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-500 text-xs uppercase w-24">Mapping:</span>
                          <span className="text-slate-700">
                            {saeResult.mapping_stored ? (
                              <span className="text-green-700 font-bold">Stored (AES encrypted)</span>
                            ) : (
                              <span className="text-slate-500">N/A (irreversible mode)</span>
                            )}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Encrypted mapping preview (reversible only) */}
                    {saeResult.mode === 'reversible' && saeResult.encrypted_mapping && Object.keys(saeResult.encrypted_mapping).length > 0 && (
                      <div className="bg-white rounded-xl border border-violet-200 p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <Database className="w-4 h-4 text-violet-600" />
                          <h4 className="text-sm font-bold text-violet-700">Secure Mapping Store (Encrypted)</h4>
                        </div>
                        <div className="max-h-[200px] overflow-y-auto bg-violet-50 rounded-lg p-3 border border-violet-100">
                          <pre className="text-[11px] font-mono text-violet-800 whitespace-pre-wrap">
{JSON.stringify(
  Object.fromEntries(
    Object.entries(saeResult.encrypted_mapping).map(([k, v]) => [k, v.slice(0, 40) + '...'])
  ),
  null, 2
)}
                          </pre>
                        </div>
                        <p className="text-[10px] text-violet-500 mt-2">Values are AES-encrypted. Not human-readable. Decryption requires server-side key.</p>
                      </div>
                    )}
                  </motion.div>
                )}

                {resultTab === 'traceback' && (
                  <motion.div key="traceback-tab" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    {isTracing ? (
                      <div className="flex items-center justify-center gap-3 p-12 bg-amber-50 rounded-xl border border-amber-200">
                        <Loader2 className="w-5 h-5 text-amber-600 animate-spin" />
                        <span className="text-sm font-semibold text-amber-800">Reconstructing original text from encrypted mapping...</span>
                      </div>
                    ) : tracebackResult ? (
                      <div className="bg-white rounded-xl border border-amber-200 p-4 space-y-3">
                        <div className="flex items-center gap-2 flex-wrap">
                          <KeyRound className="w-5 h-5 text-amber-600" />
                          <h4 className="text-sm font-bold text-amber-900">Original Document (Reconstructed)</h4>
                          {tracebackResult.success ? (
                            <span className="px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-xs font-bold">SUCCESS</span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-xs font-bold">FAILED</span>
                          )}
                          {tracebackResult.success && (
                            <div className="ml-auto flex items-center gap-2">
                              <button onClick={() => handleCopy(tracebackResult.reconstructed_text || '')}
                                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-700 text-xs font-bold transition-colors">
                                <Copy className="w-3 h-3" /> Copy
                              </button>
                              <button onClick={() => {
                                triggerDownload(tracebackResult.reconstructed_text || '', 'text/plain',
                                  `original_${tracebackResult.file_id}.txt`);
                              }}
                                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-bold transition-colors active:scale-95">
                                <Download className="w-3 h-3" /> Download Original
                              </button>
                            </div>
                          )}
                        </div>
                        {tracebackResult.success ? (
                          <>
                            <div className="text-xs text-amber-700">
                              Mappings applied: <strong>{tracebackResult.mappings_applied}</strong> | File ID: <code className="font-mono">{tracebackResult.file_id}</code>
                            </div>
                            <div className="max-h-[500px] overflow-y-auto bg-amber-50 rounded-lg p-4 border border-amber-100">
                              <pre className="whitespace-pre-wrap text-sm font-mono text-slate-800 leading-relaxed">{tracebackResult.reconstructed_text}</pre>
                            </div>
                          </>
                        ) : (
                          <p className="text-sm text-red-600">{tracebackResult.error}</p>
                        )}
                      </div>
                    ) : (
                      <div className="p-8 text-center text-sm text-slate-400">
                        Click to run traceback reconstruction.
                      </div>
                    )}
                  </motion.div>
                )}

                {resultTab === 'duplicate' && (
                  <motion.div key="duplicate-tab" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    {isDupChecking ? (
                      <div className="flex items-center justify-center gap-3 p-12 bg-cyan-50 rounded-xl border border-cyan-200">
                        <Loader2 className="w-5 h-5 text-cyan-600 animate-spin" />
                        <span className="text-sm font-semibold text-cyan-800">Checking SHA256 hash against file tracker...</span>
                      </div>
                    ) : duplicateResult ? (
                      <div className={`rounded-xl border p-4 space-y-3 ${
                        duplicateResult.is_duplicate ? 'bg-amber-50 border-amber-200' : 'bg-green-50 border-green-200'
                      }`}>
                        <div className="flex items-center gap-2">
                          <FileSearch className={`w-5 h-5 ${duplicateResult.is_duplicate ? 'text-amber-600' : 'text-green-600'}`} />
                          <h4 className={`text-sm font-bold ${duplicateResult.is_duplicate ? 'text-amber-900' : 'text-green-900'}`}>
                            Duplicate Check Result
                          </h4>
                          <span className={`ml-auto px-2 py-0.5 rounded-full text-xs font-bold ${
                            duplicateResult.is_duplicate ? 'bg-amber-100 text-amber-700' : 'bg-green-100 text-green-700'
                          }`}>
                            {duplicateResult.is_duplicate ? 'DUPLICATE FOUND' : 'NEW FILE'}
                          </span>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                          <div>
                            <span className="font-bold text-slate-500 text-xs uppercase">File ID:</span>
                            <code className="ml-2 font-mono text-slate-800">{duplicateResult.file_id}</code>
                          </div>
                          <div>
                            <span className="font-bold text-slate-500 text-xs uppercase">SHA256:</span>
                            <code className="ml-2 font-mono text-slate-600 text-xs">{duplicateResult.file_hash}</code>
                          </div>
                          {duplicateResult.is_duplicate && (
                            <>
                              <div>
                                <span className="font-bold text-slate-500 text-xs uppercase">First Seen:</span>
                                <span className="ml-2 text-slate-700">{duplicateResult.first_seen}</span>
                              </div>
                              <div>
                                <span className="font-bold text-slate-500 text-xs uppercase">Process Count:</span>
                                <span className="ml-2 text-slate-700 font-bold">{duplicateResult.process_count}</span>
                              </div>
                              {duplicateResult.filenames && duplicateResult.filenames.length > 0 && (
                                <div className="md:col-span-2">
                                  <span className="font-bold text-slate-500 text-xs uppercase">Previous Filenames:</span>
                                  <span className="ml-2 text-slate-700">{duplicateResult.filenames.join(', ')}</span>
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="p-8 text-center text-sm text-slate-400">
                        Click to check for duplicates.
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.section>
          )}
        </AnimatePresence>
      </div>

      {/* Document Preview Modal */}
      <AnimatePresence>
        {previewFile && (
          <DocumentPreview file={previewFile} onClose={() => setPreviewFile(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}
