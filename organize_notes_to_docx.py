#!/usr/bin/env python3
"""Grow an immutable note knowledge base from DOCs/ into OUTPUT/.

Design goals:
- Never delete previous outputs
- Keep a growing knowledge base with deduped notes
- Classify notes into topic/subtopic deterministically
- Emit timestamped DOCX snapshots per topic/subtopic
"""

from __future__ import annotations

import argparse
import csv
import re
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
  <Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

DOCX_RELS = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>
</Relationships>
"""


def timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")


def sanitize_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "General"


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


def deduplicate_and_clean(notes: Iterable[str]) -> List[str]:
    seen_by_key: Dict[str, str] = {}
    for note in notes:
        cleaned = clean_note_text(note)
        key = dedupe_key(cleaned)
        if key and key not in seen_by_key:
            seen_by_key[key] = cleaned
    return list(seen_by_key.values())


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


def latest_snapshot(index_dir: Path) -> Optional[Path]:
    if not index_dir.exists():
        return None
    candidates = sorted(index_dir.glob("master_index__*.csv"))
    return candidates[-1] if candidates else None


def load_existing_knowledge(index_dir: Path) -> List[dict]:
    snap = latest_snapshot(index_dir)
    if not snap:
        return []

    rows: List[dict] = []
    with snap.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            note = row.get("final_note", "").strip()
            topic = row.get("topic", FALLBACK_TOPIC).strip() or FALLBACK_TOPIC
            subtopic = row.get("subtopic", FALLBACK_SUBTOPIC).strip() or FALLBACK_SUBTOPIC
            if note:
                rows.append({"topic": topic, "subtopic": subtopic, "note": note, "source": "historical"})
    return rows


def merge_knowledge(existing_rows: List[dict], new_notes: List[str]) -> List[dict]:
    merged: Dict[str, dict] = {}

    for row in existing_rows:
        merged[dedupe_key(row["note"])] = row

    for note in new_notes:
        topic, subtopic = classify_note(note)
        merged[dedupe_key(note)] = {
            "topic": topic,
            "subtopic": subtopic,
            "note": note,
            "source": "current_run",
        }

    return list(merged.values())


def paragraph_xml(text: str, bold: bool = False) -> str:
    props = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f"<w:p><w:r>{props}<w:t xml:space=\"preserve\">{escape(text)}</w:t></w:r></w:p>"


def build_doc_xml(title: str, subtitle: str, notes: List[str]) -> str:
    lines = [
        paragraph_xml(title, bold=True),
        paragraph_xml(subtitle),
        paragraph_xml(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"),
        paragraph_xml(f"Items: {len(notes)}"),
        paragraph_xml(""),
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


def write_snapshot_docs(knowledge_dir: Path, rows: List[dict], run_ts: str) -> List[Path]:
    docs_root = knowledge_dir / "topics"
    docs_root.mkdir(parents=True, exist_ok=True)

    by_topic: Dict[str, List[str]] = {}
    by_topic_subtopic: Dict[Tuple[str, str], List[str]] = {}
    for row in rows:
        by_topic.setdefault(row["topic"], []).append(row["note"])
        by_topic_subtopic.setdefault((row["topic"], row["subtopic"]), []).append(row["note"])

    generated: List[Path] = []

    for topic, notes in sorted(by_topic.items()):
        topic_dir = docs_root / sanitize_name(topic)
        topic_dir.mkdir(parents=True, exist_ok=True)
        path = topic_dir / f"{sanitize_name(topic)}__{run_ts}.docx"
        write_docx(path, build_doc_xml(topic, "Topic snapshot", sort_notes(notes)))
        generated.append(path)

    for (topic, subtopic), notes in sorted(by_topic_subtopic.items()):
        sub_dir = docs_root / sanitize_name(topic) / sanitize_name(subtopic)
        sub_dir.mkdir(parents=True, exist_ok=True)
        path = sub_dir / f"{sanitize_name(subtopic)}__{run_ts}.docx"
        write_docx(path, build_doc_xml(topic, f"Subtopic snapshot: {subtopic}", sort_notes(notes)))
        generated.append(path)

    return generated


def write_indexes(knowledge_dir: Path, runs_dir: Path, rows: List[dict], run_ts: str) -> Tuple[Path, Path]:
    index_dir = knowledge_dir / "index_snapshots"
    index_dir.mkdir(parents=True, exist_ok=True)

    master_index = index_dir / f"master_index__{run_ts}.csv"
    with master_index.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["topic", "subtopic", "final_note", "source"])
        for row in sorted(rows, key=lambda r: (r["topic"], r["subtopic"], r["note"].lower())):
            writer.writerow([row["topic"], row["subtopic"], row["note"], row["source"]])

    run_manifest = runs_dir / "run_manifest.csv"
    with run_manifest.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["topic", "subtopic", "final_note", "path_hint"])
        for row in sorted(rows, key=lambda r: (r["topic"], r["subtopic"], r["note"].lower())):
            writer.writerow([
                row["topic"],
                row["subtopic"],
                row["note"],
                f"knowledge_base/topics/{sanitize_name(row['topic'])}/{sanitize_name(row['subtopic'])}/{sanitize_name(row['subtopic'])}__{run_ts}.docx",
            ])

    return master_index, run_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Grow immutable note knowledge base from DOCs/ to OUTPUT/.")
    parser.add_argument("--docs-dir", type=Path, default=Path("DOCs"), help="Raw note folder (default: DOCs)")
    parser.add_argument("--output-root", type=Path, default=Path("OUTPUT"), help="Output root folder (default: OUTPUT)")
    args = parser.parse_args()

    run_ts = timestamp()
    knowledge_dir = args.output_root / "knowledge_base"
    runs_dir = args.output_root / "runs" / f"run_{run_ts}"
    runs_dir.mkdir(parents=True, exist_ok=True)

    files = discover_input_files(args.docs_dir)
    raw_notes: List[str] = []
    for f in files:
        raw_notes.extend(load_notes_from_file(f))
    if not raw_notes:
        raise SystemExit("No note lines found in inputs.")

    cleaned_notes = deduplicate_and_clean(raw_notes)
    existing_rows = load_existing_knowledge(knowledge_dir / "index_snapshots")
    merged_rows = merge_knowledge(existing_rows, cleaned_notes)

    docs = write_snapshot_docs(knowledge_dir, merged_rows, run_ts)
    master_index, run_manifest = write_indexes(knowledge_dir, runs_dir, merged_rows, run_ts)

    print(f"Run timestamp: {run_ts}")
    print(f"Source files: {len(files)}")
    for f in files:
        print(f" - {f}")
    print(f"Knowledge notes total: {len(merged_rows)}")
    print(f"Knowledge docs generated this run: {len(docs)}")
    print(f"Master index snapshot: {master_index.resolve()}")
    print(f"Run manifest: {run_manifest.resolve()}")


if __name__ == "__main__":
    main()
