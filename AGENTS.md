# AGENTS.md

## Default operating mode

This repository uses a **model-first** workflow.

Treat the repository primarily as:
- an input storage location
- an output storage location
- a versioned workspace for final deliverables

Do not treat this repository as a coding-first processing environment unless explicitly requested.

## Primary instruction

For document understanding, training-note compilation, restructuring, synthesis, navigation building, and editorial rewriting:

- use the model itself as the primary processing engine
- read source files directly from the repository
- infer topics and subtopics semantically
- preserve nuance, detail, examples, and practical explanations
- produce polished Markdown deliverables directly in the repo

## Prohibited default behavior

Unless explicitly requested, do NOT:
- build a rule-based classifier
- build a keyword taxonomy engine
- create a parser-based summarization workflow
- create a script whose main purpose is to process the documents
- create a docx-generation pipeline
- reduce rich materials into a shallow summary
- mechanically bucket content by surface keywords

## Editorial standard

Act as a strong editor and documentation writer, not just a sorter.

The repository’s main use case is transforming messy, overlapping, partially disorganized materials into:
- comprehensive training notes
- training manuals
- work manuals
- structured internal reference documents

Outputs should:
- preserve meaningful content
- remove only true redundancy
- improve organization, flow, clarity, and readability
- create strong navigation and publication-friendly structure

## Output rules

Default output location:

`/OUTPUT/model_outputs/`

Preferred outputs:
- `master_training_manual.md`
- `table_of_contents.md`
- `topic_01_<name>.md`
- `topic_02_<name>.md`
- additional topic files if needed

Default output format:
- Markdown only

Do not default to `.docx` generation.

## Compression rule

This is not primarily a high-level summary workflow.

When in doubt:
- keep more useful content
- organize it better
- rewrite it more clearly
- do not over-compress

## Repository behavior

Inputs should be read directly from the GitHub repository.
Outputs should be written directly back into the GitHub repository.
The final product is the documentation itself, not code.
