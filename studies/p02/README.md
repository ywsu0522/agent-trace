# P02：本機每日 email 摘要

2026-10-31 保存的完整驗證 run：5 天全部通過長度、必提內容與禁提內容檢查。這是同一組 fixture 上調整設定後的驗證結果，不代表未見資料的泛化成績。

| 日期 | 摘要單字數 | 長度 | 必提內容 | 禁提內容 |
|---|---:|---|---|---|
| 2001-06-22 | 127 | 通過 | 通過 | 通過 |
| 2001-07-05 | 75 | 通過 | 通過 | 通過 |
| 2001-07-25 | 110 | 通過 | 通過 | 通過 |
| 2001-08-08 | 138 | 通過 | 通過 | 通過 |
| 2001-08-21 | 129 | 通過 | 通過 | 通過 |

模型為 `qwen3.5:4b-q4_K_M`，temperature 0、think false、num_ctx 4096、num_gpu 12、num_batch 64。共 153 次真實本機推論：148 次分類與 5 次摘要，沒有分類 replay。每一天只生成一次摘要，再以相同原始字串執行三種檢查；沒有事後截斷輸出。GT 僅用於評分，不放入模型輸入。

Writer 保留完整 urgent threads 與來源 subject；最多帶入三個 normal threads 的短摘錄。Prompt 目標為 220 個英文單字，評分仍使用原始 300 個英文單字上限。完整信件與分類另存 prepared.json。

[完整摘要與評分](record/verified-20261031/results.json) · [設定、模型 digest 與來源 checksum](record/verified-20261031/metadata.json) · [逐檔 SHA-256](integrity.json)

`record/verified-20261031/` 完整保存選定 run 的原始位元組，包括 fixture、每一天的 events.jsonl、prepared.json、written.json、輸出與 evaluation。歷史 metadata 中的本機路徑保留原樣；它們不作為目前執行所需路徑。此目錄記錄 daily_digest pipeline 的執行，不使用 agent tool-call loop。

重跑全部 deterministic 與 live cases：

```sh
uv sync --locked --extra test
uv run agent-trace prepare-data --download
uv run python -m scripts.test02
```

需要本機 Ollama 已啟動且模型已安裝。新結果寫入 `runs/`；輸出可能因執行環境而不同。[測試與輸出格式說明](../../scripts/README.md)。
