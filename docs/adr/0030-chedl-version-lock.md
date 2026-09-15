---
status: accepted
date: 2026-09-15
accepted_date: 2026-09-15
---

# ChEDL 版本锁定：pyproject.toml 单一来源 + 包装层隔离 + dir() 前置核验

PCS 后端工艺计算强依赖 Caleb Bell 维护的 ChEDL 生态三库（`fluids` / `chemicals` / `ht`）。三库在 P4 实施期间频繁更新，存在四类风险：

1. **复现性风险**：`fluids` / `chemicals` 是活跃项目（年均 5-10 次 release），无锁定时不同时间部署的 PCS 实例计算结果可能不一致，工艺复核无基线
2. **许可传染风险**：`fluids` 是 MIT|GPL-3.0 双许可，当前仓库 `vendor/` 下若 vendoring 副本会触发 GPL-3.0 传染（PCS 闭源交付物形态不容许）
3. **维护可持续性风险**：单点维护者（Caleb Bell）+ 多仓库，ht 8 个月无 release，fpi 已停滞 8 年（不采用）；ChEDL 生态断供或函数重命名时无内部替代路径
4. **实施时序风险**：版本锁定后才发现所需函数不存在，触发返工（Task 5/11 RED 阶段直接 dir() 验证本可避免）

本 ADR 记录 ChEDL 版本锁定的 8 项架构裁决。Task 25 (P5-0-6) + Task 25b (P5-0-7) 共同落地。

决定：**pyproject.toml 单一来源 + 包装层隔离 + dir() 前置核验 + 降级预案 + 独立升级流程**。

## 决策

### 决策 1：版本声明单一来源 = pyproject.toml（F-11-8）

ChEDL 三库版本号**仅在 pyproject.toml 声明**，其他位置禁止出现版本号硬编码。

```toml
# pyproject.toml [project.dependencies]
fluids = "==1.0.20"      # 精确版本，禁止 >= / ~=
chemicals = "==1.1.4"
ht = "==1.0.1"
```

替代方案：分散在多处（如 Dockerfile + pyproject.toml + 文档）——否决。版本号多源会导致"一处更新另处遗忘"的不一致，且无机器可读的 source of truth。

### 决策 2：禁止浮动版本约束

pyproject.toml 中 ChEDL 三库必须使用 `==X.Y.Z` 精确版本。

- 禁止 `>=X.Y.Z`（自动接受小版本/补丁更新）
- 禁止 `~=X.Y.Z`（接受兼容更新）
- 禁止 `*` 或省略（默认浮动）

替代方案：使用 `>=` 浮动——否决。浮动会引入隐式升级，绕过 ADR 评审流程；工艺室对 PSV/PIPE 计算结果的可追溯性要求每次部署都用同一版本。

### 决策 3：取消 vendoring，依赖 uv/pip 安装（F-13-1 / 许可合规）

取消 `pcs-backend/vendor/` 下的 ChEDL 本地副本策略。

- 当前 vendoring 策略要求 PCS 后端重新分发 ChEDL 源码 → 触发 `fluids` 的 GPL-3.0 条款传染
- 改为：通过 `uv sync`（生产）/ `uv pip install`（开发）从 PyPI 安装 ChEDL 三库
- `pyproject.toml` 与 `uv.lock` 是版本传递链；ChEDL 源码不进入 PCS 仓库

替代方案：保留 vendoring + 切换 ChEDL 至纯 MIT 库——否决。`fluids` 已选定且工艺室实际项目已用，无法临时切换；`chemicals` / `ht` 同样有许可混合或传染风险。

### 决策 4：三层文件关系明确（pyproject.toml → uv.lock → requirements.txt）

| 文件 | 性质 | 生成方式 | 测试断言 |
|---|---|---|---|
| `pyproject.toml` | 人类编辑，source of truth | 手工 | 不直接断言（被 uv.lock 间接断言） |
| `uv.lock` | 机器生成，机器可读 | `uv lock` 自动 | **测试以此为准**：解析后 `fluids == X.Y.Z` |
| `requirements.txt` | 人类可读快照 | `uv export --no-hashes -o` | 与 uv.lock **集合比较**（非字节比较） |

- `uv.lock` 禁止手工编辑（与 uv 工具链不兼容）
- `requirements.txt` 仅作快照 + 外部工具（如 docker）回退使用；CI 以 `uv.lock` 为准
- P5-1 之后 ChEDL 版本冻结；P5+ 升级须走决策 8 流程

替代方案：测试以 `requirements.txt` 字节匹配为准——否决。`uv export` 输出格式因 uv 版本而异（hash 格式、字段顺序），字节匹配脆性高。集合比较（解析 `{pkg: version}` 字典后比对键集与版本）稳定可维护。

### 决策 5：dir() 前置核验（F-14-3 / V1.9 GSTACK P0 时序修正）

ChEDL 版本锁定采用**"先选候选 → 核验 → 回退"**顺序（避免对数十个候选版本全部 dir() 的不切实际工作量）：

1. **选定候选版本**：基于 P4 已闭环的版本号（如 `fluids==1.0.20`），写入临时 `pyproject.toml` + `uv lock`
2. **dir() 核验 P5 所需函数**：
   ```python
   import importlib

   REQUIRED = {
       "fluids.separator": ["v_Souders_Brown", "K_separator_Watkins", "K_separator_demister_York"],
       "fluids.particle_size": ["v_terminal"],
       "fluids.tanks": ["time_to_empty", "tank_level_to_volume"],   # 已知公开 API 不含
       "fluids.safety_valve": ["API520_round_size"],
   }

   missing = [
       (mod, fn)
       for mod, fns in REQUIRED.items()
       for fn in fns
       if not hasattr(importlib.import_module(mod), fn)
   ]
   ```
3. **缺失处理**：
   - 若 `fluids.tanks` 函数缺失 → **预期内**（F-13-5），启用决策 7 降级预案，核验通过
   - 若其他模块函数缺失 → **非预期**，回退步骤 1 选上一个稳定版本；ADR 备选版本评估记录
4. **核验通过后**：最终版本写入 `pyproject.toml`（决策 1）+ `uv lock` 重生成

替代方案：版本锁定后实施时再 dir()——否决。Task 5/11 RED 阶段才发现函数不存在需返工，且需重新选版本 + 重跑 `uv lock` + 重测。版本选择前置核验把返工收敛到 Task 25 单点。

### 决策 6：包装层隔离（F-13-2 + F-14-9 provenance 结构化）

所有 ChEDL 调用经 `app/services/chedl_wrapper.py` 集中封装。

- 7 包装函数：`v_Souders_Brown` / `K_separator_Watkins` / `K_separator_demister_York` / `v_terminal` / `time_to_empty` / `tank_level_to_volume` / `API520_round_size`
- 每个包装函数 docstring 记录：ChEDL 函数全名 + ChEDL 版本 + 已知限制 + fallback 占位
- 业务模块（Task 5/6/11/16 等）禁止 `import fluids.*` / `import chemicals.*` / `import ht.*`；只调 `chedl_wrapper.*`
- ChEDL 升级或函数重命名时，仅修改包装层内部；业务模块零改动

**透明 fallback 语义**（决策 7 兼容）：

```python
# app/services/chedl_wrapper.py
def time_to_empty(...) -> ...:
    """排空时间计算。

    ChEDL 函数: fluids.tanks.time_to_empty（公开 API 不含 → fallback）
    ChEDL 版本: 1.0.20
    已知限制:
      - ChEDL docs: 对应牛顿区 Re > 500
      - PCS 团队发现: 黏度 > 100 cP 时数值偏小，建议参考 Hall-Smolik 手册
    fallback: self_implemented（伯努利方程 + 孔口出流）
    fallback_formula_ref: "Q = Cd × A × √(2g·h)"
    """
    if hasattr(fluids.tanks, "time_to_empty"):
        return fluids.tanks.time_to_empty(...)
    else:
        return _self_implemented_time_to_empty(...)  # 内部自研实现
```

包装层内部透明 fallback，业务层无感知（不抛异常，业务模块零改动）。

**known_limitations 填充规则**：

- 来源 1：**ChEDL 官方文档** Notes / Examples 章节摘录（标注 `ChEDL docs:`）
- 来源 2：**ChEDL 源码 docstring** 摘录（标注 `ChEDL source:`）
- 来源 3：**PCS 团队实施中发现**（标注 `PCS 团队发现:`，记录在 buglog.json 中）
- 每条限制格式：`"<来源>: <限制内容>"`

替代方案：业务模块直接 import——否决。直接 import 会让 ChEDL 升级（或函数被改名为 `v_souders_brown` 等小写化）变成跨模块改动，diff 大且回归成本高。

### 决策 7：fluids.tanks 降级预案（F-13-5 + V1.9 GSTACK P2 双套测试）

`fluids.tanks.time_to_empty` / `tank_level_to_volume` 经核验公开 API 未包含（F-13-5 确认）：

- Task 6 调整 GREEN 为自研几何计算 + 伯努利方程 + 孔口出流（`Q = Cd × A × √(2g·h)`）
- `formula_ref.source = "self_implemented"` 标注自研降级路径
- Task 6 双套测试模式（F-14-4）：
  - `test_empty_time_with_chedl`：`skipif not hasattr(...)` 守卫，函数缺失时跳过；存在时与 ChEDL 交叉验证
  - `test_empty_time_self_implemented`：始终执行，验证自研路径
- 自研路径与 ChEDL 路径并存；P5+ ChEDL 补齐后可平滑切换（仅修改包装层）

替代方案：硬等待 ChEDL 补齐——否决。ChEDL 升级不可控，会阻塞 P5-1 实施；自研降级 + 包装层隔离已足够解耦。

### 决策 8：升级流程（独立 PR + 全量回归 + 复审机制）

ChEDL 版本升级须走以下流程：

1. **独立 PR**：不允许混入其他功能改动；PR 标题格式 `chore(deps): bump ChEDL to <new versions>`
2. **dir() 核验**：PR 中必须包含 `tests/fixtures/chedl_dir_check_<old>.txt` → `<new>.txt` 差异分析，确认新版本函数集兼容
3. **全量回归**：`pcs_test` 库基线全跑；任何工艺计算结果偏差 > 阈值（API 521 火灾 ≤2%、GB 泄放面积 ≤5% 等，按 ADR-0028 决策 11 独立 golden）须分析并文档化
4. **ADR 更新**：本 ADR 评审通过后状态为 `accepted`（不采用"长期 proposed"，符合 ADR 惯例——决策做出即 accepted，后续修订通过复审机制处理）；附录 A 追加升级历史（版本号 + 日期 + 偏差分析摘要）
5. **包装层同步**：包装层 docstring 中 ChEDL 版本号必须同步更新
6. **复审机制**：`last_reviewed_at` 字段记录最近一次复审时间；ChEDL 生态重大变更时（如上游 license 变更、主维护者变动、ChEDL 生态断供）触发重新评审，必要时新建 ADR-0031 取代本 ADR

**升级触发条件**（满足任一即启动升级流程）：

| # | 触发类型 | 描述 | 优先级 |
|---|---|---|---|
| 1 | 被动（安全）| ChEDL 发布安全补丁（CVE 或 maintainer security advisory）| 立即启动，最高优先级 |
| 2 | 主动（bugfix）| ChEDL 修复了 PCS 已知的 bug（记录在 ADR-0030 附录 B 或 buglog.json 中）| 纳入 P5+/P6 规划 |
| 3 | 主动（功能）| PCS 新需求依赖 ChEDL 新版本的功能 | 纳入 P5+/P6 规划 |
| 4 | 定期评估 | 每半年定期评估兼容性 | 不强制升级，仅评估 |

替代方案：升级走常规 PR 流程——否决。ChEDL 升级会触发全量工艺计算回归，需独立评审通道而非与功能 PR 混排。

## 影响

- **修改文件** 3 个：
  - `pcs-backend/pyproject.toml` — 精确版本声明
  - `pcs-backend/uv.lock` — uv lock 生成（不手工编辑）
  - `pcs-backend/requirements.txt` — uv export 生成快照（不手工编辑）
- **新文件** 4 个：
  - `app/services/chedl_wrapper.py` — 7 包装函数 + 异常捕获 + fallback 占位
  - `app/services/chedl_provenance.py` — `ChEDLProvenance` dataclass + `get_chedl_provenance()` 接口（F-14-9）
  - `tests/architecture/test_chedl_version.py` — 5 例测试（fluids / chemicals / ht 版本 + uv.lock 存在性 + requirements 一致性 + 升级文档链接 + dir() 核验）
  - `tests/services/test_chedl_wrapper.py` — 包装层存在性测试
- **取消** 1 处：`pcs-backend/vendor/` 下 ChEDL 本地副本（确认无现存 vendoring 后执行；若有残留需评估是否在 PCS 范围外，仅 ADR 引用即可）
- **RECORD_TYPE_REGISTRY 不登记** `ChEDLVersionSnapshot`：ChEDLVersionSnapshot 是 CI baseline 类型，非工艺计算记录；RECORD_TYPE_REGISTRY 仅服务于 `finalize_calc_record` 落库的计算记录（与 ADR-0028 影响段一致：Task 1 后 12 类、Task 24 后 13 类不变）
- **CI baseline 独立管理**：`tests/fixtures/chedl_version_snapshot.txt` + `tests/architecture/test_chedl_version.py` 5 例测试断言；不上 registry，不进 lineage，不写数据表
- **provenance 接口**：每个包装函数对应 `ChEDLProvenance` 条目（`chEDL_function` + `chEDL_version` + `known_limitations` + `fallback_available` + `fallback_formula_ref`），由 `get_chedl_provenance()` 返回字典；运维可观测，不入 registry

## 后续

- Task 25 (P5-0-6) + **Task 26 (P5-0-7，原 Task 25b)** 落地本 ADR 全部 8 项决策
- Task 25 + 26 完成后立即提交评审申请；评审委员会在 5 个工作日内决议
- **生效时机**：P5-0 批内完成（P5-1 启动前生效）
- **回退预案**：若评审未通过，包装层与版本锁定策略可分阶段保留（包装层 + dir() 核验无争议；版本锁定可回退到决策 4 的"测试以 requirements.txt 为准"过渡方案）
- **V1.8 计划同步**：Task 26（原 Task 25b）编号调整（V1.8 总任务数 25 → 26）；Task 25 文件路径 `docs/adr/0029-chedl-version-lock.md` → `docs/adr/0030-chedl-version-lock.md`；裁决 #22 / 全局约束 / 验收段中"ADR-0029"引用 → "ADR-0030"

### ADR 编号说明

- **ADR-0029 空洞**：V1.8 计划中 P5-0-6 ChEDL 版本锁定的 ADR 编号从 ADR-0029 调整为 **ADR-0030**（因现有 `docs/adr/0029-toe-conversion-and-detail-htri-templates.md` 已占用 0029 编号，2026-09-04 Accepted 保留不动）
- **ADR-0029 编号保留**：未来某项 ADR（建议 P5 实施期间给 P4 相关的遗漏决策）可使用 0029 编号
- **同步到 README.md**：ADR 索引已更新（2026-09-15 同步追加 0028 + 0030 条目）

supersedes：无。

## 附录 A：ChEDL 升级历史

| 日期 | fluids | chemicals | ht | 触发原因 | 偏差分析 | 操作人 |
|---|---|---|---|---|---|---|
| 2026-09-15 | 1.0.20 | 1.1.4 | 1.0.1 | 初始锁定（P5-0-6）| N/A（基线）| 工艺部 |

## 附录 B：PCS 已知的 ChEDL bug（驱动升级触发条件 #2）

_（暂无；P5-1+ 实施中如发现 ChEDL bug，记录于此，触发决策 8 触发条件 #2）_

| 日期 | ChEDL 包 | 函数 | bug 描述 | 影响 | 链接 |
|---|---|---|---|---|---|
| _（待填）_ | | | | | |
