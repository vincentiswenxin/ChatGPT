#!/usr/bin/env python3
"""Organize free-form notes into category-based Word documents.

Key behaviors:
- Accept a single file or a folder of note files
- Support .txt, .md, and .docx note inputs
- Deduplicate notes (exact and near-exact normalization)
- Lightly clean shorthand so notes are easier to read
- Categorize each note by topic
- Export one .docx file per topic/section (OneNote-friendly)
- Export an audit CSV so categorization remains transparent and editable

Examples:
  python organize_notes_to_docx.py --input sample_notes.txt --output-dir out_docs
  python organize_notes_to_docx.py --input DOCS --output-dir out_docs --first-only
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


@dataclass(frozen=True)
class CategoryRule:
    name: str
    keywords: tuple[str, ...]


CATEGORY_RULES: tuple[CategoryRule, ...] = (
    CategoryRule("Work & Career", ("meeting", "client", "deadline", "project", "team", "manager", "office", "stakeholder", "quarter", "kpi", "roadmap")),
    CategoryRule("Learning & Research", ("learn", "study", "course", "article", "tutorial", "research", "practice", "exam", "certificate", "textbook")),
    CategoryRule("Health & Wellness", ("doctor", "workout", "exercise", "gym", "sleep", "diet", "therapy", "meditation", "health", "checkup", "clinic", "walk")),
    CategoryRule("Finance", ("budget", "expense", "invoice", "bill", "tax", "investment", "salary", "bank", "saving", "debt")),
    CategoryRule("Personal & Family", ("family", "friend", "birthday", "home", "kids", "parent", "partner", "trip", "vacation", "call")),
    CategoryRule("Ideas & Brainstorming", ("idea", "brainstorm", "concept", "draft", "prototype", "vision", "could", "might", "explore")),
    CategoryRule("Operations & Admin", ("renew", "subscription", "appointment", "form", "document", "license", "schedule", "plan", "todo")),
)

SHORTHAND_MAP: tuple[Tuple[str, str], ...] = (
    (r"\bmtg\b", "meeting"),
    (r"\bw/\b", "with"),
    (r"\bw/o\b", "without"),
    (r"\bappt\b", "appointment"),
    (r"\bdocs\b", "documents"),
    (r"\bmins\b", "minutes"),
)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".docx"}

DOCX_CONTENT_TYPES = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
  <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>
  <Default Extension=\"xml\" ContentType=\"application/xml\"/>
  <Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>
</Types>
"""

DOCX_RELS = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>
</Relationships>
"""


def normalize_note(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[-*•]\s+", "", line)
    line = re.sub(r"^\d+[.)]\s+", "", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def clean_note_text(note: str) -> str:
    cleaned = note.strip()
    for pattern, replacement in SHORTHAND_MAP:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def dedupe_key(note: str) -> str:
    lowered = note.lower()
    lowered = re.sub(r"[^a-z0-9\s]", "", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def split_lines_to_notes(text: str) -> List[str]:
    notes: List[str] = []
    for raw in text.splitlines():
        note = normalize_note(raw)
        if note:
            notes.append(note)
    return notes


def load_notes_from_docx(path: Path) -> List[str]:
    with ZipFile(path, "r") as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")

    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return split_lines_to_notes(xml)


def load_notes_from_file(path: Path) -> List[str]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return split_lines_to_notes(path.read_text(encoding="utf-8"))
    if suffix == ".docx":
        return load_notes_from_docx(path)
    return []


def discover_input_files(input_path: Path, first_only: bool) -> List[Path]:
    if input_path.is_file():
        return [input_path]
    if not input_path.is_dir():
        raise SystemExit(f"Input path not found: {input_path}")

    candidates = sorted(
        p for p in input_path.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not candidates:
        raise SystemExit(
            f"No supported note files found in {input_path}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    return candidates[:1] if first_only else candidates


def deduplicate_and_clean(notes: List[str]) -> Tuple[List[str], Dict[str, int]]:
    seen: Dict[str, str] = {}
    duplicate_counts: Counter[str] = Counter()

    for note in notes:
        cleaned = clean_note_text(note)
        key = dedupe_key(cleaned)
        if not key:
            continue
        if key in seen:
            duplicate_counts[seen[key]] += 1
        else:
            seen[key] = cleaned
            duplicate_counts[cleaned] += 1

    unique_notes = list(seen.values())
    return unique_notes, dict(duplicate_counts)


def categorize_note(note: str) -> str:
    lowered = note.lower()
    scores: Dict[str, int] = {rule.name: 0 for rule in CATEGORY_RULES}

    for rule in CATEGORY_RULES:
        for kw in rule.keywords:
            if kw in lowered:
                scores[rule.name] += 1

    best_category = max(scores, key=scores.get)
    return best_category if scores[best_category] > 0 else "General / Unclassified"


def categorize_notes(notes: List[str]) -> Dict[str, List[str]]:
    categorized: Dict[str, List[str]] = {}
    for note in notes:
        category = categorize_note(note)
        categorized.setdefault(category, []).append(note)
    return categorized


def paragraph_xml(text: str, bold: bool = False) -> str:
    escaped = escape(text)
    run_props = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f"<w:p><w:r>{run_props}<w:t xml:space=\"preserve\">{escaped}</w:t></w:r></w:p>"


def build_document_xml(title: str, notes: List[str], duplicate_counts: Dict[str, int]) -> str:
    paragraphs: List[str] = [
        paragraph_xml(title, bold=True),
        paragraph_xml(f"Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"),
        paragraph_xml(f"Unique notes in section: {len(notes)}"),
        paragraph_xml(""),
    ]

    for idx, note in enumerate(notes, start=1):
        count = duplicate_counts.get(note, 1)
        suffix = f" (merged duplicates: {count - 1})" if count > 1 else ""
        paragraphs.append(paragraph_xml(f"{idx}. {note}{suffix}"))

    body = "".join(paragraphs)
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}<w:sectPr/></w:body></w:document>'''


def write_simple_docx(path: Path, document_xml: str) -> None:
    with ZipFile(path, mode="w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", DOCX_CONTENT_TYPES)
        zf.writestr("_rels/.rels", DOCX_RELS)
        zf.writestr("word/document.xml", document_xml)


def write_docx_per_category(categorized: Dict[str, List[str]], output_dir: Path, duplicate_counts: Dict[str, int]) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: List[Path] = []

    for category, notes in sorted(categorized.items()):
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", category).strip("_")
        out_path = output_dir / f"{safe_name}.docx"
        write_simple_docx(out_path, build_document_xml(category, notes, duplicate_counts))
        generated.append(out_path)

    return generated


def write_audit_csv(output_dir: Path, categorized: Dict[str, List[str]], duplicate_counts: Dict[str, int]) -> Path:
    path = output_dir / "categorization_audit.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "note", "merged_count"])
        for category, notes in sorted(categorized.items()):
            for note in notes:
                writer.writerow([category, note, duplicate_counts.get(note, 1)])
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Deduplicate, clean, categorize, and export notes into Word documents by topic.")
    parser.add_argument("--input", type=Path, default=Path("DOCS"), help="Input note file or directory (default: DOCS)")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory where category .docx files will be written")
    parser.add_argument("--first-only", action="store_true", help="When input is a directory, process only the first note file")
    args = parser.parse_args()

    files = discover_input_files(args.input, first_only=args.first_only)
    raw_notes: List[str] = []
    for file in files:
        file_notes = load_notes_from_file(file)
        if file_notes:
            raw_notes.extend(file_notes)

    if not raw_notes:
        raise SystemExit("No notes found in selected input files.")

    unique_notes, duplicate_counts = deduplicate_and_clean(raw_notes)
    categorized = categorize_notes(unique_notes)

    generated = write_docx_per_category(categorized, args.output_dir, duplicate_counts)
    audit_file = write_audit_csv(args.output_dir, categorized, duplicate_counts)

    print(f"Processed {len(files)} file(s):")
    for file in files:
        print(f" - {file}")
    print(f"Processed {len(raw_notes)} raw notes into {len(unique_notes)} unique notes across {len(generated)} Word documents.")
    print(f"Audit CSV: {audit_file}")
    for path in generated:
        print(f" - {path}")


if __name__ == "__main__":
    main()
