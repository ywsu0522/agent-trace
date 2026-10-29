"""Derive compact, factual run reports from recorded events; never call a model.

The JSONL is evidence. Reports are replaceable views, including when a run was
interrupted. Missing completions/parses stay missing; historical text is never
reparsed with today's protocol implementation.
"""

from copy import deepcopy
import hashlib
from html import escape
import json
from pathlib import Path
import re
import shutil

from agent_trace.tokens import count_tokens


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def read_events(path):
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    events, warnings = [], []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            if number != len(lines):
                raise ValueError(f'Invalid JSONL at line {number}; evidence was not changed')
            warnings.append('最後一筆 JSONL 不完整；只呈現先前已完整寫入的事件。')
            break
        events.append({**event, '_line': number})
    return events, warnings


def request_record(events, request):
    call_id = request.get('call_id')
    start = events.index(request)
    response = next((e for e in events[start + 1:] if e['kind'] in ('model_response', 'model_error')
                     and e.get('call_id') == call_id), None)
    end = events.index(response) if response else len(events)
    candidates = [e for e in events[start + 1:end] if e['kind'] == 'ollama_http_request'
                  and e.get('role') == request.get('role')]
    http = next((e for e in candidates if e.get('call_id') == call_id), None)
    if http is None:
        # Older traces did not attach call_id to HTTP events. Only accept an
        # unambiguous match; concurrent auxiliary requests can interleave.
        matches = [e for e in candidates if e.get('payload', {}).get('messages') == request['messages']]
        http = matches[0] if len(matches) == 1 else None
    raw = next((e for e in events if e['kind'] in ('ollama_http_response', 'ollama_http_error')
                and http and e.get('http_id') == http.get('http_id')), None)
    parsed = next((e for e in events if e['kind'] == 'parse_result' and e.get('call_id') == call_id), None)
    checks = []
    if http and http.get('payload', {}).get('messages') != request['messages']:
        checks.append('application request 與 HTTP messages 不一致。')
    native_content = (raw or {}).get('response', {}).get('message', {}).get('content')
    if native_content is not None and response and response['kind'] == 'model_response' and response.get('content') != native_content:
        checks.append('application completion 與 HTTP content 不一致。')
    return {'call_id': call_id, 'time': request.get('time'), 'model': request.get('model'),
            'messages': deepcopy(request['messages']),
            'completion': response.get('content') if response else None,
            'error': ({'type': response.get('error_type'), 'message': response.get('message')}
                      if response and response['kind'] == 'model_error' else None),
            'response_recorded': response is not None,
            'parse': deepcopy(parsed) if parsed else None,
            'http_request': deepcopy(http.get('payload')) if http else None,
            'http_response': deepcopy(raw.get('response')) if raw else None,
            'seconds': raw.get('seconds') if raw else None,
            'source_lines': {'request': request['_line'], 'response': response['_line'] if response else None},
            'integrity_warnings': checks}


def build_trace(events, *, metadata=None, result=None, context=None):
    metadata, result, context = metadata or {}, result or {}, context or {}
    settings = metadata.get('settings', {})
    expected = context.get('expected_answers', settings.get('expected_answers', []))
    if isinstance(expected, str):
        expected = [expected]
    expected = [s for s in (expected or []) if isinstance(s, str) and s]
    kind = context.get('kind', settings.get('mode', 'full'))
    main = [i for i, e in enumerate(events) if e['kind'] == 'model_request' and e.get('role') == 'agent']
    turns, previous, windows, queries = [], [], {}, set()
    doc_tokens = 0
    for ordinal, index in enumerate(main, 1):
        request = events[index]
        stop = main[ordinal] if ordinal < len(main) else len(events)
        segment = events[index + 1:stop]
        turn = request_record(events, request)
        turn.update(number=ordinal, send_id=request.get('send_id', 1), recorded_turn=request.get('turn'),
                    tools=[], aux=[], annotations=[])
        common = 0
        for old, new in zip(previous, turn['messages']):
            if old != new:
                break
            common += 1
        turn['unchanged_prefix'] = common
        previous = turn['messages']
        parsed = turn['parse']
        intent = parsed.get('tool_call') if parsed else None
        turn['decision'] = ('model_error' if turn['error'] else 'incomplete_request' if not turn['response_recorded']
                            else 'parse_unrecorded' if parsed is None else 'parse_error' if parsed.get('error')
                            else intent['name'] if intent else 'final_answer')
        if parsed and parsed.get('error'):
            turn['annotations'].append('工具格式解析失敗；不代表工具已執行。')
        if not turn['response_recorded']:
            turn['annotations'].append('未記錄到 response；可能仍在執行或已中斷。')
        for event in segment:
            if event['kind'] == 'model_request' and event.get('role') != 'agent':
                aux = request_record(events, event)
                aux.update(number=len(turn['aux']) + 1, tool=event.get('tool'))
                turn['aux'].append(aux)
            if event['kind'] != 'agent_event':
                continue
            item = event['event']
            if item['type'] == 'tool_call':
                turn['tools'].append({'name': item['name'], 'args': deepcopy(item['args']),
                                      'status': 'no_result', 'content': None, 'annotations': [],
                                      'source_line': event['_line'], 'next_request_contains_result': None})
            elif item['type'] == 'tool_result':
                tool = next((t for t in reversed(turn['tools']) if t['name'] == item['name'] and t['status'] == 'no_result'), None)
                if tool is None:
                    turn['annotations'].append('工具結果缺少對應的呼叫事件；請核對原始事件。')
                    continue
                tool.update(status=item['status'], content=item['content'], result_source_line=event['_line'])
        if intent and not turn['tools']:
            turn['annotations'].append('解析出工具意圖，但沒有工具呼叫事件；probe／replay 不執行工具。'
                                       if kind != 'full' else '解析出工具意圖，但未記錄工具呼叫事件。')
        for tool in turn['tools']:
            try:
                value = json.loads(tool['content'])
            except (ValueError, TypeError):
                value = None
            tool['value'] = value
            if tool['status'] == 'ok' and isinstance(value, list):
                tool['result_count'] = len(value)
                tool['annotations'].append(f'回傳 {len(value)} 筆結果。')
                tool['result_ids'] = [v.get('doc_id', v.get('id')) for v in value if isinstance(v, dict)]
            if tool['status'] == 'ok' and tool['name'] in ('search_docs', 'read_doc'):
                doc_tokens += count_tokens(tool['content'])
            if tool['status'] == 'ok' and tool['name'] == 'read_doc' and isinstance(value, dict):
                keys = ('start_line', 'end_line', 'total_lines')
                if all(isinstance(value.get(k), int) for k in keys):
                    a, b, total = (value[k] for k in keys)
                    tool['window'] = {k: value[k] for k in ('doc_id', *keys) if k in value}
                    tool['annotations'].append(f'第 {a}–{b} / {total} 行；' + ('尚有後續內容。' if b < total else '已到文件結尾。'))
                    doc = value.get('doc_id', tool['args'].get('doc_id'))
                    seen = windows.setdefault(doc, [])
                    if (a, b) in seen:
                        tool['annotations'].append('重複讀取相同文件視窗。')
                    elif seen and a == seen[-1][1] + 1:
                        tool['annotations'].append('接續前一次視窗。')
                    seen.append((a, b))
            if tool['name'].startswith('search_') and 'query' in tool['args']:
                query = (tool['name'], json.dumps(tool['args']['query'], sort_keys=True))
                if query in queries:
                    tool['annotations'].append('重複相同工具與查詢字串。')
                queries.add(query)
            if ordinal < len(main) and tool['content']:
                following = events[main[ordinal]]['messages']
                included = any(tool['content'] in str(m.get('content', '')) for m in following)
                tool['next_request_contains_result'] = included
                tool['annotations'].append('完整結果文字出現在下一個主 request。' if included
                                           else '未在下一個主 request 找到完整結果文字。')
        turns.append(turn)
    last_send = next((e for e in reversed(events) if e['kind'] == 'send_complete'), {})
    legacy_turns = result.get('turns') or []
    final = result.get('text', legacy_turns[-1].get('agent', '') if legacy_turns else last_send.get('text', ''))
    status = result.get('status', legacy_turns[-1].get('status') if legacy_turns else last_send.get('status', 'incomplete'))
    question = context.get('question', settings.get('question'))
    if question is None:
        question = next((e.get('message') for e in events if e['kind'] == 'send_start' and e.get('message')), None)
    if question is None and main:
        question = next((m['content'] for m in reversed(events[main[0]]['messages']) if m.get('role') == 'user'), '')
    if 'answer_match' in result:
        match, method = result['answer_match'], result.get('answer_match_method', 'recorded result; not a semantic judge')
    else:
        match = any(s in final for s in expected) if expected and kind == 'full' and status == 'done' else None
        method = 'exact substring; not a semantic judge' if expected else 'not evaluated'
    first = next((t['number'] for t in turns if expected and any(s in str(m.get('content', ''))
                  for m in t['messages'] for s in expected)), None)
    warnings = [w for t in turns for w in t['integrity_warnings']]
    budget = context.get('document_result_budget', settings.get('document_result_budget'))
    if budget is not None and doc_tokens > budget:
        warnings.append(f'文件工具結果估算用量 {doc_tokens} 超過設定的 {budget}。')
    return {'schema_version': 1, 'id': context.get('id', result.get('id', 'run')), 'question': question or '',
            'kind': kind, 'environment': context.get('environment', result.get('condition', settings.get('environment'))),
            'status': status, 'final': final, 'error': result.get('error'), 'answer_match': match,
            'answer_match_method': method, 'evidence_support': 'not_reviewed',
            'expected_answers': expected, 'first_accepted_string_request': first,
            'accepted_string_note': '只檢查 request 是否包含接受字串；不代表已取得支持證據。',
            'main_count': len(turns), 'aux_count': sum(len(t['aux']) for t in turns),
            'tool_attempts': sum(len(t['tools']) for t in turns),
            'document_result_tokens_estimate': doc_tokens, 'document_result_budget': budget,
            'token_metric': 'ceil(characters/4), document tool results only; not native model tokens',
            'warnings': warnings, 'turns': turns, 'settings': deepcopy(settings)}


def short(value, limit=180):
    text = ' '.join((value if isinstance(value, str) else dump(value)).split())
    return text if len(text) <= limit else text[:limit] + '…'


def route(turn):
    intent = (turn.get('parse') or {}).get('tool_call')
    if intent:
        return intent['name'] + '(' + short(intent['args'], 220) + ')'
    return turn['decision']


def notes(turn):
    return turn['annotations'] + [f"{tool['name']}: {note}" for tool in turn['tools'] for note in tool['annotations']]


def fence(text, language='text'):
    text = text if isinstance(text, str) else dump(text)
    ticks = '`' * max(3, max((len(m.group()) + 1 for m in re.finditer(r'`+', text)), default=3))
    return f'{ticks}{language}\n{text}\n{ticks}'


def table_cell(text):
    return escape(str(text), quote=False).replace('|', '&#124;').replace('\n', '<br>')


def markdown(trace):
    lines = ['# Agent run 路徑', '', fence(trace['question']), '',
             f"環境：{trace['environment'] or '未標記'} · 類型：{trace['kind']} · 狀態：{trace['status']}", '',
             f"主 requests：{trace['main_count']} · aux requests：{trace['aux_count']} · 工具嘗試：{trace['tool_attempts']}", '',
             f"答案比對：{trace['answer_match']}（{trace['answer_match_method']}）；證據支持：尚未審查。", '',
             '[結構化 trace](trace.json) · [原始事件](events.jsonl)', '',
             '| Turn | 路徑 | 工具結果狀態 | AUX | 事實註解 |', '|---:|---|---|---:|---|']
    for t in trace['turns']:
        cells = [f"[T{t['number']}](#turn-{t['number']})", route(t),
                 ', '.join(c['status'] for c in t['tools']) or '無工具結果', len(t['aux']), ' '.join(notes(t))]
        lines.append('| ' + ' | '.join(table_cell(c) for c in cells) + ' |')
    if trace['warnings']:
        lines += ['', '注意：' + ' '.join(trace['warnings'])]
    lines += ['', '<details><summary>最終輸出與停止資訊</summary>', '', fence(trace['final']),
              fence(trace['error'], 'json'), '', '</details>']
    for t in trace['turns']:
        lines += ['', f'<a id="turn-{t["number"]}"></a>', f'## Turn {t["number"]}', '',
                  f"<details><summary>展開完整 request、completion、工具結果與 AUX</summary>", '',
                  f"Messages：{len(t['messages'])}；與前次相同的前綴：{t['unchanged_prefix']}（仍完整送出）。", '',
                  'Request：', fence(t['messages'], 'json'), '', 'Completion：', fence(t['completion']), '',
                  '模型錯誤：', fence(t['error'], 'json'), '', '記錄的解析結果：', fence(t['parse'], 'json'), '',
                  '工具嘗試與結果：', fence(t['tools'], 'json'), '', 'AUX：', fence(t['aux'], 'json'), '',
                  'HTTP request：', fence(t['http_request'], 'json'), '', 'HTTP response：', fence(t['http_response'], 'json'),
                  '', '</details>']
    return '\n'.join(lines) + '\n'


def html_report(trace):
    def pre(value, cls=''):
        return '<pre class="' + cls + '">' + escape(value if isinstance(value, str) else dump(value)) + '</pre>'

    def detail(label, content, cls=''):
        return f'<details class="{cls}"><summary>{escape(label)}</summary>{content}</details>'

    def request_details(record):
        return ''.join(detail(f"Message {i} · {m['role']}", pre(m['content'], 'message-content'))
                       for i, m in enumerate(record['messages']))

    cards, rows = [], []
    for t in trace['turns']:
        number = t['number']
        states = ', '.join(c['status'] for c in t['tools']) or '無工具結果'
        annotations = ''.join('<li>' + escape(n) + '</li>' for n in notes(t))
        rows.append(f'<tr><td data-label="Turn"><a href="#turn-{number}">T{number}</a></td><td data-label="路徑">{escape(route(t))}</td>'
                    f'<td data-label="工具結果狀態">{escape(states)}</td><td data-label="AUX">{len(t["aux"])}</td><td data-label="事實註解"><ul>{annotations}</ul></td></tr>')
        body = detail(f"完整 request · {len(t['messages'])} messages · {t['unchanged_prefix']} 個相同前綴仍送出",
                      request_details(t), 'request')
        body += detail('完整 completion', pre(t['completion'], 'completion'))
        body += detail('記錄的解析結果與模型錯誤', pre({'parse': t['parse'], 'error': t['error']}))
        for tool in t['tools']:
            body += detail(f"{tool['name']} · {tool['status']} · 完整工具結果", pre(tool['args']) + pre(tool['content'], 'tool-content'))
        for aux in t['aux']:
            body += detail(f"AUX {aux['number']} · {aux.get('tool') or '工具內部'}",
                           request_details(aux) + pre(aux['completion'], 'aux-completion') + pre(aux['error'])
                           + detail('完整 HTTP', pre({'request': aux['http_request'], 'response': aux['http_response']})))
        body += detail('完整 HTTP request / response', pre({'request': t['http_request'], 'response': t['http_response']}))
        cards.append(f'<section id="turn-{number}"><h2>T{number} · {escape(t["decision"])}</h2>' +
                     detail('展開此 turn 的完整內容', body, 'turn-evidence') + '</section>')
    warnings = ''.join('<p class="warning">' + escape(w) + '</p>' for w in trace['warnings'])
    return '''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent run 路徑</title><style>
:root{color-scheme:light dark;font-family:system-ui,sans-serif;line-height:1.65}body{max-width:1120px;margin:auto;padding:24px;background:#101820;color:#e5edf4}a{color:#8bd8e8}h1{margin-bottom:8px}h2{font-size:1.15rem}p{overflow-wrap:anywhere}.meta{color:#b8cbd9}.table{overflow:auto}table{width:100%;border-collapse:collapse;font-size:.9rem}td,th{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #385061}td:nth-child(2){min-width:170px;max-width:330px;overflow-wrap:anywhere}td:last-child{min-width:210px}ul{margin:0;padding-left:18px}section{border:1px solid #385061;border-radius:10px;padding:16px;margin:16px 0;scroll-margin-top:12px}summary{cursor:pointer;padding:9px 0;color:#a6e3e9}details details{margin-left:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:65vh;overflow:auto;background:#172631;padding:12px;border-radius:6px;font:13px/1.6 ui-monospace,monospace}.warning{color:#ffcf82}footer{color:#b8cbd9;font-size:.85rem;margin-top:28px}@media(max-width:600px){body{padding:12px}.table{overflow:visible}thead{display:none}table,tbody,tr,td{display:block}tr{margin-bottom:12px;padding:12px;background:#172631;border-radius:8px}td{border:0;padding:4px 0;min-width:0!important;max-width:none!important}td:before{content:attr(data-label) "：";color:#b8cbd9;margin-right:5px}td:last-child:before{display:block}td ul{margin-top:4px}details details{margin-left:5px}}
</style><main><h1>Agent run 路徑</h1>''' + '<p>' + escape(trace['question']) + '</p>' + \
        f'<p class="meta">{escape(str(trace["environment"] or "未標記"))} · {escape(trace["kind"])} · status={escape(str(trace["status"]))} · {trace["main_count"]} 主 requests / {trace["aux_count"]} aux</p>' + \
        f'<p>答案比對：{escape(str(trace["answer_match"]))}；證據支持：尚未審查。done 只表示流程結束。</p>' + \
        '<p><a href="trace.md">Markdown</a> · <a href="trace.json">完整結構化 trace</a> · <a href="events.jsonl">原始事件</a></p>' + warnings + \
        '<div class="table"><table><thead><tr><th>Turn</th><th>路徑</th><th>工具結果狀態</th><th>AUX</th><th>事實註解</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>' + \
        detail('最終輸出與停止資訊', pre(trace['final']) + pre(trace['error'])) + ''.join(cards) + \
        detail('設定與記錄資訊', pre({k: v for k, v in trace.items() if k != 'turns'})) + \
        '<footer>離線可讀；不執行模型或外部資源。註解由事件規則產生，不推測模型內部原因。原文只顯示為文字。</footer></main></html>'


def write_report(source, out=None, *, metadata=None, result=None, context=None):
    source = Path(source).resolve()
    out = Path(out or source.parent).resolve()
    out.mkdir(parents=True, exist_ok=True)
    events, warnings = read_events(source)
    trace = build_trace(events, metadata=metadata, result=result, context=context)
    trace['warnings'][:0] = warnings
    trace['raw_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    target = out / 'events.jsonl'
    if target != source:
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise FileExistsError(f'Refusing to overwrite raw evidence: {target}')
        if not target.exists():
            shutil.copyfile(source, target)
    # Imported logs must remain rebuildable after their original batch/companion
    # files are absent. Preserve the supplied evaluation context, without
    # replacing a live run's original metadata or result.
    meta_path = out / 'metadata.json'
    if not meta_path.exists():
        saved = deepcopy(metadata or {})
        saved['run_context'] = {k: trace[k] for k in ('id', 'question', 'kind', 'environment',
                                                     'expected_answers', 'document_result_budget')}
        meta_path.write_text(dump(saved) + '\n', encoding='utf-8')
    result_path = out / 'result.json'
    if not result_path.exists():
        saved_result = {k: trace[k] for k in ('id', 'status', 'error', 'answer_match', 'answer_match_method')}
        saved_result['text'] = trace['final']
        result_path.write_text(dump(saved_result) + '\n', encoding='utf-8')
    (out / 'trace.json').write_text(dump(trace) + '\n', encoding='utf-8')
    (out / 'trace.md').write_text(markdown(trace), encoding='utf-8')
    (out / 'trace.html').write_text(html_report(trace), encoding='utf-8')
    return trace
