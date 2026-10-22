# LongToxiCN: A Chinese Long-Form Identity-Harm Dataset (1,766-document release)

Gold annotations for 1,766 Chinese long-form articles, per-document predictions from 13 language models, four-condition evaluation results on a shared 200-document subset, and the annotation specification, prompts, dual-review and adjudication records that produced them.

Directories follow the order in which the artefacts are produced: prompts → data → model outputs → evaluation → human review → scripts.

## Layout

| Directory | Contents | Files | Size |
|---|---|---|---|
| `01_prompts/` | Annotation specification (`definitions/`), review and adjudication prompts (`review/`), and the nine-stage annotation pipeline prompts (P0 segmentation → P1 target → P2A extraction → P2B boundary check → summary rewrite → P2C local threshold → P2D threshold verification → P3A grouping and relations → P3B source/uptake/terminal state), plus usage notes and a checksum manifest | 16 | 212 KB |
| `02_data/` | Gold labels, per-model prediction matrix, the two structured sources used to rebuild inputs (`abcd_source_200.json.gz`, `document_units_1766.jsonl.gz`), and two gzip-compressed Markdown files (per-document text + full annotation; review + adjudication) split into numbered parts | 2 CSV + 2 sources + 5 archive parts | 43.4 MiB |
| `03_model_outputs/` | `model_outputs.zip.part*`, containing per-document output for each of 13 models (label, status, raw output) | 2 archive parts (13 JSON files) | 12.2 MiB compressed |
| `04_evaluation/` | Per-document scores for the four input conditions (A/B/C/D) on the 200-document subset, with Gold reference | 4 | 1.5 MB |
| `05_human_review/` | Two reviewers' 200-document review records (what to change, original → proposed) | 2 | 94 KB |
| `06_scripts/` | One single-file runner per condition, the four prompt templates, and `build_inputs.py` that rebuilds every input from `02_data/` (see `06_scripts/README.md`) | 10 | 82 KB |

`01_prompts/` has two layers:

```
definitions/  definition_master.md    the decision standard: four-step threshold, relation set, terminal states, label derivation
              annotation_manual.md    the practical manual: how annotators apply it
review/       review_prompt.md        prompt used for dual review (produces "review result" in 02_data)
              adjudication_prompt.md  prompt used for adjudication (produces "adjudication" in 02_data)
0*.md         the nine annotation-stage prompts, numbered in pipeline order
```

## Data flow

```
01_prompts ──► annotation  (02_data/text_and_annotations_1766.md)
                  │  per document: target, proposition groups, instances,
                  │  local thresholds, relations, terminal states, document label
                  ▼
03_model_outputs ──► 04_evaluation  (Gold comparison → per-document correctness → BA)
                  ▲
                  │  same 200 documents, four input conditions
06_scripts ───────┘  A = structured v6 | B = spans only | C = spans + relations | D = direct

02_data/review_and_adjudication_1766.md
    input annotation ──► review result (verbatim) ──► adjudication (original → new value)
05_human_review = the two reviewers' side of the same review round, kept per reviewer
```

## Key numbers

- Documents: 1,766 (HATE 944 / NON_HATE 822); 277 of them are rewritten versions already merged into the same set
- Models: 13 (5 API, 8 local), 1,766 documents each
- Evaluation subset: 200 documents (HATE 105 / NON_HATE 95), four input conditions × 11 models
- Dual review: 2 reviewers × 200 documents, 684 change proposals (A 336 / B 348) and 50 keep proposals (A 25 / B 25)
- Adjudication: 241 documents with substantive changes (194 document-label changes, 185 annotation-field changes)

## Naming conventions

- `01_`–`13_` prefixes in `03_model_outputs/` and the columns of `02_data/model_predictions_1766.csv` are model indices and match one-to-one
- `01_`–`09_` prefixes under `01_prompts/` are annotation pipeline stages, not execution time order (target discovery precedes P0)
- Document indices are local to each file: `0001`–`1766` in the annotation and review tables, `01`–`200` in the 200-document evaluation files. Join across files by `doc_id`, never by row number

## Protocol notes

- **BA** = (HATE recall + NON_HATE recall) / 2; invalid outputs count as wrong
- **A/B/C/D** differ only in what the input provides: A gives the raw text and lets the model identify target, instances and relations itself; B adds the target and instance spans; C further adds group IDs and five relation labels; D gives the decision definition, the target and the full text, and asks for the label only
- The 200-document subset uses the revised Gold (2026-10-19); the 1,766-document set uses the v3 freeze (2026-10-07). Eight documents carry different labels between the two versions
- Model identifiers are canonicalized to `gpt-5.6-sol`, `gpt-5.6-luna`, `glm-5.3`, `glm-5.3-flash`; provider-side alias drift is not retained

## Unpack the data

The release compresses the two large Markdown files as gzip and the 13 model-output JSON files as one ZIP archive. Each archive is split into numbered `.part001`, `.part002`, etc. files of at most 7 MiB to stay below Anonymous GitHub's documented 8 MB per-file limit. Compression is lossless, and extraction restores the original filenames and contents. The tracked release is approximately 47 MiB before extraction. Archive parts are stored directly in Git; Git LFS is not required.

Run these commands from the repository root (macOS/Linux):

```bash
cat 02_data/text_and_annotations_1766.md.gz.part* > 02_data/text_and_annotations_1766.md.gz
cat 02_data/review_and_adjudication_1766.md.gz.part* > 02_data/review_and_adjudication_1766.md.gz
cat 03_model_outputs/model_outputs.zip.part* > 03_model_outputs/model_outputs.zip
gzip -dk 02_data/text_and_annotations_1766.md.gz
gzip -dk 02_data/review_and_adjudication_1766.md.gz
unzip -n 03_model_outputs/model_outputs.zip -d 03_model_outputs
```

The archive parts and reconstructed archives are retained. Reconstructed archives and extracted files are ignored by Git to prevent accidentally recommitting large files. Paths in the data-flow diagram and integrity notes refer to the extracted files.

To verify all 15 extracted files against their original SHA-256 checksums:

```bash
# macOS
shasum -a 256 -c data_checksums.sha256
# Linux alternative
sha256sum -c data_checksums.sha256
```

## Integrity

- `data_checksums.sha256`: SHA-256 checksums of the two original Markdown files and all 13 original JSON files; all compressed files were decompressed and verified before packaging
- `02_data/text_and_annotations_1766.md`: 1,766 sections; annotation round-trips against the source Gold with zero field differences (1,931,273 leaf values)
- `02_data/review_and_adjudication_1766.md`: 1,766 sections; each carries an explicit label chain `input → reviewed → adjudicated → final`, and every chain closes at the v3 final label (0 mismatches). The three record layers come from different stages: review changes (32), adjudication changes (194), and 19 post-processing label changes applied in the v3 freeze, which the package itself does not record per document.
- `03_model_outputs/`: 13 × 1,766 = 22,958 records, consistent line by line with `02_data/model_predictions_1766.csv`
- `01_prompts/checksums.json`: SHA-256 of the nine pipeline prompts verifies against the files as shipped
- `06_scripts/build_inputs.py`: regenerates the 200-document inputs for conditions B, C and D byte-for-byte identical to the prompts actually sent (600 files, 0 differences)

## Anonymization

Local absolute paths appearing in provenance fields have been replaced with `<workspace>/`. No credentials, endpoints, or provider routing details are included.
