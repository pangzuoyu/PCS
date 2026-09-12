---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1000
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-09-13.

---

## ✅ Done (P3.x sprint 全闭环 — 2026-09-13)

- **27 task (SIM-14~SIM-40) + V1.0 变更管理 4 task 全部 completed**
  - 收口报告：`docs/PCS-P3.2-SIM-P3X-CLOSE-REPORT.md`（commit `93e4ca4`）
    —— task→commit 映射 + 验收对照 + TODO 终态 + P4 衔接建议，**勿重复读计划文件**
- **终态指标**：1219 passed + 1 flake（TODO-041 偶发）+ 1 skip（pcs_test 守卫）；
  覆盖率 88%；ruff 445 基线持平；55 commits（09-09 起）
- **TODO 终态**：5 闭环（035/037/040/043/044）+ 3 P4 裁决保留（034/041/042）
- **批 3/4 本期交付**：24/25/26/27/28/29/30/31/32/35（批 3）+
  33/34/36/37a/37b×3/38a/38b×3/39/40（批 4）+ V1.0 变更管理
  SIM-37(项目级审批)/38(变更单)/39(弃用)/40(反向签署)
- **编号冲突**：commit 前缀 `p3x-38/39/40` 是 V1.0 变更管理系列；
  V1.1 的 38a/38b/39/40 是炼油塔盘/TODO/报告系列——两系列均已闭环
- **本 session buglog**：bug-069（续行 joiner 三行 &）/ bug-070（段标题宽守卫
  误杀列头行）/ bug-071（snapshot_id str(None)）——详见 `.wolf/buglog.json`

---

## 🚀 Next quest

**Goal:** P4 启动（P3.x 闸门条件已满足，用户 2026-09-09 裁决的闭环前提达成）

### P4 首批建议（收口报告 §6，优先序）
1. **ruff 归零专项**：445 → 0（31 fixable + 手工复核），半天
2. **calculate 入口接 Guard**：P4 工艺计算首个端点调
   `UnreliableStreamGuard.check`（422 STREAM_UNRELIABLE_BLOCKED 契约已备 + 测试）
3. **enum 9 态扩展（TODO-036）**：`ALTER TYPE ADD VALUE` 不可逆，迁移前备份
   enum definition
4. **parser 入库链路**：SIM-37b/38b 产出为 dataclass 层，P4 需 import_service
   集成写 sim_tower_results / stream_properties_json
5. 覆盖率 88% → 90%（未覆盖行集中在 api 层 error 分支）

### 锁定的用户裁决（累积）
- 全程中文；"继续" = 驱动下一 task 不重议
- 每 task 一 commit；约定式提交；ruff 基线不净增（当前 445）
- 30 项漏项 P4 前闭环（2026-09-09）→ ✅ 已达成
- StreamResponse 字段顺序非契约（2026-09-08）
- TODO-045 ruff 历史债 = 独立 cleanup sprint（并入 P4 首批建议 #1）
- CI/CD 不做（单人开发裁决）

### 注意（跨 session 有效）
- schema 敏感测试前对 pcs_test 跑 `cd pcs-backend && uv run alembic upgrade head`；
  **默认 DATABASE_URL 指 pcs 开发库**，测试需显式 pcs_test（round-trip 测试
  已带守卫）
- 不可逆迁移锚点：`p3sim_stream_sign_status_extend`（enum ADD VALUE）
- PRO/II fixture 预期按**输出实测**对齐，勿按 INDEX 推断（proii .out 多
  problem 拼接 + T1 重复 ×2；T2/T3 仅 INDEX 有条目）
- Pydantic v2 Field description 必含中文
- 塔盘/炼油 parser 段标题守卫必须精确枚举动词（bug-070 教训）

---

## Context

- 分支 main（单人直提）；后端 uv+FastAPI+SQLAlchemy 2.0 async+PG16+pytest
- 测试全量：`cd pcs-backend && uv run pytest`（~70s）
- sample/ 9 个 PRO/II 工程不入 git（回归 fixture）
- 详细交接：`.wolf/HANDOFF-2026-09-13.md`（含 suggested skills；用户裁决交接文档入项目目录）
