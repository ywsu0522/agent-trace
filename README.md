# Agent Trace

一個使用 Ollama 的 agent loop 實作，包含文件與 email 搜尋工具，以及逐回合的執行紀錄。每次提問會保存模型輸入、回覆、工具呼叫與結果，並自動產生可離線閱讀的報告。

## 一次實際的 agent loop

問題：**What is the minimum password length under the IT and Security Policy?**

以下摘自已保存的 d02 執行紀錄，使用 `qwen3.5:4b-q4_K_M` 與 baseline 設定：

| 回合 | Agent 動作 | 執行結果 |
|---|---|---|
| 1 | `search_docs(query="minimum password length IT Security Policy")` | 回傳 5 筆文件搜尋結果，結果加入下一回合的 messages。 |
| 2 | `read_doc(doc_id="it-security-policy")` | 讀取文件第 1–83 行，其中包含密碼長度規定。 |
| 3 | 回答問題 | 回答最低 **14 characters**，並引用文件 ID。 |

每回合將目前 messages 送給模型；如果回覆是工具呼叫，就驗證參數、執行工具，把結果加入 messages 後繼續。模型輸出一般文字或達到回合上限時結束。

[查看這次執行的完整 request、completion 與工具結果](studies/baseline-20/record/d02/trace.md)。這是保存的真實紀錄；重新推論時，模型輸出與工具路徑可能不同。

## 執行

先安裝 [uv](https://docs.astral.sh/uv/getting-started/installation/) 與 [Ollama](https://ollama.com/)，啟動 Ollama，再執行：

```sh
git clone https://github.com/ywsu0522/agent-trace.git
cd agent-trace
ollama pull qwen3.5:4b-q4_K_M
uv sync --locked --extra test
uv run agent-trace prepare-data --download
uv run agent-trace run --task d02 --agent baseline --trace
```

文件已包含在 repo；email archive 另行下載並核對 checksum。預設工具目錄也包含 email 工具，因此完整執行前需準備 archive。

每次執行會在 `runs/run-<timestamp>/` 保存 `trace.md`、`trace.html`、`trace.json`、`events.jsonl`、設定與結果。模型錯誤或 Ctrl+C 也會嘗試產生報告；已有事件可用以下指令離線重建：

```sh
uv run agent-trace report runs/my-run
uv run pytest
```

## 程式與實驗紀錄

- `agent_trace/`：agent loop、工具註冊與參數驗證、BM25 retrieval、Ollama client、trace 與報告。
- `configs/`：agent profiles 與 prompt。
- `tests/fixtures/doc_questions.json`：HW1 P09 `search_docs` 的原始 20 題 live 測試資料，原封保留課程 `tests/fixtures/doc_questions.json` 的陣列格式、問題、答案別名與參考證據；`--task d01` 至 `d20` 直接從此檔選題。
- `datasets/docs/`：共用的 24 份 Cardinal Energy 文件；`datasets/docs.provenance.json` 保存來源與 checksum，`datasets/email-source.json` 描述共用 email archive。
- `studies/`：已保存的實驗紀錄與比較。

HTML 閱讀頁可在本機重建，不納入 Git；已保存的紀錄可直接閱讀 Markdown。

[其他用法](docs/reproducibility.md) · [20 題歷史紀錄](studies/baseline-20/README.md) · [d06 prompt 比較](studies/d06/README.md)

實驗使用 [CS329Z Assignment 1](https://github.com/cs329z/assignment1-harness) 整理的文件與 email 資料；詳見[資料來源](datasets/SOURCES.md)。

## P01／P02 本機測試

`python -m scripts.test01` 與 `python -m scripts.test02` 分別執行原始 deterministic 案例及完整的本機 Ollama live 測試，直接使用獨立 pipeline API。資料沿用 HW1 fixture，GT 僅供評分。[指令、門檻與輸出紀錄](scripts/README.md)。

已驗證的本機實驗：[P01 分類，54/60](studies/p01/README.md) · [P02 摘要，5/5](studies/p02/README.md)。完整 request、原始 completion 與評分結果隨研究紀錄保存；後續執行仍寫入不納入 Git 的 `runs/`。

本專案可獨立 checkout、安裝與測試，不需要課程 repository 或 PDF。所有程式、fixture 與執行資料都從本專案或其資料準備流程取得；課程網址僅用於來源註記與人工參考。
