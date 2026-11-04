"""The batch driver preserves all cases and keeps generation/scoring separate."""

import json
from pathlib import Path

from scripts import test09


def test_batch_visits_all_twenty_in_order_and_preserves_failure(tmp_path, monkeypatch):
    calls = []
    def agent(argv):
        calls.append(argv)
        case = argv[2]
        folder = Path(argv[4])
        assert argv == ['run', '--task', case, '--out', str(folder)]
        # Generation receives no gold strings, doc_id or reference line arguments.
        if case == 'd07':
            raise RuntimeError('simulated provider failure')
        folder.mkdir()
        (folder / 'result.json').write_text(json.dumps({'status': 'done', 'text': 'Unknown.', 'seconds': 1}))
        (folder / 'trace.json').write_text(json.dumps({'turns': [], 'main_count': 1, 'aux_count': 0,
                                                       'document_result_tokens_estimate': 100}))
        return 0
    monkeypatch.setattr(test09, 'run_agent', agent)
    out = tmp_path / 'baseline'
    assert test09.run_batch(out) == 1
    result = test09.load(out / 'results.json')
    assert len(calls) == result['completed'] == 20
    assert [a[2] for a in calls] == [f'd{i:02d}' for i in range(1, 21)]
    assert result['errors'] == 1
    assert result['rows'][6]['error']['message'] == 'simulated provider failure'
    assert result['rows'][-1]['id'] == 'd20'
    assert test09.load(out / 'progress.json')['running'] is None
    assert test09.load(out / 'metadata.json')['repair'] is False


def test_answer_and_evidence_budget_are_independent_metrics(tmp_path):
    item = {'id': 'd06', 'kind': 'direct', 'question': 'When?', 'answers': ['2026-12-31'],
            'doc_id': 'spec', 'line': 120}
    (tmp_path / 'result.json').write_text(json.dumps({'status': 'done', 'text': '2026-12-31 [spec]'}))
    trace = {'main_count': 3, 'aux_count': 0, 'document_result_tokens_estimate': 6100,
             'turns': [{'tools': [{'name': 'read_doc', 'status': 'ok',
                                  'value': {'doc_id': 'spec', 'start_line': 90, 'end_line': 131}}]}]}
    (tmp_path / 'trace.json').write_text(json.dumps(trace))
    row = test09.evaluate(item, tmp_path)
    assert row['answer_match'] is True and row['reference_line_read'] is True
    assert row['within_document_budget'] is False
    assert row['evidence_support'] == 'not_reviewed'
    assert test09.summarize([row])['passed'] is False
