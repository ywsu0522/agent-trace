"""Build an optional curated study; daily run reports use traces.py.

uv run python -m agent_trace.notebook
uv run python -m agent_trace.notebook --manifest studies/d06/manifest.json
"""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import difflib
import hashlib
from html import escape
import json
from pathlib import Path
import re
import shutil

from agent_trace.tokens import count_message_tokens, count_tokens
from agent_trace.paths import asset_root
from agent_trace.traces import write_report


ROOT = asset_root()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def block(text, language='text'):
    # A retrieved document may itself contain Markdown fences.
    fence = '`' * max(3, max((len(m.group()) + 1 for m in re.finditer(r'`+', text)), default=3))
    return f'{fence}{language}\n{text}\n{fence}\n'


def tool_schemas(system):
    tools = []
    for match in re.finditer(r'^Tool: (.+)\nDescription: (.*)\nParameters JSON Schema: (.+)$', system, re.MULTILINE):
        tools.append({'name': match[1], 'description': match[2], 'parameters': json.loads(match[3])})
    return tools


def match_request(events, index):
    request = events[index]
    response = next((e for e in events[index + 1:] if e['kind'] in ('model_response', 'model_error')
                     and e.get('call_id') == request['call_id']), None)
    if response is None:
        raise ValueError(f"Missing response for {request['call_id']}")
    end = events.index(response, index + 1)
    between = events[index + 1:end]
    http = next((e for e in between if e['kind'] == 'ollama_http_request' and e.get('role') == request['role']), None)
    raw = next((e for e in between if e['kind'] == 'ollama_http_response' and http and e['http_id'] == http['http_id']), None)
    if http:
        if http['payload']['messages'] != request['messages']:
            raise ValueError('Application request differs from recorded HTTP payload')
    raw_content = raw['response'].get('message', {}).get('content') if raw else None
    if raw_content is not None and response.get('content') != raw_content:
        raise ValueError('Application completion differs from recorded HTTP response')
    parse = next((e for e in events[end + 1:] if e['kind'] == 'parse_result' and e.get('call_id') == request['call_id']), None)
    return {'call_id': request['call_id'], 'time': request['time'], 'messages': deepcopy(request['messages']),
            'completion': response.get('content'), 'error': response if response['kind'] == 'model_error' else None,
            'parse': parse, 'http_payload': http['payload'] if http else None,
            'http_response': raw['response'] if raw else None,
            'native_prompt_tokens': raw['response'].get('prompt_eval_count') if raw else None,
            'native_output_tokens': raw['response'].get('eval_count') if raw else None,
            'course_prompt_tokens': count_message_tokens(request['messages']),
            'course_completion_tokens': count_tokens(response.get('content', '')),
            'seconds': raw.get('seconds') if raw else None,
            'source_lines': {'request': index + 1, 'response': end + 1}}


def evidence_paths(entry, repo, archive=None):
    def resolve(key, fallback):
        path = repo / entry[key] if entry.get(key) else None
        if path is not None and path.exists():
            return path
        captured = archive / fallback if archive is not None else None
        if captured is not None and captured.exists():
            return captured
        if key == 'result':
            return None
        raise FileNotFoundError(f'Missing {key} for {entry["id"]}: {path}')
    return (resolve('source', f'evidence/{entry["id"]}.jsonl'),
            resolve('metadata', f'metadata/{entry["id"]}.json'),
            resolve('result', f'metadata/{entry["id"]}.result.json'))


def normalize(entry, repo, archive=None, expected_answers=()):
    source, metadata_path, result_path = evidence_paths(entry, repo, archive)
    events = [json.loads(line) for line in source.read_text(encoding='utf-8').splitlines()]
    main_indices = [i for i, e in enumerate(events) if e['kind'] == 'model_request' and e['role'] == 'agent']
    if not main_indices:
        raise ValueError(f'No main requests: {source}')
    result = load(result_path) if result_path else {}
    metadata = load(metadata_path)
    settings = deepcopy(metadata.get('settings', {}))
    turns = []
    previous = []
    for ordinal, index in enumerate(main_indices, 1):
        bound = main_indices[ordinal] if ordinal < len(main_indices) else len(events)
        request = events[index]
        turn = match_request(events, index)
        common = 0
        for old, new in zip(previous, turn['messages']):
            if old != new:
                break
            common += 1
        turn.update(number=ordinal, recorded_turn=request['turn'], source_turn=entry.get('source_turn'),
                    unchanged_prefix=common, tools=[], aux=[])
        pending = None
        for j in range(index + 1, bound):
            event = events[j]
            if event['kind'] == 'agent_event':
                item = event['event']
                if item['type'] == 'tool_call':
                    pending = {'name': item['name'], 'args': item['args'], 'status': 'no_result', 'content': None,
                               'source_line': j + 1}
                    turn['tools'].append(pending)
                elif item['type'] == 'tool_result':
                    if pending is None or pending['name'] != item['name']:
                        raise ValueError('Tool result without matching call')
                    pending.update(status=item['status'], content=item['content'], result_source_line=j + 1)
                    try:
                        pending['value'] = json.loads(item['content'])
                    except (ValueError, TypeError):
                        pending['value'] = None
            elif event['kind'] == 'model_request' and event['role'] != 'agent':
                aux = match_request(events, j)
                aux['number'] = len(turn['aux']) + 1
                turn['aux'].append(aux)
        if turn['parse'] is None:
            raise ValueError('Trace lacks a recorded parse_result; do not infer historical decisions using the current parser')
        turn['parse']['source'] = 'recorded'
        turn['decision'] = ('parse_error' if turn['parse']['error'] else
                            turn['parse']['tool_call']['name'] if turn['parse']['tool_call'] else 'final_answer')
        turn['answer_in_request'] = any(answer in m['content'] for m in turn['messages'] for answer in expected_answers)
        previous = turn['messages']
        turns.append(turn)
    if result.get('turns'):
        final, status = result['turns'][-1]['agent'], result['turns'][-1]['status']
    else:
        final = result.get('text', turns[-1]['completion'])
        status = result.get('status', 'decision_only' if entry['kind'] != 'full' else 'unrecorded')
    systems = [m['content'] for m in turns[0]['messages'] if m['role'] == 'system']
    if len(systems) != 1:
        raise ValueError('Expected one system message')
    model = settings.get('model')
    tags = metadata.get('ollama_tags', {}).get('models', [])
    tag = next((m for m in tags if m.get('name') == model), metadata.get('model_tag', {}))
    return {**entry, 'started': events[main_indices[0]]['time'], 'turns': turns, 'system': systems[0],
            'settings_recorded': settings, 'model_digest': tag.get('digest'),
            'ollama_version': metadata.get('ollama_version'), 'source_hashes': metadata.get('source_hashes'),
            'status': status, 'final': final, 'answer_match': any(answer in (final or '') for answer in expected_answers) if expected_answers and entry['kind'] == 'full' else None,
            'answer_match_method': 'accepted substring; not a semantic judge',
            'main_count': len(turns), 'aux_count': sum(len(t['aux']) for t in turns),
            'tool_count': sum(len(t['tools']) for t in turns),
            'read_count': sum(c['name'] == 'read_doc' for t in turns for c in t['tools']),
            'parse_errors': sum(bool(t['parse']['error']) for t in turns),
            'raw_sha256': digest(source.read_bytes())}


def markdown_run(run, out):
    lines = [f"# {run['label']}", '', '[返回研究首頁](../../README.md)', '', run['notes'], '',
             f"類型：{run['kind']}；環境：[{run['environment']}](../environments/{run['environment']}.system.txt)；"
             f"主 requests：{run['main_count']}；aux：{run['aux_count']}；status：{run['status']}。", '',
             f"原始 JSONL：[證據副本](../evidence/{run['id']}.jsonl)；SHA-256：`{run['raw_sha256']}`。", '',
             '`done` 只代表流程結束。probe/replay 的合法 tool call 未執行；aux 不算主 turn。', '',
             '| Turn | 決策 | 執行狀態 | Native prompt tokens |', '|---:|---|---|---:|']
    for t in run['turns']:
        states = ', '.join(c['status'] for c in t['tools']) or ('未執行' if t['parse'].get('tool_call') else '無工具結果')
        lines.append(f"| [T{t['number']}](#turn-{t['number']}) | {t['decision']} | {states} | {t['native_prompt_tokens'] if t['native_prompt_tokens'] is not None else '未記錄'} |")
    for t in run['turns']:
        n = t['number']
        lines += ['', f'<a id="turn-{n}"></a>', f'## Turn {n}', '',
                  f"完整 request 有 {len(t['messages'])} 個 messages；與前一 request 相同的前綴有 {t['unchanged_prefix']} 個，仍實際送出。", '',
                  '### Completion', '', block(t['completion'] or ''),
                  '### Tool calling', '', block(json.dumps({'parse_error': t['parse']['error'], 'parsed_call': t['parse']['tool_call'],
                                                           'execution': [{'name': c['name'], 'args': c['args'], 'status': c['status']} for c in t['tools']]}, ensure_ascii=False, indent=2), 'json'),
                  '<details><summary>展開完整 request messages（原文，未省略）</summary>', '']
        for i, m in enumerate(t['messages']):
            lines += [f"#### Message {i} · {m['role']}", '', block(m['content'])]
        lines += ['</details>', '', f"[完整 request JSON]({run['id']}/turn-{n:02d}.request.json)", '']
        if t['http_payload']:
            lines += [f"[實際 HTTP payload]({run['id']}/turn-{n:02d}.http-request.json) · [完整 HTTP response]({run['id']}/turn-{n:02d}.http-response.json)", '']
        else:
            lines += ['此歷史 trace 未保存 HTTP JSON；以上為 application 層完整 messages，native token 數未記錄。', '']
        for c in t['tools']:
            lines += [f"<details><summary>{c['name']} · {c['status']} · 完整工具結果</summary>", '',
                      block(c['content'] or ''), '</details>', '']
        for aux in t['aux']:
            lines += [f"<details><summary>AUX {aux['number']} · 完整 request / completion</summary>", '',
                      '此 request 在工具內部發生，不增加主 turn。', '', block(json.dumps(aux['messages'], ensure_ascii=False, indent=2), 'json'),
                      'Completion：', '', block(aux['completion'] or ''), '</details>', '']
    (out / 'traces' / f"{run['id']}.md").write_text('\n'.join(lines) + '\n', encoding='utf-8')


def build(manifest_path, out, repo=ROOT):
    manifest = load(manifest_path)
    out.mkdir(parents=True, exist_ok=True)
    for sub in ('traces', 'evidence', 'metadata', 'environments'):
        (out / sub).mkdir(exist_ok=True)
    archive = manifest_path.parent / 'record'
    expected = manifest.get('expected_answers', [manifest['expected_answer']] if manifest.get('expected_answer') else [])
    runs = [normalize(entry, repo, archive, expected) for entry in manifest['runs']]
    environments = {}
    for run in runs:
        system_hash = digest(run['system'].encode())
        declared = next((e for e in manifest.get('environment_versions', []) if e['sha256'] == system_hash), None)
        if declared:
            eid, name, parent = declared['id'], declared['label'], declared['parent']
        else:
            eid, name, parent = 'S-' + system_hash[:10], '新研究環境 ' + system_hash[:10], None
        env = {'id': eid, 'label': name, 'parent': parent, 'system': run['system'],
               'sha256': digest(run['system'].encode()), 'tools': tool_schemas(run['system'])}
        if eid in environments and environments[eid]['sha256'] != env['sha256']:
            raise ValueError(f'Different prompts mapped to {eid}; register a new environment')
        environments[eid] = env
        run['environment'] = eid
        paths = evidence_paths(run, repo, archive)
        targets = [out / 'evidence' / f"{run['id']}.jsonl", out / 'metadata' / f"{run['id']}.json", out / 'metadata' / f"{run['id']}.result.json"]
        for source_path, target in zip(paths, targets):
            if source_path and source_path.resolve() != target.resolve():
                shutil.copyfile(source_path, target)
        for t in run['turns']:
            folder = out / 'traces' / run['id']
            folder.mkdir(exist_ok=True)
            write_json(folder / f"turn-{t['number']:02d}.request.json", t['messages'])
            (folder / f"turn-{t['number']:02d}.completion.txt").write_text(t['completion'] or '', encoding='utf-8')
            if t['http_payload']:
                write_json(folder / f"turn-{t['number']:02d}.http-request.json", t['http_payload'])
                write_json(folder / f"turn-{t['number']:02d}.http-response.json", t['http_response'])
        markdown_run(run, out)
        # Every run gets the same compact view as a fresh CLI execution. The
        # richer historical comparison UI is an optional study asset below.
        write_report(paths[0], out / 'runs' / run['id'], metadata=load(paths[1]),
                     result={'text': run['final'], 'status': run['status'], 'answer_match': run['answer_match']},
                     context={'id': run['id'], 'question': manifest['question'], 'kind': run['kind'],
                              'environment': eid, 'expected_answers': expected})
    for eid, env in environments.items():
        before = environments[env['parent']]['system'] if env['parent'] else ''
        env['diff'] = '\n'.join(difflib.unified_diff(before.splitlines(), env['system'].splitlines(),
                                                   fromfile=env['parent'] or 'empty', tofile=eid, lineterm=''))
        (out / 'environments' / f'{eid}.system.txt').write_text(env['system'], encoding='utf-8')
        (out / 'environments' / f'{eid}.diff').write_text(env['diff'] + '\n', encoding='utf-8')
        write_json(out / 'environments' / f'{eid}.tools.json', env['tools'])
    corpus = {**manifest, 'built_at': datetime.now(timezone.utc).isoformat(), 'runs': runs,
              'environments': sorted(environments.values(), key=lambda e: e['id'])}
    if manifest.get('expected_source'):
        source = repo / manifest['expected_source']['path']
        if manifest['expected_source'].get('sha256') and digest(source.read_bytes()) != manifest['expected_source']['sha256']:
            raise ValueError('Ground-truth source changed; create a new study version instead of rewriting evidence')
        truth_target = out / 'evidence' / source.name
        if source.resolve() != truth_target.resolve():
            shutil.copyfile(source, truth_target)
        corpus['ground_truth_sha256'] = digest(source.read_bytes())
    corpus['counts'] = {'runs': len(runs), 'full_runs': sum(r['kind'] == 'full' for r in runs),
                        'main_requests': sum(r['main_count'] for r in runs), 'aux_requests': sum(r['aux_count'] for r in runs)}
    write_json(out / 'records.json', corpus)
    write_json(out / 'manifest.snapshot.json', manifest)
    checks = {'schema_version': 1, 'raw_hashes': {r['id']: r['raw_sha256'] for r in runs},
              'raw_copies_verified': all(digest((out / 'evidence' / f"{r['id']}.jsonl").read_bytes()) == r['raw_sha256'] for r in runs),
              'request_exports_verified': all(load(out / 'traces' / r['id'] / f"turn-{t['number']:02d}.request.json") == t['messages'] for r in runs for t in r['turns']),
              'native_http_requests': sum(t['http_payload'] is not None for r in runs for t in r['turns']),
              'application_only_requests': sum(t['http_payload'] is None for r in runs for t in r['turns'])}
    write_json(out / 'integrity.json', checks)
    overview = ['# ' + manifest['title'] + '：實驗總表', '', '[研究首頁](../README.md) · [離線互動頁](index.html)', '',
                '| 紀錄 | 類型 | 環境 | 主 / aux | read_doc | 格式錯誤 | 接受答案比對 |', '|---|---|---|---:|---:|---:|---|']
    for r in runs:
        verdict = ('符合' if r['answer_match'] else '不符合') if r['kind'] == 'full' else '不評分'
        overview.append(f"| [{r['label']}](runs/{r['id']}/trace.md) | {r['kind']} | [{r['environment']}](environments/{r['environment']}.system.txt) | {r['main_count']} / {r['aux_count']} | {r['read_count']} | {r['parse_errors']} | {verdict} |")
    (out / 'OVERVIEW.md').write_text('\n'.join(overview) + '\n', encoding='utf-8')
    if manifest.get('viewer_template'):
        template = (manifest_path.parent / manifest['viewer_template']).read_text(encoding='utf-8')
        payload = json.dumps(corpus, ensure_ascii=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
        (out / 'research.html').write_text(template.replace('__RESEARCH_DATA__', payload), encoding='utf-8')
    rows = []
    for run in runs:
        verdict = '未評分' if run['answer_match'] is None else '命中' if run['answer_match'] else '未命中'
        cells = [run['kind'], run['environment'], f"{run['main_count']} / {run['aux_count']}", run['status'], verdict]
        rows.append(f'<tr><td><a href="runs/{escape(run["id"], quote=True)}/trace.html">{escape(run["label"])}</a></td>' +
                    ''.join('<td>' + escape(str(c)) + '</td>' for c in cells) + '</tr>')
    landing = '<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + escape(manifest['title']) + '</title><style>body{font:16px/1.7 system-ui;max-width:1100px;margin:auto;padding:24px}a{color:#007d86}main{overflow:auto}table{width:100%;border-collapse:collapse}td,th{padding:10px;text-align:left;border-bottom:1px solid #aaa}td:first-child{min-width:200px}</style><h1>' + escape(manifest['title']) + '</h1><p>' + escape(manifest['question']) + '</p>'
    landing += '<p>選擇一次 run，先看精簡路徑；每個 turn 的完整內容預設收合。答案命中與證據支持分開評估。</p><p><a href="OVERVIEW.md">Markdown 總表</a> · <a href="../README.md">研究摘要</a>'
    if manifest.get('viewer_template'):
        landing += ' · <a href="research.html">詳細研究比較與環境 diff</a>'
    landing += '</p><main><table><thead><tr>' + ''.join('<th>' + c + '</th>' for c in ('Run', '類型', '環境', '主 / AUX', '停止狀態', '答案比對')) + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></main></html>'
    (out / 'index.html').write_text(landing, encoding='utf-8')
    if not checks['raw_copies_verified'] or not checks['request_exports_verified']:
        raise ValueError('Integrity verification failed')
    print(json.dumps({'output': str(out), **corpus['counts'], 'environments': len(environments), 'integrity': checks}, ensure_ascii=False, indent=2))
    return corpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'studies/d06/manifest.json')
    parser.add_argument('--out', type=Path, default=Path.cwd() / 'studies/d06/record')
    args = parser.parse_args()
    build(args.manifest.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
