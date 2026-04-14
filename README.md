# Note Organizer to Word Documents

This project helps you turn long-running notes into **separate Word files by topic**, ready to upload into OneNote.

## What this version improves

- Removes duplicates (including near-duplicates after normalization).
- Lightly cleans shorthand (example: `mtg` → `meeting`) so notes read clearly.
- Categorizes notes into topic sections using transparent keyword rules.
- Writes one `.docx` file per section/topic.
- Writes an `categorization_audit.csv` report so you can verify accuracy.

## Categories included

- Work & Career
- Learning & Research
- Health & Wellness
- Finance
- Personal & Family
- Ideas & Brainstorming
- Operations & Admin
- General / Unclassified

## Quick start

No external Python packages are required.

```bash
python organize_notes_to_docx.py --input sample_notes.txt --output-dir output_docs
```

## Input format

- Plain text file.
- One note per line.
- Empty lines ignored.
- Bullets (`-`, `*`, numbered lists) are cleaned automatically.

## Output

In `output_docs/`, the script creates:

- One `.docx` file per category/topic.
- `categorization_audit.csv` containing:
  - category
  - note text (after light cleanup)
  - merged duplicate count

## Accuracy and control

- The script does **light cleanup only** to avoid changing meaning.
- Categorization is rule-based and editable in `CATEGORY_RULES`.
- Use `categorization_audit.csv` as a final review list before importing into OneNote.
