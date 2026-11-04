# 20 題 baseline：逐題來源支持審查

已完成 20/20 題事後審讀。由本次 Codex assistant 核對原始回答、實際工具結果、後續 HTTP messages 與固定語料；沒有重跑模型或修正答案。
原始 results.json、evaluation.json、trace、events 均保留原樣；本檔是另外的審查層。

## 結果

- 核心答案有實際送入證據支持：18/20。
- 完整回覆的事實支持：17 supported、1 partial（d20 的附帶適用範圍）、2 unsupported（d06、d18）。
- d08、d14、d15：答案有支持，但把文件 doc_id 標成 Email ID。
- d01、d16、d19：有角色／金額加成／and-or 措辭精準度問題，另列提醒，不直接當成核心答案錯誤。
- d06、d18：最終 native done_reason=length，但 session status=done；兩題的 prompt+completion native tokens 均為 8192。
- 全部 78 個應用層 request 與 HTTP messages 逐一相符；所有下列支持引文均確實出現在工具結果及下一次模型請求。

這不是把 18/20 字串命中直接改名為證據成功；搜尋 snippet 本身可以充分支持答案，引用錯誤和額外推論則另行標示。

| 題目 | 核心支持 | 完整事實支持 | 引用 | 審查結論 |
|---|---|---|---|---|
| [d01](d01/trace.md) | supported | supported | accurate | Nadia Ferreira 與 Firmware Engineering Manager 身分由實際 snippet 支持；不必只認 fixture 的 org-chart。Heron 的附帶角色描述較籠統，原文件為 Product manager，snippet 從 manager 開始而漏掉前綴。 |
| [d02](d02/trace.md) | supported | supported | accurate | 14 characters、政策編號／版本與 Section 3 均在已讀內容中。 |
| [d03](d03/trace.md) | supported | supported | accurate | 600 requests/min、429、Retry-After 與 Enterprise 申請較高上限均有已讀證據，引用 4.1 正確。 |
| [d04](d04/trace.md) | supported | supported | accurate | Professional 每 meter 每月 $1.40 與 Pricing and contracts 章節均在已讀視窗中。 |
| [d05](d05/trace.md) | supported | supported | accurate | Jonas Weber 及 Senior Data Scientist 身分均在實際搜尋 snippet 中。 |
| [d06](d06/trace.md) | unsupported | unsupported | insufficient | 沒有回答關閉日期；只搜尋文件與 email，未 read_doc。摘要缺少日期不能支持整份文件未記載的結論。原文件第 120 行實際有日期，但沒有進入工具觀察。最後原生回覆因 length 停止，session 卻標 done。 |
| [d07](d07/trace.md) | supported | supported | accurate | 第三次搜尋的 snippet 已完整呈現每曆年最多 10 working days 全薪陪審服務；沒有 read_doc 不等於缺乏支持。 |
| [d08](d08/trace.md) | supported | supported | source_type_mislabeled | 電話與 Section 34 正確，已讀到第 258 行；employee-handbook 是文件 doc_id，輸出卻標為 Email ID。 |
| [d09](d09/trace.md) | supported | supported | accurate | E-214、11.2、11.3、M4／15 分鐘及恢復條件全部在已讀視窗內。 |
| [d10](d10/trace.md) | supported | supported | accurate | 第二次搜尋 snippet 明載 draft 於 resolution 後 5 business days 到期；文件來源正確。 |
| [d11](d11/trace.md) | supported | supported | accurate | 4 hours、Section 5 與 Oregon/us-west 對應 Virginia/us-east 災難復原區均有已讀支持。 |
| [d12](d12/trace.md) | supported | supported | accurate | $75、餐別與小費、出發／返程半額均有已讀來源；$37.50 是 75/2 的正確推算，並非捏造引文。引用 2026 版 Section 6 正確。 |
| [d13](d13/trace.md) | supported | supported | accurate | 新 $750 門檻、生效日與舊 March policy 的 $750–$1,000 區間都在 snippet 內。提及舊金額屬正確歷史對照，不是答成舊政策。 |
| [d14](d14/trace.md) | supported | supported | source_type_mislabeled | 10 days/80 hours、2025→2026 起適用及 June 30 截止都有 snippet 支持；公告是文件，卻標成 Relevant Email ID。 |
| [d15](d15/trace.md) | supported | supported | source_type_mislabeled | Tuesday/Wednesday/Thursday 與 2026-06-01 生效日均有 snippet 支持；公告 doc_id 被標成 Relevant Email ID。 |
| [d16](d16/trace.md) | supported | supported | accurate | $500、2026-03-02 與假日／winter closure 額外 $250 均有 snippet 支持。includes an additional 的用語容易含混，建議寫成 $500 加上條件式額外 $250。 |
| [d17](d17/trace.md) | supported | supported | accurate | $65/月、fitness facility dues、Ledgerly/Wellness 與不結轉均在第三次搜尋的同一 snippet 內。 |
| [d18](d18/trace.md) | unsupported | unsupported | insufficient | 未回答分機，未讀 Security policy 正文。引用的 em-22128 只談舊公司電腦／支票與 Security desk，無法回答 Cardinal 通報分機。文件結果超過 6000，最後原生回覆 length-stop 後仍被當 done。 |
| [d19](d19/trace.md) | supported | supported | accurate | semi-monthly、15th 與 last business day、遇假日提前及 PeopleHub 均有已讀支持；摘要條列用 or 有歧義，但同一輸出的直接引文正確使用 and。 |
| [d20](d20/trace.md) | supported | partial | accurate | $1,800/年與 current/target role 的 learning 範圍有 snippet 支持。snippet 在 Eligible 一詞後截斷，沒有呈現 event registration/coursework 清單；會議／線上課程明確適用是從題意與 learning 類別推得，未由實際送入內容完整核對。完整語料確實列出該清單，屬事後查核，不能回填為 agent 已看過。 |

## 各題可核對的支持片段

### d01

Nadia Ferreira 與 Firmware Engineering Manager 身分由實際 snippet 支持；不必只認 fixture 的 org-chart。Heron 的附帶角色描述較籠統，原文件為 Product manager，snippet 從 manager 開始而漏掉前綴。

- [firmware-spec-emberos](../../datasets/docs/firmware-spec-emberos.md) 第 6–6 行；實際由 [search_docs, turn 1](d01/trace.md#turn-1) 送入：
  > Owner: Firmware team (Nadia Ferreira, Firmware Engineering Manager)
- [firmware-spec-emberos](../../datasets/docs/firmware-spec-emberos.md) 第 3–3 行；實際由 [search_docs, turn 1](d01/trace.md#turn-1) 送入：
  > Document number: FW-SPEC-003
- [project-heron-brief](../../datasets/docs/project-heron-brief.md) 第 6–6 行；實際由 [search_docs, turn 1](d01/trace.md#turn-1) 送入：
  > manager: Rohan Kapoor

### d02

14 characters、政策編號／版本與 Section 3 均在已讀內容中。

- [it-security-policy](../../datasets/docs/it-security-policy.md) 第 3–3 行；實際由 [search_docs, turn 1](d02/trace.md#turn-1) 送入：
  > Policy number: SEC-400, version 3.0
- [it-security-policy](../../datasets/docs/it-security-policy.md) 第 27–27 行；實際由 [read_doc, turn 2](d02/trace.md#turn-2) 送入：
  > ## 3. Accounts and passwords
- [it-security-policy](../../datasets/docs/it-security-policy.md) 第 30–30 行；實際由 [read_doc, turn 2](d02/trace.md#turn-2) 送入：
  > Passwords must be at least 14 characters long.

### d03

600 requests/min、429、Retry-After 與 Enterprise 申請較高上限均有已讀證據，引用 4.1 正確。

- [gridlens-api-spec](../../datasets/docs/gridlens-api-spec.md) 第 3–3 行；實際由 [search_docs, turn 1](d03/trace.md#turn-1) 送入：
  > Document number: API-SPEC-002
- [gridlens-api-spec](../../datasets/docs/gridlens-api-spec.md) 第 4–4 行；實際由 [search_docs, turn 1](d03/trace.md#turn-1) 送入：
  > Version: 2.1
- [gridlens-api-spec](../../datasets/docs/gridlens-api-spec.md) 第 42–42 行；實際由 [read_doc, turn 2](d03/trace.md#turn-2) 送入：
  > 4.1 Each client may make up to 600 requests per minute. A request over the limit receives status 429 with a `Retry-After` header that gives the number of seconds to wait.
- [gridlens-api-spec](../../datasets/docs/gridlens-api-spec.md) 第 48–48 行；實際由 [read_doc, turn 2](d03/trace.md#turn-2) 送入：
  > 4.4 Enterprise customers may ask for higher limits through their Customer Success Manager.

### d04

Professional 每 meter 每月 $1.40 與 Pricing and contracts 章節均在已讀視窗中。

- [gridlens-product-faq](../../datasets/docs/gridlens-product-faq.md) 第 87–87 行；實際由 [read_doc, turn 2](d04/trace.md#turn-2) 送入：
  > ## Pricing and contracts
- [gridlens-product-faq](../../datasets/docs/gridlens-product-faq.md) 第 95–95 行；實際由 [read_doc, turn 2](d04/trace.md#turn-2) 送入：
  > | Professional | $1.40 |

### d05

Jonas Weber 及 Senior Data Scientist 身分均在實際搜尋 snippet 中。

- [project-kestrel-brief](../../datasets/docs/project-kestrel-brief.md) 第 5–5 行；實際由 [search_docs, turn 1](d05/trace.md#turn-1) 送入：
  > Technical lead: Jonas Weber, Senior Data Scientist

### d06

沒有回答關閉日期；只搜尋文件與 email，未 read_doc。摘要缺少日期不能支持整份文件未記載的結論。原文件第 120 行實際有日期，但沒有進入工具觀察。最後原生回覆因 length 停止，session 卻標 done。

- 沒有支持所問答案的已見來源；見下方事後反證。

### d07

第三次搜尋的 snippet 已完整呈現每曆年最多 10 working days 全薪陪審服務；沒有 read_doc 不等於缺乏支持。

- [employee-handbook](../../datasets/docs/employee-handbook.md) 第 132–132 行；實際由 [search_docs, turn 3](d07/trace.md#turn-3) 送入：
  > Cardinal Energy pays your full salary for up to 10 working days of jury service per calendar year.

### d08

電話與 Section 34 正確，已讀到第 258 行；employee-handbook 是文件 doc_id，輸出卻標為 Email ID。

- [employee-handbook](../../datasets/docs/employee-handbook.md) 第 256–256 行；實際由 [read_doc, turn 4](d08/trace.md#turn-4) 送入：
  > ## 34. Raising concerns and the ethics hotline
- [employee-handbook](../../datasets/docs/employee-handbook.md) 第 258–258 行；實際由 [read_doc, turn 5](d08/trace.md#turn-5) 送入：
  > call the ethics hotline at 1-800-555-0142.

### d09

E-214、11.2、11.3、M4／15 分鐘及恢復條件全部在已讀視窗內。

- [firmware-spec-emberos](../../datasets/docs/firmware-spec-emberos.md) 第 129–129 行；實際由 [read_doc, turn 5](d09/trace.md#turn-5) 送入：
  > 11.2 Error codes are reported as events.
- [firmware-spec-emberos](../../datasets/docs/firmware-spec-emberos.md) 第 136–136 行；實際由 [read_doc, turn 5](d09/trace.md#turn-5) 送入：
  > | E-214 | Sensor mesh link lost |
- [firmware-spec-emberos](../../datasets/docs/firmware-spec-emberos.md) 第 143–143 行；實際由 [read_doc, turn 5](d09/trace.md#turn-5) 送入：
  > 11.3 E-214 is raised by the M4 when a joined sensor has sent no report for 15 minutes. It is cleared when the sensor reports again.

### d10

第二次搜尋 snippet 明載 draft 於 resolution 後 5 business days 到期；文件來源正確。

- [oncall-incident-process](../../datasets/docs/oncall-incident-process.md) 第 96–96 行；實際由 [search_docs, turn 2](d10/trace.md#turn-2) 送入：
  > The draft is due within 5 business days of resolution.

### d11

4 hours、Section 5 與 Oregon/us-west 對應 Virginia/us-east 災難復原區均有已讀支持。

- [architecture-overview](../../datasets/docs/architecture-overview.md) 第 57–57 行；實際由 [read_doc, turn 3](d11/trace.md#turn-3) 送入：
  > ## 5. Recovery targets
- [architecture-overview](../../datasets/docs/architecture-overview.md) 第 61–61 行；實際由 [read_doc, turn 3](d11/trace.md#turn-3) 送入：
  > The recovery time objective is 4 hours: service in the recovery region must be available within that time.
- [architecture-overview](../../datasets/docs/architecture-overview.md) 第 51–51 行；實際由 [read_doc, turn 3](d11/trace.md#turn-3) 送入：
  > | us-west | Oregon | Primary for customers in North America |
- [architecture-overview](../../datasets/docs/architecture-overview.md) 第 52–52 行；實際由 [read_doc, turn 3](d11/trace.md#turn-3) 送入：
  > | us-east | Virginia | Disaster recovery for us-west |

### d12

$75、餐別與小費、出發／返程半額均有已讀來源；$37.50 是 75/2 的正確推算，並非捏造引文。引用 2026 版 Section 6 正確。

- [expense-policy-2026](../../datasets/docs/expense-policy-2026.md) 第 38–38 行；實際由 [read_doc, turn 2](d12/trace.md#turn-2) 送入：
  > ## 6. Meals while traveling
- [expense-policy-2026](../../datasets/docs/expense-policy-2026.md) 第 40–40 行；實際由 [read_doc, turn 2](d12/trace.md#turn-2) 送入：
  > meals are reimbursed up to a daily limit of $75 per day for domestic travel
- [expense-policy-2026](../../datasets/docs/expense-policy-2026.md) 第 40–40 行；實際由 [read_doc, turn 2](d12/trace.md#turn-2) 送入：
  > The limit covers breakfast, lunch, dinner, and tips.
- [expense-policy-2026](../../datasets/docs/expense-policy-2026.md) 第 40–40 行；實際由 [read_doc, turn 2](d12/trace.md#turn-2) 送入：
  > On the day you depart and the day you return, the limit is half of the daily amount.

### d13

新 $750 門檻、生效日與舊 March policy 的 $750–$1,000 區間都在 snippet 內。提及舊金額屬正確歷史對照，不是答成舊政策。

- [finance-memo-2026-08-approval-thresholds](../../datasets/docs/finance-memo-2026-08-approval-thresholds.md) 第 4–4 行；實際由 [search_docs, turn 1](d13/trace.md#turn-1) 送入：
  > Effective: 2026-09-01
- [finance-memo-2026-08-approval-thresholds](../../datasets/docs/finance-memo-2026-08-approval-thresholds.md) 第 13–13 行；實際由 [search_docs, turn 1](d13/trace.md#turn-1) 送入：
  > From 2026-09-01, any single expense over $750 requires approval from your department's vice president
- [finance-memo-2026-08-approval-thresholds](../../datasets/docs/finance-memo-2026-08-approval-thresholds.md) 第 9–9 行；實際由 [search_docs, turn 1](d13/trace.md#turn-1) 送入：
  > individual expenses between $750 and $1,000, which under the March policy reach Finance with only a manager's approval.

### d14

10 days/80 hours、2025→2026 起適用及 June 30 截止都有 snippet 支持；公告是文件，卻標成 Relevant Email ID。

- [people-announcement-2025-11-pto-carryover](../../datasets/docs/people-announcement-2025-11-pto-carryover.md) 第 11–11 行；實際由 [search_docs, turn 1](d14/trace.md#turn-1) 送入：
  > Starting with the rollover from 2025 into 2026, you may carry over up to 10 days (80 hours) of unused PTO into the next calendar year. Carried-over PTO must be used by June 30 of that year.

### d15

Tuesday/Wednesday/Thursday 與 2026-06-01 生效日均有 snippet 支持；公告 doc_id 被標成 Relevant Email ID。

- [people-announcement-2026-05-office-days](../../datasets/docs/people-announcement-2026-05-office-days.md) 第 7–7 行；實際由 [search_docs, turn 1](d15/trace.md#turn-1) 送入：
  > Starting 2026-06-01, hybrid employees will work from their assigned office at least 3 days each week. The anchor days will be Tuesday, Wednesday, and Thursday.

### d16

$500、2026-03-02 與假日／winter closure 額外 $250 均有 snippet 支持。includes an additional 的用語容易含混，建議寫成 $500 加上條件式額外 $250。

- [engineering-announcement-2026-02-oncall-stipend](../../datasets/docs/engineering-announcement-2026-02-oncall-stipend.md) 第 7–7 行；實際由 [search_docs, turn 1](d16/trace.md#turn-1) 送入：
  > The new amounts apply to rotations that start on or after 2026-03-02.
- [engineering-announcement-2026-02-oncall-stipend](../../datasets/docs/engineering-announcement-2026-02-oncall-stipend.md) 第 11–11 行；實際由 [search_docs, turn 1](d16/trace.md#turn-1) 送入：
  > | Primary | $500 |
- [engineering-announcement-2026-02-oncall-stipend](../../datasets/docs/engineering-announcement-2026-02-oncall-stipend.md) 第 14–14 行；實際由 [search_docs, turn 1](d16/trace.md#turn-1) 送入：
  > An engineer who is primary or secondary during a week that contains a company holiday, or during the winter closure, receives an additional $250 for that week.

### d17

$65/月、fitness facility dues、Ledgerly/Wellness 與不結轉均在第三次搜尋的同一 snippet 內。

- [benefits-summary-2026](../../datasets/docs/benefits-summary-2026.md) 第 31–31 行；實際由 [search_docs, turn 3](d17/trace.md#turn-3) 送入：
  > Cardinal Energy reimburses up to $65 per month
- [benefits-summary-2026](../../datasets/docs/benefits-summary-2026.md) 第 31–31 行；實際由 [search_docs, turn 3](d17/trace.md#turn-3) 送入：
  > Eligible expenses include fitness facility dues
- [benefits-summary-2026](../../datasets/docs/benefits-summary-2026.md) 第 31–31 行；實際由 [search_docs, turn 3](d17/trace.md#turn-3) 送入：
  > Submit the expense in Ledgerly under the Wellness category.
- [benefits-summary-2026](../../datasets/docs/benefits-summary-2026.md) 第 31–31 行；實際由 [search_docs, turn 3](d17/trace.md#turn-3) 送入：
  > Unused amounts do not roll over from month to month.

### d18

未回答分機，未讀 Security policy 正文。引用的 em-22128 只談舊公司電腦／支票與 Security desk，無法回答 Cardinal 通報分機。文件結果超過 6000，最後原生回覆 length-stop 後仍被當 done。

- 沒有支持所問答案的已見來源；見下方事後反證。

### d19

semi-monthly、15th 與 last business day、遇假日提前及 PeopleHub 均有已讀支持；摘要條列用 or 有歧義，但同一輸出的直接引文正確使用 and。

- [employee-handbook](../../datasets/docs/employee-handbook.md) 第 68–68 行；實際由 [read_doc, turn 4](d19/trace.md#turn-4) 送入：
  > ## 8. Compensation and payroll
- [employee-handbook](../../datasets/docs/employee-handbook.md) 第 70–70 行；實際由 [read_doc, turn 5](d19/trace.md#turn-5) 送入：
  > Salaries are disbursed semi-monthly, on the 15th and on the last business day of each month. If the 15th falls on a weekend or a bank holiday, the deposit is made on the business day before. Pay statements are available in PeopleHub.

### d20

$1,800/年與 current/target role 的 learning 範圍有 snippet 支持。snippet 在 Eligible 一詞後截斷，沒有呈現 event registration/coursework 清單；會議／線上課程明確適用是從題意與 learning 類別推得，未由實際送入內容完整核對。完整語料確實列出該清單，屬事後查核，不能回填為 agent 已看過。

- [benefits-summary-2026](../../datasets/docs/benefits-summary-2026.md) 第 35–35 行；實際由 [search_docs, turn 2](d20/trace.md#turn-2) 送入：
  > Each full-time employee may spend up to $1,800 per calendar year on learning that relates to their current role or a role they are working toward.

## 事後反證／補充查核（不回填為 agent 已見）

- d06：gridlens-api-spec 第 120 行：
  > API version 1 will be shut down on 2026-12-31.
- d18：it-security-policy 第 57 行：
  > Call the Security hotline at extension 4911
- d20：benefits-summary-2026 第 35 行：
  > Eligible expenses include event registration fees, coursework, certification examinations, and books.
- d01：project-heron-brief 第 6 行：
  > Product manager: Rohan Kapoor

## 失敗的停止狀態

| 題目 | final prompt tokens | final completion tokens | native stop | session status |
|---|---:|---:|---|---|
| d06 | 8131 | 61 | length | done |
| d18 | 8098 | 94 | length | done |

這兩題在 8192 context 下沒有留下足夠輸出空間，回覆被截斷。現有 Ollama adapter 未將該 length stop 轉為 OutputTruncated，agent 因沒有完整工具呼叫而把它當作最終文字。這是後續修正方向，這次不改動 baseline 行為或原始結果。

## 審查界線

- One assistant review, not independent multiple-rater agreement or a trained semantic verifier.
- Recorded messages show what was sent; they do not prove which earlier tokens the backend retained internally.
- Full-corpus counter-evidence was consulted only after generation; it was not supplied to the agent.
- No new overall pass threshold is invented by this review.

機器可讀的逐題資料、來源座標與輸入 hashes：[evidence-review.json](evidence-review.json)。
