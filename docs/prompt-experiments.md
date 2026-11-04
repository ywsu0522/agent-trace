# System prompt 實驗紀錄與評估流程

## E0–E5 是歷史紀錄標籤

E 編號代表當時完整的 system prompt 快照；其中包含工具描述、參數 schema、呼叫格式與部分示例。它們不是六種模型，也不是六套完整的執行環境。模型設定、程式與語料版本必須另外記錄。

從本次整理起，E 編號只用來解讀歷史研究。程式不提供 `--env` 或 `--agent` 的版本選項，不讀取 E 版本表，也不依 E 編號切換工具。一般執行固定使用 `configs/agents/current.json` 與 `configs/prompts/system.txt`。

| 歷史 ID | 當時的改動／假設 | 已觀察的結果 | 可以作出的結論與限制 |
|---|---|---|---|
| E0 | 原始 prompt，含 email_qa interaction 示例 | 保存的 20 題歷史答案字串命中 15/20；d06 未答對 | 歷史參考，不是目前程式／模型設定的全新 baseline；證據支持未全體審查 |
| E1 | 將同一 interaction 示例改成 search_docs，觀察路由 | d06 的三個起手都選 search_docs；完整 run 仍未答對 | 單題示例消融，不能推論全體問答改善 |
| E2 | 直接移除 interaction 示例 | d06 三個 probes 均缺少外層 name／args | 保存格式失敗；probes 未執行工具，不是三次完整任務 |
| E3 | 明確 name／args 格式，說明 search snippets 不等同全文 | d06 呼叫合法並讀文件，API spec 只讀 1–89/131 行，仍答錯 | 在同一題同時調整格式與工具描述；無法分開歸因，也無法證明泛化 |
| E4 | 明確 read_doc 分頁與接續方式 | d06 該次完全沒有 read_doc；固定歷史重播顯示路徑受描述與歷史共同影響 | 未進入翻頁階段，不能宣稱分頁指引改善成功；每格 replay 一次 |
| E5 | 移除工具目錄中的 email_qa，由主 agent 自行 search/read | 目前同內容 prompt 的新 baseline：18/20 答案命中、18/20 核心有支持、19/20 文件預算合格 | 未隔離 prompt 的因果效果，也沒有保留題泛化證據；目前採用相同 prompt 內容 |

詳細原始證據：[d06 研究](../studies/d06/RESEARCH.md)、[20 題歷史](../studies/baseline-20/README.md)、[近期補救實驗](../studies/refinement/README.md)。

2026-11-04 已完成目前 prompt 的[全體新 baseline 與事後證據審查](../studies/doc-baseline-20261104/README.md)。完整回覆的事實支持為 17 supported、1 partial、2 unsupported；另有引用標籤與停止狀態問題。舊 E0 的 15/20 與本次 18/20 使用不同時期的程式／設定，不能直接歸因於 prompt 改善。

## 是否對特定題目 overfit

**E1–E4 曾反覆使用 d06 的失敗作開發依據，因此有單題過度調整與評估污染的風險。** 格式、snippet 與分頁說明雖然寫成通用規則，調整依據仍來自同一個已知問題。沒有獨立保留題與全體新評估，無法判定已發生何種程度的 overfitting，也不能宣稱改善具有通用性。

本次逐份檢查六個 prompt：未包含 d06 的完整問題或正確日期 `2026-12-31`。這只排除了這兩個明顯的答案洩漏字串，不代表沒有間接偏差。E0 的示例本身也有 email 工具路由偏向；E5 繼承了部分先前描述，其泛化仍待評估。

已保存的 P01 60 封與 P02 五天 fixture 也曾用於調整設定；其通過結果屬開發資料上的驗證。它們不作為未見資料成績。

## 保存原文而不建立程式選項

E0–E4 的原始 prompt、工具目錄與 diff 保留在 `studies/d06/record/environments/`，原始 request/completion 與 metadata 不修改。移除 `configs/` 的重複 E 檔案前，已逐檔確認它們與研究封存位元組一致。

目前 `configs/prompts/system.txt` 與整理前 E5 prompt 位元組相同；工具目錄直接從其中的 Tool／Description／Parameters JSON Schema 解析。原先獨立的 E5.tools.json 與該解析結果相同，故不再維護第二份衍生設定。

以下 SHA-256 依原有規則計算：讀取文字、正規化換行後，以 UTF-8 編碼計算。保留這些值供人工核對，runtime 不讀取此表。

| ID | Prompt SHA-256 | 原文 |
|---|---|---|
| E0 | `b4175ce770533e292335930b7fb969f5a8fbe615ef9584c207050207d6d88651` | [歷史快照](../studies/d06/record/environments/E0.system.txt) |
| E1 | `734d91b737cc1dbd9ca025d1a1ff549bc8bb23061257289ceb2b67b7f055beec` | [歷史快照](../studies/d06/record/environments/E1.system.txt) |
| E2 | `f6a835fb69c20b1ed858ed67a0592fce83bad4fe7926ccddeb5806753f03297b` | [歷史快照](../studies/d06/record/environments/E2.system.txt) |
| E3 | `69b57f6bc9df6b11f65d39199c3c1709cf5199fd8893eac007cead39394a60c1` | [歷史快照](../studies/d06/record/environments/E3.system.txt) |
| E4 | `e22ad82e59eb0f4f59639dbc7eacdc407ac3507c5731d29fd174a32a12b37284` | [歷史快照](../studies/d06/record/environments/E4.system.txt) |
| E5 | `9277c4bfa6707a2bd355e30edd957adfd66deb2e6d7dd311f2fdea259677a88c` | [目前同內容的 prompt](../configs/prompts/system.txt) |

## 後續實驗流程

1. **先寫假設與變因。**在 Markdown 說明要解決的錯誤、觀察過哪些開發題，以及這次唯一主要改動；不把某題日期、文件 ID 或答案塞入通用 prompt。
2. **區分開發與評估。**公開 20 題可以用於開發及報告回歸；另建尚未用於調整的保留題。若已看過某題並據此修改，就將其列為開發資料，不再稱為盲測。
3. **固定輸入與成本定義。**保存完整 prompt、解析出的工具 schema、模型 digest／參數、程式快照、語料 hashes、呼叫與文件結果預算。任何修復、aux、失敗呼叫都計入。
4. **執行受控比較。**一般執行只有一份目前設定。一次性的研究可以透過通用 `--system FILE` 指定實驗文字檔；不新增 E 預設、不在 runtime 寫版本分支。檢索與修正策略的差異寫在該研究 Markdown 與 run metadata。
5. **分開評分。**答案命中、正確證據是否進入上下文、引用 ID／行號是否正確、格式／停止狀態與成本各自報告。gold 只作事後評分，不用來決定補救或挑答案。
6. **保存負面結果。**保留原始輸出、環境錯誤、沒有改善與改壞的案例；重跑另建目錄，不覆寫舊紀錄。
7. **再決定是否採用。**只有在全體回歸與保留題結果支持時，才把通用改動合併到目前 prompt，並更新唯一設定中的 checksum。若沒有提升，照實記錄，不另累積一套可選 runtime 模式。

`report`／研究 builder 仍能離線閱讀舊紀錄。通用的單次 request replay 與 `--system FILE` 仍保留；原始 E 標籤只屬保存資料。舊 runtime 程式快照若已隨研究封存，可供查核，不由目前 CLI 內建選取。
