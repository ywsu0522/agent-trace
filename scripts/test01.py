"""HW1 P01: 25 deterministic cases and all 60 local Ollama live emails.

Run from the agent-trace root: python -m scripts.test01 [--mode live]
"""

from agent_trace.pipelines.priority import classify_priority
from scripts._common import arguments, deterministic, load, run_cases


def evaluate_priority(item, output):
    reasons = []
    valid = isinstance(output, dict)
    if not valid:
        reasons.append('output must be a dict')
        output = {}
    category, reason = output.get('category'), output.get('reason')
    if category not in ('urgent', 'normal', 'ignore', 'unknown'):
        valid = False
        reasons.append('invalid category')
    if not isinstance(reason, str) or not reason.strip():
        valid = False
        reasons.append('reason must be a nonempty string')
    unknown = category == 'unknown'
    if unknown:
        reasons.append('unknown is not allowed in live evaluation')
    correct = category == item['category']
    if not correct:
        reasons.append(f"expected {item['category']}, got {category}")
    return {'passed': valid and correct and not unknown, 'correct': correct,
            'valid_contract': valid, 'unknown': unknown, 'reasons': reasons}


def summarize(rows):
    correct = sum(row['correct'] for row in rows)
    unknown = sum(row['unknown'] for row in rows)
    valid = all(row['valid_contract'] and row['error'] is None for row in rows)
    accuracy = correct / len(rows)
    return {'passed': valid and unknown == 0 and accuracy >= 0.85,
            'correct': correct, 'total': len(rows), 'accuracy': accuracy,
            'required_accuracy': 0.85, 'unknown': unknown, 'valid_contracts': valid}


def main(argv=None):
    args = arguments('p01', 'priority_gold.json', argv)
    if args.mode != 'live':
        code = deterministic('priority')
        if code or args.mode == 'deterministic':
            return code
    items = load(args.fixture)
    if not isinstance(items, list) or not items:
        raise ValueError('Priority fixture must contain at least one case')
    cases = [{**item, 'id': item['email']['id']} for item in items]
    return run_cases(args, 'p01', cases,
                     lambda item, run: classify_priority(item['email'], run.lm),
                     evaluate_priority, summarize)


if __name__ == '__main__':
    raise SystemExit(main())
