# Notes Organizer (Codex workflow, no API keys)

This repo is now designed for your requested workflow:

- Raw files go into `DOCs/`.
- Processing runs in this Codex environment.
- Notes are organized into **Topic → Subtopic** and exported as Word files.
- New runs keep building on prior knowledge from `OUTPUT/latest/search_index.csv`.

## Run

```bash
python organize_notes_to_docx.py
```

Optional:

```bash
python organize_notes_to_docx.py --docs-dir DOCs --output-root OUTPUT
```

## Output structure

Each run creates:

- `OUTPUT/notes_export_YYYYMMDD_HHMMSS/`
  - topic master docs: `Topic/Topic.docx`
  - subtopic docs: `Topic/Subtopic/Subtopic.docx`
  - `categorization_audit.csv`
  - `search_index.csv`
- `OUTPUT/latest/`
  - mirror of newest run (easy download path)

## Taxonomy

Current taxonomy includes:

- `Training Notes`
  - `Leadership_Training`
  - `Compliance_Training`
  - `Product_Training`
  - `Process_Training`
- `Client & Wealth`
  - `Client_Reviews`
  - `Portfolio_Planning`
  - `Market_View`
- `Finance & Operations`
  - `Budgeting`
  - `Operations`
  - `Risk_Controls`
- `General`
  - `General_Notes`

## Important clarification

This script does **not** require OpenAI API keys.
The note processing here runs in Codex via this repo workflow and deterministic taxonomy rules.
