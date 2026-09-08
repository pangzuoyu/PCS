---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1000
---
# STATUS — PCS

> Single source of truth for resuming work. Read this FIRST when starting a session.
> Last updated: 2026-09-08

---

## ✅ Done

- **P2 全系列 SDD 闭环（2026-09-04~06，commits ad25700..f59233d，462 passed）**
  - Sprint 1.8 + 1.10：formula preconditions / 折标煤 / DETAIL 模板 / ADR-0029
  - Sprint 1.9（6 个子任务）：vendor 三件接线 / PipeClassService 7 端点 / PetroleumService / CATEGORY_3 seed / equip-lib 沉淀检索 / Excel 导入 71/71；终审 3 修复（settle name 截断/短行 IndexError/limit ge=1）
  - **SUP-002 全部 11 task**（PC-1→2→3→4→6、SYM-1→2→3、FMT-1→2→3→4、INT-1→3）：管道代码自定义（自然码+asset_id 镜像/5 态挂 ConfigAsset/scope/STALE，V1.4 26 项审查修正全落）
  - 终 close：bug-051 收口 + P2 Sprint close 报告（462 passed / 43 裁决 / 25 迁移 / 62 表）
- **P3.3 COMMON 闭环（2026-09-08，commit 37f34f8）**：物性 + 许用应力 + 介质安全数据查询 API
- **P3-SIM spec V1.1→V1.2** 入库（合并 ADD-001/ADD-002，三 CRITICAL 裁决落地）
- **P3.2 SIM 实施 Writing-Plan V1.0 入库**（docs/PCS-PLAN-P3.2-SIM.md，2026-09-08，Eng Review CLEAR，12 task × 20.5d）；V1.0.1 修订（2026-09-08，PRO/II parser 三版支持 + 5 样例构造方案）
- 前史：R19 运行面落库、ADR-0001~0029、P0/P1-MVP——见 git log

---

## 🚀 Next quest

**Goal:** P3.2 SIM 实施（按 docs/PCS-PLAN-P3.2-SIM.md V1.0 落地 12 task）
- SIM-1（schema 升级 + ORM + Schema 三套，1d）开路，后续 SIM-2..12 串/并依赖图见 plan §任务依赖图
- 依赖：P3.3 COMMON `CommonService.get_material(cas)` 已平，SIM-3 直接 import

### 待用户裁决
1. **开工顺序**：先单跑 SIM-1（schema）拿绿 baseline，还是开 SIM-1+SIM-3 并行（schema 不依赖物性补全）
2. ✅ **PRO/II 5 样例构造方案已落地**（plan V1.0.1 修订）：spec §607-633 5 样例是测试构造（每样例一个最小 .inp + .out 双文件），非仓库 sample/ 工程实例；仓库 sample/ 9 文件作 parser 鲁棒性回归（`-m regression`，不入 git）；parser 三版支持 V2.71+V4.17+V8.x
3. **stream 字段顺序对前端契约影响**（plan 未解决问题 #2）：StreamResponse 新增 17+ 字段后 JSON 顺序——前端 SPEC-P3-SIM V1.3 §2.5 示例按字典序，Pydantic v2 默认定义序；需确认前端是否依赖字段顺序（YAGNI 默认按定义序）
4. **仓库级未跟踪面再扫**：cerebrum Do-Not-Repeat 已确认 2026-09-06 无遗留 untracked；本次新增 P3.2 plan 已入库；如需再扫确认可跑 `git status --short` 全检

### 注意
- pcs_test 库 schema 敏感运行前先 `cd pcs-backend && uv run alembic upgrade head`（矫正迁移只应用了 pcs）
- 新表迁移必须含 TimestampMixin 三列（created_by/created_at/updated_at；created_at timezone+server_default，updated_at nullable）
- Pydantic v2 Schema 必须 Field(description=...)：spec 本体论 V1.6 §5.3 要求每字段含中文描述
- StreamSignStatus：PG enum 'streamsignstatus' 已落；P3 活跃 4 态（DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED），P4 扩展走 `ALTER TYPE streamsignstatus ADD VALUE`（不可逆）
- case_type 双层语义：streams.case_type ≠ stream_state_points.case_type，独立两字段（spec V1.6 §3.2.2）
- 冲突三级：BLOCK（阻止保存）/ WARN（用户值优先+标记）/ INFO（计算值优先派生）
- 收敛分层：CONVERGED/WARNINGS 全量导入，NOT_CONVERGED/ABORTED SOLVED 单元产品 `unreliable=True`
- 实施纪律：每步独立 commit；复跑依赖测试后再 commit；干净 worktree 验证 import + alembic + pytest 是唯一可信证据
- YAGNI：HYSYS/Aspen/HTRI 解析器后置 P4，本 Sprint 仅 PRO/II + 手工 + Excel

---

## Context

- 分支 main（单人直提惯例）；后端 uv+FastAPI+PG16（vendor 三件+python-multipart 已入锁），前端 Vite+React+antd
- SDD 工作区已删（git 史为正式记录）；TODO-033 = Sprint 1.9 终审 DEFER 清单；P3.2 plan 自带未解决问题 #3~#6 已建 TODO-034/035/037
- bug-046（python-multipart）/bug-047（dn 单口径）/bug-051（assign_to_project）入 .wolf/buglog.json
- ADR-0029「已接受」2026-09-04，旧交接中残留待裁决项已除名
