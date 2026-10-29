# d06 Agent 研究紀錄：實驗總表

[研究首頁](../README.md)

| 紀錄 | 類型 | 環境 | 主 / aux | read_doc | 格式錯誤 | 接受答案比對 |
|---|---|---|---:|---:|---:|---|
| [最初的 d06](runs/historical/trace.md) | full | [E0](environments/E0.system.txt) | 7 / 0 | 1 | 0 | 不符合 |
| [A：email 示例／probe1](runs/a-probe1/trace.md) | probe | [E0](environments/E0.system.txt) | 1 / 0 | 0 | 0 | 不評分 |
| [A：email 示例／probe2](runs/a-probe2/trace.md) | probe | [E0](environments/E0.system.txt) | 1 / 0 | 0 | 0 | 不評分 |
| [A：email 示例／完整 run](runs/a-full/trace.md) | full | [E0](environments/E0.system.txt) | 6 / 4 | 0 | 0 | 不符合 |
| [B：文件示例／probe1](runs/b-probe1/trace.md) | probe | [E1](environments/E1.system.txt) | 1 / 0 | 0 | 0 | 不評分 |
| [B：文件示例／probe2](runs/b-probe2/trace.md) | probe | [E1](environments/E1.system.txt) | 1 / 0 | 0 | 0 | 不評分 |
| [B：文件示例／完整 run](runs/b-full/trace.md) | full | [E1](environments/E1.system.txt) | 4 / 0 | 0 | 0 | 不符合 |
| [C：直接移除示例／probe1](runs/c-probe1/trace.md) | probe | [E2](environments/E2.system.txt) | 1 / 0 | 0 | 1 | 不評分 |
| [C：直接移除示例／probe2](runs/c-probe2/trace.md) | probe | [E2](environments/E2.system.txt) | 1 / 0 | 0 | 1 | 不評分 |
| [C：直接移除示例／probe3](runs/c-probe3/trace.md) | probe | [E2](environments/E2.system.txt) | 1 / 0 | 0 | 1 | 不評分 |
| [格式改善前／控制組](runs/protocol-before/trace.md) | full | [E0](environments/E0.system.txt) | 6 / 4 | 0 | 0 | 不符合 |
| [格式與 search_docs 說明改善後](runs/protocol-after/trace.md) | full | [E3](environments/E3.system.txt) | 6 / 0 | 2 | 0 | 不符合 |
| [明確分頁說明後](runs/paging-after/trace.md) | full | [E4](environments/E4.system.txt) | 6 / 0 | 0 | 0 | 不符合 |
| [前次歷史 × 舊描述](runs/replay-old-old/trace.md) | replay | [E3](environments/E3.system.txt) | 1 / 0 | 0 | 0 | 不評分 |
| [前次歷史 × 新描述](runs/replay-old-new/trace.md) | replay | [E4](environments/E4.system.txt) | 1 / 0 | 0 | 0 | 不評分 |
| [本次歷史 × 新描述](runs/replay-new-new/trace.md) | replay | [E4](environments/E4.system.txt) | 1 / 0 | 0 | 0 | 不評分 |
| [本次歷史 × 舊描述](runs/replay-new-old/trace.md) | replay | [E3](environments/E3.system.txt) | 1 / 0 | 0 | 0 | 不評分 |
