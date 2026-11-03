# Agent Trace：常見 test-time 方法與可行性排序

查核日期：2026-11-03。本紀錄整理已討論的方法及其適用性，供後續選題參考；排序不是已決定的實作清單，也不是效果排名。沒有新增模型實驗。

本文以 *Taming Imperfect Process Verifiers* 的 literature review 為起點，補充 self-consistency 與 self-refinement。原論文主要討論 verifier 引導的生成、搜尋與抽樣，並非所有 test-time 技術的完整綜述。[R1]

## 分類與專案範圍

本文的 test-time 方法指：固定主模型權重，在當前任務中透過額外生成、評估、修正或搜尋改善結果。需分清三件事：

- **評估器：**規則、outcome verifier 或 process verifier 提供判斷。PRM 是評估中間過程的模型；value function 則估計未來回報，不能把「工具呼叫合法」當成「最終會成功」。[R2]
- **使用判斷的策略：**Best-of-N 選最高分；self-consistency 聚合答案；rejection sampling 依接受條件或機率留樣本；tree search 決定哪些部分路徑繼續展開。
- **評估粒度：**可在完整答案、部分文字或 agent action／數個 turns 上評估。粒度與策略可以組合，並非互斥分類。

可行性依目前的本機 Ollama、文字型工具協定、既有 pipeline 與 trace／replay 能力判斷。對照範圍包括：

| 專案任務 | 用來判斷方法適用性的重點 |
|---|---|
| P01 email 分類 | 類別與理由、歧義判斷；目前函式及 deterministic 測試固定一次模型呼叫，多候選需放在獨立研究入口 |
| P02 每日摘要 | 分類與 writer 分開；可評估涵蓋、來源支持與字數，不能以事後裁切滿足長度限制 |
| P04 email QA | 多跳取證與支持來源；獨立 pipeline 每題最多三次 search，新增分支不能各自重領額度 |
| P06／P07 工具協定與 agent loop | 格式、參數、工具回饋及停止；可比較局部修復與路徑選擇 |
| P09／E5 文件及 email 問答 | 文件讀取、政策更新、跨來源證據與工具路徑；E5 主 agent 的 email 搜尋依 session 預算，不等同 P04 的三次 search 上限 |

P03 BM25 是取證基礎，保留原有公式與排序契約。d06 可提供失敗案例，但適用性判斷不只依據它。HW1 的其他功能不在本文另立開發計畫。

依據：[專案首頁](../README.md)、[測試說明](../scripts/README.md)、[重現說明](reproducibility.md)、[目前設定](../configs/agents/current.json)，以及課程 reference checkout 的 `cs329z_hw1/adapters.py`。查核時課程參考版本為 `c6cab03d161e4e8db8a9e2c12caf8e353b079beb`；能力描述以當時工作目錄為準，不表示所有課程功能已完成。[課程來源](https://github.com/cs329z/assignment1-harness)

## 常見方法：依本專案可行性由高至低

排序考慮現有介面、額外狀態管理、評估訊號與運算成本。相鄰項目的順序可能隨任務改變；下列用途是適用性例子，並非新增研究承諾。

| 順序／可行性 | 方法與基本機制 | 在專案中的適用性 | 主要限制 |
|---|---|---|---|
| 1／高 | **Iterative refinement：驗證後修正。**先產生結果，再根據回饋改寫或補取證；Self-Refine 使用模型自身回饋。[R3] | P02 摘要內容與長度；P04／P09 答案支持性；既有工具格式／參數錯誤修復也是局部應用 | 應分清純自評、規則回饋與來源證據回饋。格式合法不代表內容正確；修正也可能把正確答案改錯 |
| 2／高 | **Self-consistency／多數決。**抽樣多條路徑，將最終答案正規化後聚合。[R4] | P01 三分類、QA 的日期／人名／數值答案；不必先建立額外 scorer | 多條路徑可能共享錯誤；摘要不適合直接字串投票。僅分類標籤投票時稱 majority voting，不等同完整 CoT self-consistency 重現 |
| 3／高 | **Best-of-N／reranking。**生成 N 個完整候選，以 verifier 或 scorer 選最高分。[R5] | P02 多份摘要、P01 分類與理由、P04／P09 完整 QA 候選；現有執行紀錄容易沿用 | scorer 本身會錯且需要成本；要分開看候選是否含正解，以及 selector 是否選對。P01 多候選不直接改掉原始單次 API |
| 4／中高，限既有 backend 能力 | **Constrained decoding。**生成時限制可輸出的結構；PICARD 以增量 parsing 排除非法 token。[R6] | P01 已使用 backend schema 輸出，可作格式控制；工具結構化輸出也與此相關 | 本機 schema 功能不代表 HW1 文字 callable 原生支援；任意 grammar 控制需額外介面。生成後 parse／validate 再重試屬第 1 項，不是 constrained decoding；語法約束不能保證內容正確 |
| 5／中 | **Action／block-level 候選選擇或抽樣。**每次只生成下一步或一小段，再選擇或按權重抽樣 | QA 的下一個工具呼叫或少量 turns；可利用固定 messages 比較不同決策，不必每次整條重跑 | 需新增候選與續跑管理。選最高分與機率抽樣分開標示；只看呼叫文字，可能看不出執行後是否取得有用證據 |
| 6／中 | **Checkpoint backtracking。**後續發現路徑有問題時，回到較早決策改走別條路。[R7] | 文件與 email 多跳問答；特別適合有明確缺證據或重複操作的路徑 | 需要狀態快照、分支隔離與共用預算。現有單次 request replay 不等於完整回溯續跑；保留被放棄的 trace |
| 7／中低 | **Beam／tree search。**保留多條部分路徑，反覆展開、評估與剪枝；部分設計支援前瞻與回溯。[R5]、[R8] | 通用工具選擇及多跳 QA，比較不同取證路徑 | 多分支成本與 partial-state 評估需求較高；錯誤評分會過早淘汰正路。列出多個備案本身不等於 tree search |
| 8／中低 | **Outcome-level rejection sampling。**完整生成後依接受條件或機率保留，否則重抽。[R7] | 有可靠終局檢查的輸出；可理解為完整候選篩選的另一種方式 | 程式簡單，但 QA 正確性缺少完全可靠的接受器；成功率低時昂貴。任意分數閾值不保證指定目標分布，僅檢查格式不能宣稱答案正確 |
| 9／低 | **SMC／particle filtering。**維持多條軌跡，以增量權重與重抽樣分配運算。[R9] | 多跳 QA 的多路徑取證；能兼顧評分與路徑多樣性 | 要定義 proposal、目標與 importance weights，並處理粒子退化。依任意分數複製路徑只能稱啟發式方法，不能直接繼承 SMC 的性質 |
| 10／低 | **Token-level value guidance。**用部分文字的預測分數調整下一個 token 的機率；FUDGE 是代表方法。[R10] | 概念上可引導文字生成，但目前以工具 action 層級介入較切合架構 | 現有 adapter 主要回傳完整文字，沒有任意逐 token 重加權介面；另需合適的 prefix predictor，成本高於現階段的流程改動 |

VGB 的發想是：只往前生成可能累積 verifier 的偏差，而稍後的評分可能有助辨認較早的錯誤。因此把部分生成當作樹節點，借用近似抽樣的 random walk，設計機率式前進與回溯；在相應假設下減輕錯誤放大、控制抽樣分布。本文僅保留此想法，不列為實作重點。[R1]

## 必要的技術背景補充

常見發展還包括**長推理與 thinking budget 控制**，以及**依題目分配 test-time compute**。s1 的 budget forcing 結合特定模型訓練與思考終止控制，不能用增加 agent turns 等同替代；Snell 等人的研究則指出，不同難度下適合的運算配置會不同。[R11]、[R5] 這兩點補足原論文較偏 verifier sampling 的視角，僅作背景，不在此新增實作方向。

本文不討論測試時更新模型參數的 test-time training，也不將 prompt／messages 更新稱為模型訓練。

## 適用性判斷時保留的四項原則

1. **沿用任務契約。**P01 的多候選需與單次函式分開；P04 的 search 額度以整題合計；P02 保留未裁切的模型原始摘要。
2. **計入全部成本。**候選、失敗分支、verifier、修復與 aux 呼叫都計入，不能只報最後被選路徑。多候選可依序執行；temperature=0 重跑或 cache replay 不等於取得有用的獨立樣本。
3. **評分與生成分開。**Gold 答案／支持來源只用於事後評分，不進生成或 selector。格式合法、工具執行成功、答案字串命中與證據支持分開判斷；來源 ID 存在不等於來源支持答案。
4. **跨任務看效果。**分類看類別與漏判，摘要看涵蓋及無來源內容，QA 看答案與證據，loop 看路徑與成本；d06 的單題改善不能直接推論整個專案。可行性高也不代表一定能提升準確率。

目前 `AgentSession.send()` 的回合與估算 token 預算以單次呼叫為單位，token 計數只涵蓋主模型，不合計 aux 呼叫；它不是跨候選、修正或分支共用的整題預算。實作上述方法時需另設共用成本帳本，計入所有模型呼叫與搜尋次數。現有 replay 僅重播單次模型決策；checkpoint 續跑仍需保存分支狀態與剩餘預算。

## 代表文獻

保留直接支撐本文分類的原始研究；方法排序是對本專案的判斷。核心論文參考正文與 Appendix A，其餘依原始論文頁／摘要核對機制與範圍。

- [R1] [Taming Imperfect Process Verifiers (2025)](https://arxiv.org/abs/2510.03149)：verifier 引導抽樣、搜尋與回溯的文獻起點。
- [R2] [Let's Verify Step by Step (2023)](https://arxiv.org/abs/2305.20050)：process 與 outcome supervision。
- [R3] [Self-Refine (2023)](https://arxiv.org/abs/2303.17651)：回饋與迭代修正。
- [R4] [Self-Consistency (2022／ICLR 2023)](https://arxiv.org/abs/2203.11171)：多路徑答案聚合。
- [R5] [Scaling LLM Test-Time Compute Optimally (2024／ICLR 2025)](https://arxiv.org/abs/2408.03314)：verifier search 與運算配置。
- [R6] [PICARD (2021)](https://arxiv.org/abs/2109.05093)：增量 parsing 約束解碼。
- [R7] [On the Query Complexity of Verifier-Assisted Language Generation (2025)](https://arxiv.org/abs/2502.12123)：rejection sampling 與回溯。
- [R8] [Tree of Thoughts (2023)](https://arxiv.org/abs/2305.10601)：中間步驟分支、評估與回溯。
- [R9] [Syntactic and Semantic Control via Sequential Monte Carlo (2025)](https://arxiv.org/abs/2504.13139)：SMC 引導生成。
- [R10] [FUDGE (2021)](https://arxiv.org/abs/2104.05218)：prefix predictor 引導生成機率。
- [R11] [s1: Simple test-time scaling (2025)](https://arxiv.org/abs/2501.19393)：長推理與 budget forcing。

[R1]: https://arxiv.org/abs/2510.03149
[R2]: https://arxiv.org/abs/2305.20050
[R3]: https://arxiv.org/abs/2303.17651
[R4]: https://arxiv.org/abs/2203.11171
[R5]: https://arxiv.org/abs/2408.03314
[R6]: https://arxiv.org/abs/2109.05093
[R7]: https://arxiv.org/abs/2502.12123
[R8]: https://arxiv.org/abs/2305.10601
[R9]: https://arxiv.org/abs/2504.13139
[R10]: https://arxiv.org/abs/2104.05218
[R11]: https://arxiv.org/abs/2501.19393
