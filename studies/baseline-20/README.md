# E0：20 題歷史 Agent 路徑

[全體總表](record/README.md) · [批次 JSON](record/batch.json)

2026-10-24 的原始 E0 prompt／工具描述，模型 qwen3.5:4b-q4_K_M。由既有 JSONL **離線重建**，未重新推論。20 題答案字串命中 15 題，其中 13 題文件結果用量也未超標。證據支持尚未逐題人工審查；不是課程評分模型成績。

## 代表案例

| 案例 | 可核對的行為 | 精簡路徑 |
|---|---|---|
| d03 | API spec 第一頁已含請求上限，答案命中；與 d06 使用同文件 | [閱讀](record/d03/trace.md) |
| d09 | 讀 1–88，再接續 89–158 行，答案命中 | [閱讀](record/d09/trace.md) |
| d13 | 一次文件搜尋後命中新版核准門檻 | [閱讀](record/d13/trace.md) |
| d06 | 讀 release notes，錯用更新日期 | [閱讀](record/d06/trace.md) |
| d07 | 答案命中，但同視窗重讀；文件結果 6790，超過 6000 | [閱讀](record/d07/trace.md) |
| d17 | 三次格式錯誤，沒有工具執行 | [閱讀](record/d17/trace.md) |

依不同機制挑選案例，完整結果仍保留 20 題。延伸：[d01 主／aux](record/d01/trace.md)、[d19 搜尋至 turns 用盡](record/d19/trace.md)、[d20 lexical 成功](record/d20/trace.md)。

每次 run 保留 trace.md／trace.json 與逐位元組保存的 events.jsonl；HTML 閱讀頁可由 report 指令在本機重建，不納入版本控制。接續／重讀、結果筆數、下一個 request 是否包含完整工具結果等註解由同一套通用規則產生；沒有補造歷史 HTTP 或模型設定。

可直接用 `uv run agent-trace report studies/baseline-20/record/d09 --out runs/d09-report` 離線重建單次報告。完整 batch 的來源 checksum 保存在 [batch.json](record/batch.json)。

課程 source archive 與 PDF 不納入此 repo。[d06 後續探索](../d06/README.md)。
