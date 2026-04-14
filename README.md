# Note Organizer to Word Documents

This project turns raw notes into **separate Word files by topic**, ready for OneNote upload.

## What it does

- Supports note input from a **single file** or a **folder**.
- Supports `.txt`, `.md`, and `.docx` note files.
- Removes exact/near duplicates.
- Applies light shorthand cleanup (for readability only).
- Categorizes notes by topic using transparent rules.
- Exports one `.docx` file per topic.
- Generates `categorization_audit.csv` for verification.

## Quick start

### Process the first note file in `DOCS/`

```bash
python organize_notes_to_docx.py --output-dir output_docs --first-only
```

### Process all files in `DOCS/`

```bash
python organize_notes_to_docx.py --output-dir output_docs
```

### Process a specific file

```bash
python organize_notes_to_docx.py --input sample_notes.txt --output-dir output_docs
```

## Input behavior

- `--input` defaults to `DOCS`.
- If input is a directory:
  - `--first-only` processes only the first supported file (sorted by filename).
  - without `--first-only`, all supported files are processed.

## Output

In `output_docs/`, the script creates:

- one `.docx` file per category/topic
- `categorization_audit.csv` with:
  - category
  - cleaned note text
  - merged duplicate count

## Accuracy control

- Cleanup is intentionally light to avoid changing note meaning.
- Category logic is editable in `CATEGORY_RULES`.
- Use `categorization_audit.csv` as your final review list before import.
