# Professional Note Organizer (DOCs ➜ OUTPUT)

This tool is built for your workflow:

- You place raw materials in `DOCs/`.
- Script organizes notes into professional sections.
- Script creates a downloadable run folder in `OUTPUT/`.
- Script also refreshes `OUTPUT/latest/` so you always know where to download from.
- Every output artifact is a **Word document (`.docx`)**, grouped by section folder.

## Run

```bash
python organize_notes_to_docx.py
```

Defaults:
- input folder: `DOCs/`
- output root: `OUTPUT/`

Optional:

```bash
python organize_notes_to_docx.py --docs-dir DOCs --output-root OUTPUT
```

## Output structure

For each run, the script creates:

- `OUTPUT/notes_export_YYYYMMDD_HHMMSS/`
  - one folder per section (e.g., `People_Management/`)
  - one Word file per section (e.g., `People_Management/People_Management.docx`)
- `OUTPUT/latest/`
  - copy of the newest run, for quick download

## Sections (professional taxonomy)

- People Management
- Compliance & Risk
- Wealth Management
- Investments & Markets
- Client Service
- Finance & Planning
- Operations & Admin
- Learning & Research
- General

## Logic quality rules

- Notes are deduplicated using normalized matching.
- Cleanup is intentionally light so original meaning remains intact.
- Dates (if present) are extracted and used for ordering.
- Similar topics are grouped into the same section document.

## Supported raw formats in DOCs

- `.txt`
- `.md`
- `.docx`
