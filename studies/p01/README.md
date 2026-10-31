# P01：本機 email 優先級分類

2026-10-31 保存的完整驗證 run：60 封全部執行，答對 54 封，準確率 90%，超過原始 85% 門檻；unknown 為 0，輸出格式全部通過。這是同一組 fixture 上調整設定後的驗證結果，不代表未見資料的泛化成績。

模型為 `qwen3.5:4b-q4_K_M`，temperature 0、think false、num_ctx 4096、num_gpu 12、num_batch 64。分類使用 category／reason JSON schema 與 128 token 上限。共 60 次真實本機推論，沒有分類 replay。GT 僅用於評分，不放入模型輸入。

[完整結果與未通過原因](record/verified-20261031/results.json) · [設定、模型 digest 與來源 checksum](record/verified-20261031/metadata.json) · [逐檔 SHA-256](integrity.json)

`record/verified-20261031/` 完整保存選定 run 的原始位元組，包括 fixture、每封信的 events.jsonl、原始 completion、解析輸出與 evaluation。歷史 metadata 中的本機路徑保留原樣；它們不作為目前執行所需路徑。此目錄不是 agent tool-call loop，而是直接呼叫 priority pipeline 的真實推論紀錄。

重跑全部 deterministic 與 live cases：

```sh
uv sync --locked --extra test
uv run python -m scripts.test01
```

需要本機 Ollama 已啟動且模型已安裝。新結果寫入 `runs/`；輸出可能因執行環境而不同。[測試與輸出格式說明](../../scripts/README.md)。
