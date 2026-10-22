# Reproduction

Four single-file runners, one per input condition, plus the tooling that rebuilds their inputs from the released annotation data.

## 1. Build the inputs

```bash
cd 06_scripts
python3 build_inputs.py \
    --source   ../02_data/abcd_source_200.json.gz \
    --templates prompts \
    --out      ../inputs
```

Writes, for every document:

```
../inputs/a/<doc>.txt   structured v6: full text only, model identifies target/instances/relations
../inputs/b/<doc>.txt   spans: text + target + instance positions (ids only, no groups, no relations)
../inputs/c/<doc>.txt   spans + relations: adds group ids and the five relation labels
../inputs/d/<doc>.txt   direct: decision definition + target + full text, label only
../inputs/scoring_reference.json    [{doc_id, gold}]
../inputs/manifest.json             sha256 of every rendered input
```

Rendering is deterministic: the same source always yields byte-identical files.

**Verified**: for the 200-document evaluation subset, conditions B and C regenerate byte-for-byte identical to the prompts that were actually sent (400 files, 0 differences). Condition A has no archived sent copy to compare against, but its document body is checked to equal the joined sentence units.

## 2. Check the inputs (optional)

```bash
python3 - <<'PY'
import hashlib, json, pathlib
man = json.load(open('../inputs/manifest.json'))
bad = [k for k, v in man.items()
       if hashlib.sha256((pathlib.Path('../inputs') / (k + '.txt')).read_bytes()).hexdigest() != v]
print('mismatched files:', len(bad), bad[:5])
PY
```

## 3. Run a condition

```bash
export API_BASE="<openai-compatible endpoint>"
export API_KEY="<key>"

python3 run_B_spans.py \
    --inputs ../inputs/b \
    --reference ../inputs/scoring_reference.json \
    --model-name "<served model name>" \
    --out runs
```

`run_A_structured.py` takes `--source ../02_data/abcd_source_200.json.gz --templates prompts` instead of `--inputs`; it renders the structured prompt itself.

## 4. Output layout

Results are isolated **per condition**:

```
runs/
├── B/<model>/calls/<doc>.json        per-document record (label, status, parse method)
├── B/<model>/attempts/<doc>_<n>.json one file per HTTP attempt
├── B/<model>/raw/<doc>_<n>.json      raw provider response
├── B/<model>/summary.json            totals and BA
├── C/…  D/…  A/…                     separate trees, never shared
```

The request identity hashes include the condition, so a record from another condition can never be picked up. Re-running the same condition sends nothing for documents that already have a valid record.

## Limits

- **Endpoints**: the runners call any OpenAI-compatible chat or responses API; no endpoint, credential or provider routing is included.
- **B/C depend on Gold structure** (target, instance spans, group ids, relations). That is human annotation, shipped in `02_data/abcd_source_200.json.gz`; it cannot be regenerated from the raw text.
- **Condition A on the full 1,766 documents** needs `02_data/document_units_1766.jsonl.gz` plus an annotation export in the same shape as `abcd_source_200.json.gz`; the builder accepts either source.
