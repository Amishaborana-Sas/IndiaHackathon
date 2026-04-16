import {
  AnalysisResult,
  SummarisationResult,
  CompletenessResult,
  ComparisonResult,
  Module3Result,
  ClassificationResult,
  InspectionResult,
  ModuleResult,
  VaultInfo,
} from '../types';

const API_BASE = '/api';

// 15-minute timeout for large PDFs with OCR
const FETCH_TIMEOUT_MS = 15 * 60 * 1000;

function fetchWithTimeout(url: string, options: RequestInit = {}): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  return fetch(url, { ...options, signal: controller.signal }).finally(() => clearTimeout(timer));
}

// --------------------------------------------------------------------------- //
// Helper: map backend FileAnonymiseResponse -> frontend AnalysisResult
// --------------------------------------------------------------------------- //
function mapFileResponse(data: any): AnalysisResult {
  return {
    extractedText: data.extracted_text || '',
    processedText: data.anonymised_text || '',
    entities: data.num_entities || 0,
    entitiesByType: data.entities_by_type || {},
    time: `${Math.round(data.processing_time_ms || 0)} ms`,
    fileType: data.source_type || 'unknown',
    isScanned: data.is_scanned || false,
    mode: data.mode || '',
    ocrEngine: data.ocr_engine || undefined,
    filename: data.filename || undefined,
    handwrittenRegions: data.handwritten_regions || 0,
    totalPages: data.total_pages || 0,
    pagesScanned: data.pages_scanned || 0,
    pagesSkipped: data.pages_skipped || 0,
  };
}

function combineFileResults(results: any[]): AnalysisResult {
  if (!results || results.length === 0) {
    return { extractedText: '', processedText: '', entities: 0, entitiesByType: {}, time: '0 ms', fileType: 'unknown', isScanned: false, mode: '' };
  }
  if (results.length === 1) return mapFileResponse(results[0]);

  const combined: AnalysisResult = {
    extractedText: '', processedText: '', entities: 0, entitiesByType: {}, time: '0 ms',
    fileType: 'multiple', isScanned: results.some((r) => r.is_scanned), mode: results[0].mode || '', handwrittenRegions: 0,
  };
  let totalTime = 0;
  for (const r of results) {
    const sep = combined.extractedText ? `\n\n--- ${r.filename || 'File'} ---\n\n` : '';
    combined.extractedText += sep + (r.extracted_text || '');
    combined.processedText += sep + (r.anonymised_text || '');
    combined.entities += r.num_entities || 0;
    combined.handwrittenRegions = (combined.handwrittenRegions || 0) + (r.handwritten_regions || 0);
    totalTime += r.processing_time_ms || 0;
    for (const [k, v] of Object.entries(r.entities_by_type || {})) {
      combined.entitiesByType[k] = (combined.entitiesByType[k] || 0) + (v as number);
    }
  }
  combined.time = `${Math.round(totalTime)} ms`;
  return combined;
}

// --------------------------------------------------------------------------- //
// Module 1: Anonymisation
// --------------------------------------------------------------------------- //
async function analyzeAnonymisation(
  files: File[],
  mode: string,
  text?: string
): Promise<AnalysisResult> {
  try {
    // Text-only mode
    if (text && text.trim() && files.length === 0) {
      const res = await fetchWithTimeout(`${API_BASE}/anonymise/text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, mode }),
      });
      if (!res.ok) {
        const err = await res.text();
        throw new Error(`Server error (${res.status}): ${err}`);
      }
      const data = await res.json();
      return {
        extractedText: text,
        processedText: data.anonymised_text,
        entities: data.num_entities,
        entitiesByType: data.entities_by_type || {},
        time: `${Math.round(data.processing_time_ms || 0)} ms`,
        fileType: 'text/plain',
        isScanned: false,
        mode: data.mode,
      };
    }

    // Single file upload
    if (files.length === 1) {
      const formData = new FormData();
      formData.append('file', files[0]);
      const res = await fetchWithTimeout(`${API_BASE}/anonymise/file?mode=${encodeURIComponent(mode)}`, {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        const err = await res.text();
        throw new Error(`Server error (${res.status}): ${err}`);
      }
      const data = await res.json();
      return mapFileResponse(data);
    }

    // Multiple files
    const formData = new FormData();
    files.forEach((f) => formData.append('files', f));
    const res = await fetchWithTimeout(`${API_BASE}/anonymise/files?mode=${encodeURIComponent(mode)}`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Server error (${res.status}): ${err}`);
    }
    const data = await res.json();
    return combineFileResults(data.results);
  } catch (err: any) {
    if (err.name === 'AbortError') {
      throw new Error('Request timed out. Scanned PDFs with many pages take longer — try a smaller file or fewer pages.');
    }
    throw err;
  }
}

// --------------------------------------------------------------------------- //
// Module 2: Summarisation (real backend on port 8002)
// --------------------------------------------------------------------------- //
const M2_BASE = '/api/m2';  // -> port 8000 /m2 (mounted sub-app)

async function analyzeSummarisation(
  files: File[],
  text?: string,
): Promise<SummarisationResult> {
  // Text-only mode
  if (text && text.trim() && files.length === 0) {
    const res = await fetchWithTimeout(`${M2_BASE}/summarise/text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, doc_type: 'SUGAM / Inspection Data', sentence_count: 8 }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Module 2 error (${res.status})`);
    }
    const data = await res.json();
    return mapSummarisationResponse(data);
  }

  // File upload mode
  if (files.length === 0) {
    throw new Error('Please upload a document or paste text to summarise.');
  }

  const formData = new FormData();
  formData.append('file', files[0]);
  formData.append('doc_type', 'SUGAM / Inspection Data');
  formData.append('sentence_count', '8');

  const res = await fetchWithTimeout(`${M2_BASE}/summarise/file`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Module 2 error (${res.status})`);
  }
  const data = await res.json();
  return mapSummarisationResponse(data);
}

function mapSummarisationResponse(data: any): SummarisationResult {
  return {
    summary: data.summary || '',
    keyPoints: (data.key_points || []).map((p: string) => p.replace(/^[•\-]\s*/, '')),
    wordCount: data.word_count || 0,
    sentenceCount: data.sentence_count || 0,
    algorithm: data.algorithm || 'unknown',
    docType: data.doc_type || '',
    processingTime: `${Math.round(data.processing_time_ms || 0)} ms`,
    sections: data.sections || {},
  };
}

// --------------------------------------------------------------------------- //
// Module 3: Completeness & Comparison (real backend on port 8003)
// --------------------------------------------------------------------------- //
const M3_BASE = '/api/m3';  // -> port 8003/api/v1 via vite proxy

async function analyzeModule3(
  files: File[],
  m3Mode: string,
  text?: string,
): Promise<Module3Result> {
  if (m3Mode === 'comparison') {
    return analyzeModule3Comparison(files);
  }
  return analyzeModule3Completeness(files);
}

async function analyzeModule3Completeness(files: File[]): Promise<Module3Result> {
  if (files.length === 0) {
    throw new Error('Please upload a document for completeness assessment.');
  }

  const formData = new FormData();
  formData.append('file', files[0]);

  const res = await fetchWithTimeout(`${M3_BASE}/completeness/completeness/sae?report_type=initial`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Module 3 error (${res.status})`);
  }
  const data: CompletenessResult = await res.json();
  return { mode: 'completeness', data };
}

async function analyzeModule3Comparison(files: File[]): Promise<Module3Result> {
  if (files.length < 2) {
    throw new Error('Please upload exactly 2 files to compare.');
  }

  const formData = new FormData();
  formData.append('file_a', files[0]);
  formData.append('file_b', files[1]);

  const res = await fetchWithTimeout(`${M3_BASE}/comparison/comparison/structured`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Module 3 error (${res.status})`);
  }
  const data: ComparisonResult = await res.json();
  return { mode: 'comparison', data };
}

// --------------------------------------------------------------------------- //
// Module 4: Classification (SAE Severity — via /m4 mounted Module 4)
// --------------------------------------------------------------------------- //
const M4_BASE = '/api/m4';

async function analyzeClassification(
  files: File[],
  text?: string
): Promise<ClassificationResult> {
  // Text-only mode — send as SAE record JSON
  if (text && text.trim() && files.length === 0) {
    const res = await fetchWithTimeout(`${M4_BASE}/classify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ narrative: text, reaction: text, case_id: 'text_input' }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `Module 4 error (${res.status})`);
    }
    const data = await res.json();
    return mapClassificationResponse(data);
  }

  // File upload mode — use /classify/pdf
  if (files.length === 0) {
    throw new Error('Please upload an SAE report or paste text to classify.');
  }

  const formData = new FormData();
  formData.append('file', files[0]);
  const res = await fetchWithTimeout(`${M4_BASE}/classify/pdf`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Module 4 error (${res.status})`);
  }
  const data = await res.json();
  return mapClassificationResponse(data);
}

function mapClassificationResponse(data: any): ClassificationResult {
  // Module 4 returns: {case_id, severity_label, severity_confidence, severity_probabilities}
  const probs = data.severity_probabilities || {};
  return {
    category: data.severity_label || data.category || 'Unknown',
    confidence: data.severity_confidence || data.confidence || 0,
    subCategories: Object.entries(probs).map(([name, conf]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      confidence: conf as number,
    })),
    processingTime: `${Math.round(data.processing_time_ms || 0)} ms`,
  };
}

// --------------------------------------------------------------------------- //
// Module 5: Inspection Report Generator (Flask backend on port 5000)
// --------------------------------------------------------------------------- //
const M5_BASE = '/api/m5';  // -> port 8000 /m5 (mounted Flask via WSGI)

async function analyzeInspection(
  files: File[],
  text?: string,
  overrides?: { firm_name?: string; license_number?: string; inspection_date?: string; state?: string; manual_notes?: string },
): Promise<InspectionResult> {
  // Text-only mode (no file uploaded)
  if (files.length === 0 && text && text.trim()) {
    const res = await fetchWithTimeout(`${M5_BASE}/inspect-text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        firm_name: overrides?.firm_name || '',
        license_number: overrides?.license_number || '',
        inspection_date: overrides?.inspection_date || '',
        state: overrides?.state || '',
        manual_notes: overrides?.manual_notes || '',
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || err.error || `Module 5 error (${res.status})`);
    }
    const data = await res.json();
    return mapInspectionResponse(data);
  }

  if (files.length === 0) {
    throw new Error('Please upload a document or paste inspection text.');
  }

  const formData = new FormData();
  formData.append('file', files[0]);

  // Add field overrides
  if (overrides?.firm_name) formData.append('firm_name', overrides.firm_name);
  if (overrides?.license_number) formData.append('license_number', overrides.license_number);
  if (overrides?.inspection_date) formData.append('inspection_date', overrides.inspection_date);
  if (overrides?.state) formData.append('state', overrides.state);
  if (overrides?.manual_notes) formData.append('manual_notes', overrides.manual_notes);

  const res = await fetchWithTimeout(`${M5_BASE}/upload`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || err.error || `Module 5 error (${res.status})`);
  }
  const data = await res.json();
  return mapInspectionResponse(data);
}

function mapInspectionResponse(data: any): InspectionResult {
  return {
    success: data.success ?? true,
    raw_text: data.raw_text || '',
    doc_type: data.doc_type || data.parsed_data?.document_type || 'unknown',
    form_ref: data.form_ref || data.parsed_data?.form_reference || '',
    parsed_data: data.parsed_data || {},
    observations: data.observations || data.parsed_data?.observations || { critical: [], major: [], minor: [] },
    sections: data.sections || [],
    reports: data.reports || {},
    message: data.message || '',
  };
}

// --------------------------------------------------------------------------- //
// Main API: analyzeDocument (unified dispatcher)
// --------------------------------------------------------------------------- //
export const analyzeDocument = async (
  moduleId: string,
  files: File[],
  mode: string,
  text?: string,
  m5Overrides?: { firm_name?: string; license_number?: string; inspection_date?: string; state?: string; manual_notes?: string },
): Promise<ModuleResult> => {
  switch (moduleId) {
    case 'anonymisation': {
      const data = await analyzeAnonymisation(files, mode, text);
      return { type: 'anonymisation', data };
    }
    case 'summarisation': {
      const data = await analyzeSummarisation(files, text);
      return { type: 'summarisation', data };
    }
    case 'comparison': {
      // mode is 'completeness' or 'comparison' for Module 3
      const data = await analyzeModule3(files, mode, text);
      return { type: 'comparison', data };
    }
    case 'classification': {
      const data = await analyzeClassification(files, text);
      return { type: 'classification', data };
    }
    case 'inspection': {
      const data = await analyzeInspection(files, text, m5Overrides);
      return { type: 'inspection', data };
    }
    default:
      throw new Error(`Unknown module: ${moduleId}`);
  }
};

// --------------------------------------------------------------------------- //
// Download helpers
// --------------------------------------------------------------------------- //

function buildPlainText(result: ModuleResult, baseFilename: string): string {
  const divider = '='.repeat(70);
  if (result.type === 'anonymisation') {
    const r = result.data;
    const entityList = Object.entries(r.entitiesByType || {})
      .sort(([, a], [, b]) => b - a)
      .map(([type, count]) => `  - ${type}: ${count}`)
      .join('\n');
    return [
      divider, '  RegLens AI - ANONYMISATION REPORT',
      `  Generated: ${new Date().toLocaleString()}`, divider, '',
      `Source File:     ${baseFilename}`, `Mode:            ${r.mode}`,
      `Scanned Doc:     ${r.isScanned ? 'Yes (OCR applied)' : 'No (digital text)'}`,
      `Processing Time: ${r.time}`, `Entities Found:  ${r.entities}`, '',
      'BREAKDOWN OF MASKED ENTITY:', entityList || '  No entities detected', '',
      divider, '  ANONYMISED TEXT', divider, '', r.processedText || '(No output)', '',
      divider, '  END OF REPORT', divider,
    ].join('\n');
  } else if (result.type === 'summarisation') {
    const r = result.data;
    return [
      divider, '  RegLens AI - SUMMARISATION REPORT',
      `  Generated: ${new Date().toLocaleString()}`, divider, '',
      `Word Count: ${r.wordCount}`, `Processing Time: ${r.processingTime}`, '',
      'KEY POINTS:', ...r.keyPoints.map((p, i) => `  ${i + 1}. ${p}`), '',
      divider, '  SUMMARY', divider, '', r.summary, '', divider,
    ].join('\n');
  } else if (result.type === 'comparison') {
    const m3 = result.data;
    if (m3.mode === 'completeness') {
      const r = m3.data;
      return [
        divider, '  RegLens AI - COMPLETENESS REPORT',
        `  Generated: ${new Date().toLocaleString()}`, divider, '',
        `Document: ${r.document_id}`, `Type: ${r.document_type}`,
        `Score: ${r.completeness_score.toFixed(1)}%`,
        `Total Fields: ${r.total_fields}  |  Complete: ${r.complete_fields}  |  Missing: ${r.missing_fields}`, '',
        'FLAGS:', ...r.flags.map((f: any) => `  [${f.severity.toUpperCase()}] ${f.field_label} (${f.status}): ${f.message}`), '',
        r.summary, '', divider,
      ].join('\n');
    } else {
      const r = m3.data;
      return [
        divider, '  RegLens AI - COMPARISON REPORT',
        `  Generated: ${new Date().toLocaleString()}`, divider, '',
        `Version A: ${r.version_a}`, `Version B: ${r.version_b}`,
        `Fields Compared: ${r.total_fields_compared}  |  Changed: ${r.fields_changed}`, '',
        r.summary, '', 'FIELD CHANGES:',
        ...r.field_changes.map((c: any) => `  [${c.significance.toUpperCase()}] ${c.field_name}: ${c.description}`), '',
        divider,
      ].join('\n');
    }
  } else if (result.type === 'classification') {
    const r = result.data;
    return [
      divider, '  RegLens AI - CLASSIFICATION REPORT',
      `  Generated: ${new Date().toLocaleString()}`, divider, '',
      `Category: ${r.category}`, `Confidence: ${(r.confidence * 100).toFixed(1)}%`, '',
      'SUB-CATEGORIES:', ...r.subCategories.map((s) => `  - ${s.name} (${(s.confidence * 100).toFixed(1)}%)`), '',
      divider,
    ].join('\n');
  } else {
    const r = result.data as any;
    const obs = r.observations || {};
    return [
      divider, '  RegLens AI - INSPECTION REPORT',
      `  Generated: ${new Date().toLocaleString()}`, divider, '',
      `Document Type: ${r.doc_type}`, `Form Reference: ${r.form_ref}`,
      `Firm: ${r.parsed_data?.firm_name || 'N/A'}`, '',
      'CRITICAL:', ...(obs.critical || []).map((o: string) => `  - ${o}`), '',
      'MAJOR:', ...(obs.major || []).map((o: string) => `  - ${o}`), '',
      'MINOR:', ...(obs.minor || []).map((o: string) => `  - ${o}`), '',
      divider,
    ].join('\n');
  }
}

function buildCsv(result: ModuleResult): string {
  if (result.type === 'anonymisation') {
    const r = result.data;
    const rows = [['Entity Type', 'Count']];
    for (const [type, count] of Object.entries(r.entitiesByType || {})) {
      rows.push([type, String(count)]);
    }
    rows.push([], ['Mode', r.mode], ['Processing Time', r.time], ['Entities Found', String(r.entities)]);
    return rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
  } else if (result.type === 'summarisation') {
    const r = result.data;
    const rows = [['Field', 'Value'], ['Summary', r.summary], ['Word Count', String(r.wordCount)],
      ['Algorithm', r.algorithm], ['Processing Time', r.processingTime]];
    r.keyPoints.forEach((p, i) => rows.push([`Key Point ${i + 1}`, p]));
    return rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
  } else if (result.type === 'comparison') {
    const m3 = result.data;
    if (m3.mode === 'completeness') {
      const r = m3.data;
      const rows = [['Field', 'Message']];
      r.flags.forEach((f: any) => rows.push([f.field_label, f.message]));
      return rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
    } else {
      const r = m3.data;
      const v1 = r.version_a || 'V1';
      const v2 = r.version_b || 'V2';
      const rows = [['Field', v1, v2]];
      r.field_changes.forEach((c: any) => rows.push([c.field_name, String(c.old_value || ''), String(c.new_value || '')]));
      return rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
    }
  } else if (result.type === 'classification') {
    const r = result.data;
    const rows = [['Field', 'Value'], ['Category', r.category], ['Confidence', String((r.confidence * 100).toFixed(1)) + '%'],
      ['Processing Time', r.processingTime]];
    r.subCategories.forEach((s, i) => rows.push([`Sub-Category ${i + 1}`, `${s.name} (${(s.confidence * 100).toFixed(1)}%)`]));
    return rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
  } else if (result.type === 'inspection') {
    const r = result.data as any;
    const obs = r.observations || {};
    const rows = [['Severity', 'Observation']];
    (obs.critical || []).forEach((o: string) => rows.push(['Critical', o]));
    (obs.major || []).forEach((o: string) => rows.push(['Major', o]));
    (obs.minor || []).forEach((o: string) => rows.push(['Minor', o]));
    rows.push([], ['Field', 'Value'], ['Document Type', r.doc_type], ['Form Reference', r.form_ref],
      ['Firm', r.parsed_data?.firm_name || 'N/A']);
    return rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
  }
  return `"Field","Value"\n"Type","${result.type}"\n"Data","${JSON.stringify(result.data).replace(/"/g, '""')}"`;
}

async function downloadAsPdf(result: ModuleResult, baseFilename: string) {
  const { jsPDF } = await import('jspdf');
  const doc = new jsPDF();
  const text = buildPlainText(result, baseFilename);
  const lines = doc.splitTextToSize(text, 180);
  let y = 15;
  for (const line of lines) {
    if (y > 280) { doc.addPage(); y = 15; }
    doc.setFontSize(9);
    doc.text(line, 15, y);
    y += 5;
  }
  doc.save(baseFilename.replace(/\.\w+$/, '') + `_${result.type}.pdf`);
}

async function downloadAsDocx(result: ModuleResult, baseFilename: string) {
  const { Document, Packer, Paragraph, TextRun, HeadingLevel } = await import('docx');
  const text = buildPlainText(result, baseFilename);
  const paragraphs = text.split('\n').map(line => {
    if (line.startsWith('===')) {
      return new Paragraph({ children: [] });
    }
    const isHeading = line.trim().startsWith('RegLens AI') || /^[A-Z ]{5,}:$/.test(line);
    return new Paragraph({
      heading: isHeading ? HeadingLevel.HEADING_2 : undefined,
      children: [new TextRun({ text: line, size: isHeading ? 24 : 20, bold: !!isHeading })],
    });
  });
  const docFile = new Document({ sections: [{ children: paragraphs }] });
  const blob = await Packer.toBlob(docFile);
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = baseFilename.replace(/\.\w+$/, '') + `_${result.type}.docx`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function triggerDownload(content: string, mimeType: string, filename: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export const downloadResult = (
  result: ModuleResult,
  format: 'txt' | 'json' | 'csv' | 'pdf' | 'docx',
  baseFilename: string
) => {
  const stem = baseFilename.replace(/\.\w+$/, '') + `_${result.type}`;

  if (format === 'json') {
    triggerDownload(JSON.stringify(result, null, 2), 'application/json', `${stem}.json`);
  } else if (format === 'csv') {
    triggerDownload(buildCsv(result), 'text/csv', `${stem}.csv`);
  } else if (format === 'pdf') {
    downloadAsPdf(result, baseFilename);
  } else if (format === 'docx') {
    downloadAsDocx(result, baseFilename);
  } else {
    triggerDownload(buildPlainText(result, baseFilename), 'text/plain', `${stem}.txt`);
  }
};

// --------------------------------------------------------------------------- //
// Vault info
// --------------------------------------------------------------------------- //
export const fetchVaultInfo = async (): Promise<VaultInfo | null> => {
  try {
    const res = await fetch(`${API_BASE}/vault/info`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
};

// --------------------------------------------------------------------------- //
// Module 5: Report listing + download URLs
// --------------------------------------------------------------------------- //
export const fetchM5Reports = async (): Promise<any[]> => {
  try {
    const res = await fetch(`${M5_BASE}/reports`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.files || [];
  } catch {
    return [];
  }
};

export const getM5ReportDownloadUrl = (filename: string) => `${M5_BASE}/reports/${encodeURIComponent(filename)}`;
export const getM5ReportPreviewUrl = (filename: string) => `${M5_BASE}/preview/${encodeURIComponent(filename)}`;

// --------------------------------------------------------------------------- //
// Health checks
// --------------------------------------------------------------------------- //
export const checkHealth = async (): Promise<{ status: string; ocr_engine: string } | null> => {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
};

// --------------------------------------------------------------------------- //
// Scan Detection (Phase 1 — classify files as scanned vs digital)
// --------------------------------------------------------------------------- //
export interface ScanFileInfo {
  filename: string;
  size_bytes: number;
  is_scanned: boolean;
  needs_ocr: boolean;
  page_count: number;
  digital_pages: number;
  scanned_pages: number;
}

export interface ScanDetectResult {
  files: ScanFileInfo[];
  summary: {
    total_files: number;
    scanned_files: number;
    digital_files: number;
    total_pages: number;
    scanned_pages: number;
    digital_pages: number;
  };
}

export const scanDetectFiles = async (files: File[]): Promise<ScanDetectResult> => {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  const res = await fetchWithTimeout(`${API_BASE}/scan-detect`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    throw new Error(`Scan detection failed (${res.status})`);
  }
  return res.json();
};

export const checkOcrHealth = async (): Promise<{ status: string; easyocr: boolean; pymupdf: boolean } | null> => {
  try {
    const res = await fetch('/api/ocr/health');
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
};

// --------------------------------------------------------------------------- //
// SAE Engine — Anonymization & De-Identification
// --------------------------------------------------------------------------- //
import type { SAEResult, SAETracebackResult, SAEDuplicateResult } from '../types';

export const saeAnonymizeText = async (
  text: string,
  mode: 'irreversible' | 'reversible',
  filename: string = 'unknown',
): Promise<SAEResult> => {
  const res = await fetchWithTimeout(`${API_BASE}/sae/anonymize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, mode, filename }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`SAE engine error (${res.status}): ${err}`);
  }
  return res.json();
};

export const saeAnonymizeFile = async (
  file: File,
  mode: 'irreversible' | 'reversible',
): Promise<SAEResult> => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetchWithTimeout(
    `${API_BASE}/sae/file?mode=${encodeURIComponent(mode)}`,
    { method: 'POST', body: formData },
  );
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`SAE engine error (${res.status}): ${err}`);
  }
  return res.json();
};

export const saeTraceback = async (
  fileId: string,
  anonymizedText: string,
): Promise<SAETracebackResult> => {
  const res = await fetchWithTimeout(`${API_BASE}/sae/traceback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_id: fileId, anonymized_text: anonymizedText }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`SAE traceback error (${res.status}): ${err}`);
  }
  return res.json();
};

export const saeCheckDuplicateFile = async (
  file: File,
): Promise<SAEDuplicateResult> => {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetchWithTimeout(`${API_BASE}/sae/check-duplicate`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`SAE duplicate check error (${res.status}): ${err}`);
  }
  return res.json();
};

export const saeCheckDuplicateText = async (
  text: string,
): Promise<SAEDuplicateResult> => {
  const res = await fetchWithTimeout(`${API_BASE}/sae/check-duplicate-text`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`SAE duplicate check error (${res.status}): ${err}`);
  }
  return res.json();
};

export const lookupToken = async (
  fileId: string,
  token: string,
): Promise<{ found: boolean; token: string; original_value?: string; file_id: string }> => {
  const res = await fetchWithTimeout(`${API_BASE}/sae/lookup-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_id: fileId, token }),
  });
  if (!res.ok) throw new Error('Token lookup failed');
  return res.json();
};
