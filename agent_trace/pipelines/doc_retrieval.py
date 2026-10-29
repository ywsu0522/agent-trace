"""Whole-document retrieval and query snippets; record examples: docs/README.md."""

from agent_trace.pipelines import bm25
import re
from agent_trace.tokenizer import tokenize
from agent_trace.tokens import count_tokens
from agent_trace.types import DocWindow


READ_MAX_TOKENS = 1500


def make_snippet(text, query):
    """從全文首個命中單字起，取最多 150 tokens 的原文；不建立 chunk。"""
    query_terms = set(tokenize(query))
    words = list(re.finditer(r"\S+", text))

    for i, word in enumerate(words):
        # 用課程 tokenizer 比對，處理大小寫與標點符號。
        if not query_terms.intersection(tokenize(word.group())):
            continue

        start = word.start()
        end = start

        # 延伸到後續完整單字，但不得超過 150 tokens。
        for following in words[i:]:
            candidate_end = following.end()
            if count_tokens(text[start:candidate_end]) > 150:
                break
            end = candidate_end

        return text[start:end]

    return ""


def build_doc_index(docs: list[dict]) -> dict:
    """每份全文是一筆搜尋單位；bm25_index 保存統計與 postings，不存分數。

    bm25.rank(bm25_index, query, k) 才會依 query 計算分數並排名。
    """
    return {
        "bm25_index": bm25.build([doc["text"] for doc in docs]),
        "docs": docs,
        "by_id": {doc["doc_id"]: doc for doc in docs},
    }


def search_docs(index: dict, query, k=5):
    """將文件排名映射成 doc_id、title、snippet，最多回傳 k 筆。"""
    hits = bm25.rank(index["bm25_index"], query, k)
    results = []

    for doc_idx, score in hits:
        doc = index["docs"][doc_idx]

        snippet = make_snippet(doc["text"], query)

        results.append({
            "doc_id": doc["doc_id"],
            "title": doc["title"],
            "snippet": snippet,
        })

    return results


def read_doc(index: dict, doc_id: str, start_line: int = 1) -> DocWindow:
    """從原文的 1-based 行號讀取最多 1500 tokens 的完整行視窗。

    end_line 含最後一行；下一頁從 end_line + 1 開始。行號依原文
    splitlines() 計算，回傳文字以換行連接，不添加行號或省略號。
    未知文件、越界行號會拋出 LookupError／ValueError。若第一行本身
    已超過 token 上限，則明確報錯，避免截斷原文或回傳不前進的視窗。
    """
    lines = index["by_id"][doc_id]["text"].splitlines()
    total_lines = len(lines)
    if not 1 <= start_line <= total_lines:
        raise ValueError(f"start_line must be between 1 and {total_lines}: {start_line}")

    window_lines = []
    for line in lines[start_line - 1:]:
        candidate = "\n".join(window_lines + [line])
        if count_tokens(candidate) > READ_MAX_TOKENS:
            break
        window_lines.append(line)

    if not window_lines:
        raise ValueError(f"Line {start_line} of {doc_id!r} exceeds {READ_MAX_TOKENS} tokens")

    return {
        "doc_id": doc_id,
        "start_line": start_line,
        "end_line": start_line + len(window_lines) - 1,
        "total_lines": total_lines,
        "text": "\n".join(window_lines),
    }
