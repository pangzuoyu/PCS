---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1000
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-09-09.

---

## ✅ Done (本会话 P3.2 SIM Sprint 收尾)

- **P3.2 SIM Sprint 14 task 全部 completed**（`7cdfc17` 收口报告 V1.1 + `949dd13` 审计 V2.0 + `4fcee64` P3.x 计划 V1.0）：
  - SIM-1/2/3/4/5/6/7/8/9/10/10.1/10.2/11/12/13 全部 ✅
  - 702 passing（591 → 675 → 702, +111）
  - 覆盖率 88%；ruff 0 错
  - 6 alembic migrations（pcs + pcs_test 对齐）
  - 17 commit in P3.2 SIM 范围
- **审计 V2.0**：`docs/PCS-P3.2-SIM-AUDIT-V2.md`（`949dd13`）
  - 4 严重偏离 + 5 中度偏离 + 30 项漏项
  - 用户裁决 2026-09-09："所有项必须再进 P4 前解决"
- **P3.x 续推计划 V1.0**：`docs/PCS-PLAN-P3.2-SIM-P3X.md`（`4fcee64`）
  - 27 task (SIM-14 ~ SIM-40), 估时 ~32.5d 串行 / ~15-20d 4 批并行
  - 4 批：批 1 基础数据层（9.5d）→ 批 2 功能补全（7d）→ 批 3 API+校验（4.5d）→ 批 4 增补+收口（11.5d）
  - 原 9 项 TODO 全部纳入（034/035/037/039-044）

---

## ✅ Done (P3.x 批 1 基础数据层 收口)

- **6 task 全部 completed**（9 commits in 批 1）：
  - SIM-14 sim_imports + sim_import_warnings（3 commits: 14a/14b/14c）
  - SIM-15 sim_unit_op_results + 6 专用结果表
  - SIM-16 sim_tower_results + COLUMN SUMMARY 解析
  - SIM-17 streams 4 字段（simulation_status / tear_stream / estimated / stream_properties_json）
  - SIM-18 streams 4 JSON（user_provided / calculated / effective / conflict_resolutions）
  - SIM-19 PRO/II composition + 17 项 LIBID→CAS 别名映射
- **ruff 0 错**（批 1 范围 15 个 SIM 文件全 clean）
- **回归 740 passing**（702 → 740, +38）
- **bug-063 已记录**：SQLite in-memory FK PRAGMA 失效 → 改 PG inspector 元数据契约测试
- **bug-064 已记录**：PRO/II _LIBID_LINE_RE 越界污染后续段 → 行扫描 + 段边界检测 + 严格 ID 前缀校验

### 批 1 ruff 历史债（专项跟踪，不在本批处理）
- 全量 ruff 错误基线：**431 errors**（非批 1 引入）
- 范围：`formula_engine.py` / `pipe_class_migration.py` / `detail_templates.py` 等
- 处理方式：**新增 TODO-045 ruff 历史债专项清理**（独立 cleanup sprint，详见裁决 9）

---

## 🚀 Next quest

**Goal:** P3.x 续推（27 task，批 1 ✅ 完成，剩余批 2/3/4）

- ✅ **批 1 基础数据层**：6 task 全部 closed（2026-09-09）
- **批 2 功能补全**（7d）：SIM-20/21/22/23/27
- **批 3 API + 校验**（4.5d）：SIM-24/25/26/28/29/30/31/32/35
- **批 4 增补 + 收口**（11.5d）：SIM-33/34/36/37/38/39/40
- **总估时 ~32.5d 串行 / ~15-20d 4 批并行**

### 待用户裁决（plan §8 10 项，批 1 后状态）
1. 起点：批 1 立即启动 vs 等 P3.3 COMMON 衔接 → ✅ **批 1 已启动且完成**
2. 并行度：批 1 6 task 全并行 vs 顺序 → ✅ **实际并行**
3. commit 粒度：每 task 一 commit vs 每批一 commit → ✅ **每 task 一 commit**
4. SIM-37/38 P5 范畴：真 P4 前闭环（5d+3d）vs 延后
5. SIM-22 PropertyConflictResolver 估时（1d）
6. SIM-20 .out 20+ 解析估时（3d）
7. CoolProp 5 类物性精度阈值
8. pcs_test 库对齐策略
9. 是否需要新分支 `p3.2-sim-p3x` → ✅ **未开新分支（直提 main）**
10. 每批收口是否要 batch checkpoint commit → ✅ **无 checkpoint commit，仅 task 级 commit + STATUS.md 同步**

### 锁定的用户裁决（新增批 1 后）
1. ✅ P3.2 SIM 14 task 全部完成（2026-09-09 闭环）
2. ✅ P3.x 30 项漏项 P4 前闭环（2026-09-09 裁决）
3. ✅ StreamResponse 字段顺序不构成契约
4. ✅ SIM-7 三级冲突 + 4 大维度 + Conflict dataclass
5. ✅ SIM-9 状态点 5 规则（SV01~SV05）
6. ✅ SIM-4 集成 SIM-3+SIM-7：BLOCK 拒绝 / WARN 保存+返回 / INFO 保存+返回
7. ✅ SIM-13 状态机集成 + N+1 防护 + 文件大小 middleware（D-1/D-2/D-3 闭环）
8. ✅ 批 1 6 task 全部完成（2026-09-09 收口）
9. ✅ **TODO-045 ruff 历史债专项清理** = 独立 cleanup sprint（不并入 P4 / 批 4），P4 启动后空窗期或 P4.x 小 sprint 启动；当前仅保持新增/修改文件 ruff 0 错 + 全量不净增（431 基线）
10. ✅ **批 1 不出正式子报告**，仅 STATUS.md 即时同步 + buglog 即时记录

### 注意
- pcs_test 库 schema 敏感运行前先 `cd pcs-backend && uv run alembic upgrade head`
- Pydantic v2 Schema 必 Field(description=含中文)
- 收敛分层：CONVERGED/WARNINGS 全量导入，NOT_CONVERGED/ABORTED 单元产品 `unreliable=True`
- StreamSignStatus：PG enum 'streamsignstatus'；P3 活跃 4 态 DRAFT/IN_APPROVAL/CHECKED/OBSOLETE
- case_type 双层：streams.case_type (4 态) ≠ stream_state_points.case_type (4 态)
- 单位：schema temp °C/press kPa → service 转 K/Pa 后才进 ParsedStream
- 每步独立 commit；ruff 0 错 + 全 pytest 绿是 commit 前提
- YAGNI：HYSYS/Aspen/HTRI 解析器后置 P4
- **质量门（批 1+ 调整）**：新增/修改文件 ruff 0 错，全量 ruff 错误数不净增（基线 431）
- **bug-053 经验**：regex `^` 锚点必须配 MULTILINE 或按行扫描
- **bug-054 经验**：SQLite/PG IntegrityError 错误信息格式不同（PG 含约束名；SQLite 仅列名），unique 检查需双匹配
- **bug-063 经验**：SQLite in-memory FK PRAGMA 默认 OFF → 改 PG inspector 元数据契约测试，不依赖 SQLite 行为
- **bug-064 经验**：regex body capture 越界污染后续段 → 行扫描 + 段边界跳出 + 严格 ID 前缀校验
- **P3.x 新约束**：每 task 实施流程（RED→GREEN→IMPROVE）必须独立；buglog 记录新坑；spec § + audit V2.0 编号引用
- **批 1 LIBID 别名表**：17 项 PRO/II 常用 LIBID→CAS（C1→METHANE / NC4→N_BUTANE 等），未知名大写兜底

---

## Context

- 分支 main（单人直提）；后端 uv+FastAPI+SQLAlchemy 2.0 async+PG16+pytest；前端 Vite+React+antd
- TODO-033 = Sprint 1.9 终审 DEFER
- TODO-045 = ruff 历史债专项清理（独立 cleanup sprint）
- bug-046/047/051/052/053/054/063/064 入 .wolf/buglog.json
- **P3.2 SIM 状态**：全部 14 task ✅ closed（2026-09-09）
- **P3.x 状态**：批 1 ✅（6 task closed），批 2/3/4 pending
- **ruff 历史债基线**：431 errors
