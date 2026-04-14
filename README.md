# Notes Organizer (Codex-first Workflow)

This repository is built for your exact process:

1. You drop raw notes into `DOCs/`.
2. We run processing inside this Codex environment.
3. Notes are cleaned, deduplicated, categorized, and exported into Word files.
4. New notes are merged into the existing knowledge base so organization improves over time.

No API key is required for this workflow.

---

## Repository Structure

- `organize_notes_to_docx.py`  
  Main script for note ingestion, cleanup, categorization, and Word export.
- `DOCs/`  
  Input folder for your raw source notes (`.txt`, `.md`, `.docx`).
- `OUTPUT/`  
  Generated exports. The latest run is always mirrored to `OUTPUT/latest/`.

---

## How to Run

```bash
python organize_notes_to_docx.py
```

Optional:

```bash
python organize_notes_to_docx.py --docs-dir DOCs --output-root OUTPUT
```

---

## What the Script Does

### 1) Ingests notes from `DOCs/`
Supported formats:
- `.txt`
- `.md`
- `.docx`

### 2) Cleans and deduplicates
- Normalizes list prefixes and spacing.
- Expands common shorthand (`mtg` → `meeting`, etc.).
- Deduplicates semantically similar lines using normalized keys.

### 3) Classifies into Topic → Subtopic
Deterministic taxonomy (keyword-based), currently including:

- **Training Notes**
  - Leadership_Training
  - Compliance_Training
  - Product_Training
  - Process_Training
- **Client & Wealth**
  - Client_Reviews
  - Portfolio_Planning
  - Market_View
- **Finance & Operations**
  - Budgeting
  - Operations
  - Risk_Controls
- **General**
  - General_Notes

### 4) Merges with prior knowledge
If `OUTPUT/latest/search_index.csv` exists, previously organized notes are loaded and merged with new notes.

### 5) Exports Word documents and indexes
Each run creates:

- `OUTPUT/notes_export_YYYYMMDD_HHMMSS/`
  - Topic master docs (`Topic/Topic.docx`)
  - Subtopic docs (`Topic/Subtopic/Subtopic.docx`)
  - `categorization_audit.csv`
  - `search_index.csv`
- `OUTPUT/latest/`
  - Fresh mirror of the newest run for easy download.

---

## Output Files Explained

### `categorization_audit.csv`
Audit trail containing:
- topic
- subtopic
- final_note
- duplicates_merged
- source (`historical` or `current_run`)

### `search_index.csv`
Search helper containing:
- topic
- subtopic
- final_note
- path_hint (where note lives in output docs)

---

## Ongoing Usage Pattern

When you provide more notes in future:
1. Add files to `DOCs/`
2. Run the script
3. Download from `OUTPUT/latest/`

This keeps your training notes and related topics continuously organized and searchable.

---

## Notes About Codex + Model Usage

- This repository script is deterministic and does not call external APIs.
- In Codex sessions, we can still iteratively improve taxonomy and structure based on your feedback.
- If you want deeper semantic rewriting in the future, we can add an optional model-assisted mode again, but the current default is API-key-free.
