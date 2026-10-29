"""Offline imports of existing runs and batches into the generic trace view."""

import hashlib
from html import escape
import json
from pathlib import Path
import re

from agent_trace.paths import asset_root
from agent_trace.traces import dump, read_events, write_report, route, table_cell


def optional_json(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}


def report_path(source, out=None, *, kind=None, expected_answers=None, result=None, context=None):
    source = Path(source).resolve()
    folder = source if source.is_dir() else source.parent
    if source.is_dir():
        preferred = source / 'events.jsonl'
        paths = [preferred] if preferred.is_file() else list(source.glob('*.jsonl'))
        if len(paths) != 1:
            raise ValueError('Select a single JSONL file; use --batch for an archived batch')
        source = paths[0]
    if not source.is_file():
        raise FileNotFoundError(source)
    companion = optional_json(source.with_suffix('.json'))
    metadata = optional_json(folder / 'metadata.json') or {k: companion[k] for k in ('settings', 'started') if k in companion}
    result = result if result is not None else optional_json(folder / 'result.json') or companion
    context = {**metadata.get('run_context', {}), **(context or {})}
    if kind is not None:
        context['kind'] = kind
    if expected_answers is not None:
        context['expected_answers'] = expected_answers
    context.setdefault('id', folder.name)
    events, _ = read_events(source)
    first = next((e for e in events if e['kind'] == 'model_request' and e.get('role') == 'agent'), None)
    if first and 'environment' not in context:
        system = next((m['content'] for m in first['messages'] if m.get('role') == 'system'), '')
        sha = hashlib.sha256(system.encode('utf-8')).hexdigest()
        versions = optional_json(asset_root() / 'configs/prompts/versions.json')
        known = next((v['id'] for v in versions if v['sha256'] == sha), None)
        context['environment'] = known or 'custom-' + sha[:10]
    trace = write_report(source, out or folder, metadata=metadata, result=result, context=context)
    print(dump({'report': str(Path(out or folder).resolve() / 'trace.html'),
                'main_requests': trace['main_count'], 'aux_requests': trace['aux_count'], 'status': trace['status']}))
    return trace


def report_batch(source, out=None):
    source = Path(source).resolve()
    folder = source if source.is_dir() else source.parent
    batch_path = source / 'results.json' if source.is_dir() else source
    batch = optional_json(batch_path)
    if not isinstance(batch.get('rows'), list):
        raise ValueError('Batch needs results.json with rows and relative conversation paths')
    out = Path(out or Path.cwd() / 'runs' / (folder.name + '-report')).resolve()
    # Validate all identifiers and input paths before creating any output.
    sources = []
    seen = set()
    for row in batch['rows']:
        case_id = row['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', case_id) or case_id in seen:
            raise ValueError('Batch IDs must be unique safe directory names')
        seen.add(case_id)
        case = (folder / row['conversation'].replace('\\', '/')).resolve()
        if not case.is_relative_to(folder):
            raise ValueError('Batch evidence paths must remain inside the batch directory')
        raw = case.with_suffix('.jsonl')
        if not raw.is_file():
            raise FileNotFoundError(raw)
        sources.append(raw)
    rows = []
    for row, raw in zip(batch['rows'], sources):
        result = {'text': row['text'], 'status': row['status'], 'answer_match': row['correct'],
                  'answer_match_method': 'archived fixture matcher; not a semantic judge', 'error': row.get('error')}
        trace = report_path(raw, out / row['id'], result=result,
                            context={'id': row['id'], 'question': row['question'], 'kind': 'full',
                                     'expected_answers': row.get('answers', []),
                                     'document_result_budget': batch.get('max_tool_result_tokens')})
        computed = trace['document_result_tokens_estimate']
        if row.get('tokens') is not None and row['tokens'] != computed:
            raise ValueError(f"Derived document usage differs from archived batch for {row['id']}")
        rows.append({'id': row['id'], 'question': row['question'], 'category': row.get('kind'),
                     'environment': trace['environment'], 'answer_match': trace['answer_match'],
                     'within_document_budget': row.get('within_token_limit'), 'status': trace['status'],
                     'main_requests': trace['main_count'], 'aux_requests': trace['aux_count'],
                     'document_result_tokens_estimate': computed,
                     'route': [route(t) for t in trace['turns']], 'raw_sha256': trace['raw_sha256']})
    summary = {'source_sha256': hashlib.sha256(batch_path.read_bytes()).hexdigest(),
               'new_model_requests': 0, 'runs': len(rows),
               'answer_matches': sum(r['answer_match'] is True for r in rows),
               'matched_within_document_budget': sum(r['answer_match'] is True and r['within_document_budget'] is True for r in rows),
               'evidence_support': 'not_reviewed', 'rows': rows}
    out.mkdir(parents=True, exist_ok=True)
    (out / 'batch.json').write_text(dump(summary) + '\n', encoding='utf-8')
    lines = ['# 批次 Agent 路徑總覽', '',
             f"{len(rows)} runs；答案命中 {summary['answer_matches']}；命中且文件結果用量未超標 {summary['matched_within_document_budget']}。", '',
             '由歷史事件離線重建，沒有重新呼叫模型。答案命中不等於證據支持已審查。', '',
             '| 案例 | 環境 | 答案命中 | 文件用量未超標 | 主 / AUX | 狀態 |', '|---|---|---|---|---:|---|']
    html_rows = []
    for row in rows:
        case_id = row['id']
        values = [row['environment'], row['answer_match'], row['within_document_budget'],
                  f"{row['main_requests']} / {row['aux_requests']}", row['status']]
        lines.append(f'| [{case_id}]({case_id}/trace.md) | ' + ' | '.join(table_cell(v) for v in values) + ' |')
        html_rows.append(f'<tr><td><a href="{case_id}/trace.html">{case_id}</a></td><td>{escape(row["question"])}</td>' +
                         ''.join('<td>' + escape(str(v)) + '</td>' for v in values) + '</tr>')
    (out / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    html = '<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>批次 Agent 路徑</title><style>body{font:16px/1.7 system-ui;max-width:1200px;margin:auto;padding:20px}main{overflow:auto}table{border-collapse:collapse}td,th{padding:10px;border-bottom:1px solid #aaa;text-align:left}a{color:#007d86}</style><h1>批次 Agent 路徑總覽</h1>'
    html += f'<p>{len(rows)} runs · 答案命中 {summary["answer_matches"]} · 命中且文件結果用量未超標 {summary["matched_within_document_budget"]}</p>'
    html += '<p>歷史事件離線重建；沒有新模型請求。證據支持尚未審查。<a href="README.md">Markdown</a> · <a href="batch.json">JSON</a></p><main><table><thead><tr>'
    html += ''.join('<th>' + label + '</th>' for label in ('案例', '問題', '環境', '答案命中', '文件用量未超標', '主 / AUX', '狀態'))
    html += '</tr></thead><tbody>' + ''.join(html_rows) + '</tbody></table></main></html>'
    (out / 'index.html').write_text(html, encoding='utf-8')
    print(dump({k: v for k, v in summary.items() if k != 'rows'}))
    return summary
