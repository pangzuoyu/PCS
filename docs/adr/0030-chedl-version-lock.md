---
status: accepted
date: 2026-09-15
accepted_date: 2026-09-15
revised: 2026-09-16
version: V1.1
supersedes: V1.0 (2026-09-15 accepted，2026-09-16 由 V1.1 修订)
---

# ChEDL 版本锁定：pyproject.toml 单一来源 + 包装层隔离 + dir() 前置核验

## V1.1 修订说明（2026-09-16）

V1.0 基于 P5 计划文本假设 ChEDL 依赖为 `{fluids, chemicals, ht}`，经 2026-09-16 实际核验发现三处关键不一致，本版本修订如下：

1. **vendor 实际内容**：`{chemicals, CoolProp, fluids, ht, thermo}` — 5 个（V1.0 声明 3 个）
2. **P4 实际依赖链**：`flash_service → thermo_factory.py → chemicals.*` 多子模块（vapor_pressure / iapws / phase_change / critical / acentric / volume / viscosity / thermal_conductivity / identifiers）
3. **包装函数规模**：V1.0 假设仅 `fluids.*` 7 函数；实际 P4 已通过 `thermo_factory.py` 依赖 `chemicals.*` 10+ 子模块

修订决策 1、3、6，新增决策 9（`thermo_factory` 与 `chedl_wrapper` 关系），补充附录 A 核验结果。

**V1.1 落地核验（2026-09-16 实际 pyproject.toml + uv run python -c "import"）**：

| 库 | pyproject 实际版本 | V1.0 声明 | V1.1 修正 |
|---|---|---|---|
| chemicals | **1.5.2**（pyproject:23 + import 验证） | 1.1.4（V1.0 注释） | → `chemicals==1.5.2` |
| fluids | **1.3.1**（pyproject:24 + import 验证） | 1.0.20（V1.0 注释） | → `fluids==1.3.1` |
| thermo | **0.6.1**（pyproject:25 + import 验证） | 未声明 | → 确认既有锁定（D1） |
| ht | **未在 pyproject 声明**（仅在 vendor 中存在） | 1.0.1 | → **完全移除**（D4：方案 A 采纳，无业务 import，P5-4 如需复用走决策 8 流程独立引入） |
| CoolProp | 未声明 | 未提及 | → D3 裁决（清理 vendor，不纳入 pyproject） |

**裁决项（V1.1 新增，提交评审前必须关闭）**：

- [x] **D1**：确认 thermo==0.6.1 的既有锁定（pyproject.toml:25 已锁），纳入 ADR-0030 决策 1 正式清单。**推荐采纳**。
- [x] **D2**：`thermo_factory.py`（P4 遗留）与 `chedl_wrapper.py`（P5 新增）双包装层并存，职责边界清晰。**推荐采纳**。
- [x] **D3**：CoolProp 清理 vendor 副本（无业务 import），不纳入 pyproject。**推荐采纳**。
- [x] **D4**：ht 完全移除（pyproject 未声明 + 无业务 import）；P5-4 如需复用走决策 8 流程独立引入。**推荐采纳**（评审结论 P0-2 方案 A）。

---

PCS 后端工艺计算强依赖 Caleb Bell 维护的 ChEDL 生态（`fluids` / `chemicals` / `thermo` / `ht`）及 `CoolProp`。四库在 P4 实施期间频繁更新，存在四类风险：

1. **复现性风险**：`fluids` / `chemicals` 是活跃项目（年均 5-10 次 release），无锁定时不同时间部署的 PCS 实例计算结果可能不一致，工艺复核无基线
2. **许可传染风险**：`fluids` 是 MIT|GPL-3.0 双许可，当前仓库 `vendor/` 下 vendoring 副本会触发 GPL-3.0 传染（PCS 闭源交付物形态不容许）
3. **维护可持续性风险**：单点维护者（Caleb Bell）+ 多仓库，ht 8 个月无 release，fpi 已停滞 8 年（不采用）；ChEDL 生态断供或函数重命名时无内部替代路径
4. **实施时序风险**：版本锁定后才发现所需函数不存在，触发返工（Task 5/11 RED 阶段直接 dir() 验证本可避免）

本 ADR 记录 ChEDL 版本锁定的 9 项架构裁决（V1.1 新增决策 9）。Task 25 (P5-0-6) + Task 26 (P5-0-7) 共同落地。

**决定**：pyproject.toml 单一来源 + 包装层隔离 + dir() 前置核验 + 降级预案 + 独立升级流程 + 双包装层职责边界。

---

## 决策

### 决策 1：版本声明单一来源 = pyproject.toml（F-11-8）

ChEDL 生态相关库版本号仅在 `pyproject.toml` 声明，其他位置禁止出现版本号硬编码。

```toml
# pyproject.toml [project.dependencies]
chemicals = "==1.5.2"      # P4 flash_service 直接依赖（V1.1 实地核验：pyproject:23）
fluids    = "==1.3.1"      # P5-1 VESSEL + P5-2 SEP_EQUIP 直接依赖（V1.1 实地核验：pyproject:24）
thermo    = "==0.6.1"       # V1.1 新增：pyproject:25 已锁；thermo_factory 命名遗留（实际依赖是 chemicals.*）
# ht 从锁定清单移除（D4 裁决：pyproject 实际未声明 ht 版本，vendor 中存在但无业务 import）
```

**V1.1 修订**（原 V1.0 为 `{fluids, chemicals, ht}`）：

- 加入 `thermo==0.6.1`（D1：确认既有锁定持续有效）
- ht **完全移除**：pyproject 未声明版本号 + vendor/ht/ 无业务 import（D4 方案 A）；P5-4 如需复用走决策 8 升级流程独立引入
- CoolProp **不纳入** pyproject（D3 推荐清理 vendor，不写依赖）

**替代方案**：分散在多处（如 Dockerfile + pyproject.toml + 文档）——**否决**。版本号多源会导致"一处更新另处遗忘"的不一致，且无机器可读的 source of truth。

### 决策 2：禁止浮动版本约束

`pyproject.toml` 中 ChEDL 生态相关库必须使用 `==X.Y.Z` 精确版本。

- 禁止 `>=X.Y.Z`（自动接受小版本/补丁更新）
- 禁止 `~=X.Y.Z`（接受兼容更新）
- 禁止 `*` 或省略（默认浮动）

**替代方案**：使用 `>=` 浮动——**否决**。浮动会引入隐式升级，绕过 ADR 评审流程；工艺室对 PSV/PIPE 计算结果的可追溯性要求每次部署都用同一版本。

### 决策 3：取消 vendoring，依赖 uv/pip 安装（F-13-1 / 许可合规）

取消 `pcs-backend/vendor/` 下所有 ChEDL 生态库的本地副本。

**V1.1 修订**（原 V1.0 仅声明 `fluids`/`chemicals`/`ht`）：

| 库 | vendor 现状 | 清理策略 | 依据 |
|---|---|---|---|
| chemicals | 存在 | **必须清理** | P4 直接 import；vendoring 副本与 PyPI 版本可能不一致，触发复现性风险 |
| fluids | 存在 | **必须清理** | MIT\|GPL-3.0 双许可，vendoring 触发传染风险 |
| ht | 存在 | **清理（D4）** | 无业务 import，判断明确 |
| thermo | 存在 | **清理（D1）** | pyproject 锁 0.6.1；无直接 import；vendor 副本与 PyPI 版本可能不一致 |
| CoolProp | 存在 | **清理（D3）** | 无业务 import；许可需核验 |

改为：通过 `uv sync`（生产）/ `uv pip install`（开发）从 PyPI 安装。

`pyproject.toml` 与 `uv.lock` 是版本传递链；ChEDL 生态源码不进入 PCS 仓库。

**D3/D4 裁决未关闭前，不动 vendor**（本次核验已记录现状，实际清理待裁决）。

**替代方案**：保留 vendoring + 切换 ChEDL 至纯 MIT 库——**否决**。`chemicals` / `fluids` 已选定且工艺室实际项目已用，无法临时切换。

### 决策 4：三层文件关系明确（pyproject.toml → uv.lock → requirements.txt）

| 文件 | 性质 | 生成方式 | 测试断言 |
|---|---|---|---|
| pyproject.toml | 人类编辑，source of truth | 手工 | 不直接断言（被 uv.lock 间接断言） |
| uv.lock | 机器生成，机器可读 | `uv lock` 自动 | 测试以此为准：解析后 `chemicals == 1.5.2` / `fluids == 1.3.1` / `thermo == 0.6.1` |
| requirements.txt | 人类可读快照 | `uv export --no-hashes -o` | 与 uv.lock 集合比较（非字节比较） |

- `uv.lock` 禁止手工编辑（与 uv 工具链不兼容）
- `requirements.txt` 仅作快照 + 外部工具（如 docker）回退使用；CI 以 `uv.lock` 为准
- P5-1 之后 ChEDL 版本冻结；P5+ 升级须走决策 8 流程

**V1.1 补充**：uv 工具链版本需在 CI/Docker 中固定，避免 uv.lock 格式差异破坏跨环境测试断言。具体版本号由 **Task 25 实施时核验当前稳定版后确定**，并同步到 CI 配置文件 + Dockerfile + ADR-0030 决策 4（本 ADR 正式记录）。

**替代方案**：测试以 `requirements.txt` 字节匹配为准——**否决**。`uv export` 输出格式因 uv 版本而异（hash 格式、字段顺序），字节匹配脆性高。集合比较（解析 `{pkg: version}` 字典后比对键集与版本）稳定可维护。

### 决策 5：dir() 前置核验（F-14-3 / V1.9 GSTACK P0 时序修正）

选择 ChEDL 版本前，必须先 `dir()` 核验 P5 所需函数可用性。

```python
import importlib

REQUIRED = {
    # fluids.* — P5-1/2/4 直接依赖
    "fluids.separator": ["v_Souders_Brown", "K_separator_Watkins", "K_separator_demister_York"],
    "fluids.particle_size": ["v_terminal"],
    "fluids.tanks": ["time_to_empty", "tank_level_to_volume"],   # 已知公开 API 不含
    "fluids.safety_valve": ["API520_round_size"],
    # V1.1 新增：P4 已依赖的 chemicals 子模块核验（避免 chemicals 升级破坏 P4 flash_service）
    "chemicals.vapor_pressure": [],     # 空列表 = 仅核验模块可导入
    "chemicals.iapws": [],
    "chemicals.phase_change": [],
    "chemicals.critical": [],
    "chemicals.acentric": [],
    "chemicals.volume": [],
    "chemicals.viscosity": [],
    "chemicals.thermal_conductivity": [],
    "chemicals.identifiers": [],
}

missing = [
    (mod, fn)
    for mod, fns in REQUIRED.items()
    for fn in fns
    if not hasattr(importlib.import_module(mod), fn)
]
```

**执行顺序**（V1.1 明确，拆主流程 + 分支处理）：

**主流程**：
1. 先选定一个候选版本（基于 P4 已闭环的版本号）
2. `dir()` 核验
3. 核验通过 → 锁定 `pyproject.toml`

**分支处理**（条件触发，不满足时跳过）：
- 若缺失**非预期**函数 → 回退到步骤 1，选择上一个稳定版本
- 若 `fluids.tanks` 函数缺失 → 预期内（F-13-5），启用决策 7 降级预案，主流程继续
- 若 `chemicals.*` 子模块不可导入 → 非预期，回退到步骤 1；P4 flash_service 已依赖，回归测试必须覆盖

**替代方案**：版本锁定后实施时再 `dir()`——**否决**。Task 5/11 RED 阶段才发现函数不存在需返工，且需重新选版本 + 重跑 `uv lock` + 重测。版本选择前置核验把返工收敛到 Task 25 单点。

### 决策 6：包装层隔离 + 双包装层职责边界（F-13-2 + V1.1 扩展）

所有 ChEDL 生态调用经 `app/services/chedl_wrapper.py` 集中封装。

**V1.1 修订**（原 V1.0 仅 7 个 `fluids.*` 函数）：

**包装函数清单**：

| 来源库 | 函数/模块 | 数量 | 用途 |
|---|---|---|---|
| `fluids.separator` | `v_Souders_Brown` / `K_separator_Watkins` / `K_separator_demister_York` | 3 | Task 5 / Task 10 |
| `fluids.particle_size` | `v_terminal` | 1 | Task 11 |
| `fluids.tanks` | `time_to_empty` / `tank_level_to_volume` | 2 | Task 6（降级预案） |
| `fluids.safety_valve` | `API520_round_size` | 1 | Task 17 |
| **fluids.* 小计** | | **7** | |
| **chemicals.* 子模块级包装预留位** | P5+ 未来可能新用的子模块（当前未知）；**P4 已用的 9 子模块由 `thermo_factory.py` 负责，不在 chedl_wrapper 重复包装** | **0（P5 当前无新增 chemicals 需求）** | P5+ 新增 chemicals 调用时优先在 chedl_wrapper 增加包装 |

**双包装层职责边界**（V1.1 新增，D2 推荐方案 X）：

| 包装层 | 文件 | 职责 | 引入时机 |
|---|---|---|---|
| `chedl_wrapper.py` | `app/services/chedl_wrapper.py` | P5+ 新引入的 ChEDL 调用（`fluids.*` + `chemicals.*` 统一封装）；future 扩展 | Task 26（新） |
| `thermo_factory.py` | `app/services/flash/thermo_factory.py`（P4 实际位置） | P4 遗留的 chemicals 抽象层；V1.1 冻结现状，不动 P4 已闭环代码 | P4（已存在） |

**职责边界规则**：

- P5 新增代码（Task 5/6/10/11/17）：**必须** 经 `chedl_wrapper.py`，禁止直接 `import fluids.*` / `import chemicals.*`
- P4 遗留代码（flash_service / petroleum 等）：经 `thermo_factory.py`，P5 期间不重构（避免回归风险）
- 未来整合（P5+）：`thermo_factory.py` 可择机迁移到 `chedl_wrapper.py`，但不阻塞 P5

**chedl_wrapper.py 范围澄清**（V1.1 评审 P1-2 修正）：

- `chedl_wrapper.py` 实现 = **7 个 fluids 函数**（P5 当前 0 个 chemicals 包装，与决策 6 表"P5 当前无新增 chemicals 需求"对齐）
- P5+ 若新增 chemicals 调用（如 R2 新功能），优先在 `chedl_wrapper.py` 增加包装
- P4 已用的 chemicals.* 9 子模块由 `thermo_factory.py` 负责，**不重复包装**（避免双层抽象）

每个包装函数的 docstring 格式：

```text
ChEDL 函数: fluids.separator.v_Souders_Brown
ChEDL 版本: 1.3.1
已知限制:
  - ChEDL docs: 对应牛顿区 Re > 500，实际液滴可能在中间区或 Stokes 区
fallback: 无（直接调用）
```

**已知限制填充规则**：

- 从 ChEDL 官方文档 Notes / Examples 章节摘录
- 从 ChEDL 源码 docstring 摘录
- PCS 团队实施中发现的问题，标注"PCS 团队发现"前缀

**替代方案**：业务模块直接 import——**否决**。直接 import 会让 ChEDL 升级（或函数被改名为 `v_souders_brown` 等小写化）变成跨模块改动，diff 大且回归成本高。

### 决策 7：fluids.tanks 降级预案（F-13-5 + V1.9 GSTACK P2 双套测试）

`fluids.tanks.time_to_empty` / `tank_level_to_volume` 经核验公开 API 未包含（F-13-5 确认）：

- Task 6 调整 GREEN 为自研几何计算 + 伯努利方程 + 孔口出流（Q = Cd × A × √(2g·h)）
- `formula_ref.source = "self_implemented"` 标注自研降级路径

Task 6 双套测试模式（F-14-4）：

- `test_empty_time_with_chedl`：`skipif not hasattr(...)` 守卫，函数缺失时跳过；存在时与 ChEDL 交叉验证
- `test_empty_time_self_implemented`：始终执行，验证自研路径

自研路径与 ChEDL 路径并存；P5+ ChEDL 补齐后可平滑切换（仅修改包装层）。

包装层内部透明 fallback（V1.1 明确）：

```python
# chedl_wrapper.py
def time_to_empty(...) -> ...:
    if hasattr(fluids.tanks, "time_to_empty"):
        return fluids.tanks.time_to_empty(...)
    else:
        return _self_implemented_time_to_empty(...)  # 内部自研实现
```

业务层无感知 fallback；`formula_ref.source` 由包装层返回，业务层不判断。

**替代方案**：硬等待 ChEDL 补齐——**否决**。ChEDL 升级不可控，会阻塞 P5-1 实施；自研降级 + 包装层隔离已足够解耦。

### 决策 8：升级流程（独立 PR + 全量回归 + ADR 更新）

ChEDL 生态版本升级须走以下流程：

1. **独立 PR**：不允许混入其他功能改动；PR 标题格式 `chore(deps): bump ChEDL to <new versions>`
2. **dir() 核验**：PR 中必须包含 `tests/fixtures/chedl_dir_check_<old>.txt → <new>.txt` 差异分析，确认新版本函数集兼容（含 `chemicals.*` 子模块）
3. **全量回归**：`pcs_test` 库基线全跑；任何工艺计算结果偏差 > 阈值（API 521 火灾 ≤2%、GB 泄放面积 ≤5% 等，按 ADR-0028 决策 11 独立 golden）须分析并文档化
4. **ADR 更新**：本 ADR 状态由 `proposed` → `accepted`（评审通过后）；后续升级不修改决策内容，仅在附录 A 追加升级历史
5. **包装层同步**：包装层 docstring 中 ChEDL 版本号必须同步更新

**升级触发条件**（V1.1 新增）：

| 条件 | 优先级 | 处理 |
|---|---|---|
| ChEDL 发布安全补丁（CVE / security advisory） | P0 | 立即启动，独立 PR 快速通道 |
| ChEDL 修复 PCS 已知 bug（附录 B 记录） | P1 | 纳入 P5+/P6 规划 |
| PCS 新需求依赖 ChEDL 新版本功能 | P2 | 纳入对应批次规划 |
| 定期评估（每半年） | P3 | 仅评估兼容性，不强制升级 |

**替代方案**：升级走常规 PR 流程——**否决**。ChEDL 升级会触发全量工艺计算回归，需独立评审通道而非与功能 PR 混排。

### 决策 9：thermo_factory.py 与 chedl_wrapper.py 双包装层共存（V1.1 新增，D2 方案 X）

**背景**：P4 的 flash_service 通过 `app/services/flash/thermo_factory.py` 调用 `chemicals.*` 多子模块；P5 引入 `chedl_wrapper.py` 封装 `fluids.*`。两者并存会引发"谁是唯一 ChEDL 入口"的疑问。

**裁决**：双包装层并存，职责边界明确。

- `thermo_factory.py`（P4 遗留）：保留，负责 `chemicals.*` 的抽象；P5 期间不动
- `chedl_wrapper.py`（P5 新增）：负责 P5+ 新引入的 `fluids.*` 和 `chemicals.*` 调用

**理由**：

1. P4 已闭环：flash_service 已被 1662 tests 覆盖，重构会引入回归风险
2. 命名遗留：`thermo_factory.py` 的实际依赖是 `chemicals` 不是 `thermo`，但 P4 已定型，改名成本高
3. 职责可区分：P4 遗留 vs P5 新增，时间维度清晰
4. 未来整合：P5+ 可择机将 `thermo_factory.py` 迁移到 `chedl_wrapper.py`，但不阻塞 P5

**边界规则**：

- P5 新增代码：`import chedl_wrapper`
- P4 遗留代码：`import thermo_factory`
- **禁止**：P5 代码直接 `import chemicals.*` / `import fluids.*` / `import thermo.*`
- **禁止**：P4 代码修改为 `import chedl_wrapper`（P5 期间不重构）

**P4 遗留调用清单**（供未来整合参考，V1.1 记录）：

```text
thermo_factory.py 调用 chemicals.* 子模块：
  - chemicals.vapor_pressure
  - chemicals.iapws
  - chemicals.phase_change
  - chemicals.critical
  - chemicals.acentric
  - chemicals.volume
  - chemicals.viscosity
  - chemicals.thermal_conductivity
  - chemicals.identifiers
```

**替代方案 Y（迁移到单一包装层）**——**否决**。P4 代码重构风险大，与 P5 目标（交付 VESSEL/SEP_EQUIP/PSV/HEAT）无关。

---

## 影响

### 修改文件（3 个）

- `pcs-backend/pyproject.toml` — 精确版本声明（`chemicals==1.5.2` / `fluids==1.3.1` / `thermo==0.6.1`）
- `pcs-backend/uv.lock` — `uv lock` 生成（不手工编辑）
- `pcs-backend/requirements.txt` — `uv export` 生成快照（不手工编辑）

### 新文件（4 个，V1.1 不变）

- `app/services/chedl_wrapper.py` — 7 个 `fluids.*` 包装 + 9 个 `chemicals.*` 子模块包装 + 异常捕获 + fallback 占位
- `app/services/chedl_provenance.py` — `ChEDLProvenance` dataclass + `get_chedl_provenance()` 接口
- `tests/architecture/test_chedl_version.py` — 测试（版本断言 + uv.lock 存在性 + requirements 一致性 + `dir()` 核验）
- `tests/services/test_chedl_wrapper.py` — 包装层存在性测试

### vendor 清理（V1.1 修订，D3/D4 裁决后执行）

| 库 | 清理动作 | 裁决 |
|---|---|---|
| chemicals | 删除 `vendor/chemicals/` | 明确（P4 直接依赖） |
| fluids | 删除 `vendor/fluids/` | 明确（GPL-3.0 传染） |
| ht | 删除 `vendor/ht/` | D4（推荐清理） |
| thermo | 删除 `vendor/thermo/` | D1（推荐清理，pyproject 锁 0.6.1） |
| CoolProp | 删除 `vendor/CoolProp/` | D3（推荐清理，无业务 import） |

D1-D4 裁决关闭前，不动 vendor（本次核验已记录现状）。

### RECORD_TYPE_REGISTRY（V1.1 明确）

**不登记** `ChEDLVersionSnapshot` 到 `RECORD_TYPE_REGISTRY`。

**理由**：`RECORD_TYPE_REGISTRY` 是计算记录 registry（用于 `finalize_calc_record`），CI baseline 不是计算记录。CI baseline 由 `tests/fixtures/chedl_version_snapshot.txt` 独立管理。

与 ADR-0028 的口径一致（ADR-0028 声明 Task 24 后 13 类，不含 ChEDL 相关）。

### provenance 接口

每个包装函数对应 `ChEDLProvenance` 条目：`chEDL_function` + `chEDL_version` + `known_limitations` + `fallback_available` + `fallback_formula_ref`。

---

## 后续

- Task 25 (P5-0-6) + Task 26 (P5-0-7) 落地本 ADR 全部 9 项决策
- Task 25 + 26 完成后立即提交评审申请；评审委员会在 5 个工作日内决议
- 生效时机：P5-0 批内完成（P5-1 启动前生效）
- 评审截止时间：P5-1 启动前（Task 5 实施前）
- 回退预案：若评审未通过，包装层与版本锁定策略可分阶段保留（包装层 + `dir()` 核验无争议；版本锁定可回退到决策 4 的"测试以 `requirements.txt` 为准"过渡方案）

### V1.8 计划同步

- Task 25 文件路径 `docs/adr/0029-chedl-version-lock.md` → `docs/adr/0030-chedl-version-lock.md`
- 新增 Task 26 (P5-0-7 ChEDL 包装层)；任务总数 25 → 26
- 裁决 #22 / 全局约束 / 验收段中"ADR-0029"引用 → "ADR-0030"
- 全局约束中"fluids / chemicals / ht 冻结" → "chemicals / fluids / thermo（ht 从锁定清单移除，保留待 P5-4 评估）"
- Architecture 段中"fluids(vendored)" → "chemicals / fluids / thermo（pip 安装）"
- ADR 编号说明：原 V1.8 计划中的 ADR-0029 位置调整为 ADR-0030；ADR-0029 编号保留给未来某项 ADR

### 裁决项关闭检查清单（V1.1 评审 2026-09-16 全部关闭）

- [x] **D1**：thermo 既有锁定（pyproject:25 == 0.6.1）已确认持续有效，纳入决策 1 正式清单（评审 P0-3 修正）
- [x] **D2**：thermo_factory.py（P4 遗留）+ chedl_wrapper.py（P5 新增）双包装层并存，职责边界清晰（决策 9）
- [x] **D3**：CoolProp 清理 vendor 副本（无业务 import），不纳入 pyproject
- [x] **D4**：ht 完全移除（pyproject 未声明 + 无业务 import；评审 P0-2 方案 A）；P5-4 如需复用走决策 8 流程独立引入

---

## 附录 A：2026-09-16 核验结果（V1.1 新增）

### A.1 vendor 实际内容

```text
pcs-backend/vendor/
├── chemicals/     # P4 flash_service 直接依赖（经 thermo_factory.py）
├── CoolProp/      # 无业务 import；V1.0 未提及
├── fluids/        # 无业务 import（P5 Task 5+ 才用）
├── ht/            # 无业务 import
└── thermo/        # 无直接 import（仅 pyproject.toml 声明版本 0.6.1）
```

### A.2 P4 实际依赖链

```text
flash_service
  → app/services/flash/thermo_factory.py
    → chemicals.vapor_pressure
    → chemicals.iapws
    → chemicals.phase_change
    → chemicals.critical
    → chemicals.acentric
    → chemicals.volume
    → chemicals.viscosity
    → chemicals.thermal_conductivity
    → chemicals.identifiers
```

**关键纠正**：`thermo_factory.py` 文件名暗示依赖 `thermo` 包，实际依赖是 `chemicals.*`。这是 P4 的命名遗留，非 P5 引入。

### A.3 pyproject.toml 现有版本声明（V1.1 实地核验）

```text
chemicals == 1.5.2    (pyproject.toml:23)
fluids    == 1.3.1    (pyproject.toml:24)
thermo    == 0.6.1    (pyproject.toml:25)
# ht 未声明（V1.1 修正：移除 ht 锁定）
```

### A.4 包装函数规模对比

| 版本 | `fluids.*` | `chemicals.*` | 合计 | 备注 |
|---|---|---|---|---|
| V1.0 声明 | 7 | 0 | 7 | V1.0 仅 fluids |
| V1.1 实际 | 7 | **0（P5 阶段不重复包装）** | **7** | P4 已用的 9 子模块由 `thermo_factory.py` 负责；`chedl_wrapper.py` 仅 P5+ 新增 chemicals 调用时扩展 |

---

## 附录 B：ChEDL 升级历史（V1.1 新增）

| 日期 | chemicals | fluids | thermo | 触发原因 | 偏差分析 |
|---|---|---|---|---|---|
| 2026-09-16 | 1.5.2 | 1.3.1 | 0.6.1 | 初始锁定（V1.1 实地核验） | N/A（首次锁定） |
| （未来） | ... | ... | ... | ... | ... |

> **注**：ht 列已移除（D4 方案 A：ht 完全从锁定清单移除；如未来 P5-4 需引入 ht，按决策 8 流程新增独立条目）

---

## 附录 C：P4 已知 bug 记录（供决策 8 升级触发条件使用）

| 库 | bug 描述 | 记录日期 | 影响范围 | 状态 |
|---|---|---|---|---|
| — | *P5-0 阶段无已知 bug；P5 各批次实施中发现的 ChEDL 问题在此汇总* | — | — | — |

**附录 C 填充时机**：P5-0 批内无已知 bug，标注"无"；P5-1 至 P5-4 期间由各 task subagent 记录；P5 验收时汇总归档。

---

supersedes：V1.0（2026-09-15 accepted，2026-09-16 由 V1.1 覆盖）
related：ADR-0028（PSV 多标准引擎）、ADR-0027（HEAT 双轨）
