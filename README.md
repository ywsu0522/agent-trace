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
- `configs/`：agent profiles、prompt 與題目設定。
- `datasets/`：實驗文件與 email 來源描述。
- `studies/`：已保存的實驗紀錄與比較。

HTML 閱讀頁可在本機重建，不納入 Git；已保存的紀錄可直接閱讀 Markdown。

[其他用法](docs/reproducibility.md) · [20 題歷史紀錄](studies/baseline-20/README.md) · [d06 prompt 比較](studies/d06/README.md)

實驗使用 [CS329Z Assignment 1](https://github.com/cs329z/assignment1-harness) 整理的文件與 email 資料；詳見[資料來源](datasets/SOURCES.md)。
