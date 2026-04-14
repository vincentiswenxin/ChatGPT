# Notes Organizer (Immutable Knowledge-Base Workflow)

This repo now follows your required operating model:

1. Put raw notes in `DOCs/`.
2. Run processing in Codex.
3. Classify each note into topic/subtopic.
4. Grow a **knowledge base that never deletes prior outputs**.

## Core guarantees

- **No deletion of previous outputs**: every run creates timestamped snapshot files.
- **No overwrite requirement for history**: prior snapshots stay on disk.
- **Knowledge base growth over time**: new runs merge with latest index snapshot and add newly discovered notes.

---

## Run

```bash
python organize_notes_to_docx.py
```

Optional:

```bash
python organize_notes_to_docx.py --docs-dir DOCs --output-root OUTPUT
```

---

## Output layout

Every run creates two major areas:

### 1) Persistent knowledge base snapshots
- `OUTPUT/knowledge_base/topics/...`
  - Topic snapshots: `Topic__YYYYMMDD_HHMMSS.docx`
  - Subtopic snapshots: `Subtopic__YYYYMMDD_HHMMSS.docx`
- `OUTPUT/knowledge_base/index_snapshots/master_index__YYYYMMDD_HHMMSS.csv`

### 2) Per-run manifest
- `OUTPUT/runs/run_YYYYMMDD_HHMMSS/run_manifest.csv`

This means older output files are preserved and never removed by the script.

---

## Topic and subtopic taxonomy

Current deterministic taxonomy:

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

If a new theme appears that is not covered by current rules, it currently falls back to `General / General_Notes`.

---

## How growth works

On each run:

1. Script reads all input files from `DOCs/` (`.txt`, `.md`, `.docx`).
2. Cleans and deduplicates line notes.
3. Loads the latest master index snapshot from `OUTPUT/knowledge_base/index_snapshots/`.
4. Merges new notes into the knowledge base without duplicating existing note entries.
5. Writes new timestamped topic/subtopic `.docx` snapshots and new CSV snapshots.

---

## Important limitations (transparent)

- The CLI itself is deterministic/rule-based and does not directly invoke live model APIs.
- In Codex sessions, we can still iteratively improve taxonomy and structure based on your feedback.
- For true semantic rewriting with the model on every run, that must happen through an interactive Codex run (or a separate API-integrated mode).

---

## Practical usage for your workflow

When you upload more raw files into `DOCs/`:

1. Ask Codex to process them.
2. Codex runs the script and can also review/restructure taxonomy as needed.
3. New snapshot files are produced and old files remain preserved.
