# 實驗資料來源

實驗使用 [CS329Z Assignment 1](https://github.com/cs329z/assignment1-harness) 整理的資料，參考版本為 `c6cab03d161e4e8db8a9e2c12caf8e353b079beb`。

- `docs/`：共用的 24 份 Cardinal Energy 文件，原路徑為 `data/docs/`，供 P09 文件搜尋與後續 agent 測試使用；各檔 checksum 見 [docs.provenance.json](docs.provenance.json)。
- Email archive：P01-P04 與後續 agent 工具共用的 email 語料，由課程網站另行下載，預設解壓至 `.cache/emails.jsonl`，完整 archive 不包含在 repo。網址、筆數及 checksum 見 [email-source.json](email-source.json)。此描述不另替第三方 email 內容宣告授權。
- `studies/`：實驗者保存的 request、completion 與工具結果，其中含上述資料的摘錄。
- `configs/` 與歷史 trace 的工具名稱、參數格式保留與原實驗相容的介面；文件問答的參考規格也保留在研究紀錄中。

語料與測試題目分開存放：`tests/fixtures/` 保存題目、標準答案與評分資料；`studies/d06/` 保存 P09 單題 d06 的實驗紀錄。文件語料原存於 `datasets/d06/docs/`，現移至共用目錄，內容與 checksum 不變；歷史執行紀錄保留當時的原始路徑。

課程 repository 隨附的 MIT 條文與原 copyright notice 保留於 [LICENSE.cs329z](LICENSE.cs329z)，適用於取用的上游素材；不代表本專案的程式碼整體採用 MIT，亦不替第三方 email 內容另行授權。

- `tests/fixtures/priority_gold.json`：HW1 P01 `priority` 的 60 封分類測試信件與標準分類，原始 JSON 原封保留。
- `tests/fixtures/doc_questions.json`：HW1 P09 `search_docs` 的 20 題問題、答案別名與文件證據，原始 JSON 原封保留；執行時不讀取外部課程目錄。
- `tests/fixtures/digest_days.json`：HW1 P02 `daily_digest` 的 5 天指定信件 ID、必提別名群組與禁提詞，原始 JSON 原封保留；信件本身由 email archive 取得。
- `tests/test_priority.py`、`tests/test_daily_digest.py`：原始 deterministic 案例移植，僅調整 imports、API 呼叫及離線模型替身；不匯入課程程式包。Live 評分腳本位於 `scripts/test01.py`、`scripts/test02.py`，沿用原始門檻與比對規則。
