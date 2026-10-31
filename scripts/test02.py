"""HW1 P02: 8 deterministic cases and all 5 local Ollama daily digests.

Run from the agent-trace root: python -m scripts.test02 [--mode live]
"""

from agent_trace.data import Corpus
from agent_trace.paths import asset_root
from agent_trace.pipelines.daily_digest import generate_digest
from scripts._common import arguments, contains, deterministic, load, run_cases


def evaluate_digest(item, output):
    reasons = []
    valid = isinstance(output, str)
    text = output if valid else ''
    words = len(text.split())
    length_ok = valid and bool(text.strip()) and words <= 300
    if not length_ok:
        reasons.append(f'digest must be nonempty and <= 300 words; got {words}')
    missing = [{'email_id': entry['id'], 'aliases': group}
               for entry in item['urgent'] for group in entry['must_mention']
               if not any(contains(text, alias) for alias in group)]
    forbidden = [{'email_id': entry['id'], 'term': term}
                 for entry in item['ignore'] for term in entry['must_not_mention']
                 if contains(text, term)]
    for entry in missing:
        reasons.append(f"missing urgent item {entry['email_id']}: {entry['aliases']}")
    for entry in forbidden:
        reasons.append(f"forbidden ignore term {entry['email_id']}: {entry['term']}")
    return {'passed': length_ok and not missing and not forbidden, 'words': words,
            'length_ok': length_ok, 'must_mention_ok': valid and not missing,
            'must_not_mention_ok': valid and not forbidden,
            'missing': missing, 'forbidden': forbidden, 'reasons': reasons}


def summarize(rows):
    counts = {key: sum(row[key] and row['error'] is None for row in rows)
              for key in ('length_ok', 'must_mention_ok', 'must_not_mention_ok')}
    return {'passed': all(row['passed'] for row in rows), 'days': len(rows),
            'days_passed': sum(row['passed'] for row in rows), **counts}


def main(argv=None):
    args = arguments('p02', 'digest_days.json', argv)
    if args.mode != 'live':
        code = deterministic('daily_digest')
        if code or args.mode == 'deterministic':
            return code
    items = load(args.fixture)
    if not isinstance(items, list) or not items:
        raise ValueError('Digest fixture must contain at least one day')
    # Use exactly the fixture's IDs and order, not every email on that date.
    corpus = Corpus(asset_root() / 'datasets/docs', args.emails)
    by_id = {email['id']: email for email in corpus.emails()}
    emails = {item['date']: [by_id[email_id] for email_id in item['email_ids']] for item in items}
    return run_cases(args, 'p02', items,
                     lambda item, run: generate_digest(emails[item['date']], run.lm,
                                                       max_workers=args.workers, observer=run.stage),
                     evaluate_digest, summarize, corpus_path=args.emails)


if __name__ == '__main__':
    raise SystemExit(main())
