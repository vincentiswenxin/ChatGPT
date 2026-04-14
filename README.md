# Model-First Notes Organizer

This repository follows a **model-first document processing workflow**.

The purpose of this repo is to use GitHub as a storage and versioned output workspace, while using the model itself as the primary engine for reading, organizing, restructuring, and writing documentation.

## Operating model

1. Place source materials anywhere in the repository where they are easy to access.
2. Ask Codex to read the relevant files directly from the repo.
3. Have Codex use the model itself to reorganize, synthesize, and polish the material.
4. Write all final outputs back into `OUTPUT/` so they remain accessible in GitHub.

## Core principles

- **GitHub is the storage layer**
  - Inputs live in the repo
  - Outputs live in the repo
  - Final deliverables should be committed back into GitHub

- **The model is the processing layer**
  - The main work should be done through model-based understanding and editorial transformation
  - Avoid relying on rule-based scripts, keyword taxonomies, or parser pipelines as the primary method

- **Markdown is the default output format**
  - Final deliverables should be written as `.md` files
  - Avoid `.docx` generation unless explicitly requested later

## Output goals

The desired outputs are not shallow summaries.

The goal is to produce:
- comprehensive training notes
- structured training manuals
- working reference documents
- publication-friendly internal documentation

Outputs should:
- preserve meaningful detail
- retain nuance and useful context
- merge overlapping material intelligently
- remove only true redundancy
- improve readability, structure, and navigation
- be suitable for actual use, not just high-level review

## Default output location

Write final deliverables into:

`OUTPUT/model_outputs/`

Typical deliverables may include:

- `master_training_manual.md`
- `table_of_contents.md`
- `topic_01_<name>.md`
- `topic_02_<name>.md`
- `topic_03_<name>.md`

Additional topic files may be created as needed.

## Navigation standard

Outputs should be easy to browse and reuse.

Prefer:
- clear headings and subheadings
- consistent section naming
- table of contents
- cross-references where useful
- publication-friendly document structure

## Important note

This repository should not default to a coding-first workflow.

Unless explicitly requested, Codex should **not** treat the task as:
- building a rule-based classifier
- generating a processing script
- creating a keyword taxonomy engine
- constructing a parser-based summarization pipeline

The primary deliverable is the written documentation itself.

## Practical workflow

When new materials are added to the repository:

1. Ask Codex to process the relevant files directly from GitHub.
2. Codex should use the model to interpret and reorganize the content.
3. Codex should write the final Markdown outputs into `OUTPUT/model_outputs/`.
4. Those outputs should remain in the repository for direct access through GitHub.
