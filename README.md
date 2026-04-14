# Notes Organizer (DOCs → OUTPUT)

Simple repository for one job: take raw notes from `DOCs/` and generate Word files grouped by topic in `OUTPUT/`.

## Repo structure

- `organize_notes_to_docx.py` — main script.
- `DOCs/` — your raw input files (`.txt`, `.md`, `.docx`).
- `OUTPUT/` — generated exports (timestamped folder + `latest/`).

## Run (rule-based mode)

```bash
python organize_notes_to_docx.py
```

## Run with ChatGPT/OpenAI enhancement (recommended)

```bash
export OPENAI_API_KEY="your_api_key_here"
python organize_notes_to_docx.py --use-openai --openai-model gpt-4.1-mini
```

> Important: ChatGPT web/app subscription is separate from API usage.
> To run model-assisted processing from this script, you need an OpenAI API key.

## Optional flags

```bash
python organize_notes_to_docx.py --docs-dir DOCs --output-root OUTPUT
```

## What gets generated

Each run creates:

- `OUTPUT/notes_export_YYYYMMDD_HHMMSS/`
  - one subfolder per section
  - one `.docx` file per section
  - `categorization_audit.csv` (original note, final note, category, duplicate merge count, AI mode)
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
- Applies light cleanup first.
- Supports AI-assisted professional rewrite + categorization when enabled.
- Extracts simple dates and sorts dated items first.
- Keeps all outputs in `.docx` format.
