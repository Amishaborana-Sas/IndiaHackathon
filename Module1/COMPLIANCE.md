# Compliance Notes — Module 1 Anonymisation

**Scope:** this document describes what Module 1 does, which provisions of
which frameworks it is built to align with, and — equally important — what
it does **not** do. It is an engineering document, not a legal opinion.
No software can by itself make an organisation compliant with DPDP, NDHM,
ICMR or CDSCO requirements; compliance is an organisational property that
depends on processes, contracts, access control, training, and audit.

---

## 1. What Module 1 implements

### 1.1 Detection layer
A hybrid detector runs over every input:

- **Rule-based (regex):** Aadhaar, PAN, IFSC, Indian passport, Indian phone
  (+91), MRN, CDSCO file IDs, IND/drug trial IDs, email, URL, IP address,
  credit card, ISO and common date formats.
- **NLP layer (optional):** Microsoft Presidio + spaCy `en_core_web_lg`
  for `PERSON`, `LOCATION`, `ORGANIZATION`, `NRP` in free text. The
  pipeline runs without it; installing it only adds recall.

Overlapping detections are resolved by keeping the highest-score, longest
span.

### 1.2 Two processing options exposed to the user

The interactive pipeline offers a clean binary choice:

| Menu option | Internal mode | Traceable? | Output shape |
|---|---|---|---|
| 1. De-identification | `mask` | No — nothing is written to the vault | Asterisks, length preserved, email domain / PAN suffix kept for audit |
| 2. Irreversible anonymisation | `generalise` | No | Category labels: `[PERSON]`, `[PHONE]`, `INDIA`, `YYYY-XX-XX`, `[REDACTED]` |

Both options produce output from which the original identifiers cannot be
reasonably recovered by the holder of the masked document alone.

Two additional modes (`pseudonymise`, `two_step`) are available through
the REST API and the `--mode` flag. They **do** write to the encrypted
vault and are reversible by the key holder; they are intentionally not
exposed in the interactive menu because their threat model (insider with
vault access) is very different.

### 1.3 Vault (only used by pseudonymise / two_step modes)
- SQLite file, rows encrypted with Fernet (AES-128-CBC + HMAC-SHA256).
- Key material in `vault.key` for demo; production deployments MUST
  source it from a KMS and rotate it.
- Tokens are HMAC-SHA256 truncated to 96 bits, keyed by a secret separate
  from the vault key, so the two can be held by different roles.

### 1.4 OCR and ingestion
Images, scanned PDFs, DOCX, XLSX, CSV, JSON, HTML and plain text are all
routed through a single `ingest()` function. OCR uses EasyOCR or PaddleOCR
(configurable); Tesseract is not required. Structured rows (CSV, XLSX,
JSON) are anonymised cell-by-cell so column structure is preserved for
downstream analytics.

---

## 2. Framework alignment (claims the code can support)

### 2.1 DPDP Act 2023 (India)
- **§2(b) "de-identification":** option 1 (mask) replaces identifiers
  with asterisks and stores no mapping. The resulting output cannot, on
  its own, reasonably identify the Data Principal. This matches the
  statutory definition.
- **§4 and §6 (lawful processing, consent and purpose limitation):**
  supported operationally, not technically. Module 1 does not record
  consent; the calling system must.
- **§8(5) (reasonable security safeguards):** the vault uses
  authenticated encryption at rest and a secret separate from the
  HMAC key. Key rotation is the operator's responsibility.
- **§8(7) (erasure / retention):** the pipeline writes artifacts to
  `Module1/outputs/`. Retention and deletion policies are out of scope
  for Module 1 and must be enforced by the calling system.
- **§10 (Significant Data Fiduciary obligations):** DPIA, DPO, audit —
  these are organisational, not code-level. Module 1 produces audit-
  usable artifacts (JSON records of what was detected and replaced)
  that can feed a DPIA, but does not itself perform one.

### 2.2 NDHM / ABDM Health Data Management Policy
- Entity categories for PHI (MRN, patient name, contact, Aadhaar,
  hospital name) are detected.
- The policy's distinction between de-identified and anonymised data
  is reflected in the two menu options: option 1 = de-identified,
  option 2 = anonymised.
- Module 1 does not implement ABHA number handling, consent artefacts,
  or the Health Information Exchange (HIE-CM) flow. These belong to
  a separate system.

### 2.3 ICMR Ethical Guidelines for Biomedical Research (2017)
- Supports the requirement that identifiable data be removed from
  datasets shared outside the primary research team. Option 2
  (generalise) is appropriate for research data release; option 1
  (mask) is appropriate for internal review where shape preservation
  helps clinicians verify a record is the right one.
- Does not implement ethics committee workflow, informed consent
  tracking, or benefit-sharing.

### 2.4 CDSCO guidelines
- Detects CDSCO file numbers and IND trial identifiers by pattern.
- Produces a JSON artifact per document with detected entity counts,
  mode used, timestamp, and source metadata — suitable as input to a
  regulatory-review audit trail.
- **Does not** "streamline" or "accelerate" CDSCO approval in any
  regulatory sense. Approval timelines are a function of the review
  process, not the anonymisation of supporting documents. Any claim
  to the contrary would be marketing, not engineering.

---

## 3. What Module 1 does NOT do

- **Does not guarantee k-anonymity or differential privacy.** An optional
  `k_anonymity` metric over quasi-identifier columns is reported for
  tabular inputs, but the pipeline does not enforce a minimum k and does
  not suppress rows to reach one. A dataset passed through option 2 can
  still be re-identifiable via linkage if quasi-identifiers (age, ZIP,
  gender, admission date) are present.
- **Does not defend against a vault-holder insider attack** in
  pseudonymise/two_step modes. Anyone with the vault key and the HMAC
  secret can reverse tokens by design. Split the roles.
- **Does not detect every identifier.** Free-text detection depends on
  the NER model. Unusual names, transliterated names, handwriting, and
  adversarial inputs will leak. Treat this as a first-pass filter, not
  a guarantee.
- **Does not handle consent, retention, access control, audit logging
  of re-identification, breach notification, or DPO workflows.** Those
  are system-level and must be layered on top.
- **Does not certify compliance.** Only a qualified DPO / legal reviewer
  can do that, on a system-wide basis, with reference to the specific
  deployment.

---

## 4. Operator checklist before deployment

1. Rotate `vault.key` and the `ANON_HMAC_SECRET` environment variable
   away from the demo defaults. Source both from a KMS.
2. Put the `/vault/reveal` endpoint behind authn/authz with per-call
   audit logging. The demo has neither.
3. Decide a retention policy for `Module1/outputs/` and enforce it
   outside this service.
4. Run option 1 (mask) for internal clinician / reviewer access.
   Run option 2 (generalise) for anything that leaves the organisation.
5. If you release tabular data, set `quasi_identifiers` and verify
   `k_anonymity >= 5` (or your chosen threshold) before release.
   Suppress rows manually if the metric is lower.
6. Do not represent to any regulator or user that this module, by
   itself, makes the operator DPDP / NDHM / ICMR / CDSCO compliant.
