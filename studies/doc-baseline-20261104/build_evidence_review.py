"""Materialize the assistant's post-hoc review; do not call or modify the agent."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

batch = Path(__file__).resolve().parent
root = batch.parents[1]
load = lambda p: json.loads(p.read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
results = load(batch / 'results.json')
metadata = load(batch / 'metadata.json')
original_result_sha = sha(batch / 'results.json')
sources = {}
for key, digest in metadata['file_sha256'].items():
    if key.startswith('datasets/docs/'):
        path = root / key
        assert sha(path) == digest
        sources[path.stem] = path.read_text(encoding='utf-8')

# These judgments were made by reading each full answer and its retrieved evidence.
# Literal quotes below are independently checked against the actual tool results.
decisions = [
 ('d01','supported','supported','accurate',
  'Nadia Ferreira 與 Firmware Engineering Manager 身分由實際 snippet 支持；不必只認 fixture 的 org-chart。Heron 的附帶角色描述較籠統，原文件為 Product manager，snippet 從 manager 開始而漏掉前綴。',
  ['role_precision'], [('firmware-spec-emberos','Owner: Firmware team (Nadia Ferreira, Firmware Engineering Manager)'),('firmware-spec-emberos','Document number: FW-SPEC-003'),('project-heron-brief','manager: Rohan Kapoor')]),
 ('d02','supported','supported','accurate',
  '14 characters、政策編號／版本與 Section 3 均在已讀內容中。', [],
  [('it-security-policy','Policy number: SEC-400, version 3.0'),('it-security-policy','## 3. Accounts and passwords'),('it-security-policy','Passwords must be at least 14 characters long.')]),
 ('d03','supported','supported','accurate',
  '600 requests/min、429、Retry-After 與 Enterprise 申請較高上限均有已讀證據，引用 4.1 正確。', [],
  [('gridlens-api-spec','Document number: API-SPEC-002'),('gridlens-api-spec','Version: 2.1'),('gridlens-api-spec','4.1 Each client may make up to 600 requests per minute. A request over the limit receives status 429 with a `Retry-After` header that gives the number of seconds to wait.'),('gridlens-api-spec','4.4 Enterprise customers may ask for higher limits through their Customer Success Manager.')]),
 ('d04','supported','supported','accurate',
  'Professional 每 meter 每月 $1.40 與 Pricing and contracts 章節均在已讀視窗中。', [],
  [('gridlens-product-faq','## Pricing and contracts'),('gridlens-product-faq','| Professional | $1.40 |')]),
 ('d05','supported','supported','accurate',
  'Jonas Weber 及 Senior Data Scientist 身分均在實際搜尋 snippet 中。', [],
  [('project-kestrel-brief','Technical lead: Jonas Weber, Senior Data Scientist')]),
 ('d06','unsupported','unsupported','insufficient',
  '沒有回答關閉日期；只搜尋文件與 email，未 read_doc。摘要缺少日期不能支持整份文件未記載的結論。原文件第 120 行實際有日期，但沒有進入工具觀察。最後原生回覆因 length 停止，session 卻標 done。',
  ['missing_evidence','false_absence_inference','final_length_stop'], []),
 ('d07','supported','supported','accurate',
  '第三次搜尋的 snippet 已完整呈現每曆年最多 10 working days 全薪陪審服務；沒有 read_doc 不等於缺乏支持。', [],
  [('employee-handbook','Cardinal Energy pays your full salary for up to 10 working days of jury service per calendar year.')]),
 ('d08','supported','supported','source_type_mislabeled',
  '電話與 Section 34 正確，已讀到第 258 行；employee-handbook 是文件 doc_id，輸出卻標為 Email ID。', ['source_type_label'],
  [('employee-handbook','## 34. Raising concerns and the ethics hotline'),('employee-handbook','call the ethics hotline at 1-800-555-0142.')]),
 ('d09','supported','supported','accurate',
  'E-214、11.2、11.3、M4／15 分鐘及恢復條件全部在已讀視窗內。', [],
  [('firmware-spec-emberos','11.2 Error codes are reported as events.'),('firmware-spec-emberos','| E-214 | Sensor mesh link lost |'),('firmware-spec-emberos','11.3 E-214 is raised by the M4 when a joined sensor has sent no report for 15 minutes. It is cleared when the sensor reports again.')]),
 ('d10','supported','supported','accurate',
  '第二次搜尋 snippet 明載 draft 於 resolution 後 5 business days 到期；文件來源正確。', [],
  [('oncall-incident-process','The draft is due within 5 business days of resolution.')]),
 ('d11','supported','supported','accurate',
  '4 hours、Section 5 與 Oregon/us-west 對應 Virginia/us-east 災難復原區均有已讀支持。', [],
  [('architecture-overview','## 5. Recovery targets'),('architecture-overview','The recovery time objective is 4 hours: service in the recovery region must be available within that time.'),('architecture-overview','| us-west | Oregon | Primary for customers in North America |'),('architecture-overview','| us-east | Virginia | Disaster recovery for us-west |')]),
 ('d12','supported','supported','accurate',
  '$75、餐別與小費、出發／返程半額均有已讀來源；$37.50 是 75/2 的正確推算，並非捏造引文。引用 2026 版 Section 6 正確。', [],
  [('expense-policy-2026','## 6. Meals while traveling'),('expense-policy-2026','meals are reimbursed up to a daily limit of $75 per day for domestic travel'),('expense-policy-2026','The limit covers breakfast, lunch, dinner, and tips.'),('expense-policy-2026','On the day you depart and the day you return, the limit is half of the daily amount.')]),
 ('d13','supported','supported','accurate',
  '新 $750 門檻、生效日與舊 March policy 的 $750–$1,000 區間都在 snippet 內。提及舊金額屬正確歷史對照，不是答成舊政策。', [],
  [('finance-memo-2026-08-approval-thresholds','Effective: 2026-09-01'),('finance-memo-2026-08-approval-thresholds','From 2026-09-01, any single expense over $750 requires approval from your department\'s vice president'),('finance-memo-2026-08-approval-thresholds','individual expenses between $750 and $1,000, which under the March policy reach Finance with only a manager\'s approval.')]),
 ('d14','supported','supported','source_type_mislabeled',
  '10 days/80 hours、2025→2026 起適用及 June 30 截止都有 snippet 支持；公告是文件，卻標成 Relevant Email ID。', ['source_type_label'],
  [('people-announcement-2025-11-pto-carryover','Starting with the rollover from 2025 into 2026, you may carry over up to 10 days (80 hours) of unused PTO into the next calendar year. Carried-over PTO must be used by June 30 of that year.')]),
 ('d15','supported','supported','source_type_mislabeled',
  'Tuesday/Wednesday/Thursday 與 2026-06-01 生效日均有 snippet 支持；公告 doc_id 被標成 Relevant Email ID。', ['source_type_label'],
  [('people-announcement-2026-05-office-days','Starting 2026-06-01, hybrid employees will work from their assigned office at least 3 days each week. The anchor days will be Tuesday, Wednesday, and Thursday.')]),
 ('d16','supported','supported','accurate',
  '$500、2026-03-02 與假日／winter closure 額外 $250 均有 snippet 支持。includes an additional 的用語容易含混，建議寫成 $500 加上條件式額外 $250。', ['bonus_wording_precision'],
  [('engineering-announcement-2026-02-oncall-stipend','The new amounts apply to rotations that start on or after 2026-03-02.'),('engineering-announcement-2026-02-oncall-stipend','| Primary | $500 |'),('engineering-announcement-2026-02-oncall-stipend','An engineer who is primary or secondary during a week that contains a company holiday, or during the winter closure, receives an additional $250 for that week.')]),
 ('d17','supported','supported','accurate',
  '$65/月、fitness facility dues、Ledgerly/Wellness 與不結轉均在第三次搜尋的同一 snippet 內。', [],
  [('benefits-summary-2026','Cardinal Energy reimburses up to $65 per month'),('benefits-summary-2026','Eligible expenses include fitness facility dues'),('benefits-summary-2026','Submit the expense in Ledgerly under the Wellness category.'),('benefits-summary-2026','Unused amounts do not roll over from month to month.')]),
 ('d18','unsupported','unsupported','insufficient',
  '未回答分機，未讀 Security policy 正文。引用的 em-22128 只談舊公司電腦／支票與 Security desk，無法回答 Cardinal 通報分機。文件結果超過 6000，最後原生回覆 length-stop 後仍被當 done。',
  ['missing_evidence','irrelevant_email','document_budget_exceeded','final_length_stop'], []),
 ('d19','supported','supported','accurate',
  'semi-monthly、15th 與 last business day、遇假日提前及 PeopleHub 均有已讀支持；摘要條列用 or 有歧義，但同一輸出的直接引文正確使用 and。', ['payday_conjunction_precision'],
  [('employee-handbook','## 8. Compensation and payroll'),('employee-handbook','Salaries are disbursed semi-monthly, on the 15th and on the last business day of each month. If the 15th falls on a weekend or a bank holiday, the deposit is made on the business day before. Pay statements are available in PeopleHub.')]),
 ('d20','supported','partial','accurate',
  '$1,800/年與 current/target role 的 learning 範圍有 snippet 支持。snippet 在 Eligible 一詞後截斷，沒有呈現 event registration/coursework 清單；會議／線上課程明確適用是從題意與 learning 類別推得，未由實際送入內容完整核對。完整語料確實列出該清單，屬事後查核，不能回填為 agent 已看過。',
  ['additional_scope_inferred_from_partial_snippet'],
  [('benefits-summary-2026','Each full-time employee may spend up to $1,800 per calendar year on learning that relates to their current role or a role they are working toward.')]),
]

def proof(trace, doc_id, quote):
    for i, turn in enumerate(trace['turns']):
        for j, tool in enumerate(turn['tools']):
            if tool['status'] != 'ok':
                continue
            value = json.loads(tool['content'])
            chunks = value if tool['name'] == 'search_docs' and isinstance(value, list) else [value] if tool['name'] == 'read_doc' else []
            for v in chunks:
                if v.get('doc_id') != doc_id:
                    continue
                text = v.get('snippet', v.get('text', ''))
                if quote not in text:
                    continue
                assert i + 1 < len(trace['turns'])
                assert any(tool['content'] in m['content'] for m in trace['turns'][i+1]['messages'])
                source = sources[doc_id]
                offset = source.find(quote)
                assert offset >= 0, (doc_id, quote)
                return {'doc_id': doc_id, 'line_start': source[:offset].count('\n')+1,
                        'line_end': source[:offset+len(quote)].count('\n')+1,
                        'tool': tool['name'], 'turn': turn['number'], 'tool_index': j,
                        'quote': quote, 'sent_in_next_model_request': True,
                        'trace_link': f'{trace["id"]}/trace.md#turn-{turn["number"]}'}
    raise AssertionError(('Quote was not in the observed evidence', trace['id'], doc_id, quote))

rows = []
requests_verified = 0
for cid, core, full, citation, note, warnings, evidence in decisions:
    trace_path = batch/cid/'trace.json'
    trace = load(trace_path)
    events_path = batch/cid/'events.jsonl'
    assert sha(events_path) == trace['raw_sha256']
    events = [json.loads(s) for s in events_path.read_text(encoding='utf-8').splitlines()]
    app = {e['call_id']:e for e in events if e['kind']=='model_request'}
    for event in events:
        if event['kind']=='ollama_http_request' and event.get('endpoint')=='/api/chat':
            assert event['payload']['messages']==app[event['call_id']]['messages']
            requests_verified += 1
    responses = [e['response'] for e in events if e['kind']=='ollama_http_response' and 'message' in e.get('response',{})]
    final = responses[-1]
    assert final['message']['content']==trace['final']
    rows.append({'id':cid,'question':trace['question'],'core_answer_support':core,
                 'full_response_support':full,'citation_status':citation,'review_note':note,
                 'warnings':warnings,'evidence':[proof(trace,doc,quote) for doc,quote in evidence],
                 'final_native_stop':final.get('done_reason'),
                 'final_prompt_tokens':final.get('prompt_eval_count'),
                 'final_completion_tokens':final.get('eval_count'),
                 'session_status':trace['status'],'trace_sha256':sha(trace_path),
                 'events_sha256':sha(events_path)})

# Counter-evidence is explicitly separate from evidence the agent actually saw.
posthoc = []
for cid, doc, quote in [
 ('d06','gridlens-api-spec','API version 1 will be shut down on 2026-12-31.'),
 ('d18','it-security-policy','Call the Security hotline at extension 4911'),
 ('d20','benefits-summary-2026','Eligible expenses include event registration fees, coursework, certification examinations, and books.'),
 ('d01','project-heron-brief','Product manager: Rohan Kapoor')]:
    text=sources[doc]
    index=text.find(quote)
    assert index>=0
    posthoc.append({'case':cid,'doc_id':doc,'line':text[:index].count('\n')+1,'quote':quote,
                    'origin':'full-corpus post-hoc review, not additional agent retrieval'})

assert [r['id'] for r in rows]==[f'd{i:02d}' for i in range(1,21)]
assert requests_verified==78
summary={'reviewed':20,'core_answers_supported':sum(r['core_answer_support']=='supported' for r in rows),
         'full_response_support_counts':dict(Counter(r['full_response_support'] for r in rows)),
         'citation_source_type_mislabeled':[r['id'] for r in rows if r['citation_status']=='source_type_mislabeled'],
         'precision_warnings':[r['id'] for r in rows if any('precision' in w for w in r['warnings'])],
         'final_length_stop_marked_done':[r['id'] for r in rows if r['final_native_stop']=='length' and r['session_status']=='done'],
         'native_requests_checked':requests_verified,'new_ollama_inference_calls':0}
review={'schema_version':1,'reviewed_at':datetime.now(timezone.utc).isoformat(),
        'reviewer':'Codex assistant, explicit post-hoc reading in this conversation',
        'method':'Read all final answers and actual tool evidence; verify quoted support against corpus and next HTTP request. No new generation or answer repair.',
        'rubric':{'core_answer_support':'Does the requested main fact have support in evidence sent to the agent?',
                  'full_response_support':'Do substantive added claims have support? Inference from a partial snippet is labeled partial, not automatically false.',
                  'citation_status':'Are the cited document and section correct, and is a document mislabeled as email?',
                  'warnings':'Precision issues are recorded separately and do not automatically negate factual support.'},
        'limitations':['One assistant review, not independent multiple-rater agreement or a trained semantic verifier.',
                       'Recorded messages show what was sent; they do not prove which earlier tokens the backend retained internally.',
                       'Full-corpus counter-evidence was consulted only after generation; it was not supplied to the agent.',
                       'No new overall pass threshold is invented by this review.'],
        'original_results_sha256':original_result_sha,'summary':summary,'rows':rows,'posthoc_counter_evidence':posthoc}
(batch/'evidence-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

lines=['# 20 題 baseline：逐題來源支持審查','',
       '已完成 20/20 題事後審讀。由本次 Codex assistant 核對原始回答、實際工具結果、後續 HTTP messages 與固定語料；沒有重跑模型或修正答案。',
       '原始 results.json、evaluation.json、trace、events 均保留原樣；本檔是另外的審查層。','',
       '## 結果','',
       '- 核心答案有實際送入證據支持：18/20。',
       '- 完整回覆的事實支持：17 supported、1 partial（d20 的附帶適用範圍）、2 unsupported（d06、d18）。',
       '- d08、d14、d15：答案有支持，但把文件 doc_id 標成 Email ID。',
       '- d01、d16、d19：有角色／金額加成／and-or 措辭精準度問題，另列提醒，不直接當成核心答案錯誤。',
       '- d06、d18：最終 native done_reason=length，但 session status=done；兩題的 prompt+completion native tokens 均為 8192。',
       '- 全部 78 個應用層 request 與 HTTP messages 逐一相符；所有下列支持引文均確實出現在工具結果及下一次模型請求。','',
       '這不是把 18/20 字串命中直接改名為證據成功；搜尋 snippet 本身可以充分支持答案，引用錯誤和額外推論則另行標示。','',
       '| 題目 | 核心支持 | 完整事實支持 | 引用 | 審查結論 |', '|---|---|---|---|---|']
for row in rows:
    lines.append(f'| [{row["id"]}]({row["id"]}/trace.md) | {row["core_answer_support"]} | {row["full_response_support"]} | {row["citation_status"]} | {row["review_note"]} |')
lines+=['','## 各題可核對的支持片段','']
for row in rows:
    lines += [f'### {row["id"]}', '', row['review_note'], '']
    for proof in row['evidence']:
        lines += [f'- [{proof["doc_id"]}](../../datasets/docs/{proof["doc_id"]}.md) 第 {proof["line_start"]}–{proof["line_end"]} 行；'
                  f'實際由 [{proof["tool"]}, turn {proof["turn"]}]({row["id"]}/trace.md#turn-{proof["turn"]}) 送入：',
                  '  > '+proof['quote']]
    if not row['evidence']:
        lines+=['- 沒有支持所問答案的已見來源；見下方事後反證。']
    lines+=['']
lines+=['## 事後反證／補充查核（不回填為 agent 已見）','']
for item in posthoc:
    lines += [f'- {item["case"]}：{item["doc_id"]} 第 {item["line"]} 行：', '  > '+item['quote']]
lines+=['','## 失敗的停止狀態','',
        '| 題目 | final prompt tokens | final completion tokens | native stop | session status |',
        '|---|---:|---:|---|---|']
for row in rows:
    if row['final_native_stop']=='length':
        lines.append(f'| {row["id"]} | {row["final_prompt_tokens"]} | {row["final_completion_tokens"]} | length | {row["session_status"]} |')
lines+=['','這兩題在 8192 context 下沒有留下足夠輸出空間，回覆被截斷。現有 Ollama adapter 未將該 length stop 轉為 OutputTruncated，agent 因沒有完整工具呼叫而把它當作最終文字。這是後續修正方向，這次不改動 baseline 行為或原始結果。',
        '', '## 審查界線','']+['- '+x for x in review['limitations']]
lines+=['','機器可讀的逐題資料、來源座標與輸入 hashes：[evidence-review.json](evidence-review.json)。']
(batch/'evidence-review.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
readme=batch/'README.md'
text=readme.read_text(encoding='utf-8')
text=text.replace('Evidence support has not been semantically reviewed. No repair or response reuse.',
                  'Automated scoring is preserved in results.json. Post-hoc evidence review is now complete for 20/20 cases: [review](evidence-review.md). No repair or response reuse.')
readme.write_text(text,encoding='utf-8')
assert sha(batch/'results.json')==original_result_sha
print(json.dumps(summary,indent=2))
