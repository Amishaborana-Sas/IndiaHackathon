export interface ModuleInfo {
  id: string;
  title: string;
  description: string;
  icon: string;
  color: string;
}

// --------------------------------------------------------------------------- //
// Module 1 — Anonymisation
// --------------------------------------------------------------------------- //
export interface AnalysisResult {
  extractedText: string;
  processedText: string;
  entities: number;
  entitiesByType: Record<string, number>;
  time: string;
  fileType: string;
  isScanned: boolean;
  mode: string;
  ocrEngine?: string;
  filename?: string;
  handwrittenRegions?: number;
  totalPages?: number;
  pagesScanned?: number;
  pagesSkipped?: number;
}

export type InputType = 'pdf' | 'image' | 'scanned' | 'text';

export type AnonymisationMode = 'de-identification' | 'irreversible-anonymisation' | 'reversible-anonymisation';

// --------------------------------------------------------------------------- //
// Module 2 — Summarisation
// --------------------------------------------------------------------------- //
export interface SummarisationResult {
  summary: string;
  keyPoints: string[];
  wordCount: number;
  sentenceCount: number;
  algorithm: string;
  docType: string;
  processingTime: string;
  sections: Record<string, string>;
}

// --------------------------------------------------------------------------- //
// Module 3 — Completeness & Comparison
// --------------------------------------------------------------------------- //

// Which sub-mode the user chose inside Module 3
export type Module3Mode = 'completeness' | 'comparison';

// --- Completeness (single file upload) ---
export interface FieldFlag {
  field_id: string;
  field_label: string;
  status: 'ok' | 'missing' | 'invalid' | 'inconsistent' | 'warning';
  severity: 'critical' | 'major' | 'minor' | 'info';
  message: string;
  value: any;
  expected?: any;
  section?: string;
  record_index?: number;
}

export interface CompletenessResult {
  document_id: string;
  document_type: string;
  assessed_at: string;
  total_fields: number;
  complete_fields: number;
  missing_fields: number;
  invalid_fields: number;
  inconsistent_fields: number;
  completeness_score: number;        // 0–100
  flags: FieldFlag[];
  section_scores: Record<string, number>;
  summary: string;
}

// --- Comparison (two file upload) ---
export interface FieldChange {
  field_name: string;
  change_type: 'added' | 'deleted' | 'modified' | 'unchanged' | 'reordered';
  significance: 'critical' | 'substantive' | 'editorial' | 'no_change';
  old_value: any;
  new_value: any;
  description: string;
  record_id?: string;
  section?: string;
}

export interface ComparisonResult {
  comparison_id: string;
  document_type: string;
  version_a: string;
  version_b: string;
  compared_at: string;
  total_fields_compared: number;
  fields_changed: number;
  fields_added: number;
  fields_deleted: number;
  fields_unchanged: number;
  critical_changes: number;
  substantive_changes: number;
  editorial_changes: number;
  field_changes: FieldChange[];
  semantic_summary: string;
  summary: string;
  change_heatmap: Record<string, number>;
}

// Union for Module 3
export type Module3Result =
  | { mode: 'completeness'; data: CompletenessResult }
  | { mode: 'comparison'; data: ComparisonResult };

// --------------------------------------------------------------------------- //
// Module 4 — Classification
// --------------------------------------------------------------------------- //
export interface SubCategory {
  name: string;
  confidence: number;
}

export interface ClassificationResult {
  category: string;
  confidence: number;
  subCategories: SubCategory[];
  processingTime: string;
}

// --------------------------------------------------------------------------- //
// Module 5 — Inspection Report Generator
// --------------------------------------------------------------------------- //
export interface InspectionObservations {
  critical: string[];
  major: string[];
  minor: string[];
  compliant?: string[];
  pending?: string[];
  na?: string[];
  raw?: string;
}

export interface InspectionReportFile {
  name: string;
  path?: string;
  type?: string;
}

export interface InspectionResult {
  success: boolean;
  raw_text: string;
  doc_type: string;                // 'drug_manufacturing' | 'gcp_checklist'
  form_ref: string;
  parsed_data: Record<string, any>;  // firm_name, license_number, overall_rating, etc.
  observations: InspectionObservations;
  sections: string[];
  reports: Record<string, any>;     // generated report files info
  message: string;
}

// --------------------------------------------------------------------------- //
// Union type for all module results
// --------------------------------------------------------------------------- //
export type ModuleResult =
  | { type: 'anonymisation'; data: AnalysisResult }
  | { type: 'summarisation'; data: SummarisationResult }
  | { type: 'comparison'; data: Module3Result }
  | { type: 'classification'; data: ClassificationResult }
  | { type: 'inspection'; data: InspectionResult };

// --------------------------------------------------------------------------- //
// SAE Engine — Anonymization & De-Identification
// --------------------------------------------------------------------------- //
export type SAEMode = 'irreversible' | 'reversible';

export interface SAEEntity {
  entity_type: string;
  original_value: string;
  replacement: string;
  position: { start: number; end: number };
  confidence: number;
}

export interface SAEResult {
  processed_text: string;
  mode: SAEMode;
  num_entities: number;
  entities_by_type: Record<string, number>;
  entities: SAEEntity[];
  file_id: string;
  file_hash: string;
  timestamp: string;
  mapping_size: number;
  tracking: Record<string, any>;
  mapping_stored?: boolean;
  mapping_file_id?: string;
  encrypted_mapping?: Record<string, string>;
  processing_time_ms: number;
  // File upload extras
  filename?: string;
  source_type?: string;
  is_scanned?: boolean;
  extracted_text?: string;
}

export interface SAETracebackResult {
  success: boolean;
  file_id?: string;
  reconstructed_text?: string;
  mappings_applied?: number;
  error?: string;
}

export interface SAEDuplicateResult {
  is_duplicate: boolean;
  file_id: string;
  file_hash: string;
  filename?: string;
  first_seen?: string;
  process_count?: number;
  filenames?: string[];
}

// --------------------------------------------------------------------------- //
// OCR Progress tracking
// --------------------------------------------------------------------------- //
export interface OcrProgressEvent {
  page: number;
  total: number;
  elapsedMs: number;
  estimatedRemainingMs: number;
}

// --------------------------------------------------------------------------- //
// Vault info
// --------------------------------------------------------------------------- //
export interface VaultInfo {
  location: string;
  size: number;
  exists: boolean;
}
