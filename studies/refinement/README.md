# Bounded evidence refinement: a repaired date with unresolved citation errors

2026-11-04，本機 `qwen3.5:4b-q4_K_M` 的小規模回顧性實驗。**補讀未讀尾頁後，d06 的日期答對了；只再檢查原有證據仍答錯。修正輸出的引用行號依然錯誤，所以不能宣稱完整取證成功。**

這是兩個問題、三種既有軌跡的診斷，並非全新 E5 或全體 P09 benchmark。原始答案沒有重新推論；不拿歷史 E0/E3/E4 的差異比較版本效能。

## 成對比較

使用 d06 E3 `protocol-after` 的同一份問題、原始草稿和工具觀察。兩個 treatment 使用相同的 review prompt、模型與設定，各最多一次新模型呼叫；只有補頁條件新增 `gridlens-api-spec` 第 90–131 行。補頁由已讀範圍決定，不使用參考答案或參考行號。

| 條件 | 日期結果 | 額外模型請求 | 額外讀取 | 文件結果用量，課程估算 tokens |
|---|---|---:|---:|---:|
| 原始草稿 | 2027-08-25，錯誤 | 0 | 0 | 5,142 |
| review-only | 2026-08-25，錯誤；仍混淆 release/shutdown 日期 | 1 | 0 | 5,142 |
| continue-then-review | 2026-12-31，日期命中；引用行號錯誤 | 1 | 1 | 5,855／6,000 |

[完整成對輸出與成本](record/d06-paired-repeat/results.json) · [兩個條件的模型輸入](record/d06-paired-repeat/plans.json) · [設定、模型 digest 與來源 hashes](record/d06-paired-repeat/metadata.json)

成對重跑的 review-only 回覆達 384 個 backend output tokens，`done_reason=length`；原始字串完整保留，未裁切成合格答案。補頁後回覆為 262 tokens，正常停止。不能將這個單題差異當成準確率或穩定度的改善估計。

## 控制與未補救的失敗

| 來源軌跡 | review-only | continue-then-review | 可說明的範圍 |
|---|---|---|---|
| d09 E0，已完整讀過文件，原本答對 | 保留正確 E-214，輸出逐字相同 | 無未讀尾頁，跳過，0 新請求 | 規則沒有對完整閱讀追加無效補頁 |
| d06 E4，只有 search、未進入 read | 仍未取得日期，並把 snippet 缺漏擴大成文件沒有 | 沒有已讀文件可續接，跳過，0 新請求 | 本策略無法補救「根本沒開始讀」的路由失敗 |

[d09 正例控制](record/d09-complete-control/results.json) · [d06 search-only 失敗控制](record/d06-search-only-control/results.json)

跳過是觸發條件不成立，不是模型作出的正確回答，也不算一次成功的獨立樣本。完整閱讀不等於內容一定正確；這兩個控制僅驗證本次規則與案例。

## 執行失敗與成本

第一組 review-only 遇到 CUDA 初始化錯誤；同組補頁條件隨後成功，日期命中但引用行號錯誤。為取得可比較的兩份 completion，另做一組成對重跑。**第一組的錯誤、補頁成功與完整重跑全部保留**，沒有刪除失敗。[第一組結果](record/d06-initial/results.json)

整組實際新增 6 個 HTTP 模型請求：5 個成功回覆、1 個環境錯誤。兩個沒有可補頁的控制不發出補頁推論。每個策略的完整成本是原始 baseline 加該 treatment；歷史 baseline 為共用紀錄，不能在實際新增成本中重複計算。[整組成本](summary.json)

所有成功回覆的 native token 計數與完整 HTTP request/response 均保存；失敗請求的 native 用量未知，不補成零。模型載入、固定執行順序與 prefix cache 影響耗時，所以不將耗時差異歸因於策略。

## 引用核對與下一步

補頁條件兩次都取得正確日期及正確原文句子，但第一次宣稱 API spec 第 97 行、重跑宣稱第 103 行；實際句子在第 120 行。第 97 行是空行，第 103 行是 HTTP 404 表格項目。[事後引用核對](citation-review.json)

這證明「答案字串正確」「正確證據已進上下文」「引用定位正確」必須分開記錄。沒有以引用核對或 gold 替生成器挑答案。本實驗尚未建立完整語義支持 verifier。

後續狀態更新（2026-11-05）：目前 prompt 的[全體 baseline 與來源審查](../doc-baseline-20261104/README.md)已完成。兩個 baseline 失敗均只有搜尋、未開始閱讀，不在本次尾頁續接規則涵蓋範圍內。下一步比較檢索定位與可驗證的引用格式；補救策略保留為獨立條件。測試保留題與正例回歸後，才判斷是否啟用有條件修正。

## 重現與原始證據

```sh
python -m scripts.refine_docs --source studies/d06/record/runs/protocol-after --task d06 --mode live
```

新結果存於新的 `runs/` 目錄；本研究的 `record/` 不覆寫。每組保存 baseline trace/events、目前語料 hashes、實際使用的程式快照、每個 treatment 的原始 HTTP 證據與輸出。報告欄位在實作期間補充了耗時與截斷標記；`summary.json` 已核對第一組與成對重跑的模型 messages 及設定完全相同。

研究範圍及預算：[研發計畫](../../docs/qa-development.md)。所有紀錄檔案的 SHA-256 見 [integrity.json](integrity.json)。
