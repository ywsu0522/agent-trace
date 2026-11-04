"""BM25 inverted index over list[str]; record examples: docs/README.md."""

import math
from collections import Counter, defaultdict
from heapq import nsmallest

from agent_trace.tokenizer import tokenize

K1 = 1.5
B = 0.75


def build(docs: list[str]) -> dict:
    """Build corpus statistics and inverted postings; do not compute scores.

    Internal IDs are positions in docs. Each posting stores [position, tf],
    not a BM25 score; rank() computes query-dependent scores from this index.
    """
    postings = defaultdict(list)
    lengths = []
    for doc_idx, text in enumerate(docs):
        counts = Counter(tokenize(text))
        lengths.append(sum(counts.values()))
        for term, tf in counts.items():
            postings[term].append([doc_idx, tf])
    n = len(lengths)
    avgdl = sum(lengths) / n if n else 0.0
    # Query-independent denominator factors; preserve the original operation order.
    length_norms = [K1 * (1 - B + B * length / avgdl) for length in lengths] if avgdl else [0.0] * n
    return {
        "N": n,
        "avgdl": avgdl,
        "length_norms": length_norms,
        "doc_lengths": lengths,
        "postings": dict(postings),     # index["postings"][term] = [[0, 3], [2, 1], [doc_idx, tf], ...]
    }


def build_index(records: list[dict]) -> dict:
    """Index text/chunk_id records and add chunk_ids; does not split text."""
    index = build([record["text"] for record in records])
    index["chunk_ids"] = [record["chunk_id"] for record in records]
    return index


def validate_index(index: dict, records: list[dict]) -> None:
    assert index["N"] == len(records)
    assert len(index["doc_lengths"]) == index["N"]
    assert index["chunk_ids"] == [record["chunk_id"] for record in records]
    assert sum(index["doc_lengths"]) == sum(
        tf for hits in index["postings"].values() for _, tf in hits
    )
    for i, record in enumerate(records):
        assert index["doc_lengths"][i] == len(tokenize(record["text"]))


def _score(index: dict, terms: list[str], *, collect_parts: bool = False):
    """Share scoring between rank and explain; allocate details only on request."""
    scores = defaultdict(float)
    parts = defaultdict(dict) if collect_parts else None
    if index["N"] == 0:
        return scores, parts

    length_norms = index["length_norms"]
    tf_scale = K1 + 1
    for term in terms:
        hits = index["postings"].get(term, [])      # index["postings"]: term -> [[doc_idx, tf]]
        if not hits:
            continue
        df = len(hits)
        idf = math.log(1 + (index["N"] - df + 0.5) / (df + 0.5))
        if not scores:
            # The first matching term needs no addition to zero or missing-key lookup.
            scores = defaultdict(float, {
                doc_idx: idf * tf * tf_scale / (tf + length_norms[doc_idx])
                for doc_idx, tf in hits
            })
            if parts is not None:
                for doc_idx, value in scores.items():
                    parts[doc_idx][term] = value
            continue
        for doc_idx, tf in hits:
            bm25 = idf * tf * tf_scale / (tf + length_norms[doc_idx])
            scores[doc_idx] += bm25
            if parts is not None:
                parts[doc_idx][term] = bm25

    return scores, parts


def _top_k(scores: dict[int, float], k: int) -> list[tuple[int, float]]:
    # Highest score first; ties use the smaller internal document index.
    return nsmallest(max(0, k), scores.items(), key=lambda pair: (-pair[1], pair[0]))


def rank(index: dict, query: str, k: int = 5) -> list[tuple[int, float]]:
    """Return (internal document index, score) for up to k matching records."""
    if k <= 0 or index["N"] == 0:
        return []
    # Deduplicate in query order so floating-point accumulation is reproducible.
    terms = list(dict.fromkeys(tokenize(query)))
    scores, _ = _score(index, terms)
    return _top_k(scores, k)


def explain(
    index: dict, query: str, k: int = 5,
) -> tuple[list[str], int, list[tuple[int, float, dict[str, float]]]]:
    """Return unique terms, candidate count, and (index, score, contributions).

    Candidates match at least one query term. Contributions map each matching
    term to its BM25 score; their sum is the record's total score. Records and
    display formatting belong to callers, not this module.
    """
    terms = list(dict.fromkeys(tokenize(query)))
    scores, parts = _score(index, terms, collect_parts=True)
    results = [(i, score, parts[i]) for i, score in _top_k(scores, k)]
    return terms, len(scores), results
