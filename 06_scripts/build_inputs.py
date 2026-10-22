#!/usr/bin/env python3
"""Render the four input conditions from released annotation data.

    python3 build_inputs.py --source ../02_data/abcd_source_200.json.gz \
                            --templates prompts --out ../inputs

Writes inputs/{a,b,c,d}/<doc_id>.txt plus inputs/scoring_reference.json and
inputs/manifest.sha256. Rendering is deterministic: the same source always
yields byte-identical inputs.
"""
import argparse
import gzip
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


def load_source(path: Path) -> list:
    raw = path.read_bytes()
    if path.suffix == '.gz':
        raw = gzip.decompress(raw)
    data = json.loads(raw)
    if isinstance(data, dict):
        data = data.get('results', [])
    docs = []
    for row in data:
        docs.append({
            'doc_id': row['doc_id'],
            'target': row['target'],
            'units': row['units'],
            'propositions': row.get('propositions') or [],
            'instances': row.get('instances') or [],
            'label': row.get('label'),
        })
    return docs


def xml_escape(text: str) -> str:
    """Escape like ElementTree, which produced the released inputs."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def render_document(units, instances=None, with_relations=False) -> str:
    lines = [f"{u['id']}\t{u['text']}" for u in units]
    if instances:
        lines = [f"{u['id']}\t{xml_escape(u['text'])}" for u in units]
    if not instances:
        return '<document>\n' + '\n'.join(lines) + '\n</document>'
    pos = {u['id']: i + 1 for i, u in enumerate(units)}
    opens, closes = defaultdict(list), defaultdict(list)
    for ordinal, inst in enumerate(instances, 1):
        start, end = pos[inst['start']], pos[inst['end']]
        attrs = f' id="E{ordinal:03d}"'
        if with_relations:
            if inst.get('proposition_id'):
                attrs += f' proposition_id="{inst["proposition_id"]}"'
            if inst.get('relation'):
                attrs += f' relation="{inst["relation"]}"'
        opens[start].append((end, ordinal, attrs))
        closes[end].append((start, end, ordinal, attrs))
    out = ['<document>']
    for number, line in enumerate(lines, 1):
        for _, _, attrs in sorted(opens.get(number, []), key=lambda x: (-x[0], x[1])):
            out.append(f'<instance{attrs}>')
        out.append(line)
        for _, _, _, attrs in sorted(closes.get(number, []), key=lambda x: (-x[0], x[1])):
            out.append(f'</instance>')
    out.append('</document>')
    return '\n'.join(out)


def render(doc, condition, templates):
    units = doc['units']
    tpl = templates[condition]
    if condition == 'd':
        body = render_document(units)
        if '{{TARGET}}' in tpl:
            body = tpl.replace('{{TARGET}}', doc['target']).replace('{{DOCUMENT}}', body)
            return body
        return tpl.replace('{{DOCUMENT}}', body)
    if condition == 'a':
        body = '\n'.join(f"{u['id']}\t{u['text']}" for u in doc['units'])
        return tpl.replace('{{DOCUMENT}}', body)
    if condition == 'b':
        body = render_document(units, doc.get('instances'), with_relations=False)
        return tpl.replace('{{TARGET}}', doc['target']).replace('{{DOCUMENT}}', body)
    props = '<propositions>\n' + ''.join(f'<proposition id="{p}" />' for p in doc['propositions']) + '</propositions>'
    body = render_document(units, doc.get('instances'), with_relations=True)
    return tpl.replace('{{TARGET}}', doc['target']).replace('{{PROPOSITIONS}}', props).replace('{{DOCUMENT}}', body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True, help='structured source (.json or .json.gz)')
    ap.add_argument('--templates', required=True, help='directory with a/b/c/d templates')
    ap.add_argument('--out', required=True, help='output directory')
    ap.add_argument('--docs', nargs='*', help='only these doc_ids')
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    docs = load_source(Path(args.source))
    if args.docs:
        keep = set(args.docs)
        docs = [d for d in docs if d['doc_id'] in keep]
    if args.limit:
        docs = docs[:args.limit]
    tdir = Path(args.templates)
    templates = {c: (tdir / name).read_text(encoding='utf-8')
                 for c, name in (('a', 'a_structured_v6.txt'), ('b', 'b_spans.txt'),
                                 ('c', 'c_gold_minimal.txt'), ('d', 'd_direct.txt'))}
    out = Path(args.out)
    manifest = {}
    for condition in 'abcd':
        folder = out / condition
        folder.mkdir(parents=True, exist_ok=True)
        for doc in docs:
            text = render(doc, condition, templates)
            path = folder / (doc['doc_id'] + '.txt')
            text = text.rstrip('\n') + '\n'
            path.write_text(text, encoding='utf-8')
            manifest[f"{condition}/{doc['doc_id']}"] = hashlib.sha256(text.encode()).hexdigest()
    reference = [{'doc_id': d['doc_id'], 'gold': d['label']} for d in docs if d.get('label')]
    (out / 'scoring_reference.json').write_text(
        json.dumps(reference, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=0, sort_keys=True), encoding='utf-8')
    print(f'{len(docs)} documents × 4 conditions → {out}')
    print(f'manifest entries: {len(manifest)}')


if __name__ == '__main__':
    main()
