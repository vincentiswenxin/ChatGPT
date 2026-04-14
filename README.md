# Notes Organizer (DOCs → OUTPUT)

Simple repository for one job: take raw notes from `DOCs/` and generate Word files grouped by topic in `OUTPUT/`.

## Repo structure

- `organize_notes_to_docx.py` — main script.
- `DOCs/` — your raw input files (`.txt`, `.md`, `.docx`).
- `OUTPUT/` — generated exports (timestamped folder + `latest/`).

## Run

```bash
python organize_notes_to_docx.py
```

Optional:

```bash
python organize_notes_to_docx.py --docs-dir DOCs --output-root OUTPUT
```

## What gets generated

Each run creates:

- `OUTPUT/notes_export_YYYYMMDD_HHMMSS/`
  - one subfolder per section
  - one `.docx` file per section
  - `categorization_audit.csv` (section mapping + duplicate merge count)
- `OUTPUT/latest/`
  - mirror of the newest run for easy download

## Categories

- People Management
- Compliance & Risk
- Wealth Management
- Investments & Markets
- Client Service
- Finance & Planning
- Operations & Admin
- Learning & Research
- General (fallback)

## Notes

- Deduplicates similar lines.
- Applies light cleanup (preserves original meaning).
- Extracts simple dates and sorts dated items first.
- Keeps all outputs in `.docx` format.
