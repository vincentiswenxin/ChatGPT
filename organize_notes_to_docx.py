#!/usr/bin/env python3
"""Organize notes from DOCs/ into section-based Word documents.

Default workflow:
- Read raw materials from DOCs/
- Clean + deduplicate notes
- Categorize into professional sections (management, compliance, finance, etc.)
- Create a downloadable output folder with one Word document per section
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile
import shutil


@dataclass(frozen=True)
class CategoryRule:
    name: str
    keywords: tuple[str, ...]


CATEGORY_RULES: tuple[CategoryRule, ...] = (
    CategoryRule("People Management", ("manager", "leadership", "1:1", "one on one", "hiring", "coach", "feedback", "promotion", "performance", "team")),
    CategoryRule("Compliance & Risk", ("compliance", "regulation", "regulatory", "sec", "finra", "kyc", "aml", "risk", "policy", "audit", "control", "breach")),
    CategoryRule("Wealth Management", ("portfolio", "allocation", "asset mix", "advisor", "client objective", "retirement", "estate", "trust", "wealth", "tax efficiency")),
    CategoryRule("Investments & Markets", ("equity", "fixed income", "bond", "market", "valuation", "earnings", "macro", "rate", "duration", "volatility", "hedge")),
    CategoryRule("Client Service", ("client", "meeting", "follow up", "proposal", "onboarding", "review", "relationship", "service")),
    CategoryRule("Finance & Planning", ("budget", "expense", "invoice", "p&l", "forecast", "revenue", "margin", "cash flow", "opex", "capex")),
    CategoryRule("Operations & Admin", ("process", "workflow", "document", "renew", "subscription", "appointment", "schedule", "checklist", "todo")),
    CategoryRule("Learning & Research", ("learn", "study", "course", "research", "read", "book", "training", "certification")),
)

SHORTHAND_MAP: tuple[Tuple[str, str], ...] = (
    (r"\bmtg\b", "meeting"),
    (r"\bw/\b", "with"),
    (r"\bw/o\b", "without"),
    (r"\bappt\b", "appointment"),
    (r"\bdocs\b", "documents"),
)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".docx"}
DATE_PATTERNS = (
    r"\b(\d{4}-\d{2}-\d{2})\b",  # 2026-04-14
    r"\b(\d{1,2}/\d{1,2}/\d{4})\b",  # 04/14/2026
    r"\b([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})\b",  # April 14, 2026
)

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


def parse_date(note: str) -> Optional[datetime]:
    for pattern in DATE_PATTERNS:
        m = re.search(pattern, note)
        if not m:
            continue
        raw = m.group(1)
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(raw, fmt)
            except ValueError:
                pass
    return None


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


def discover_docs_files(docs_dir: Path) -> List[Path]:
    if not docs_dir.exists() or not docs_dir.is_dir():
        raise SystemExit(f"DOCs directory not found: {docs_dir}")
    files = sorted(p for p in docs_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)
    if not files:
        raise SystemExit(f"No supported raw note files in {docs_dir}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
    return files


def deduplicate_and_clean(notes: List[str]) -> Tuple[List[str], Dict[str, int]]:
    seen: Dict[str, str] = {}
    counts: Dict[str, int] = {}
    for note in notes:
        cleaned = clean_note_text(note)
        key = dedupe_key(cleaned)
        if not key:
            continue
        if key in seen:
            canonical = seen[key]
            counts[canonical] = counts.get(canonical, 1) + 1
        else:
            seen[key] = cleaned
            counts[cleaned] = 1
    return list(seen.values()), counts


def categorize_note(note: str) -> str:
    lowered = note.lower()
    scores = {rule.name: 0 for rule in CATEGORY_RULES}
    for rule in CATEGORY_RULES:
        for kw in rule.keywords:
            if kw in lowered:
                scores[rule.name] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "General"


def categorize_and_sort(notes: List[str]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for n in notes:
        out.setdefault(categorize_note(n), []).append(n)

    for section, items in out.items():
        out[section] = sorted(items, key=lambda x: (parse_date(x) is None, parse_date(x) or datetime.min, x.lower()))
    return out


def paragraph_xml(text: str, bold: bool = False) -> str:
    props = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f"<w:p><w:r>{props}<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"


def build_doc_xml(title: str, notes: List[str], dup_counts: Dict[str, int]) -> str:
    lines = [
        paragraph_xml(title, bold=True),
        paragraph_xml(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", False),
        paragraph_xml(f"Items: {len(notes)}", False),
        paragraph_xml("", False),
    ]
    for i, note in enumerate(notes, start=1):
        d = parse_date(note)
        date_prefix = f"[{d.strftime('%Y-%m-%d')}] " if d else ""
        merged = dup_counts.get(note, 1)
        suffix = f" (merged duplicates: {merged - 1})" if merged > 1 else ""
        lines.append(paragraph_xml(f"{i}. {date_prefix}{note}{suffix}"))
    body = "".join(lines)
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}<w:sectPr/></w:body></w:document>'


def write_docx(path: Path, xml: str) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", DOCX_CONTENT_TYPES)
        zf.writestr("_rels/.rels", DOCX_RELS)
        zf.writestr("word/document.xml", xml)




def refresh_latest_pointer(output_root: Path, run_folder: Path) -> Path:
    latest_dir = output_root / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_folder, latest_dir)
    return latest_dir

def write_outputs(base_out: Path, sections: Dict[str, List[str]], dup_counts: Dict[str, int]) -> List[Path]:
    generated: List[Path] = []
    for section, notes in sorted(sections.items()):
        folder_name = re.sub(r"[^A-Za-z0-9_-]+", "_", section).strip("_") or "General"
        section_dir = base_out / folder_name
        section_dir.mkdir(parents=True, exist_ok=True)
        docx_path = section_dir / f"{folder_name}.docx"
        write_docx(docx_path, build_doc_xml(section, notes, dup_counts))
        generated.append(docx_path)
    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description="Organize raw notes from DOCs/ into professional section-based Word files.")
    parser.add_argument("--docs-dir", type=Path, default=Path("DOCs"), help="Raw materials folder (default: DOCs)")
    parser.add_argument("--output-root", type=Path, default=Path("OUTPUT"), help="Root output folder for downloadable results")
    args = parser.parse_args()

    source_files = discover_docs_files(args.docs_dir)
    raw_notes: List[str] = []
    for f in source_files:
        raw_notes.extend(load_notes_from_file(f))
    if not raw_notes:
        raise SystemExit("No note lines found in DOCs inputs.")

    unique_notes, dup_counts = deduplicate_and_clean(raw_notes)
    sections = categorize_and_sort(unique_notes)

    run_folder = args.output_root / f"notes_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    run_folder.mkdir(parents=True, exist_ok=True)
    generated = write_outputs(run_folder, sections, dup_counts)
    latest_folder = refresh_latest_pointer(args.output_root, run_folder)

    print(f"Source files: {len(source_files)}")
    for f in source_files:
        print(f" - {f}")
    print(f"Output folder: {run_folder.resolve()}")
    print(f"Latest folder: {latest_folder.resolve()}")
    print(f"Generated section documents: {len(generated)}")
    for g in generated:
        print(f" - {g}")


if __name__ == "__main__":
    main()
