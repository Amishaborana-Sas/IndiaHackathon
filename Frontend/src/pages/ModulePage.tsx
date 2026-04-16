import { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Shield, FileText, FileSearch, Tag, ClipboardCheck, ArrowLeft, Play, Loader2, Lock, Unlock, KeyRound, AlertCircle, Database, Mic, Square, Eye } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import UploadBox from '../components/UploadBox';
import ResultPanel from '../components/ResultPanel';
import DocumentPreview from '../components/DocumentPreview';
import { analyzeDocument, downloadResult, fetchVaultInfo, scanDetectFiles, ScanDetectResult } from '../services/api';
import { ModuleResult, AnonymisationMode, Module3Mode, VaultInfo } from '../types';

const moduleMeta: Record<string, any> = {
  anonymisation: { title: 'Anonymisation Tool', icon: Shield, color: 'text-blue-600', bgColor: 'bg-blue-600', moduleNo: 1 },
  summarisation: { title: 'Document Summarisation', icon: FileText, color: 'text-indigo-600', bgColor: 'bg-indigo-600', moduleNo: 2 },
  comparison: { title: 'Completeness & Comparison', icon: FileSearch, color: 'text-cyan-600', bgColor: 'bg-cyan-600', moduleNo: 3 },
  classification: { title: 'Classification Tool', icon: Tag, color: 'text-sky-600', bgColor: 'bg-sky-600', moduleNo: 4 },
  inspection: { title: 'Inspection Report Generator', icon: ClipboardCheck, color: 'text-blue-500', bgColor: 'bg-blue-500', moduleNo: 5 },
};

export default function ModulePage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [textInput, setTextInput] = useState(
    (location.state as any)?.inputText || ''
  );
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<ModuleResult | null>(null);
  const [mode, setMode] = useState<AnonymisationMode>('de-identification');
  const [m3Mode, setM3Mode] = useState<Module3Mode>('completeness');
  const [previewFile, setPreviewFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [vaultInfo, setVaultInfo] = useState<VaultInfo | null>(null);
  const [activeButton, setActiveButton] = useState<string | null>(null);
  const [scanInfo, setScanInfo] = useState<ScanDetectResult | null>(null);
  const [isDetecting, setIsDetecting] = useState(false);
  const [processingStatus, setProcessingStatus] = useState<string>('');
  // Module 5 field overrides
  const [m5FirmName, setM5FirmName] = useState('');
  const [m5License, setM5License] = useState('');
  const [m5Date, setM5Date] = useState('');
  const [m5State, setM5State] = useState('');
  const [m5Notes, setM5Notes] = useState('');

  // Module 2 — audio recording + case details + summary sentences
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [mediaRecorderRef, setMediaRecorderRef] = useState<MediaRecorder | null>(null);
  const [m2SentenceCount, setM2SentenceCount] = useState('8');
  const [m2FirmName, setM2FirmName] = useState('');
  const [m2LicenceNo, setM2LicenceNo] = useState('');
  const [m2Date, setM2Date] = useState('');
  const [m2Division, setM2Division] = useState('NDD');
  const [m2Address, setM2Address] = useState('');
  const [m2SugamRef, setM2SugamRef] = useState('');
  const [m2Inspectors, setM2Inspectors] = useState('');
  const [m2Deficiency, setM2Deficiency] = useState('');
  const [m2GeneralRemark, setM2GeneralRemark] = useState('');
  const [m2ResultTab, setM2ResultTab] = useState<'summary' | 'remark'>('summary');

  const meta = id ? moduleMeta[id] : null;
  const Icon = meta?.icon || Shield;

  // When navigated to from another module's "Move Output To", populate the text input
  useEffect(() => {
    const incoming = (location.state as any)?.inputText;
    if (incoming) {
      setTextInput(incoming);
      setResult(null);
      setSelectedFiles([]);
      setError(null);
      // Clear the state so refreshing doesn't re-populate
      window.history.replaceState({}, '');
    }
  }, [location.state, location.key]);

  useEffect(() => {
    if (!meta) navigate('/');
  }, [meta, navigate]);

  // Fetch vault info when reversible mode is selected
  useEffect(() => {
    if (mode === 'reversible-anonymisation') {
      fetchVaultInfo().then(setVaultInfo);
    }
  }, [mode]);

  const handleRunAnalysis = async () => {
    if (!id) return;
    setError(null);
    setActiveButton('run');

    // Phase 1: Scan detection (for file uploads, not text-only)
    if (selectedFiles.length > 0 && id === 'anonymisation') {
      setIsDetecting(true);
      setProcessingStatus('Detecting scanned vs digital pages...');
      try {
        const detect = await scanDetectFiles(selectedFiles);
        setScanInfo(detect);
        setProcessingStatus(
          `Found ${detect.summary.total_files} file(s): ${detect.summary.digital_files} digital, ${detect.summary.scanned_files} need OCR (${detect.summary.scanned_pages} scanned pages)`
        );
      } catch {
        // scan-detect is optional, continue anyway
      }
      setIsDetecting(false);
    }

    // Phase 2: Full processing (with OCR for scanned pages)
    setIsProcessing(true);
    setProcessingStatus('Processing documents...');
    try {
      const effectiveMode = id === 'comparison' ? m3Mode : mode;
      const m5Over = id === 'inspection' ? {
        firm_name: m5FirmName, license_number: m5License,
        inspection_date: m5Date, state: m5State, manual_notes: m5Notes,
      } : undefined;
      const data = await analyzeDocument(id, selectedFiles, effectiveMode, textInput, m5Over);
      setResult(data);
      setProcessingStatus('');
    } catch (err: any) {
      console.error('Analysis failed', err);
      setError(err.message || 'Analysis failed. Make sure the backend server is running.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReset = () => {
    setResult(null);
    setSelectedFiles([]);
    setTextInput('');
    setError(null);
    setActiveButton(null);
    setScanInfo(null);
    setProcessingStatus('');
  };

  const handleDownload = (format: 'txt' | 'json' | 'csv' | 'pdf' | 'docx') => {
    if (result) {
      const baseName = selectedFiles.length > 0 ? selectedFiles[0].name : 'output';
      downloadResult(result, format, baseName);
    }
  };

  const handleMoveTo = (targetModuleId: string) => {
    if (result) {
      let outputText = '';
      if (result.type === 'anonymisation') {
        outputText = result.data.processedText;
      } else if (result.type === 'summarisation') {
        outputText = result.data.summary;
      } else if (result.type === 'comparison') {
        const m3 = result.data;
        if (m3.mode === 'completeness') {
          outputText = m3.data.summary || '';
        } else {
          const cmp = m3.data as any;
          outputText = (cmp.field_changes || []).map((c: any) => `[${c.significance}] ${c.field_name}: ${c.description}`).join('\n');
        }
      } else if (result.type === 'classification') {
        outputText = `Category: ${result.data.category}\n${result.data.subCategories.map(s => `- ${s.name}`).join('\n')}`;
      } else if (result.type === 'inspection') {
        outputText = result.data.raw_text || '';
      }
      navigate(`/module/${targetModuleId}`, {
        state: { inputText: outputText },
        replace: false,
      });
    }
  };

  // ---- Module 2: Audio recording handlers ----
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm';
      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      const chunks: BlobPart[] = [];
      mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunks, { type: mimeType });
        const file = new File([blob], `recording_${Date.now()}.webm`, { type: mimeType });
        setSelectedFiles([file]);
        stream.getTracks().forEach(t => t.stop());
      };
      mediaRecorder.start();
      setMediaRecorderRef(mediaRecorder);
      setIsRecording(true);
      setRecordingTime(0);
      // Timer
      const interval = setInterval(() => {
        setRecordingTime(prev => {
          if (prev >= 420) { // 7 minutes max
            mediaRecorder.stop();
            setIsRecording(false);
            clearInterval(interval);
            return prev;
          }
          return prev + 1;
        });
      }, 1000);
      (mediaRecorder as any)._interval = interval;
    } catch {
      setError('Microphone access denied. Please allow microphone permissions.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef) {
      if ((mediaRecorderRef as any)._interval) clearInterval((mediaRecorderRef as any)._interval);
      mediaRecorderRef.stop();
      setIsRecording(false);
      setMediaRecorderRef(null);
    }
  };

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, '0')}`;

  if (!meta) return null;

  const stepNumber = id === 'anonymisation' ? { upload: 1, mode: 2, run: 3 } : { upload: 1, run: 2 };

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="flex items-center justify-between mb-10">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/')}
            className="p-2 hover:bg-slate-100 rounded-full transition-colors"
          >
            <ArrowLeft className="w-6 h-6 text-slate-600" />
          </button>
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg bg-blue-50 ${meta.color}`}>
              <Icon className="w-6 h-6" />
            </div>
            <h1 className="text-2xl font-black text-slate-900">{meta.title}</h1>
          </div>
        </div>
        <div className="hidden md:block">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">
            Module {meta.moduleNo}
          </span>
        </div>
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
              <p className="text-sm font-bold text-red-800">Processing Error</p>
              <p className="text-xs text-red-600 mt-1">{error}</p>
            </div>
            <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600">
              <span className="text-xs font-bold">Dismiss</span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {!result ? (
          <motion.div
            key="input-form"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="space-y-8"
          >
            {/* Module 3: Mode selector (Completeness vs Comparison) */}
            {id === 'comparison' && (
              <section className="space-y-4">
                <div className="flex items-center gap-2 text-slate-900 font-bold">
                  <span className="w-6 h-6 rounded-full bg-cyan-600 text-white flex items-center justify-center text-xs font-bold">1</span>
                  <h2>Select Assessment Mode</h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <button
                    onClick={() => { setM3Mode('completeness'); setSelectedFiles([]); setActiveButton('completeness'); }}
                    className={`p-5 rounded-xl border-2 text-left transition-all ${
                      m3Mode === 'completeness'
                        ? 'border-cyan-500 bg-cyan-50 shadow-md shadow-cyan-100 ring-2 ring-cyan-300'
                        : 'border-slate-200 hover:border-cyan-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <div className={`p-2 rounded-lg ${m3Mode === 'completeness' ? 'bg-cyan-100' : 'bg-slate-100'}`}>
                        <FileSearch className={`w-5 h-5 ${m3Mode === 'completeness' ? 'text-cyan-600' : 'text-slate-400'}`} />
                      </div>
                      <h4 className="font-bold text-slate-900">Completeness Check</h4>
                    </div>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      Upload a single clinical document (SAE report, scan, image, PDF).
                      Checks for missing/invalid mandatory fields per CDSCO GCP rules.
                    </p>
                  </button>
                  <button
                    onClick={() => { setM3Mode('comparison'); setSelectedFiles([]); setActiveButton('comparison'); }}
                    className={`p-5 rounded-xl border-2 text-left transition-all ${
                      m3Mode === 'comparison'
                        ? 'border-cyan-500 bg-cyan-50 shadow-md shadow-cyan-100 ring-2 ring-cyan-300'
                        : 'border-slate-200 hover:border-cyan-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <div className={`p-2 rounded-lg ${m3Mode === 'comparison' ? 'bg-cyan-100' : 'bg-slate-100'}`}>
                        <FileSearch className={`w-5 h-5 ${m3Mode === 'comparison' ? 'text-cyan-600' : 'text-slate-400'}`} />
                      </div>
                      <h4 className="font-bold text-slate-900">Document Comparison</h4>
                    </div>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      Upload two or more versions of a document (e.g. Initial, Follow-up, Final SAE).
                      Compares field-level changes across versions.
                    </p>
                  </button>
                </div>
              </section>
            )}

            {/* Section: Upload */}
            <section className="space-y-4">
              <div className="flex items-center gap-2 text-slate-900 font-bold">
                <span className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold">{id === 'comparison' ? 2 : stepNumber.upload}</span>
                <h2>
                  {id === 'comparison' && m3Mode === 'comparison'
                    ? 'Upload Document Versions (2 or more)'
                    : id === 'comparison' && m3Mode === 'completeness'
                      ? 'Upload Clinical Document'
                      : id === 'summarisation'
                        ? 'Upload Documents, Audio Files, or Paste Text'
                        : 'Upload Documents or Paste Text'}
                </h2>
              </div>
              {id === 'comparison' && m3Mode === 'comparison' && (
                <p className="text-xs text-slate-500 -mt-2 ml-8">
                  Upload versions in order: <strong>V1</strong> (oldest) first, then <strong>V2</strong>, <strong>V3</strong>, etc.
                </p>
              )}
              <UploadBox
                onFilesSelect={setSelectedFiles}
                selectedFiles={selectedFiles}
                onPreview={setPreviewFile}
              />

              {/* Module 2: Audio Recording + File Preview */}
              {id === 'summarisation' && (
                <div className="space-y-4">
                  {/* Audio recording buttons */}
                  <div className="flex items-center gap-3 flex-wrap">
                    <button
                      onClick={startRecording}
                      disabled={isRecording}
                      className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-all ${
                        isRecording
                          ? 'bg-red-100 text-red-400 cursor-not-allowed'
                          : 'bg-red-600 text-white hover:bg-red-700 shadow-sm'
                      }`}
                    >
                      <Mic className="w-4 h-4" />
                      Record Audio (max 7 min)
                    </button>
                    <button
                      onClick={stopRecording}
                      disabled={!isRecording}
                      className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold transition-all ${
                        !isRecording
                          ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                          : 'bg-slate-800 text-white hover:bg-slate-900 shadow-sm'
                      }`}
                    >
                      <Square className="w-4 h-4" />
                      Stop Recording
                    </button>
                    {isRecording && (
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
                        <span className="text-sm font-bold text-red-600">Recording... {formatTime(recordingTime)}</span>
                      </div>
                    )}
                  </div>

                  {/* File/audio preview */}
                  {selectedFiles.length > 0 && (
                    <div className="p-3 bg-indigo-50 border border-indigo-200 rounded-xl">
                      <div className="flex items-center gap-2 text-sm">
                        <Eye className="w-4 h-4 text-indigo-500" />
                        <span className="font-semibold text-indigo-700">Uploaded / Recorded:</span>
                        <span className="text-indigo-600">{selectedFiles[0].name}</span>
                        <span className="text-indigo-400">({(selectedFiles[0].size / 1024).toFixed(1)} KB)</span>
                        <button
                          onClick={() => setPreviewFile(selectedFiles[0])}
                          className="ml-auto text-xs font-bold text-indigo-600 hover:text-indigo-800"
                        >
                          Preview
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Module 2: Case / Firm Details */}
              {id === 'summarisation' && (
                <div className="pt-4 space-y-4">
                  <div className="flex items-center gap-2 text-slate-900 font-bold text-sm">
                    <FileText className="w-4 h-4 text-indigo-600" />
                    <span>Case / Firm Details (required)</span>
                  </div>
                  <div className="bg-white border border-slate-200 rounded-xl p-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Firm / Case Name *</label>
                        <input type="text" value={m2FirmName} onChange={(e) => setM2FirmName(e.target.value)}
                          className="w-full p-2.5 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none text-sm" />
                      </div>
                      <div>
                        <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Address / Institution</label>
                        <input type="text" value={m2Address} onChange={(e) => setM2Address(e.target.value)}
                          className="w-full p-2.5 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none text-sm" />
                      </div>
                      <div>
                        <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Licence No / Case ID *</label>
                        <input type="text" value={m2LicenceNo} onChange={(e) => setM2LicenceNo(e.target.value)}
                          className="w-full p-2.5 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none text-sm" />
                      </div>
                      <div>
                        <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">SUGAM Ref / Form Type</label>
                        <input type="text" value={m2SugamRef} onChange={(e) => setM2SugamRef(e.target.value)}
                          className="w-full p-2.5 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none text-sm" />
                      </div>
                      <div>
                        <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Date (DD/MM/YYYY) *</label>
                        <input type="text" value={m2Date} onChange={(e) => setM2Date(e.target.value)}
                          placeholder="DD/MM/YYYY"
                          className="w-full p-2.5 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none text-sm" />
                      </div>
                      <div>
                        <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Inspectors / Officers / Chair *</label>
                        <input type="text" value={m2Inspectors} onChange={(e) => setM2Inspectors(e.target.value)}
                          className="w-full p-2.5 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none text-sm" />
                      </div>
                      <div>
                        <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Division</label>
                        <input type="text" value={m2Division} onChange={(e) => setM2Division(e.target.value)}
                          className="w-full p-2.5 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none text-sm" />
                      </div>
                      <div>
                        <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Deficiency / Severity</label>
                        <input type="text" value={m2Deficiency} onChange={(e) => setM2Deficiency(e.target.value)}
                          className="w-full p-2.5 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none text-sm" />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Module 2: Summary Sentences count */}
              {id === 'summarisation' && (
                <div className="flex items-center gap-3 pt-2">
                  <label className="text-sm font-bold text-slate-700">Summary sentences:</label>
                  <input
                    type="number"
                    min="1"
                    max="30"
                    value={m2SentenceCount}
                    onChange={(e) => setM2SentenceCount(e.target.value)}
                    className="w-16 p-2 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none text-sm text-center font-bold"
                  />
                </div>
              )}

              {/* Module 5: Field overrides + manual notes */}
              {id === 'inspection' && (
                <div className="pt-4 space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Firm / Site Name (override)</label>
                      <input type="text" value={m5FirmName} onChange={(e) => setM5FirmName(e.target.value)}
                        placeholder="Auto-detected from document"
                        className="w-full p-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none text-sm" />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">License Number (override)</label>
                      <input type="text" value={m5License} onChange={(e) => setM5License(e.target.value)}
                        placeholder="Auto-detected from document"
                        className="w-full p-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none text-sm" />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Inspection Date (override)</label>
                      <input type="text" value={m5Date} onChange={(e) => setM5Date(e.target.value)}
                        placeholder="DD/MM/YYYY"
                        className="w-full p-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none text-sm" />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">State (override)</label>
                      <input type="text" value={m5State} onChange={(e) => setM5State(e.target.value)}
                        placeholder="Auto-detected from document"
                        className="w-full p-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none text-sm" />
                    </div>
                  </div>
                  <div>
                    <label className="text-xs font-bold text-slate-500 uppercase mb-1 block">Additional Manual Notes (appended to extracted text)</label>
                    <textarea value={m5Notes} onChange={(e) => setM5Notes(e.target.value)}
                      placeholder="Type any additional observations or corrections here..."
                      className="w-full p-3 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none text-sm min-h-[80px] resize-y" />
                  </div>
                </div>
              )}

              {/* Text input for non-comparison modules (includes inspection for text-only mode) */}
              {id !== 'comparison' && (
                <div className="pt-4">
                  <div className="flex items-center gap-2 mb-2 text-sm font-bold text-slate-700">
                    <FileText className="w-4 h-4 text-blue-600" />
                    <span>{id === 'inspection' ? 'Paste Inspection Notes (alternative to file upload)' : 'Manual Text Input (Optional)'}</span>
                  </div>
                  <textarea
                    value={textInput}
                    onChange={(e) => setTextInput(e.target.value)}
                    placeholder={id === 'inspection'
                      ? 'Paste inspection notes, observations, or raw findings here if not uploading a file...'
                      : 'Paste your regulatory text here if not uploading a file...'}
                    className="w-full p-4 rounded-xl border border-slate-200 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all font-mono text-sm min-h-[120px] resize-y"
                  />
                </div>
              )}
            </section>

            {/* Section 2: Mode Selection (only for anonymisation) */}
            {id === 'anonymisation' && (
              <section className="space-y-4">
                <div className="flex items-center gap-2 text-slate-900 font-bold">
                  <span className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold">{stepNumber.mode}</span>
                  <h2>Select Anonymisation Method</h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* De-identification (Identifier Replacement) */}
                  <button
                    onClick={() => { setMode('de-identification'); setActiveButton('de-id'); }}
                    className={`p-5 rounded-xl border-2 text-left transition-all ${
                      mode === 'de-identification'
                        ? 'border-amber-500 bg-amber-50 shadow-md shadow-amber-100 ring-2 ring-amber-300'
                        : 'border-slate-200 hover:border-amber-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <div className={`p-2 rounded-lg ${mode === 'de-identification' ? 'bg-amber-100' : 'bg-slate-100'}`}>
                        <Unlock className={`w-5 h-5 ${mode === 'de-identification' ? 'text-amber-600' : 'text-slate-400'}`} />
                      </div>
                      <h4 className="font-bold text-slate-900">De-identification</h4>
                    </div>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      Replaces sensitive data with identifiers (e.g., Dr. Ninad &rarr; <code className="bg-amber-100 text-amber-700 px-1 rounded text-[10px]">[PERSON]</code>).
                      Each entity type gets a unique label. DPDP Act 2023 Section 2(b) compliant.
                    </p>
                    {/* Inline Legend */}
                    <div className="mt-3 pt-2 border-t border-slate-100 flex items-center gap-2 flex-wrap">
                      <span className="text-[9px] font-bold text-slate-400 uppercase">Legend:</span>
                      <span className="bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded text-[10px] font-semibold border border-amber-200">[PERSON]</span>
                      <span className="bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded text-[10px] font-semibold border border-amber-200">[PHONE]</span>
                      <span className="bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded text-[10px] font-semibold border border-amber-200">[ADDRESS]</span>
                    </div>
                  </button>

                  {/* Irreversible Anonymisation (Masking) */}
                  <button
                    onClick={() => { setMode('irreversible-anonymisation'); setActiveButton('irreversible'); }}
                    className={`p-5 rounded-xl border-2 text-left transition-all ${
                      mode === 'irreversible-anonymisation'
                        ? 'border-red-500 bg-red-50 shadow-md shadow-red-100 ring-2 ring-red-300'
                        : 'border-slate-200 hover:border-red-300 bg-white'
                    }`}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <div className={`p-2 rounded-lg ${mode === 'irreversible-anonymisation' ? 'bg-red-100' : 'bg-slate-100'}`}>
                        <Lock className={`w-5 h-5 ${mode === 'irreversible-anonymisation' ? 'text-red-600' : 'text-slate-400'}`} />
                      </div>
                      <h4 className="font-bold text-slate-900">Irreversible  (Masking)</h4>
                    </div>
                    <p className="text-xs text-slate-500 leading-relaxed">
                      Masks all sensitive data with asterisks (e.g., Dr. Ninad &rarr; <code className="bg-red-100 text-red-600 px-1 rounded text-[10px] font-mono">************</code>).
                      Original values are permanently irrecoverable. Suitable for public release.
                    </p>
                    {/* Inline Legend */}
                    <div className="mt-3 pt-2 border-t border-slate-100 flex items-center gap-2">
                      <span className="text-[9px] font-bold text-slate-400 uppercase">Legend:</span>
                      <span className="bg-red-100 text-red-600 px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold border border-red-200">************</span>
                      <span className="text-[10px] text-slate-400">= Fully masked</span>
                    </div>
                  </button>
                </div>
              </section>
            )}

            {/* Scan Detection Info Panel */}
            {(scanInfo || isDetecting || processingStatus) && (
              <section className="space-y-3">
                {isDetecting && (
                  <div className="flex items-center gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
                    <Loader2 className="w-5 h-5 text-amber-600 animate-spin" />
                    <span className="text-sm font-semibold text-amber-800">Detecting scanned vs digital pages...</span>
                  </div>
                )}
                {scanInfo && (
                  <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl space-y-3">
                    <div className="flex items-center gap-2 text-sm font-bold text-blue-900">
                      <FileText className="w-4 h-4 text-blue-600" />
                      Document Scan Analysis
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div className="bg-white rounded-lg p-3 border border-blue-100 text-center">
                        <div className="text-2xl font-black text-slate-800">{scanInfo.summary.total_files}</div>
                        <div className="text-[10px] font-semibold text-slate-500 uppercase">Total Files</div>
                      </div>
                      <div className="bg-white rounded-lg p-3 border border-green-100 text-center">
                        <div className="text-2xl font-black text-green-700">{scanInfo.summary.digital_files}</div>
                        <div className="text-[10px] font-semibold text-green-600 uppercase">Digital</div>
                      </div>
                      <div className="bg-white rounded-lg p-3 border border-amber-100 text-center">
                        <div className="text-2xl font-black text-amber-700">{scanInfo.summary.scanned_files}</div>
                        <div className="text-[10px] font-semibold text-amber-600 uppercase">Need OCR</div>
                      </div>
                      <div className="bg-white rounded-lg p-3 border border-slate-100 text-center">
                        <div className="text-2xl font-black text-slate-700">{scanInfo.summary.total_pages}</div>
                        <div className="text-[10px] font-semibold text-slate-500 uppercase">Total Pages</div>
                      </div>
                    </div>
                    {/* Per-file details */}
                    <div className="space-y-1">
                      {scanInfo.files.map((f, i) => (
                        <div key={i} className="flex items-center gap-2 text-xs">
                          <span className={`w-2 h-2 rounded-full ${f.is_scanned ? 'bg-amber-500' : 'bg-green-500'}`} />
                          <span className="font-semibold text-slate-700 truncate flex-1">{f.filename}</span>
                          <span className="text-slate-500">{f.page_count} pg</span>
                          <span className={`font-bold ${f.is_scanned ? 'text-amber-700' : 'text-green-700'}`}>
                            {f.is_scanned ? `${f.scanned_pages} scanned` : 'Digital'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {processingStatus && isProcessing && (
                  <div className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-xl">
                    <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
                    <span className="text-sm text-blue-800">{processingStatus}</span>
                  </div>
                )}
              </section>
            )}

            {/* Section: Process */}
            <section className="pt-4">
              <button
                onClick={handleRunAnalysis}
                disabled={isProcessing || isDetecting || (
                  id === 'comparison'
                    ? (m3Mode === 'comparison' ? selectedFiles.length < 2 : selectedFiles.length === 0)
                    : (selectedFiles.length === 0 && !textInput.trim())
                )}
                className={`
                  w-full md:w-auto px-12 py-4 rounded-2xl font-black text-lg flex items-center justify-center gap-3 transition-all
                  ${(isProcessing || isDetecting)
                    ? 'bg-blue-800 text-white cursor-wait shadow-lg shadow-blue-300'
                    : (id === 'comparison'
                        ? (m3Mode === 'comparison' ? selectedFiles.length < 2 : selectedFiles.length === 0)
                        : (selectedFiles.length === 0 && !textInput.trim()))
                      ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                      : activeButton === 'run'
                        ? 'bg-blue-800 text-white shadow-lg shadow-blue-300 ring-2 ring-blue-400'
                        : 'bg-blue-600 text-white hover:bg-blue-700 shadow-lg shadow-blue-200 active:scale-95'}
                `}
              >
                {isDetecting ? (
                  <>
                    <Loader2 className="w-6 h-6 animate-spin" />
                    Detecting Scanned Pages...
                  </>
                ) : isProcessing ? (
                  <>
                    <Loader2 className="w-6 h-6 animate-spin" />
                    Processing{scanInfo?.summary.scanned_files ? ` (OCR on ${scanInfo.summary.scanned_pages} pages)` : ''}...
                  </>
                ) : (
                  <>
                    <Play className="w-6 h-6 fill-current" />
                    Run Analysis
                  </>
                )}
              </button>
            </section>
          </motion.div>
        ) : (
          <div className="space-y-6">
            {/* Module 2: Tabs above results */}
            {id === 'summarisation' && (
              <div className="flex items-center gap-1 border-b border-slate-200">
                <button
                  onClick={() => setM2ResultTab('summary')}
                  className={`px-4 py-2.5 text-sm font-bold transition-colors border-b-2 ${
                    m2ResultTab === 'summary'
                      ? 'border-indigo-600 text-indigo-700'
                      : 'border-transparent text-slate-400 hover:text-slate-600'
                  }`}
                >
                  Summary
                </button>
                <button
                  onClick={() => setM2ResultTab('remark')}
                  className={`px-4 py-2.5 text-sm font-bold transition-colors border-b-2 ${
                    m2ResultTab === 'remark'
                      ? 'border-indigo-600 text-indigo-700'
                      : 'border-transparent text-slate-400 hover:text-slate-600'
                  }`}
                >
                  General Remark
                </button>
              </div>
            )}

            {/* Tab content */}
            {id === 'summarisation' && m2ResultTab === 'remark' ? (
              <motion.div
                key="remark-tab"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-4"
              >
                <div className="bg-white rounded-xl border border-slate-200 p-5">
                  <h4 className="text-sm font-bold text-slate-700 mb-3">General Remark / Observations</h4>
                  <textarea
                    value={m2GeneralRemark}
                    onChange={(e) => setM2GeneralRemark(e.target.value)}
                    placeholder="Add general remarks, overall observations, or additional notes about this document..."
                    className="w-full p-4 rounded-xl border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none text-sm min-h-[200px] resize-y"
                  />
                </div>
                <button
                  onClick={() => setM2ResultTab('summary')}
                  className="px-4 py-2 rounded-lg bg-indigo-100 hover:bg-indigo-200 text-indigo-700 text-sm font-bold transition-colors"
                >
                  Back to Summary
                </button>
              </motion.div>
            ) : (
              <ResultPanel
                result={result}
                moduleId={id || 'anonymisation'}
                onReset={handleReset}
                onBack={() => navigate('/')}
                onDownload={handleDownload}
                onMoveTo={handleMoveTo}
              />
            )}

            {/* Module 2: General Remark section always visible below summary */}
            {id === 'summarisation' && m2ResultTab === 'summary' && (
              <div className="bg-white rounded-xl border border-slate-200 p-5">
                <div className="flex items-center gap-2 mb-3">
                  <FileText className="w-4 h-4 text-indigo-600" />
                  <h4 className="text-sm font-bold text-slate-700">General Remark</h4>
                </div>
                <textarea
                  value={m2GeneralRemark}
                  onChange={(e) => setM2GeneralRemark(e.target.value)}
                  placeholder="Add general remarks or additional observations..."
                  className="w-full p-3 rounded-xl border border-slate-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 outline-none text-sm min-h-[100px] resize-y"
                />
              </div>
            )}
          </div>
        )}
      </AnimatePresence>

      {/* Document Preview Modal */}
      <AnimatePresence>
        {previewFile && (
          <DocumentPreview file={previewFile} onClose={() => setPreviewFile(null)} />
        )}
      </AnimatePresence>
    </div>
  );
}
