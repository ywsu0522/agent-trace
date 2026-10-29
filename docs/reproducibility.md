# 執行與實驗紀錄

## 提問與設定

```sh
uv run agent-trace run "What is the minimum password length?" --trace
uv run agent-trace run --task d06 --agent current
uv run agent-trace run --task d06 --agent baseline
uv run agent-trace run --task d02 --dry-run
```

`current` 使用 E4 prompt；`baseline` 使用 E0。任意問題預設不評分；使用 `--expected-answer` 提供接受字串，或使用 `--task d01` 至 `d20`。答案字串命中與證據是否充分是不同判準。

可用 `--docs DIR`、`--emails PATH` 指定自己的 corpus，或用 `--system PATH` 修改 prompt。缺少工具所需資料時會在模型呼叫前停止。`--probe` 只觀察起手決策，不執行工具。

```sh
uv run agent-trace prepare-data --archive /path/to/emails.jsonl.gz
uv run agent-trace prepare-data --download
```

兩種方式均核對 corpus checksum；資料解壓至忽略追蹤的 `.cache/emails.jsonl`。

Windows 也可使用 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/reproduce.ps1 -Task d02`；macOS/Linux 可使用 `sh scripts/reproduce.sh d02 current`。這些入口會準備 uv、依賴與資料，需先自行啟動 Ollama。

## 輸出與離線閱讀

每次執行保存完整 messages、completion、解析結果、工具結果與設定，預設寫入新的 `runs/run-<timestamp>/`。可用 `--out` 指定不存在的目錄。`trace.md` 與 `trace.html` 提供路徑摘要和可展開的原文；`events.jsonl` 是逐筆寫入的原始事件。

```sh
uv run agent-trace report runs/my-run
uv run agent-trace report path/to/events.jsonl --out runs/imported
uv run agent-trace replay --request runs/my-run/initial-request.json --agent current
```

`report` 不呼叫模型。`replay` 只發送一次主 request，不執行工具。強制終止或斷電後，可從已保存的事件重建報告；不完整的最後一筆事件會標示缺漏。

需要彙整研究時，可執行 `uv run agent-trace register runs/my-run --label "我的實驗"`，再執行 `uv run agent-trace build`。

## 歷史實驗

[20 題紀錄](../studies/baseline-20/README.md) 使用 E0；保存的答案字串命中為 15/20。E4 尚未完整重跑全部 20 題。[d06](../studies/d06/README.md) 保存 prompt 修改與固定 request 重播比較。

保存紀錄可直接離線閱讀。新推論可能因硬體、Ollama 版本及模型的非確定性而改變輸出與工具路徑。`reproduce` 會準備資料並核對模型 digest；一般 `run` 允許使用不同模型。

## 驗證

```sh
uv run pytest
uv build --wheel
uv run python tools/audit_publication.py
```

Python 版本由 `.python-version` 指定，依賴由 `uv.lock` 鎖定。工具實作包含文件、email 搜尋／讀取、email QA 與 daily digest；歷史 prompt 另外列出的 terminal、memory、ask_user 在此 runtime 中未實作。
