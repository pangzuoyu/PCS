# PCS-NOTE: `equipment_lib` 表废弃裁决（2026-10-06）

**日期**：2026-10-06
**裁决**：删除 `equipment_lib` 表 + ORM；设备库由 `ConfigAsset` + `category == "CATEGORY_6"` 唯一承载
**关联**：`docs/adr/0032-vessel-process-calculation.md` §P5-1-3（阻塞理由作废）、`docs/PCS-UI-SPEC.md` §7.16、`alembic/versions/p7_s5_001_drop_equipment_lib.py`

---

## 背景

查 `docs/superpowers/plans/2026-10-01-p7-complete-sprint.md` 的执行进度时发现：
Sprint 3 Task S3-2「相似度计算」零实现，且 UI-SPEC §7.16（V1.0 冻结）强制要求该能力。
要补做就得先定「设备库挂在哪张表」——因为存在两套并存模型。

## 实证对比（2026-10-06 全量核查）

| 维度 | `equipment_lib` 表 | `ConfigAsset` + CATEGORY_6 |
|---|---|---|
| SPEC 授权 | **无**。P2 §3.2.6 标题即「复用设备库管理（**CATEGORY_6**）」 | SPEC 定义的正式承载 |
| 建表来源 | 2026-08-31 随 v3.1 基线 `dd47298c9c38` 一次性生成 | P2 Sprint 1.9 `f0652ae`（2026-09-06，248 行 + 5 测试） |
| 代码引用 | **0**（仅 ORM 自指） | 4 处（`equip_lib_service.py` / `equip_lib.py` / tests） |
| 专属测试 | **0**（`test_schema.py` 仅表名字符串） | `tests/api/v1/test_equip_lib.py` 5 个全过 |
| 后续迁移 | 无 | 随 CONFIG 审批链演进 |
| 库内行数 | **0**（pcs + pcs_test） | **0** |

**结论**：`equipment_lib` 是被 ConfigAsset 取代的遗留物，从未接线。
表比实现早 6 天生成，实现时选了另一条路，之后无人回头。

## 落地

1. `alembic/versions/p7_s5_001_drop_equipment_lib.py` — `drop_table(if_exists=True)`，down_revision `p7_s4_002`
2. 删除 `app/models/equipment.py` 的 `EquipmentLib` ORM 类
3. `tests/test_schema.py` — 表数 104 → 103，required 清单移除 `equipment_lib`
4. ADR-0032 §P5-1-3 阻塞理由作废并改写

## 连带纠正：一次基于错误前提的 DEFERRED

ADR-0032 在 **2026-09-17** 以「`equipment_lib` 0 行」为由把 P5-1-3
`recommend_vessels`（按相似度推荐设备）判为 DEFERRED。
但沉淀功能早在 **2026-09-06** 就接到 ConfigAsset 上了 —— **该核实做于实现之后 11 天，查错了表**。

**同一个需求因此被错误前提推迟了两次**：
1. 2026-09-17：ADR-0032 以「死表为空」为由 DEFERRED
2. 2026-10-01 → 10-02：P7 总计划列为 S3-2，次日实际执行的
   `docs/sprint3-plan-2026-10-02.md`（题为「Production 前置 + Audit 可观测性」）
   通篇零提及 EQUIP_LIB / 相似度 —— 被静默丢出范围

而 `docs/PCS-UI-SPEC.md:1648` 至今仍写着「相似度 ≥90% 推荐，80~90% 需校核，<80% 仅展示」。

## ConfigAsset 侧的遗留硬伤（不在本裁决范围，已登记）

补相似度前必须先解决，否则是在没地基的地方盖二楼：

1. **`type_code` 根本没采集** —— `EquipLibSettleRequest` 无该字段。
   `equipment_list.type_code` 在源表存在但不参与 settle。
   **相似度以 type_code 为主匹配键，现在没有主键可匹配。**
2. **无去重约束** —— settle 无 unique、不查重。同一设备重复沉淀产生 N 条独立 asset，
   库会退化成「设备台账副本」，而复用库的价值正在于去重。
3. **区间查询不可索引** —— `weight_kg` / `key_dimensions` 埋在 `content_json` JSONB，无 GIN。
4. **`category` 无枚举 + `status`/`category` 零索引** —— 已有 628 条 CATEGORY_1 混在同一张表。
5. **审批语义冲突** —— SPEC 要求 CATEGORY_6 单层（工艺负责人提交 / 审核角色审定），
   实际复用通用 5 态链，测试用同一 token 提交并 approve，无职责分离。

## 验证

- `uv run alembic upgrade head` → pcs 库 104 → **103 张表**，`equipment_lib` 已消失
- **往返验证**（实测非声称）：`downgrade p7_s4_002` → `upgrade head` → 终态
  `p7_s5_001` / 103 表 / `equipment_lib` 不存在，与单次 upgrade 一致
- `uv run pytest tests/test_schema.py -q` → **7 passed**
- 全量 `uv run pytest tests/ -q` → **3924 passed / 77 skipped / 1 xfailed / 0 failed**（与改动前同基线）
- `uv run python scripts/check_migration_idempotency.py` → **0 violations**（`p7_s5_` 已在白名单）
- `uv run ruff check` 改动文件 → **All checks passed**（注意：docstring 首行须用 ASCII `.`，
  全角 `。` 触发 D400/D415）
- `uv run alembic check` → **equipment_lib 零提及**（本改动无漂移；该命令另有 130 条
  **既有假漂移**，根因是 `alembic/env.py:7` 只 `import app.models`（95 表）而漏了
  `app.models.util`（+7 表），详见 `TODOS.md` 新登记项）
