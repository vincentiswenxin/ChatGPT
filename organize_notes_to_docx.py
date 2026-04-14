#!/usr/bin/env python3
"""Convert raw notes in DOCs/ into sectioned .docx files in OUTPUT/.

Workflow:
1) Read .txt/.md/.docx files from DOCs/
2) Normalize + lightly clean + deduplicate notes
3) Categorize notes (rule-based or OpenAI-assisted)
4) Write one .docx per section into a timestamped export folder
5) Refresh OUTPUT/latest/ with the newest export
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib import error, request
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


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

ALLOWED_CATEGORIES = {rule.name for rule in CATEGORY_RULES} | {"General"}

SHORTHAND_MAP: tuple[Tuple[str, str], ...] = (
    (r"\bmtg\b", "meeting"),
    (r"\bw/\b", "with"),
    (r"\bw/o\b", "without"),
    (r"\bappt\b", "appointment"),
    (r"\bdocs\b", "documents"),
)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".docx"}
DATE_PATTERNS = (
    r"\b(\d{4}-\d{2}-\d{2})\b",      # 2026-04-14
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


def categorize_note_rule_based(note: str) -> str:
    lowered = note.lower()
    scores = {rule.name: 0 for rule in CATEGORY_RULES}
    for rule in CATEGORY_RULES:
        for keyword in rule.keywords:
            if keyword in lowered:
                scores[rule.name] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "General"


def sort_notes(notes: Iterable[str]) -> List[str]:
    return sorted(notes, key=lambda n: (parse_date(n) is None, parse_date(n) or datetime.min, n.lower()))


def extract_json_array(text: str) -> List[dict]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON array found in model response")
    return json.loads(text[start : end + 1])


def call_openai_chat(model: str, prompt: str, api_key: str, timeout_seconds: int = 90) -> str:
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": "You are a precise financial/compliance note editor and classifier."},
            {"role": "user", "content": prompt},
        ],
    }
    req = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenAI API error: HTTP {exc.code} {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"OpenAI API connection error: {exc}") from exc

    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected OpenAI response format: {body}") from exc


def ai_rewrite_and_categorize(notes: List[str], model: str, api_key: str) -> List[dict]:
    categories = ", ".join(sorted(ALLOWED_CATEGORIES))
    notes_json = json.dumps(notes, ensure_ascii=False)
    prompt = (
        "For each note, create a professional rewrite and choose one category.\n"
        "Rules:\n"
        "- Keep factual meaning, do not invent details.\n"
        "- Improve clarity, grammar, and professionalism.\n"
        "- Keep each rewrite concise and complete.\n"
        f"- category must be exactly one of: {categories}.\n"
        "Return only JSON array with objects of shape: "
        "{\"original\": string, \"rewritten\": string, \"category\": string}.\n"
        f"Input notes: {notes_json}"
    )
    raw = call_openai_chat(model=model, prompt=prompt, api_key=api_key)
    items = extract_json_array(raw)

    by_original: Dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        original = str(item.get("original", "")).strip()
        rewritten = str(item.get("rewritten", "")).strip()
        category = str(item.get("category", "")).strip()
        if not original:
            continue
        if category not in ALLOWED_CATEGORIES:
            category = "General"
        if not rewritten:
            rewritten = original
        by_original[original] = {"original": original, "rewritten": rewritten, "category": category}

    output: List[dict] = []
    for note in notes:
        output.append(by_original.get(note, {"original": note, "rewritten": note, "category": categorize_note_rule_based(note)}))
    return output


def build_sections_from_items(items: List[dict]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for item in items:
        grouped.setdefault(item["category"], []).append(item["rewritten"])
    return {section: sort_notes(values) for section, values in grouped.items()}


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
        parsed = parse_date(note)
        date_prefix = f"[{parsed.strftime('%Y-%m-%d')}] " if parsed else ""
        merged = dup_counts.get(note, 1)
        suffix = f" (merged duplicates: {merged - 1})" if merged > 1 else ""
        lines.append(paragraph_xml(f"{i}. {date_prefix}{note}{suffix}"))
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


def write_outputs(output_dir: Path, sections: Dict[str, List[str]], dup_counts: Dict[str, int]) -> List[Path]:
    generated: List[Path] = []
    for section, notes in sorted(sections.items()):
        folder_name = re.sub(r"[^A-Za-z0-9_-]+", "_", section).strip("_") or "General"
        section_dir = output_dir / folder_name
        section_dir.mkdir(parents=True, exist_ok=True)
        docx_path = section_dir / f"{folder_name}.docx"
        write_docx(docx_path, build_doc_xml(section, notes, dup_counts))
        generated.append(docx_path)
    return generated


def write_audit_csv(path: Path, items: List[dict], dup_counts: Dict[str, int], ai_enabled: bool) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["category", "original_note", "final_note", "duplicates_merged", "ai_enhanced"])
        for item in items:
            final_note = item["rewritten"]
            writer.writerow([
                item["category"],
                item["original"],
                final_note,
                max(0, dup_counts.get(item["original"], 1) - 1),
                "yes" if ai_enabled else "no",
            ])


def refresh_latest(output_root: Path, run_dir: Path) -> Path:
    latest_dir = output_root / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)
    return latest_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Organize notes from DOCs/ into sectioned .docx outputs.")
    parser.add_argument("--docs-dir", type=Path, default=Path("DOCs"), help="Raw note folder (default: DOCs)")
    parser.add_argument("--output-root", type=Path, default=Path("OUTPUT"), help="Output root folder (default: OUTPUT)")
    parser.add_argument("--use-openai", action="store_true", help="Use OpenAI model to rewrite and categorize notes.")
    parser.add_argument("--openai-model", default="gpt-4.1-mini", help="Model name when --use-openai is enabled.")
    args = parser.parse_args()

    source_files = discover_input_files(args.docs_dir)
    raw_notes: List[str] = []
    for source in source_files:
        raw_notes.extend(load_notes_from_file(source))
    if not raw_notes:
        raise SystemExit("No note lines found in input files.")

    unique_notes, dup_counts = deduplicate_and_clean(raw_notes)

    ai_enabled = False
    if args.use_openai:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise SystemExit("--use-openai was set, but OPENAI_API_KEY is missing.")
        items = ai_rewrite_and_categorize(unique_notes, args.openai_model, api_key)
        ai_enabled = True
    else:
        items = [
            {"original": note, "rewritten": note, "category": categorize_note_rule_based(note)}
            for note in unique_notes
        ]

    sections = build_sections_from_items(items)

    run_dir = args.output_root / f"notes_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    generated = write_outputs(run_dir, sections, dup_counts)
    write_audit_csv(run_dir / "categorization_audit.csv", items, dup_counts, ai_enabled)
    latest_dir = refresh_latest(args.output_root, run_dir)

    print(f"Source files: {len(source_files)}")
    for source in source_files:
        print(f" - {source}")
    print(f"AI mode: {'enabled' if ai_enabled else 'disabled'}")
    print(f"Output folder: {run_dir.resolve()}")
    print(f"Latest folder: {latest_dir.resolve()}")
    print(f"Generated section documents: {len(generated)}")
    for output in generated:
        print(f" - {output}")


if __name__ == "__main__":
    main()
