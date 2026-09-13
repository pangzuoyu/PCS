---
status: accepted
date: 2026-09-13
---

# P4 计算链条件启动：本体论 Task 0 全量后置

P4 核心计算引擎批 0（P4-0-1 审计字段迁移 + 统一 lineage helper）启动时，本体论 Task 0（P4-TASK0：record 类型 registry、数值规范化契约、血缘契约的全量本体论梳理）尚未获架构委员会 approve。为不让计算链关键路径被治理流程阻塞，本 ADR 记录"子集先行"的条件启动裁决（用户 2026-09-13）。

决定：**子集先行 + 护栏清单**。具体：

- **统一 helper**：`app/services/calc_lineage.py` 的 `finalize_calc_record` 是计算记录唯一收口——record_hash（数值字段 6 位有效数字规范化后 sha256 截断 16 hex）+ DataLineage 血缘（source→record，含 formula_version）；审计列（`stale_resolution_path` / `hash_changed` / `changed_fields`）只经本 helper 与 CIA 引擎写，业务模块禁止直写。
- **registry 占位**：`RECORD_TYPE_REGISTRY` 仅覆盖 P4 批 0 的 4 类 record（PipingResult / PumpResult / FlashResult / PipeNetworkResult）；正式 registry 后置 P4-TASK0。
- **CI 兜底**：以 ruff 0 错 + alembic round-trip + 全量测试基线（1220 passed + 1 skipped）护栏，替代本体论全量审查。

理由：架构委员会未 approve 本体论全量方案，而计算链关键路径（P4 计划）不应被治理流程阻塞；上述护栏把"未做全量本体论"的风险收敛到可测试边界内（收口唯一入口、类型注册显式、回归基线冻结）。

影响：**P4 验收前必须关闭 P4-TASK0（全量本体论落地），否则 P4 只能条件验收**。

supersedes：无。

## Consequences

- P4 各计算批次（泵/管网/闪蒸/管道）写记录必须经 `finalize_calc_record`，不得绕开收口直写 record_hash / 审计列。
- `RECORD_TYPE_REGISTRY` 为占位常量，P4-TASK0 落地时升级为正式 registry（届时补充第五表 streams 的登记裁决与更多 record 类型）。
- 测试基线随 P4 批次增长更新；任何回归（已知 export flake 除外）视为护栏击穿，阻塞合入。
- P4-TASK0 关闭时须复核本 ADR 的护栏是否仍充分，必要时以新 ADR 取代。
