# 近期方向：可靠取證 QA 與有上限的 test-time 補救

## 定位與呈現預設

以可追查證據的本機 QA agent 為求職展示主線。沿用 Python CLI、JSON/JSONL 原始紀錄與 Markdown/HTML trace，不另建聊天前端。首頁摘要以英文呈現，深入研究筆記可保留中文；這是後續呈現預設，並非已完成首頁改寫。

每個結論附設定、來源版本、原始輸出、評估方法與限制。結果表分列答案命中、來源支持診斷、文件結果用量、模型呼叫、tokens 與時間。未知成本保留未知；實驗沒有改善也保留。

## 第一版的固定題目、條件與執行邊界

目前 baseline 批次入口為 `python -m scripts.test09`，會透過既有 CLI 與新的 AgentSession 依序執行全部 20 題。下列改良檢索及全體補救比較仍是後續規格；比較條件只用描述性名稱記錄，不增加 agent profile 或全域程式模式。下方已保存的 refinement 仍是獨立的歷史案例實驗。

使用 `tests/fixtures/doc_questions.json` 的全部 20 題（d01–d20），不另把 P02 的五天摘要或 P04 的 25 題 email QA 混入這輪成績。

| 類型 | 題數 | 題目 |
|---|---:|---|
| direct | 6 | d01 Firmware 主管；d02 密碼長度；d03 API 每分鐘請求上限；d04 Professional 每 meter 月費；d05 Kestrel 技術負責人；d06 API v1 關閉日期 |
| deep | 5 | d07 陪審義務全薪天數；d08 匿名倫理熱線；d09 sensor mesh link lost 錯誤碼；d10 postmortem 草稿期限；d11 區域故障 RTO |
| superseded | 5 | d12 美國出差每日餐費；d13 VP 核准門檻；d14 PTO 結轉天數；d15 混合辦公到班日；d16 on-call 每週津貼 |
| lexical | 4 | d17 健身房月補助；d18 筆電遭竊通報分機；d19 發薪日；d20 會議與線上課程年度預算 |

正式比較固定四個條件，採用相同模型、語料、題目與預算定義：

| 條件 | 檢索／生成流程 | 新的完整 AgentSession runs | 額外補救模型呼叫 |
|---|---|---:|---:|
| 現有檢索 | 目前 prompt＋現有檢索 | 20 | 0 |
| 改良檢索 | 同一 prompt＋改良檢索／證據定位 | 20 | 0 |
| 只做 review | 沿用改良檢索的同一草稿與證據，review 一次 | 0 | 20 |
| 補頁後 review | 沿用改良檢索的同一草稿與證據，依閱讀進度補頁後 review 一次 | 0 | 最多 20 |

因此是 **20 道不同問題、40 次完整 AgentSession runs、最多 40 個額外補救模型呼叫**，最多得到 80 個條件輸出；不是 80 道不同問題。一次完整 run 本身可能包含多個主／aux 呼叫，全部另計成本。補頁條件沒有可續讀頁面或預算不足時，明確記錄跳過，不當成一個新的推論樣本。

前兩個條件比較檢索改動；改良檢索與後兩個條件比較額外 review／補證據的作用。每題的兩種檢索各建立新的 `AgentSession`，從原始問題開始搜尋、讀取與回答，不共享其他題目的 messages。Review 是獨立的受控補救 pipeline，不是重新啟動一次完整 session，也不是現有 replay 的回溯續跑。

依使用者要求，取消五題先行試跑；已直接按 fixture 順序執行目前 agent 的全部 20 題（d01–d20），每題使用新的 AgentSession，取得無補救的完整 baseline。

實際推論開始前，先在對話中展示目前 system prompt，以及 d01 第一個 request 的完整 system／user messages 與 API 參數。這個輸入預覽不呼叫模型，不算進測試成績。

完成 baseline 與失敗分類後，再開發改良檢索與補救策略；版本凍結時才執行上表的全體比較。若開發期間有改 prompt、檢索、輸出格式或模型設定，先前紀錄保留為開發成本，正式比較重新跑，不混用版本。

Baseline 收尾必須逐題審查：以實際送進模型的工具內容核對核心答案、附帶敘述與引用，另查停止原因和預算。答案別名命中、讀到參考行及 session 的 `done` 都不能單獨當成完整通過；事後讀取全文所得的證據不可回填成 agent 當時已見的內容。審查另存 sidecar，保留原始輸出與自動評分。

2026-11-04 的 20 題 baseline 已執行並完成事後逐題審查，[完整研究紀錄](../studies/doc-baseline-20261104/README.md)與[來源審查](../studies/doc-baseline-20261104/evidence-review.md)已歸檔至 `studies/`。核心答案有支持為 18/20；完整回覆的事實支持為 17 supported、1 partial、2 unsupported。d08/d14/d15 把文件標為 Email ID；d20 的附帶適用範圍未完整取證；d06/d18 的最終原生回覆以 `length` 停止卻被 session 標成 `done`。這些分項不可合併宣稱為 18 題完整通過。審查沒有新增模型呼叫或修正 baseline 答案。

下一階段先處理停止狀態、文件預算與搜尋後讀取／定位，再凍結改良檢索條件。這兩個 baseline 失敗都未進入 `read_doc`，現有「已讀尾頁續接」規則無法補救；不能直接套用歷史 d06 補頁成功的結論。全體補救比較與保留題評估仍未完成。

本輪推論時修正的具體名稱為 **rule/evidence-guided refinement**：不更新模型權重、不讓 gold 答案或參考行號觸發補救。首版補頁只涵蓋已讀文件的尾頁續讀；引用格式與行號核對列為評估指標，引用回饋修正及 search-only 的補救另立後續條件。尚未實作 reward model 引導抽樣或特定 test-time alignment 論文演算法。

## 三個依序可驗收的階段

1. **建立可比較的 baseline。**移植 P06/P09 獨立 deterministic 測試、加入目前 prompt 的 20 題批次入口及逐題紀錄。歷史結果只作背景；比較改動時，使用相同執行環境的新推論。Prompt 調整與 overfitting 風險依[實驗流程](prompt-experiments.md)記錄，不增加版本預設。P04 的 25 題 email QA live 是另一組任務，維持整題三次 search 的契約。
2. **改善取證工具。**在獨立條件中比較現有全文排名／首個命中 snippet 與段落檢索／定位資訊。保留原文、doc_id 與行號，符合 snippet 150、read 1500、整題文件結果 6000 個課程估算 tokens 的限制。先評估是否取得相關段落，再看答案，避免把檢索成功等同回答成功。
3. **加入有上限的修正策略。**先比較 baseline、一次 review、補充證據後一次 review；只有下一階段才考慮 Best-of-N。控制檢索版本與推論設定，統計修復與退步、失敗分支及全部成本。新加保留題於最終評估前不供調整；公開題成績不宣稱泛化。

首輪的成本敏感範圍限定文件 QA，不同時擴大到 P01/P02、tree search、SMC、terminal 或 memory。程式只保留目前 prompt；歷史原文與 trace 留在研究紀錄，研究策略先透過獨立入口比較。

## 第一個補救實驗：歷史 partial-read 的 bounded refinement

入口為 `python -m scripts.refine_docs`。這是利用既有 trace 做的回顧性診斷，**不是目前 agent 的全新 baseline，也不是完整 Self-Refine 論文重現**。回饋來自程式檢查已讀文件的尾頁進度，不是另一個模型的自由自評。

| 條件 | 生成輸入 | 新增模型呼叫 | 新增文件讀取 |
|---|---|---:|---:|
| archived baseline | 原始問題、當時的工具結果與草稿；沿用已保存輸出 | 0 | 0 |
| review-only | 問題、同一草稿、當時已見的文件結果 | 最多 1 | 0 |
| continue-then-review | 與 review-only 相同，再加入未讀完文件的下一頁 | 最多 1 | 預設最多 1 |

兩個 treatment 使用相同 review prompt、模型與設定。這能區分「單純再生成」和「補頁加再生成」；沒有測試獨立的 retrieval-only 策略，也不能分離補頁的上下文長度效果。每個策略成本為原始 baseline 加該 treatment，整個比較實際新增兩次呼叫，不冒充同一題的一次免費補救。

兩個 treatment 固定依序執行，本機模型載入及 backend prefix cache 會影響耗時。本輪可報告實際時間，但不能把兩者的時間差歸因於策略本身，也不將 temperature=0 的重跑視為獨立統計樣本。

### 規則與界線

- 只對已呼叫 `read_doc`、且仍有尾頁的文件補頁；搜尋結果中的未讀文件不會自動全部展開。頁面選擇不使用答案別名、參考 doc_id、參考行號或 task ID。
- 沒有可補頁時，記錄原因並跳過補頁條件，不假造新的推論樣本。已完整讀完的正例與只有搜尋的失敗例是必要控制。
- 原始及新增文件結果合計不得超過 6000 個課程估算 tokens。原本已超標則拒絕該補救推論；不重領預算。重複結果在成本中照算，模型輸入才去除完全相同的 evidence。
- 預設每條件最多一次模型呼叫、384 個 backend output tokens；prompt 估算上限 7600，`num_ctx=8192`。課程估算並非 backend tokenizer 的硬保證；native 計數另記。模型錯誤不自動重試。
- 輸出全部保留，不依 gold 挑一個「最佳答案」。評分資料在 runner 邊界，生成函式只接收問題、草稿與觀察過的工具結果。
- 答案別名命中與參考行進入新增視窗只作事後診斷；未實作完整語義支持 verifier。新版政策衝突、未搜尋到文件、無意義的最終回覆仍是後續問題。
- 一個文件尾部未讀不代表一定需要補頁：可能引入噪音、增加延遲或改壞正確答案。正例回歸與不受觸發規則涵蓋的失敗案例必須保留。

### 執行與驗收

```sh
# 只準備兩個條件，不呼叫模型
python -m scripts.refine_docs --source studies/d06/record/runs/protocol-after --task d06

# 本機 Ollama，各 treatment 最多一個新模型呼叫
python -m scripts.refine_docs --source studies/d06/record/runs/protocol-after --task d06 --mode live

# 已讀完整文件的正例控制
python -m scripts.refine_docs --source studies/baseline-20/record/d09 --task d09 --mode live

# 只有 search、未進入 read 的失敗控制
python -m scripts.refine_docs --source studies/d06/record/runs/paging-after --task d06 --mode live
```

每次使用新目錄；預設輸出到不納入 Git 的 `runs/`。`metadata.json` 保存 baseline／source／documents hashes、模型 digest、設定與限制；`plans.json` 保存送入模型的準備結果；每個 treatment 保存 HTTP request/response、原始 completion 與 preparation；`results.json` 及 `study.md` 保留兩個 treatment 的結果與總成本。來源 trace/events 及目前程式副本一併保存，原始研究紀錄不覆寫。

[2026-11-04 首輪完整紀錄](../studies/refinement/README.md)已保存：補頁後修正 d06 日期，但引用行號仍錯；單純 review 沒有補救日期，完整閱讀與 search-only 兩類控制也保留。這些是小規模回顧性結果，並非已完成上述三個階段。

只有在結果與來源完整核對後，才挑選整組實驗（包含失敗與控制）複製進 `studies/`。首輪不以 d06 單題成功作驗收；最低要求是預算／gold 隔離測試通過、三類案例都有紀錄，以及清楚報告哪些錯誤沒有被補救。

## 求職可呈現的能力

- 從 trace 區分 retrieval、coverage、protocol、answer 與 stopping 的錯誤。
- 自行設計可執行的 inference-time refinement，而非只在 prompt 寫「再想一次」。
- 使用對照組、來源隔離、硬次數限制與成本紀錄評估補救策略。
- 保留負面結果及架構限制；完成全體與保留題評估後再寫準確率改善敘述。

相關：[test-time 方法分類](test-time-methods.md)、[d06 失敗分析](../studies/d06/RESEARCH.md)、[重現操作](reproducibility.md)。
