"""A 主实验（结构化 v6）"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

CONDITION = 'A'
LABELS = ('HATE', 'NON_HATE')
MAX_ATTEMPTS = 3
SLEEP_BASE = 5.0
RETRY_AFTER_CAP = 60.0
STOP_HTTP = (401, 402)
UNAVAILABLE_CODES = ('model_not_found', 'invalid_model', 'model_not_available', 'no_available_channel')
RETRY_STATUSES = ('invalid_output', 'http_error', 'transport_unknown', 'route_mismatch', 'calling')

_JSON_LABEL = re.compile(r'"document_label"\s*:\s*"(HATE|NON_HATE)"')
_TEXT_LABEL = re.compile(r'document[_ ]label\s*[:：=]\s*(HATE|NON_HATE)', re.I)
_TOKEN = re.compile(r'\b(HATE|NON_HATE)\b')


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding='utf-8')
    os.replace(tmp, path)


def read_json(path: Path, default=None):
    if not Path(path).exists():
        return default
    return json.loads(Path(path).read_text(encoding='utf-8'))


def parse_label(text):
    if not isinstance(text, str) or not text.strip():
        return None, 'empty'
    text = text.strip()
    fence = re.match(r'^```[a-zA-Z]*\s*(.*?)\s*```$', text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        payload = json.loads(text)
        if isinstance(payload, dict) and payload.get('document_label') in LABELS:
            return payload['document_label'], 'whole_json'
    except ValueError:
        pass
    hits = _JSON_LABEL.findall(text)
    if len(set(hits)) == 1:
        return hits[0], 'embedded_json'
    hits = _TEXT_LABEL.findall(text)
    if len(set(h.upper() for h in hits)) == 1:
        return hits[0].upper(), 'explicit_text'
    hits = _TOKEN.findall(text[-400:])
    if len(set(hits)) == 1:
        return hits[0], 'terminal_token'
    return None, 'ambiguous_or_missing'


def stop_now(record) -> bool:
    if not record:
        return False
    status = record.get('http_status')
    if status in STOP_HTTP:
        return True
    if status == 403 and record.get('api_error_code') != 'content_policy_violation':
        return True
    return status in (400, 404, 503) and record.get('api_error_code') in UNAVAILABLE_CODES


def backoff(attempt, record=None) -> float:
    if record and record.get('http_status') == 429:
        raw = record.get('retry_after')
        try:
            return min(float(raw), RETRY_AFTER_CAP)
        except (TypeError, ValueError):
            return RETRY_AFTER_CAP
    return SLEEP_BASE * attempt


def endpoint_of(base: str, protocol: str) -> str:
    return base.rstrip('/') + ('/responses' if protocol == 'responses' else '/chat/completions')


def build_body(model, protocol, content, max_tokens, effort):
    if protocol == 'responses':
        body = {'model': model, 'max_output_tokens': max_tokens,
                'input': [{'role': 'user', 'content': content}]}
        if effort:
            body['reasoning'] = {'effort': effort}
        return body
    body = {'model': model, 'max_tokens': max_tokens,
            'messages': [{'role': 'user', 'content': content}]}
    if effort:
        body['reasoning_effort'] = effort
    return body


def extract_content(payload):
    if not isinstance(payload, dict):
        return ''
    if isinstance(payload.get('output_text'), str):
        return payload['output_text']
    choices = payload.get('choices')
    if isinstance(choices, list) and choices:
        message = choices[0].get('message') or {}
        if isinstance(message.get('content'), str):
            return message['content']
    parts = []
    for item in payload.get('output') or []:
        for block in (item.get('content') or []):
            if block.get('type') in ('output_text', 'text') and isinstance(block.get('text'), str):
                parts.append(block['text'])
    return ''.join(parts)


def call(settings, content, doc_id, out_dir: Path) -> dict:
    base, key = settings['base_url'], settings['api_key']
    protocol = settings['protocol']
    endpoint = endpoint_of(base, protocol)
    body = build_body(settings['model'], protocol, content, settings['max_tokens'], settings['effort'])
    identity = digest(json.dumps({'condition': CONDITION, 'endpoint': endpoint, 'body': body},
                                 sort_keys=True, ensure_ascii=False).encode())
    record_path = out_dir / settings['key'] / 'calls' / (doc_id + '.json')
    existing = read_json(record_path)
    if existing:
        if existing.get('request_sha256') != identity:
            raise RuntimeError(doc_id + ': 输入或参数已变，拒绝复用旧记录')
        if existing.get('status') == 'valid' or stop_now(existing) \
                or existing.get('attempt_number', 0) >= MAX_ATTEMPTS:
            return existing
    latest = existing or {}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempt_path = out_dir / settings['key'] / 'attempts' / (doc_id + '_' + str(attempt) + '.json')
        if attempt_path.exists():
            latest = read_json(attempt_path)
            if latest.get('status') == 'calling':
                latest.update(status='transport_unknown', error='上次进程在落盘前中断')
                save_json(attempt_path, latest)
        else:
            latest = {'doc_id': doc_id, 'request_model': settings['key'], 'model': settings['model'],
                       'condition': CONDITION, 'request_sha256': identity, 'attempt_number': attempt,
                       'status': 'calling', 'started_at': now()}
            save_json(attempt_path, latest)
            save_json(record_path, latest)
            try:
                response = requests.post(endpoint, json=body, timeout=(20, 600),
                                         headers={'Authorization': 'Bearer ' + key,
                                                  'Content-Type': 'application/json'})
                latest['http_status'] = response.status_code
                if response.status_code == 429:
                    latest['retry_after'] = response.headers.get('Retry-After')
                try:
                    payload = response.json()
                except ValueError:
                    payload = {'raw_text': response.text}
                save_json(out_dir / settings['key'] / 'raw' / (doc_id + '_' + str(attempt) + '.json'),
                          payload)
                if response.status_code == 200:
                    latest['response_model'] = payload.get('model')
                    label, method = parse_label(extract_content(payload))
                    latest['label_parse_method'] = method
                    if label is None:
                        latest.update(status='invalid_output', error='标签无法无歧义解析')
                    else:
                        latest.update(status='valid', label=label)
                else:
                    latest['status'] = 'http_error'
                    error = payload.get('error') if isinstance(payload, dict) else None
                    if isinstance(error, dict):
                        latest['api_error_code'] = error.get('code') or error.get('type')
            except requests.RequestException as exc:
                latest.update(status='transport_unknown', error=type(exc).__name__)
            latest['completed_at'] = now()
            save_json(attempt_path, latest)
        save_json(record_path, latest)
        if latest.get('status') == 'valid' or stop_now(latest):
            break
        if attempt < MAX_ATTEMPTS:
            time.sleep(backoff(attempt, latest))
    return latest


def score(pairs):
    correct = {label: 0 for label in LABELS}
    total = {label: 0 for label in LABELS}
    statuses = {}
    for gold, record in pairs:
        status = (record or {}).get('status', 'not_run')
        statuses[status] = statuses.get(status, 0) + 1
        if gold not in LABELS:
            continue
        total[gold] += 1
        if status == 'valid' and record.get('label') == gold:
            correct[gold] += 1
    recalls = {k: (correct[k] / total[k] if total[k] else 0.0) for k in LABELS}
    return {'n': len(pairs), 'statuses': statuses, 'correct': correct,
            'recalls': recalls, 'BA': sum(recalls.values()) / 2}


def report(results, settings):
    print('\n条件 ' + CONDITION + '｜单轮')
    print('%-24s %6s %6s %10s %10s %8s' % ('模型', 'valid', '完成', 'HATE召回', 'NON召回', 'BA'))
    for key, row in results.items():
        s = row['score']
        print('%-24s %6d %6d %9.2f%% %9.2f%% %7.2f%%' % (
            settings[key]['model'], s['statuses'].get('valid', 0),
            sum(v for k, v in s['statuses'].items() if k not in ('not_run', 'calling')),
            s['recalls']['HATE'] * 100, s['recalls']['NON_HATE'] * 100, s['BA'] * 100))
        if s['statuses'].get('valid', 0) != s['n']:
            print('%-24s 状态分布 %s' % ('', s['statuses']))


def collect(args):
    """Render condition A inputs from the released structured source."""
    import build_inputs

    docs = build_inputs.load_source(Path(args.source))
    tpl = (Path(args.templates) / 'a_structured_v6.txt').read_text(encoding='utf-8')
    out = []
    for doc in docs:
        body = '\n'.join(f"{u['id']}\t{u['text']}" for u in doc['units'])
        out.append({'doc_id': doc['doc_id'], 'gold': doc.get('label'),
                    'content': tpl.replace('{{DOCUMENT}}', body)})
    return out


def main():
    parser = argparse.ArgumentParser(description=CONDITION + ' 条件单轮运行')
    parser.add_argument('--source', required=True, help='structured source (.json/.json.gz)')
    parser.add_argument('--templates', required=True, help='directory holding a_structured_v6.txt')
    parser.add_argument('--out', default='runs', help='输出目录')
    parser.add_argument('--model-name', required=True, help='服务端模型名')
    parser.add_argument('--key', default=None, help='本地模型标识，默认用模型名')
    parser.add_argument('--protocol', choices=('chat', 'responses'), default='chat')
    parser.add_argument('--base-url', default=os.environ.get('API_BASE', ''))
    parser.add_argument('--api-key', default=os.environ.get('API_KEY', ''))
    parser.add_argument('--max-tokens', type=int, default=12288)
    parser.add_argument('--effort', default=None, help='reasoning effort，留空则不传')
    parser.add_argument('--workers', type=int, default=5)
    parser.add_argument('--limit', type=int, default=0, help='只跑前 N 篇')
    args = parser.parse_args()
    if not args.base_url:
        sys.exit('缺少端点：用 --base-url 或环境变量 API_BASE')
    if not args.api_key:
        sys.exit('缺少密钥：用 --api-key 或环境变量 API_KEY')

    key = args.key or re.sub(r'[^A-Za-z0-9._-]+', '-', args.model_name)
    settings = {'base_url': args.base_url, 'api_key': args.api_key, 'protocol': args.protocol,
                'model': args.model_name, 'max_tokens': args.max_tokens, 'effort': args.effort,
                'key': key}
    docs = collect(args)
    if args.limit:
        docs = docs[:args.limit]
    out_dir = Path(args.out) / CONDITION
    out_dir.mkdir(parents=True, exist_ok=True)
    todo = [d for d in docs
            if not read_json(out_dir / key / 'calls' / (d['doc_id'] + '.json'))]
    print('共 %d 篇，已 valid %d 篇，待跑 %d 篇' % (len(docs), len(docs) - len(todo), len(todo)))
    dead = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(call, settings, d['content'], d['doc_id'], out_dir): d['doc_id']
                   for d in todo}
        done = 0
        for future in as_completed(futures):
            doc_id = futures[future]
            try:
                record = future.result()
            except Exception as exc:
                print('异常 %s %s' % (doc_id, type(exc).__name__))
                continue
            done += 1
            if stop_now(record):
                dead.append(doc_id)
            if done % 25 == 0:
                print('进度 %d / %d' % (done, len(todo)))
    if dead:
        print('端点或模型不可用，已停止该模型，受影响槽位 %d 个' % len(dead))
    pairs = [(d.get('gold'), read_json(out_dir / key / 'calls' / (d['doc_id'] + '.json'))) for d in docs]
    result = {key: {'score': score(pairs)}}
    save_json(out_dir / key / 'summary.json', result[key]['score'])
    report(result, {key: settings})


if __name__ == '__main__':
    main()
