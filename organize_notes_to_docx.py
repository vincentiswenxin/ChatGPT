#!/usr/bin/env python3
"""Organize notes from DOCs/ into section + subtopic DOCX exports.

This script is API-key free and deterministic:
- Reads notes from DOCs/
- Cleans and deduplicates notes
- Classifies into topic + subtopic via taxonomy rules
- Maintains cumulative knowledge by merging with OUTPUT/latest/search_index.csv
- Writes section/subtopic Word files and searchable indexes
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


@dataclass(frozen=True)
class SubtopicRule:
    name: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class TopicRule:
    name: str
    subtopics: tuple[SubtopicRule, ...]


TAXONOMY: tuple[TopicRule, ...] = (
    TopicRule(
        "Training Notes",
        (
            SubtopicRule("Leadership_Training", ("leadership", "manager", "coaching", "feedback", "1:1", "one on one")),
            SubtopicRule("Compliance_Training", ("compliance", "sec", "finra", "kyc", "aml", "regulatory")),
            SubtopicRule("Product_Training", ("product", "feature", "platform", "demo", "onboarding")),
            SubtopicRule("Process_Training", ("workflow", "process", "checklist", "sop", "procedure")),
        ),
    ),
    TopicRule(
        "Client & Wealth",
        (
            SubtopicRule("Client_Reviews", ("client", "meeting", "review", "follow up", "relationship")),
            SubtopicRule("Portfolio_Planning", ("portfolio", "allocation", "retirement", "estate", "wealth", "trust")),
            SubtopicRule("Market_View", ("equity", "bond", "market", "macro", "valuation", "rate", "volatility")),
        ),
    ),
    TopicRule(
        "Finance & Operations",
        (
            SubtopicRule("Budgeting", ("budget", "forecast", "expense", "cash flow", "margin", "revenue")),
            SubtopicRule("Operations", ("operations", "admin", "document", "schedule", "task", "todo")),
            SubtopicRule("Risk_Controls", ("risk", "audit", "control", "policy", "breach")),
        ),
    ),
)

FALLBACK_TOPIC = "General"
FALLBACK_SUBTOPIC = "General_Notes"

SHORTHAND_MAP: tuple[Tuple[str, str], ...] = (
    (r"\bmtg\b", "meeting"),
    (r"\bw/\b", "with"),
    (r"\bw/o\b", "without"),
    (r"\bappt\b", "appointment"),
    (r"\bdocs\b", "documents"),
)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".docx"}
DATE_PATTERNS = (
    r"\b(\d{4}-\d{2}-\d{2})\b",
    r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
    r"\b([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})\b",
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
    lowered = re.sub(r"[^a-z0-9\s]", "", note.lower())
    return re.sub(r"\s+", " ", lowered).strip()


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
    return [n for n in (normalize_note(line) for line in text.splitlines()) if n]


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


def discover_input_files(docs_dir: Path) -> List[Path]:
    if not docs_dir.exists() or not docs_dir.is_dir():
        raise SystemExit(f"DOCs directory not found: {docs_dir}")
    files = sorted(p for p in docs_dir.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)
    if not files:
        raise SystemExit(f"No supported files found in {docs_dir}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
    return files


def deduplicate_and_clean(notes: Iterable[str]) -> Tuple[List[str], Dict[str, int]]:
    seen_by_key: Dict[str, str] = {}
    counts: Dict[str, int] = {}
    for note in notes:
        cleaned = clean_note_text(note)
        key = dedupe_key(cleaned)
        if not key:
            continue
        if key in seen_by_key:
            canonical = seen_by_key[key]
            counts[canonical] = counts.get(canonical, 1) + 1
        else:
            seen_by_key[key] = cleaned
            counts[cleaned] = 1
    return list(seen_by_key.values()), counts


def classify_note(note: str) -> Tuple[str, str]:
    lowered = note.lower()
    best_topic = FALLBACK_TOPIC
    best_subtopic = FALLBACK_SUBTOPIC
    best_score = 0

    for topic in TAXONOMY:
        for subtopic in topic.subtopics:
            score = sum(1 for kw in subtopic.keywords if kw in lowered)
            if score > best_score:
                best_score = score
                best_topic = topic.name
                best_subtopic = subtopic.name

    return best_topic, best_subtopic


def sort_notes(notes: Iterable[str]) -> List[str]:
    return sorted(notes, key=lambda n: (parse_date(n) is None, parse_date(n) or datetime.min, n.lower()))


def load_prior_notes(output_root: Path) -> List[dict]:
    index_file = output_root / "latest" / "search_index.csv"
    if not index_file.exists():
        return []

    rows: List[dict] = []
    with index_file.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            note = row.get("final_note", "").strip()
            topic = row.get("topic", FALLBACK_TOPIC).strip() or FALLBACK_TOPIC
            subtopic = row.get("subtopic", FALLBACK_SUBTOPIC).strip() or FALLBACK_SUBTOPIC
            if note:
                rows.append({"topic": topic, "subtopic": subtopic, "note": note, "source": "historical"})
    return rows


def merge_new_with_prior(new_notes: List[str], prior_rows: List[dict]) -> List[dict]:
    merged: Dict[str, dict] = {}

    for row in prior_rows:
        key = dedupe_key(row["note"])
        merged[key] = row

    for note in new_notes:
        topic, subtopic = classify_note(note)
        key = dedupe_key(note)
        merged[key] = {"topic": topic, "subtopic": subtopic, "note": note, "source": "current_run"}

    return list(merged.values())


def paragraph_xml(text: str, bold: bool = False) -> str:
    props = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f"<w:p><w:r>{props}<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"


def build_doc_xml(title: str, subtitle: str, notes: List[str]) -> str:
    lines = [
        paragraph_xml(title, bold=True),
        paragraph_xml(subtitle, False),
        paragraph_xml(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", False),
        paragraph_xml(f"Items: {len(notes)}", False),
        paragraph_xml("", False),
    ]
    for i, note in enumerate(notes, start=1):
        parsed = parse_date(note)
        date_prefix = f"[{parsed.strftime('%Y-%m-%d')}] " if parsed else ""
        lines.append(paragraph_xml(f"{i}. {date_prefix}{note}"))

    body = "".join(lines)
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        f"<w:body>{body}<w:sectPr/></w:body></w:document>"
    )


def write_docx(path: Path, xml: str) -> None:
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", DOCX_CONTENT_TYPES)
        zf.writestr("_rels/.rels", DOCX_RELS)
        zf.writestr("word/document.xml", xml)


def write_outputs(run_dir: Path, rows: List[dict]) -> List[Path]:
    by_topic_subtopic: Dict[Tuple[str, str], List[str]] = {}
    by_topic: Dict[str, List[str]] = {}

    for row in rows:
        topic = row["topic"]
        subtopic = row["subtopic"]
        note = row["note"]
        by_topic_subtopic.setdefault((topic, subtopic), []).append(note)
        by_topic.setdefault(topic, []).append(note)

    generated: List[Path] = []

    for topic, notes in sorted(by_topic.items()):
        topic_dir = run_dir / sanitize_name(topic)
        topic_dir.mkdir(parents=True, exist_ok=True)
        topic_doc = topic_dir / f"{sanitize_name(topic)}.docx"
        write_docx(topic_doc, build_doc_xml(topic, "Master topic document", sort_notes(notes)))
        generated.append(topic_doc)

    for (topic, subtopic), notes in sorted(by_topic_subtopic.items()):
        subtopic_dir = run_dir / sanitize_name(topic) / sanitize_name(subtopic)
        subtopic_dir.mkdir(parents=True, exist_ok=True)
        subtopic_doc = subtopic_dir / f"{sanitize_name(subtopic)}.docx"
        write_docx(subtopic_doc, build_doc_xml(topic, f"Subtopic: {subtopic}", sort_notes(notes)))
        generated.append(subtopic_doc)

    return generated


def sanitize_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "General"


def write_indexes(run_dir: Path, rows: List[dict], duplicate_counts: Dict[str, int]) -> None:
    audit_file = run_dir / "categorization_audit.csv"
    with audit_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["topic", "subtopic", "final_note", "duplicates_merged", "source"])
        for row in sorted(rows, key=lambda r: (r["topic"], r["subtopic"], r["note"].lower())):
            writer.writerow([
                row["topic"],
                row["subtopic"],
                row["note"],
                max(0, duplicate_counts.get(row["note"], 1) - 1),
                row["source"],
            ])

    search_file = run_dir / "search_index.csv"
    with search_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["topic", "subtopic", "final_note", "path_hint"])
        for row in sorted(rows, key=lambda r: (r["topic"], r["subtopic"], r["note"].lower())):
            writer.writerow([
                row["topic"],
                row["subtopic"],
                row["note"],
                f"{sanitize_name(row['topic'])}/{sanitize_name(row['subtopic'])}/{sanitize_name(row['subtopic'])}.docx",
            ])


def refresh_latest(output_root: Path, run_dir: Path) -> Path:
    latest_dir = output_root / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)
    return latest_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Organize notes from DOCs/ into topic/subtopic .docx outputs.")
    parser.add_argument("--docs-dir", type=Path, default=Path("DOCs"), help="Raw note folder (default: DOCs)")
    parser.add_argument("--output-root", type=Path, default=Path("OUTPUT"), help="Output root folder (default: OUTPUT)")
    args = parser.parse_args()

    source_files = discover_input_files(args.docs_dir)
    raw_notes: List[str] = []
    for source in source_files:
        raw_notes.extend(load_notes_from_file(source))
    if not raw_notes:
        raise SystemExit("No note lines found in input files.")

    unique_notes, duplicate_counts = deduplicate_and_clean(raw_notes)
    prior_rows = load_prior_notes(args.output_root)
    merged_rows = merge_new_with_prior(unique_notes, prior_rows)

    run_dir = args.output_root / f"notes_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    generated = write_outputs(run_dir, merged_rows)
    write_indexes(run_dir, merged_rows, duplicate_counts)
    latest_dir = refresh_latest(args.output_root, run_dir)

    print(f"Source files: {len(source_files)}")
    for source in source_files:
        print(f" - {source}")
    print(f"Merged notes in knowledge base: {len(merged_rows)}")
    print(f"Output folder: {run_dir.resolve()}")
    print(f"Latest folder: {latest_dir.resolve()}")
    print(f"Generated documents: {len(generated)}")
    for output in generated:
        print(f" - {output}")


if __name__ == "__main__":
    main()
