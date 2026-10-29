"""Map BM25 ranks to original email dictionaries."""
from agent_trace.pipelines.bm25 import rank as rank_bm25
TOP_K = 5

class EmailBM25Retriever:
    """Callable search(query, k) adapter returning original email dictionaries."""

    def __init__(self, index: dict, emails: list[dict], verbose: bool = True):
        self.index = index
        self.emails = emails
        self.verbose = verbose

    def rank(self, query: str, k: int = TOP_K) -> list[tuple[int, float]]:
        return rank_bm25(self.index, query, k)

    def __call__(self, query: str, k: int = TOP_K) -> list[dict]:
        ranked = self.rank(query, k)
        if self.verbose:
            print(f"  [BM25] query={query!r}, returned={len(ranked)}")
            for doc_idx, score in ranked:
                email = self.emails[doc_idx]
                print(f"         {email['id']}  BM25={score:.3f}  {email['subject'][:75]}")
        return [self.emails[doc_idx] for doc_idx, _ in ranked]
